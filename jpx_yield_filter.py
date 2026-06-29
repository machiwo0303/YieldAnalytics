import yfinance as yf
import pandas as pd
import sys
import time
from utils.sector_map import translate_sector

# ============================
# safe_call（全API呼び出しを安全化）
# ============================
def safe_call(func, *args, retries=3, wait=1, **kwargs):
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except yf.exceptions.YFRateLimitError:
            print("Rate limit… retrying")
            time.sleep(wait)
        except Exception as e:
            print(f"[WARN] yfinance error: {e}")
            time.sleep(wait)
    return None


# ============================
# 配当利回り（直近1年）
# ============================
def get_dividend_yield(ticker):
    hist = safe_call(ticker.history, period="1d")
    if hist is None or hist.empty:
        return None
    price = hist["Close"].iloc[-1]

    div = safe_call(ticker.get_dividends)
    if div is None or div.empty:
        return None

    idx = pd.DatetimeIndex(div.index)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    div.index = idx

    one_year_ago = pd.Timestamp.now("UTC") - pd.Timedelta(days=365)
    one_year_ago = one_year_ago.tz_localize(None)

    total_div = div[div.index >= one_year_ago].sum()

    return total_div / price if price > 0 else None


# ============================
# 株式分割情報
# ============================
def get_split_info(ticker):
    try:
        actions = safe_call(lambda: ticker.actions)
        if actions is None or "Stock Splits" not in actions.columns:
            return ""

        splits = actions["Stock Splits"]
        splits = splits[splits > 0]
        if splits.empty:
            return ""

        splits.index = splits.index.tz_localize(None)
        one_year_ago = pd.Timestamp.now("UTC").tz_localize(None) - pd.Timedelta(days=365)

        recent_splits = splits[splits.index >= one_year_ago]
        return "Split" if not recent_splits.empty else ""
    except:
        return ""


# ============================
# 直近2年の利回り統計
# ============================
def get_dividend_yield_2years_stats(ticker):
    hist = safe_call(ticker.history, period="2y", auto_adjust=True)
    if hist is None or hist.empty:
        return None, None

    div = safe_call(ticker.get_dividends)
    if div is None or div.empty:
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


# ============================
# セクター取得（info安全化）
# ============================
def get_sector(ticker):
    try:
        info = safe_call(lambda: ticker.info)
        if info is None:
            return "不明"
        sector = info.get("sector", "")
        return translate_sector(sector)
    except Exception as e:
        print(f"[WARN] Sector取得失敗: {ticker.ticker} ({e})")
        return "不明"


# ============================
# 現在株価
# ============================
def get_current_price(ticker):
    hist = safe_call(ticker.history, period="1d")
    if hist is None or hist.empty:
        return None
    return hist["Close"].iloc[-1]


# ============================
# 買い時判定
# ============================
def get_buy_signal(size_category, dy, avg2y, max2y, total_score, avg_growth_rate, growth_flg):
    if dy is None:
        return "×"

    if avg2y is not None and dy < avg2y:
        return "×"

    if dy < 0.03:
        return "△"
    if dy < 0.025:
        return "×"

    if avg2y is not None and dy >= avg2y * 1.5 and avg_growth_rate >= 0.05 and growth_flg is not None:
        return "☆"

    if max2y is not None and dy >= max2y and avg_growth_rate >= 0.05 and growth_flg is not None:
        return "☆"

    if avg2y is not None and dy >= avg2y * 1.35:
        return "◎"

    if max2y is not None and dy >= max2y * 0.95:
        return "◎"

    if avg2y is not None and dy >= avg2y * 1.2:
        return "〇"

    if max2y is not None and dy >= max2y * 0.8:
        return "〇"

    if avg2y is None or dy >= avg2y:
        return "△"

    return "×"


# ============================
# メイン処理
# ============================
def main():
    df = pd.read_csv("scored_output.csv")
    threshold = int(sys.argv[1])
    growthrate = float(sys.argv[2])

    df_top = df[
        (
            (df["TotalScore"] >= threshold) &
            (df["AvgGrowthRate"] > 0)
        )
        |
        (
            (df["AvgGrowthRate"] >= growthrate) &
            (df["CumulativeDividend"].notna()) &
            (df["CumulativeDividend"] != "")
        )
    ]

    results = []

    for _, row in df_top.iterrows():
        symbol = row["Symbol"]
        company = row["Company"]

        ticker = yf.Ticker(symbol)

        dy = get_dividend_yield(ticker)
        avg2y, max2y = get_dividend_yield_2years_stats(ticker)
        market_cap = row.get("MarketCap", None)
        size_category = get_size_category(market_cap)
        sector_jp = get_sector(ticker)
        split_flag = get_split_info(ticker)
        avg_growth_rate = row["AvgGrowthRate"]
        growth_flg = row["CumulativeDividend"]
        buy_signal = get_buy_signal(size_category, dy, avg2y, max2y, row["TotalScore"], avg_growth_rate, growth_flg)
        current_price = get_current_price(ticker)

        results.append({
            "Symbol": symbol,
            "Company": company,
            "CurrentPrice": current_price,
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
