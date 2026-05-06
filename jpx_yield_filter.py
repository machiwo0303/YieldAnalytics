import yfinance as yf
import pandas as pd

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
# 直近2年の利回り統計（平均・最高）
# ============================
def get_dividend_yield_2years_stats(symbol):
    ticker = yf.Ticker(symbol)

    # 株価2年分
    hist = ticker.history(period="2y")
    if hist.empty:
        return None, None

    # 配当データ
    try:
        div = ticker.get_dividends()
    except:
        return None, None

    if div.empty:
        return None, None

    # tz-naive
    idx = pd.DatetimeIndex(div.index)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    div.index = idx

    # 対象年（直近2年）
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


# ============================
# GICS → 東証33業種マッピング
# ============================
sector_map_33 = {
    "Technology": "情報・通信業",
    "Communication Services": "情報・通信業",
    "Industrials": "機械 / 電気機器 / 輸送用機器 / 建設業 / その他製品",
    "Consumer Cyclical": "小売業 / 卸売業 / 輸送用機器",
    "Consumer Defensive": "食料品",
    "Healthcare": "医薬品",
    "Energy": "石油・石炭製品",
    "Utilities": "電気・ガス業",
    "Real Estate": "不動産業",
    "Financial Services": "銀行業 / 証券 / 保険 / その他金融業",
    "Basic Materials": "化学 / 鉄鋼 / 非鉄金属 / ガラス・土石製品 / ゴム製品 / パルプ・紙"
}

def get_sector_jp(symbol):
    ticker = yf.Ticker(symbol)
    info = ticker.info
    sector = info.get("sector", None)
    if sector is None:
        return "Unknown"
    return sector_map_33.get(sector, sector)


# ============================
# 規模別の利回り基準
# ============================
def meets_yield_threshold(size_category, dy):
    if dy is None:
        return False

    thresholds = {
        "超小型": 0.06,
        "小型": 0.05,
        "中型": 0.045,
        "大型": 0.04,
        "超大型": 0.035
    }

    th = thresholds.get(size_category, 0.05)
    return dy >= th


# ============================
# メイン処理
# ============================
def main():
    df = pd.read_csv("scored_output.csv")
    df_top = df[df["TotalScore"] >= 60]

    results = []

    for _, row in df_top.iterrows():
        symbol = row["Symbol"]
        company = row["Company"]

        dy = get_dividend_yield(symbol)
        avg2y, max2y = get_dividend_yield_2years_stats(symbol)

        market_cap = row.get("MarketCap", None)
        size_category = get_size_category(market_cap)
        sector_jp = get_sector_jp(symbol)

        # ★ TotalScore 80以上は無条件採用
        if row["TotalScore"] < 80:
            if not meets_yield_threshold(size_category, dy):
                continue

        results.append({
            "Symbol": symbol,
            "Company": company,
            "TotalScore": row["TotalScore"],
            "DividendYield": dy,
            "AvgYield2Y": avg2y,
            "MaxYield2Y": max2y,
            "MarketCap": market_cap,
            "SizeCategory": size_category,
            "SectorJP": sector_jp
        })

    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values("DividendYield", ascending=False)
    df_result.to_csv("yield_filtered_output.csv", index=False, encoding="utf-8-sig")

    print(df_result)


if __name__ == "__main__":
    main()
