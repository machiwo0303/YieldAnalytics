import pandas as pd
import numpy as np

# ============================
# 特別配当補正
# ============================
def normalize_special_dividends(divs):
    divs = divs.copy()
    for i in range(1, len(divs)-1):
        prev_d = divs[i-1]
        cur_d = divs[i]
        next_d = divs[i+1]
        # 特別配当判定：前後の年と比べて極端に高い
        if prev_d > 0 and cur_d >= prev_d * 1.8 and next_d <= cur_d * 0.7:
            divs[i] = max(prev_d, next_d)
    return divs

# ============================
# A. 配当スコア
# ============================
def calc_dividend_score(group):
    divs = group.sort_values("Year")["Dividend"].tolist()
    if len(divs) < 5:
        return 0

    divs = normalize_special_dividends(divs)

    score = 0

    # 無配なし
    if all(d > 0 for d in divs):
        score += 20

    # 増配年数
    inc = sum(1 for i in range(len(divs)-1) if divs[i+1] > divs[i])
    score += min(inc * 2, 20)

    return score

# ============================
# B. 財務スコア
# ============================
def calc_financial_score(group):
    latest = group.sort_values("Year").iloc[-1]

    score = 0

    # Equity Ratio
    er = latest["EquityRatio"]
    if pd.notna(er):
        if er >= 0.40:
            score += 10
        elif er >= 0.30:
            score += 5

    # Operating CF（過去4年）
    cf = group.sort_values("Year")["OperatingCF"].tail(4)
    if all((x is not None) and (x > 0) for x in cf):
        score += 10

    # Cash / MarketCap
    cash = latest["Cash"]
    mc = latest["MarketCap"]
    if pd.notna(cash) and pd.notna(mc) and mc > 0:
        if cash / mc >= 0.10:
            score += 10

    return score

# ============================
# C. 収益性スコア
# ============================
def calc_profit_score(group):
    latest = group.sort_values("Year").iloc[-1]

    score = 0

    # ROE
    roe = latest["ROE"]
    if pd.notna(roe):
        if roe >= 0.10:
            score += 10
        elif roe >= 0.05:
            score += 5

    # Revenue Growth（過去3年）
    rev = group.sort_values("Year")["Revenue"].dropna().tail(3)
    if len(rev) == 3:
        if rev.iloc[-1] > rev.iloc[0]:
            score += 10

    # EPS
    eps = latest["EPS"]
    if pd.notna(eps) and eps > 0:
        score += 10

    return score

# ============================
# メイン処理
# ============================
df = pd.read_csv("output_financial_dividend_merged.csv")

results = []

for symbol, group in df.groupby("Symbol"):
    dividend_score = calc_dividend_score(group)
    financial_score = calc_financial_score(group)
    profit_score = calc_profit_score(group)

    total = dividend_score + financial_score + profit_score

    results.append({
        "Symbol": symbol,
        "Company": group.iloc[0]["Company"],
        "DividendScore": dividend_score,
        "FinancialScore": financial_score,
        "ProfitScore": profit_score,
        "TotalScore": total
    })

df_score = pd.DataFrame(results)

# 昇順で出力
df_score = df_score.sort_values("TotalScore", ascending=False)

df_score.to_csv("scored_output.csv", index=False, encoding="utf-8-sig")

print(df_score)
