# JPX Dividend Quality Screener (日本版 SCHD スクリーナー)

このプロジェクトは、日本株約4000銘柄を対象に  
**配当の安定性・財務健全性・収益性** をスコアリングし、  
さらに **利回りが高いタイミングで買うべき銘柄を抽出する**  
完全自動のスクリーナーです。

---

# 📌 スクリプト構成

本プロジェクトは以下の3つのスクリプトで構成されています。

---

## 1. `jpx_screening_fetch.py`
### 📘 役割：**日本株の生データを取得するスクリーニング**

- yfinance を使って日本株の財務データ・配当データを取得
- 過去10年の配当
- 過去4年の財務（Revenue / EquityRatio / OperatingCF / Cash）
- 最新の ROE / EPS / MarketCap
- これらをまとめて CSV（output_financial_dividend_merged.csv）に保存

### 📤 出力ファイル
output_financial_dividend_merged.csv

コード

---

## 2. `jpx_scoring_engine.py`
### 📘 役割：**A〜D のスコアを計算するスコアリングエンジン**

このスクリプトは CSV を読み込み、以下のスコアを計算します。

### A. 配当スコア（最大40点）
- 無配なし（10年連続配当）  
- 増配年数  
- 特別配当補正あり  

### B. 財務スコア（最大30点）
- EquityRatio  
- OperatingCF の安定性  
- Cash / MarketCap  

### C. 収益性スコア（最大30点）
- ROE  
- Revenue Growth  
- EPS  

### D. 総合スコア（100点満点）

### 📤 出力ファイル
scored_output.csv

コード

---

## 3. `jpx_yield_filter.py`
### 📘 役割：**スコア上位銘柄の中から、利回りが高い銘柄を抽出**

- scored_output.csv を読み込み
- スコア上位（例：60点以上）に絞る
- 最新株価を取得
- 直近1年の配当合計を取得
- 配当利回りを計算
- 利回りの高い順に並べて出力

### 📤 出力ファイル
yield_filtered_output.csv

コード

---

# 📊 全体の流れ

[1] jpx_screening_fetch.py
↓
output_financial_dividend_merged.csv
↓
[2] jpx_scoring_engine.py
↓
scored_output.csv
↓
[3] jpx_yield_filter.py
↓
yield_filtered_output.csv（今買うべき銘柄）

コード

---

# 🏆 このスクリーナーでできること

- 日本株4000銘柄を完全自動でスクリーニング
- SCHD の思想に基づく「高品質配当株」を抽出
- 特別配当補正による正確な増配判定
- 財務・収益性を加味した総合スコアリング
- 利回りが高いタイミングで買う銘柄を抽出

---

# 📌 必要なライブラリ

pip install yfinance pandas numpy

コード

---

# 🎉 完成
この3つのスクリプトを使えば、  
**日本版 SCHD の完全自動スクリーナー** が完成します。