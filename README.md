# 📘 YieldAnalytics — 日本株 高配当 × 財務 × 収益性 スクリーニングシステム

YieldAnalytics は、JPX 全上場銘柄（約3,700銘柄）を対象に、
**配当・財務・収益性の3軸でスコアリングし、現在の利回りが割安な銘柄を「買いシグナル」で判定する**分析ツールです。
最後に、有望銘柄を NotebookLM で深掘り分析するためのプロンプトまで自動生成します。

データ取得には [yfinance](https://github.com/ranaroussi/yfinance) を使用し、GitHub Actions で定期実行されます。

---

## 🔄 全体の流れ

```
input/jpx_all.csv
      │
      ▼
① jpx_screening_fetch.py   … 配当・財務データ取得（月次）
      │  output/output_financial_dividend_merged.csv
      ▼
② jpx_scoring_engine.py    … スコアリング（週次）
      │  scored_output.csv
      ▼
③ jpx_yield_filter.py      … 利回り判定・買いシグナル付与（週次）
      │  yield_filtered_output.csv
      ▼
④ makeprompt.py            … NotebookLM 用プロンプト生成（週次）
         prompt_output.txt
```

| ステップ | スクリプト | 自動実行 |
|---|---|---|
| ① データ取得 | `jpx_screening_fetch.py` | 毎月1日 07:00 UTC（16:00 JST） |
| ② スコアリング | `jpx_scoring_engine.py` | 毎週月曜 04:10 UTC（13:10 JST） |
| ③ 利回り判定 | `jpx_yield_filter.py` | 同上（②に続けて実行） |
| ④ プロンプト生成 | `makeprompt.py` | 同上（③に続けて実行） |

> データ取得は yfinance への負荷が大きいため月次、取得済みデータを使うスコアリング以降は週次に分けています。
> 週次ジョブでは株価・利回りだけが最新になります。

---

# 🏗️ ① jpx_screening_fetch.py — データ取得

## 概要
銘柄コード一覧（CSV の1列目）を読み込み、各銘柄を `{コード}.T` として yfinance から取得します。

- 配当履歴（暦年ごとの配当合計・配当回数）
- 財務データ：売上高、自己資本比率、営業キャッシュフロー、現金同等物
- ROE / EPS（trailing）/ 時価総額

## 出力
`output_financial_dividend_merged.csv`（1銘柄 = 11行：当年を含む過去10年分）

| 列 | 内容 |
|---|---|
| Symbol / Company / Year | 銘柄コード・会社名・年 |
| Revenue / EquityRatio / OperatingCF / Cash | 年次の財務データ |
| Dividend / Count | その年の配当合計・配当回数 |
| ROE / EPS / MarketCap | 取得時点の値（全年の行に同じ値が入る） |

## 仕様のポイント

- **財務データは yfinance が返す年度分のみ**（通常は直近4年程度）。それより古い年の財務列は空欄になります。配当は10年分取得します。
- **ROE・EPS・時価総額は「現在値」** で、年ごとの値ではありません。
- **安全な取得処理**：`safe_get_info`（info 取得を最大3回リトライ、失敗時は空 dict）、`safe_get_dividends`（None 対策・タイムゾーン除去）、財務諸表の取得失敗時は空の DataFrame で継続。
- 自己資本・総資産の行名は、複数の候補名から自動検出します。
- 配当はこの段階では**生の値**です（特別配当の補正はスコアリング側で行います）。

```bash
python jpx_screening_fetch.py input/jpx_all.csv      # 全銘柄
python jpx_screening_fetch.py input/topix_core30.csv # 動作確認用（30銘柄）
```

---

# 🧮 ② jpx_scoring_engine.py — スコアリング

## 概要
`output_financial_dividend_merged.csv` を読み込み、銘柄ごとに **配当 40 点 + 財務 30 点 + 収益性 30 点 = 最大 100 点** で評価します。
各軸で検出した問題点は `Problem` 列に `/` 区切りで記録されます。

```
例）配当性向100%以上/営業CF合計マイナス/ROE低い
```

## A. 配当スコア（最大40点）

**特別配当の補正（先に実施）**
記念配当などによる見かけ上の増減を補正します。

```
前年 > 0  かつ  当年 ≥ 前年×1.8  かつ  翌年 ≤ 当年×0.7  → 当年を max(前年, 翌年) に補正
```

**加点・減点**

| 項目 | 内容 |
|---|---|
| 無配なし | 全期間で配当あり：+20 ／ 無配年あり：−40（`無配年あり`） |
| 増配年数 | 据え置きも増配扱い。1回につき +2（最大 +20）。0回なら `増配なし` |
| 減配 | 最新年（当年）の比較は除外して判定。1回以上：−1 ／ 2回以上：さらに −(回数×10)（`2回減配あり`）／ 3回以上：`3回以上減配あり` |
| 配当性向（直近4年） | 配当 ÷ EPS。100%以上：−5（`配当性向100%以上`）／ 70%以上は2回目から −2（`配当性向70%以上2回`） |
| 平均増配率 | 最新年を除く増配率の平均。3%以下：−1 ／ 1.5%以下：さらに −2 ／ 0%：さらに −17 |

- スコアが 38 点以上なら **「累進」フラグ** を付与し、40 点（満点）に補正します。
- マイナスは 0 に丸めます。
- 平均増配率は `AvgGrowthRate` 列、累進フラグは `CumulativeDividend` 列に出力され、③で利用します。

## B. 財務スコア（最大30点）

| 項目 | 内容 |
|---|---|
| 自己資本比率（最新年） | 40%以上：+10 ／ 30%以上：+5 ／ 未満：`自己資本比率低い` |
| 営業CF（直近4年） | 全年プラス：+8 ／ 合計プラス：+4（マイナスなら `営業CF合計マイナス`） |
| 現金 ÷ 時価総額 | 10%以上：+8 ／ 未満：`現金比率低い` |
| 時価総額による減点 | 1,000億円以上：0 ／ 400億円以上：−3 ／ 100億円以上：−5 ／ 未満：−10 |

## C. 収益性スコア（最大30点）

| 項目 | 内容 |
|---|---|
| ROE | 10%以上：+10 ／ 5%以上：+5 ／ 未満：`ROE低い` |
| 売上高（直近4年） | 前年比で増収の回数×2（最大 +6）。3年連続増収なら +4。0回なら `減収傾向` |
| EPS | プラス：+10 ／ 以外：`EPS低い` |

## 出力
`scored_output.csv`（TotalScore の降順）

`Symbol, Company, DividendScore, FinancialScore, ProfitScore, TotalScore, MarketCap, Problem, AvgGrowthRate, CumulativeDividend`

---

# 🎯 ③ jpx_yield_filter.py — 利回り判定

## 概要
スコアリング結果から候補を絞り込み、現在の配当利回りが「過去2年の水準と比べて割安か」を判定して **買いシグナル** を付与します。

```bash
python jpx_yield_filter.py <スコア閾値> <増配率閾値>
python jpx_yield_filter.py 80 0.1     # 週次ジョブでの設定
```

## 候補の絞り込み条件
次のいずれかを満たす銘柄が対象です。

1. `TotalScore ≥ スコア閾値` かつ `AvgGrowthRate > 0`
2. `AvgGrowthRate ≥ 増配率閾値` かつ 累進フラグあり

## 取得・算出する指標

| 指標 | 内容 |
|---|---|
| DividendYield | 直近1年の配当合計 ÷ 現在株価 |
| AvgYield2Y / MaxYield2Y | 直近2年（配当のあった直近2暦年）について「配当 ÷ 年間最安値」「配当 ÷ 年間平均株価」を算出し、その平均値・最大値 |
| SizeCategory | 時価総額で 超大型（1兆円〜）／大型（3,000億円〜）／中型（1,000億円〜）／小型（400億円〜）／超小型 |
| SectorJP | yfinance のセクターを GICS 11分類の日本語に変換（`utils/sector_map.py`） |
| SplitFlag | 直近1年以内に株式分割があれば `Split` |

## 買いシグナル（BuySignal）
上から順に判定し、最初に該当したものを採用します。

| 判定 | 条件 |
|---|---|
| × | 利回り取得不可 ／ 現在利回り < 2年平均利回り ／ 利回り 1%未満 ／ 利回り 2%未満かつ平均増配率 50%未満 |
| △ | 利回り 3%未満かつ平均増配率 20%未満 |
| ☆ | 平均増配率 5%以上 かつ 累進フラグあり、かつ（利回り ≥ 平均×1.5 または 利回り ≥ 2年最高） |
| ◎ | 利回り ≥ 平均×1.35 または ≥ 最高×0.95 |
| 〇 | 利回り ≥ 平均×1.2 または ≥ 最高×0.8 |
| △ | 利回り ≥ 平均（上記に該当しない場合） |
| × | 上記以外 |

## 出力
`yield_filtered_output.csv`（利回りの降順）

`Symbol, Company, CurrentPrice, TotalScore, DividendYield, AvgYield2Y, MaxYield2Y, MarketCap, SizeCategory, SectorJP, SplitFlag, BuySignal, Problem, AvgGrowthRate, CumulativeDividend`

> `Problem` 列は参考情報として残しており、問題のある銘柄の除外はここでは行いません。

---

# 📝 ④ makeprompt.py — NotebookLM 用プロンプト生成

```bash
python makeprompt.py yield_filtered_output.csv 7   # ☆銘柄からランダムに7銘柄
```

1. `BuySignal = ☆` の銘柄だけを対象にします（1件もなければ何も出力せず終了）。
2. ランダムに指定数を抽出し、セクター順に並べ替えます。
3. 各銘柄の Yahoo!ファイナンス（財務・プロフィール・配当）の URL 一覧を作成します。
4. 次の内容を含むプロンプトを `prompt_output.txt` に出力します。
   - 銘柄一覧（セクター・利回り・株価）と参照 URL
   - 除外判断の基準（成長性・減配・低利回り）
   - 銘柄ごとの分析項目（景気敏感、財務健全性、事業の強み・弱み、増配力、累進配当、政策との相性、グローバル展開、10年以上保有の適性、総合評価 A〜C）
   - 評価別の買い足し上限額（A：2万円、B・C：1万円）に応じた買い足し数量の調整指示
   - Excel 貼り付け用の「証券コード｜買い足し数量｜日付」表の出力指示

> 買い足し数量の計算には、手元の保有状況ファイル（`portfolio_result_all.csv`）を NotebookLM に別途読み込ませる前提です。このファイルはリポジトリには含まれません。

---

# 📂 ディレクトリ構成

```
.
├── jpx_screening_fetch.py        # ① データ取得
├── jpx_scoring_engine.py         # ② スコアリング
├── jpx_yield_filter.py           # ③ 利回り判定
├── makeprompt.py                 # ④ プロンプト生成
├── utils/sector_map.py           # セクター日本語化
├── input/
│   ├── jpx_all.csv               # JPX 全銘柄コード
│   └── topix_core30.csv          # テスト用（TOPIX Core30）
├── output/
│   ├── output_financial_dividend_merged.csv   # ① の出力（月次更新）
│   ├── weekly_scored_output.csv               # ② の出力（週次更新）
│   ├── weekly_filtered_output.csv             # ③ の出力（週次更新）
│   └── weekly_prompt_output.txt               # ④ の出力（週次更新）
├── .github/workflows/
│   ├── run-fetch.yml                  # 月次：データ取得
│   └── weekly_scoring_filter.yml      # 週次：スコアリング〜プロンプト生成
├── old/                          # 初期の仕様メモ・試作
└── requirements.txt
```

---

# 🚀 ローカルでの実行手順

```bash
pip install -r requirements.txt

# ① データ取得（全銘柄は時間がかかるため、まずは Core30 で動作確認）
python jpx_screening_fetch.py input/topix_core30.csv

# ② スコアリング（カレントディレクトリの output_financial_dividend_merged.csv を読み込む）
python jpx_scoring_engine.py

# ③ 利回り判定
python jpx_yield_filter.py 80 0.1

# ④ プロンプト生成
python makeprompt.py yield_filtered_output.csv 7
```

各スクリプトは**カレントディレクトリ**のファイルを読み書きします。
GitHub Actions 上では、実行後に `output/` 配下へ移動してコミットしています。

---

# 📄 出力ファイル一覧

| ファイル | 生成元 | 内容 |
|---|---|---|
| `output/output_financial_dividend_merged.csv` | ① | 10年分の配当＋財務データ |
| `output/weekly_scored_output.csv` | ② | 全銘柄のスコアと Problem |
| `output/weekly_filtered_output.csv` | ③ | 候補銘柄の利回り・買いシグナル |
| `output/weekly_prompt_output.txt` | ④ | NotebookLM 用プロンプト |

---

# 🚧 今後の拡張案

- 可視化ダッシュボードの追加
- バックテスト機能の実装
- Web UI 化（Streamlit）
- AI による銘柄レポート生成

---

> ⚠️ 本ツールは個人の情報整理を目的としたものであり、投資の勧誘・助言ではありません。
> yfinance のデータには欠損・誤りが含まれる場合があります。投資判断は必ずご自身で行ってください。
