# YieldAnalytics  
日本株を対象にした「高配当 × 財務健全性 × 増配 × 割安度 × 企業規模 × セクター分析 × 買い時判定」に基づく  
**日本版 SCHD スタイルの銘柄スクリーニングツール** です。

本プロジェクトは以下の 3 ステップで構成されています：

1. **jpx_screening_fetch.py**  
   └ 財務データ・配当データを Yahoo Finance から取得し、銘柄ごとの年度別データを生成  
2. **jpx_scoring_engine.py**  
   └ 財務・収益性・配当履歴からスコアリングし、総合スコアを算出  
3. **jpx_yield_filter.py**  
   └ スコア上位銘柄に対して利回り・規模・セクター・割安度・買い時判定で最終フィルタリング

最終的に **yield_filtered_output.csv** として投資候補銘柄を出力します。

---

# 📌 1. jpx_screening_fetch.py  
**目的：銘柄ごとの財務データ・配当データを取得し、年度別に整理した CSV を生成**

### 🔍 取得するデータ
- 企業名（longName）
- ROE（returnOnEquity）
- EPS（trailingEps）
- 時価総額（marketCap）
- 財務データ（過去4年）
  - Revenue（売上高）
  - EquityRatio（自己資本比率）
  - OperatingCF（営業キャッシュフロー）
  - Cash（現金等）
- 配当データ（過去10年）
  - 年間配当金合計
  - 配当回数

### 🔧 主な処理
- yfinance の不安定さに対応した **安全な get_dividends()** を使用  
- financials / balance_sheet / cashflow の欠損に強い  
- 配当データの tz-aware / tz-naive 問題を完全排除  
- 年度ごとに財務＋配当を統合した行を生成  
- 最終的に **output_financial_dividend_merged.csv** を出力

---

# 📌 2. jpx_scoring_engine.py  
**目的：財務・収益性・配当履歴をスコア化し、総合スコアを算出**

### 🧮 スコア構成（合計 100 点満点想定）

## A. 配当スコア（最大 40 点）
- 無配なし（20 点）
- 増配年数 × 2 点（最大 20 点）
- 特別配当は自動補正（normalize_special_dividends）

## B. 財務スコア（最大 30 点）
- 自己資本比率（最大 10 点）
- 営業CF が直近4年すべてプラス（10 点）
- Cash / MarketCap ≥ 10%（10 点）

## C. 収益性スコア（最大 30 点）
- ROE（最大 10 点）
- 売上成長（過去3年で増加 → 10 点）
- EPS がプラス（10 点）

### 📤 出力
- Symbol  
- Company  
- DividendScore  
- FinancialScore  
- ProfitScore  
- TotalScore  
- MarketCap  

→ **scored_output.csv** を生成

---

# 📌 3. jpx_yield_filter.py  
**目的：スコア上位銘柄に対して利回り・規模・セクター・割安度・買い時判定で最終フィルタリング**

---

# 🏢 企業規模カテゴリ（MarketCap）
| カテゴリ | 基準 |
|---------|------|
| 超大型 | 1 兆円以上 |
| 大型 | 3000 億円〜1 兆円 |
| 中型 | 1000 億円〜3000 億円 |
| 小型 | 400 億円〜1000 億円 |
| 超小型 | 400 億円未満 |

---

# 📈 規模別の最低利回り基準
| 規模 | 最低利回り |
|------|-------------|
| 超小型 | 6% |
| 小型 | 5% |
| 中型 | 4.5% |
| 大型 | 4% |
| 超大型 | 3.5% |

---

# ⭐ TotalScore ≥ 80 の銘柄は **規模・利回り条件を無視して無条件採用**

---

# 📉 割安度判定（簡易版）
直近2年の利回りを以下で計算：

- 年間配当金 ÷ 年間最安値  
- 年間配当金 ÷ 年間平均株価  

→ これを直近2年分計算し、

- **AvgYield2Y（2年平均利回り）**
- **MaxYield2Y（2年最高利回り）**

を算出。

現在利回りが MaxYield2Y × 0.9 以上なら「過去最安値級の割安」。

---

# 🏭 セクター分類（industry → 東証33業種）
yfinance の **industry** を日本語の東証33業種へマッピング。

例：
- Software - Application → 情報・通信業  
- Auto Manufacturers → 輸送用機器  
- Steel → 鉄鋼  
- Real Estate - Development → 不動産業  
- Staffing & Employment Services → サービス業  

→ **SectorJP** として出力

---

# 🔥 買い時判定（BuySignal）

最新ロジックは以下の通り：

## ◎（絶対買い）
- 超大型  
- かつ 現在利回り ≥ 6%

## 〇（買い時）
- 中型以上で現在利回り ≥ 7%  
- 小型で現在利回り ≥ 9%  
- 現在利回り ≥ Avg2Y × 1.3  
- 現在利回り ≥ Max2Y × 0.9（過去最高利回りの90%以上）

## △（監視候補）
- 平均利回り以上  
- ただし **超小型は常に最大△**

## ×（見送り）
- 現在利回り < Avg2Y  
- または利回り < 2%

---

# 🔧 株式分割フラグ（SplitFlag）
- 過去の actions["Stock Splits"] に 1 以上があれば **Split**  
- それ以外は空欄

---

# 📤 最終出力（yield_filtered_output.csv）
以下の列を含む：

- Symbol  
- Company  
- TotalScore  
- DividendYield（直近1年）  
- AvgYield2Y（直近2年平均利回り）  
- MaxYield2Y（直近2年最高利回り）  
- MarketCap  
- SizeCategory  
- SectorJP  
- SplitFlag  
- BuySignal（◎〇△×）

---

# 🚀 実行手順（切れない形式）

### **1. 財務＋配当データ取得**
- 実行コマンド：  
  `python jpx_screening_fetch.py topix_core30.csv`

### **2. スコアリング**
- 実行コマンド：  
  `python jpx_scoring_engine.py`

### **3. 最終フィルタリング**
- 実行コマンド：  
  `python jpx_yield_filter.py`

---

# 📦 出力ファイル一覧

| ファイル名 | 内容 |
|------------|------|
| output_financial_dividend_merged.csv | 銘柄ごとの年度別財務＋配当データ |
| scored_output.csv | スコアリング結果 |
| yield_filtered_output.csv | 最終選定銘柄（利回り・規模・割安度・セクター・買い時判定） |

---

# 🎉 まとめ
YieldAnalytics は、

- 財務健全性  
- 収益性  
- 配当履歴  
- 企業規模  
- セクター  
- 割安度（利回り比較）  
- 買い時判定（◎〇△×）  
- 株式分割フラグ  

を統合した **日本株高配当スクリーナーの完成形** です。

SCHD の思想を日本株に最適化した強力なツールとして利用できます。
