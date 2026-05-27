import yfinance as yf
import pandas as pd
import sys
from utils.sector_map import translate_sector

# ============================
# 配当利回り（直近1年）
# ============================
def get_dividend_yield(symbol):
    ticker = yf.Ticker(symbol)

    hist = ticker.history(period="1d")
    if hist.empty:
        return None
    price = hist["Close"].iloc[-1]

    div = ticker.get_dividends()
    if div.empty:
        return None

    idx = pd.DatetimeIndex(div.index)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    div.index = idx

    one_year_ago = pd.Timestamp.utcnow() - pd.Timedelta(days=365)
    one_year_ago = one_year_ago.replace(tzinfo=None)

    total_div = div[div.index >= one_year_ago].sum()

    if price > 0:
        return total_div / price
    return None


# ============================
# 株式分割情報（倍率＋フラグ）
# ============================
def get_split_info(symbol):
    ticker = yf.Ticker(symbol)
    try:
        actions = ticker.actions

        if "Stock Splits" not in actions.columns:
            return ""

        splits = actions["Stock Splits"]
        splits = splits[splits > 0]

        if splits.empty:
            return ""

        # ★ index を tz-naive に変換
        splits.index = splits.index.tz_localize(None)

        # ★ 過去1年以内の分割だけを見る
        one_year_ago = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=365)

        recent_splits = splits[splits.index >= one_year_ago]

        if recent_splits.empty:
            return ""

        return "Split"

    except:
        return ""


# ============================
# 直近2年の利回り統計（平均・最高）＋分割補正
# ============================
def get_dividend_yield_2years_stats(symbol):
    ticker = yf.Ticker(symbol)

    # 調整後株価（分割・配当調整済み）
    hist = ticker.history(period="2y", auto_adjust=True)
    if hist.empty:
        return None, None

    try:
        div = ticker.get_dividends()
    except:
        return None, None

    if div.empty:
        return None, None

    idx = pd.DatetimeIndex(div.index)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    div.index = idx

    years = sorted(list(set(div.index.year)))[-2:]

    yields = []

    for y in years:
        div_y = div[div.index.year == y].sum()
        hist_y = hist[hist.index.year == y]

        if hist_y.empty or div_y == 0:
            continue

        low_price = hist_y["Close"].min()
        avg_price = hist_y["Close"].mean()

        if low_price > 0:
            yields.append(div_y / low_price)

        if avg_price > 0:
            yields.append(div_y / avg_price)

    if not yields:
        return None, None

    return sum(yields) / len(yields), max(yields)



# ============================
# 企業規模カテゴリ
# ============================
def get_size_category(market_cap):
    if pd.isna(market_cap):
        return "Unknown"

    if market_cap >= 1_000_000_000_000:
        return "超大型"
    elif market_cap >= 300_000_000_000:
        return "大型"
    elif market_cap >= 100_000_000_000:
        return "中型"
    elif market_cap >= 40_000_000_000:
        return "小型"
    else:
        return "超小型"



def get_sector(symbol):
    ticker = yf.Ticker(symbol)
    info = ticker.info

    # yfinance の sector をそのまま返す
    sector = info.get("sector", "")
    sector_jp = translate_sector(sector)

    return sector_jp


# ============================
# 買い時判定（◎〇△×）
# ============================
def get_buy_signal(size_category, dy, avg2y, max2y, total_score, avg_growth_rate, growth_flg):
    if dy is None:
        return "×"

    # ×：平均利回り以下
    if avg2y is not None and dy < avg2y:
        return "×"

    # ×：利回りが低すぎる
    if dy < 0.03:
        return "△"
    # ×：利回りが低すぎる
    if dy < 0.025:
        return "×"
    
    # ☆：平均利回りの1.5倍以上　かつ　平均増配率5%以上
    if avg2y is not None and dy >= avg2y * 1.5 and avg_growth_rate >= 0.05 and growth_flg is not None:
        return "☆"

    # ☆：過去最高利回り以上（割安）　かつ　平均増配率5%以上
    if max2y is not None and dy >= max2y and avg_growth_rate >= 0.05 and growth_flg is not None:
        return "☆"

    # ◎：平均利回りの1.35倍以上
    if avg2y is not None and dy >= avg2y * 1.35:
        return "◎"

    # ◎：過去最高利回りの95%以上（割安）
    if max2y is not None and dy >= max2y * 0.95:
        return "◎"
    # 〇：平均利回りの1.2倍以上
    if avg2y is not None and dy >= avg2y * 1.2:
        return "〇"

    # 〇：過去最高利回りの80%以上（割安）
    if max2y is not None and dy >= max2y * 0.8:
        return "〇"


    # △：平均以上なら監視候補
    if avg2y is None or dy >= avg2y:
        return "△"

    return "×"


# ============================
# メイン処理
# ============================
def main():
    df = pd.read_csv("scored_output.csv")
    threshold = int(sys.argv[1])
    df_top = df[df["TotalScore"] >= threshold]
    
    # ★ Problem が 2つ以上ある銘柄を除外
    df_top = df_top[df_top["Problem"].fillna("").apply(lambda x: len([p for p in x.split("/") if p.strip()]) <= 1)]

    results = []

    for _, row in df_top.iterrows():
        symbol = row["Symbol"]
        company = row["Company"]

        dy = get_dividend_yield(symbol)
        avg2y, max2y = get_dividend_yield_2years_stats(symbol)

        market_cap = row.get("MarketCap", None)
        size_category = get_size_category(market_cap)
        sector_jp = get_sector(symbol)

        # ★ 分割フラグ（補正は2年利回り関数内で実施済み）
        split_flag = get_split_info(symbol)
        
        avg_growth_rate = row["AvgGrowthRate"]
        growth_flg = row["CumulativeDividend"]
        buy_signal = get_buy_signal(size_category, dy, avg2y, max2y, row["TotalScore"], avg_growth_rate, growth_flg)

        results.append({
            "Symbol": symbol,
            "Company": company,
            "TotalScore": row["TotalScore"],
            "DividendYield": dy,
            "AvgYield2Y": avg2y,
            "MaxYield2Y": max2y,
            "MarketCap": market_cap,
            "SizeCategory": size_category,
            "SectorJP": sector_jp,
            "SplitFlag": split_flag,
            "BuySignal": buy_signal,
            "Problem": row["Problem"],
            "AvgGrowthRate": avg_growth_rate,
            "CumulativeDividend": growth_flg
        })

    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values("DividendYield", ascending=False)
    df_result.to_csv("yield_filtered_output.csv", index=False, encoding="utf-8-sig")

    print(df_result)


if __name__ == "__main__":
    main()
