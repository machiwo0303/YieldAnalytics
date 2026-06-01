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
    group_sorted = group.sort_values("Year")
    divs = group_sorted["Dividend"].tolist()

    problems = []  # ← 問題点を記録するリスト
    excellent_dividend_flag = ""

    if len(divs) < 5:
        problems.append("配当履歴不足")
        return 0, problems

    divs = normalize_special_dividends(divs)

    score = 0

    # 無配なし
    if all(d > 0 for d in divs):
        score += 20
    else:
        score -= 40
        problems.append("無配年あり")

    # 増配年数
    inc = sum(1 for i in range(len(divs)-1) if divs[i+1] >= divs[i])
    score += min(inc * 2, 20)
    if inc == 0:
        problems.append("増配なし")
    
    # ============================
    # ★ 減配チェック（最新年は除外）
    # ============================
    
    dec = 0
    for i in range(len(divs) - 1):
        # ★ 最新年（最後の比較）はスキップ
        if i+1 == len(divs) - 1:
            continue
    
        if divs[i+1] < divs[i]:
            dec += 1
    
    if dec > 0:
        score -= 1
    if dec > 1:
        score -= dec * 10
        problems.append("2回減配あり")
    if dec > 2:
        problems.append("3回以上減配あり")
    
    # ============================
    # ★ 配当性向チェック（新規追加）
    # ============================
    payout_penalty = 0
    payout70_count = 0   # ★ 70%以上の回数カウンタ
    recent = group_sorted.tail(4)

    for _, row in recent.iterrows():
        div = row["Dividend"]
        eps = row["EPS"]

        if pd.notna(div) and pd.notna(eps) and eps > 0:
            payout = div / eps

            if payout >= 1.00:
                payout_penalty -= 5
                problems.append("配当性向100%以上")
            elif payout >= 0.70:
                payout70_count += 1
                if payout70_count >= 2:   # ★ 2回目以降減点
                    payout_penalty -= 2
                    problems.append("配当性向70%以上2回")
    
    # ============================
    # ★ 平均増配率の計算（最新年は除外）
    # ============================
    growth_rates = []
    for i in range(len(divs) - 2):  # 最新年を除外するため -2 まで
        prev = divs[i]
        curr = divs[i+1]
        if prev > 0:
            growth_rates.append((curr - prev) / prev)

    avg_growth_rate = None
    growth_flg = None
    
    if growth_rates:
        avg_growth_rate = sum(growth_rates) / len(growth_rates)
        if avg_growth_rate <= 0.1:
            payout_penalty -= 2
        if avg_growth_rate <= 0.05:
            payout_penalty -= 2
        if avg_growth_rate <= 0.025:
            payout_penalty -= 2
        if avg_growth_rate == 0:
            payout_penalty -= 14
    score += payout_penalty
    if score >= 38:
        growth_flg = "累進"
        score = 40 # 最終年のカウントの仕様上9年累進なら満点に補正
    # ★ マイナススコアは 0 に丸める
    score = max(score, 0)
    return score, problems, avg_growth_rate, growth_flg


# ============================
# B. 財務スコア
# ============================
def calc_financial_score(group):
    latest = group.sort_values("Year").iloc[-1]
    problems = []
    score = 0

    # Equity Ratio
    er = latest["EquityRatio"]
    if pd.notna(er):
        if er >= 0.40:
            score += 10
        elif er >= 0.30:
            score += 5
        else:
            problems.append("自己資本比率低い")

    # Operating CF（過去4年）
    cf = (
        group.sort_values("Year")["OperatingCF"]
        .dropna()
        .tail(4)
        .tolist()
    )

    if all(x > 0 for x in cf):
        score += 8
    if sum(cf) > 0:
        score += 4
    else:
        problems.append("営業CF合計マイナス")

    # Cash / MarketCap
    cash = latest["Cash"]
    mc = latest["MarketCap"]
    if pd.notna(cash) and pd.notna(mc) and mc > 0:
        if cash / mc >= 0.10:
            score += 8
        else:
            problems.append("現金比率低い")

    # 時価総額によるスコアリング
    if mc >= 1_000_000_000_000:
        score += 0   # 超大型
    elif mc >= 300_000_000_000:
        score += 0   # 大型
    elif mc >= 100_000_000_000:
        score += 0   # 中型
    elif mc >= 40_000_000_000:
        score -= 3   # 小型
    elif mc >= 10_000_000_000:
        score -= 5   # 小型
    else:
        score -= 10  # 超小型
    
    # ★ マイナススコアは 0 に丸める
    score = max(score, 0)
    return score, problems

# ============================
# C. 収益性スコア
# ============================
def calc_profit_score(group):
    latest = group.sort_values("Year").iloc[-1]
    problems = []
    score = 0

    # ROE
    roe = latest["ROE"]
    if pd.notna(roe):
        if roe >= 0.10:
            score += 10
        elif roe >= 0.05:
            score += 5
        else:
            problems.append("ROE低い")

    # Revenue Growth
    rev = (
        group.sort_values("Year")["Revenue"]
        .dropna()
        .tail(4)
    )
    if len(rev) == 4:
        inc_count = sum(rev.iloc[i] < rev.iloc[i+1] for i in range(3))
        score += inc_count * 2
        if inc_count == 0:
            problems.append("減収傾向")
        if inc_count == 3:
            score += 4

    # EPS
    eps = latest["EPS"]
    if pd.notna(eps) and eps > 0:
        score += 10
    else:
        problems.append("EPS低い")

    return score, problems


# ============================
# メイン処理
# ============================
df = pd.read_csv("output_financial_dividend_merged.csv")

results = []

for symbol, group in df.groupby("Symbol"):
    group_sorted = group.sort_values("Year")
    latest = group_sorted.iloc[-1]

    dividend_score, p1, avg_growth_rate, growth_flg = calc_dividend_score(group)
    financial_score, p2 = calc_financial_score(group)
    profit_score, p3 = calc_profit_score(group)

    problems = list(set(p1 + p2 + p3))  # 重複排除

    total = dividend_score + financial_score + profit_score

    results.append({
        "Symbol": symbol,
        "Company": group.iloc[0]["Company"],
        "DividendScore": dividend_score,
        "FinancialScore": financial_score,
        "ProfitScore": profit_score,
        "TotalScore": total,
        "MarketCap": latest["MarketCap"],
        "Problem": "/".join(problems),
        "AvgGrowthRate": avg_growth_rate,  # ← 追加
        "CumulativeDividend": growth_flg  # ← 追加
    })


df_score = pd.DataFrame(results)

# 昇順で出力
df_score = df_score.sort_values("TotalScore", ascending=False)

df_score.to_csv("scored_output.csv", index=False, encoding="utf-8-sig")

print(df_score)