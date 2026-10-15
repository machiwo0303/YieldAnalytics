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
# 直近2年の利回り統計（直近12か月ごとの2期間）
#   期間1: 今日から遡って365日
#   期間2: その前の365日
# 暦年ではなく12か月で区切るので、当年の配当が途中でも常に12か月分どうしで比較できる
# （期間1は get_dividend_yield の「直近1年」と同じ範囲）
# ============================
def get_dividend_yield_2years_stats(ticker):
    hist = safe_call(ticker.history, period="2y", auto_adjust=True)
    if hist is None or hist.empty:
        return None, None

    div = safe_call(ticker.get_dividends)
    if div is None or div.empty:
        return None, None

    # タイムゾーンを外す
    hist = hist.copy()
    hist_idx = pd.DatetimeIndex(hist.index)
    if hist_idx.tz is not None:
        hist_idx = hist_idx.tz_convert(None)
    hist.index = hist_idx

    idx = pd.DatetimeIndex(div.index)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    div.index = idx

    # [start, end) の2期間（期間1の end は今日を含めるため翌日にする）
    now = pd.Timestamp.now("UTC").tz_localize(None)
    windows = [
        (now - pd.Timedelta(days=365), now + pd.Timedelta(days=1)),
        (now - pd.Timedelta(days=730), now - pd.Timedelta(days=365)),
    ]

    yields = []

    for start, end in windows:
        div_w = div[(div.index >= start) & (div.index < end)].sum()
        hist_w = hist[(hist.index >= start) & (hist.index < end)]

        if hist_w.empty or div_w == 0:
            continue

        low_price = hist_w["Close"].min()
        avg_price = hist_w["Close"].mean()

        if low_price > 0:
            yields.append(div_w / low_price)
        if avg_price > 0:
            yields.append(div_w / avg_price)

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

    # ×：1%未満
    if dy < 0.01:
        return "×"
    # ×：平均増配率50%未満かつ利回りが2%未満
    if dy < 0.02 and avg_growth_rate < 0.5:
        return "×"
    # △：平均増配率20%未満かつ利回りが3%未満
    if dy < 0.03 and avg_growth_rate < 0.2:
        return "△"
    
    # ☆：平均利回りの1.5倍以上　かつ　平均増配率5%以上
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
# 設定（ウォッチリスト／今月の買い時）
# ============================
# ウォッチリスト：規模別の「過去2年平均利回り」の基準
# （現在利回りではなく2年平均を使うので、現在の株価に左右されない）
YIELD_REQ_BY_SIZE = {
    "超大型": 0.030,
    "大型":   0.035,
    "中型":   0.040,
    "小型":   0.045,
    "超小型": 0.050,
}
UNKNOWN_SIZE_REQ = 0.050          # 規模不明は最も厳しい基準を適用
GROWTH_BRANCH_MIN_YIELD = 0.03    # 増配率枠の最低2年平均利回り

# ゲートで除外する重大な問題（Problem 列のタグ）
CRITICAL_PROBLEMS = [
    "配当性向100%以上",
    "営業CF合計マイナス",
    "自己資本比率低い",
    "EPS低い",
]

# 今月の買い時として扱うシグナルと優先順（小さいほど優先）
BUY_TIERS = {"☆": 0, "◎": 1, "〇": 2}


# ============================
# ゲート判定（ネット接続不要）
# ============================
def has_critical_problem(problem):
    if not isinstance(problem, str):
        return False
    return any(tag in problem for tag in CRITICAL_PROBLEMS)


# ============================
# ウォッチリスト判定
# ============================
def judge_watch(size_category, avg2y, avg_growth_rate, growth_min):
    """(採用するか, 枠の名前) を返す。
    高利回り枠 : 2年平均利回り >= 規模別基準
    増配率枠   : 2年平均利回り >= 3% かつ 平均増配率 >= growth_min
    """
    if avg2y is None or pd.isna(avg2y):
        return False, ""

    req = YIELD_REQ_BY_SIZE.get(size_category, UNKNOWN_SIZE_REQ)
    if avg2y >= req:
        return True, "高利回り"

    if (
        avg2y >= GROWTH_BRANCH_MIN_YIELD
        and pd.notna(avg_growth_rate)
        and avg_growth_rate >= growth_min
    ):
        return True, "増配率"

    return False, ""


# ============================
# 今月の買い時（☆◎〇 → 割安度順に上位n件）
# ============================
def pick_monthly(df_watch, n):
    cand = df_watch[df_watch["BuySignal"].isin(BUY_TIERS.keys())].copy()
    if cand.empty:
        return []

    cand["_tier"] = cand["BuySignal"].map(BUY_TIERS)
    cand = cand.sort_values(["_tier", "Valuation"], ascending=[True, False])
    return cand.head(n).index.tolist()


# ============================
# メイン処理
# ============================
# 使い方: python jpx_yield_filter.py [TotalScore下限=75] [増配率枠の増配率下限=0.25]
#                                     [ウォッチリスト上限=100] [今月の買い時の件数=10]
def main():
    df = pd.read_csv("scored_output.csv")

    score_min = int(sys.argv[1]) if len(sys.argv) > 1 else 75
    growth_min = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
    watch_max = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    pick_n = int(sys.argv[4]) if len(sys.argv) > 4 else 10

    # ① ゲート：累進 & 重大な問題なし & TotalScore 下限（ネット接続前に絞る）
    progressive = df["CumulativeDividend"].notna() & (df["CumulativeDividend"] != "")
    critical = df["Problem"].apply(has_critical_problem)
    df_gate = df[progressive & ~critical & (df["TotalScore"] >= score_min)]
    print(f"ゲート通過: {len(df_gate)}件 / 全{len(df)}件")

    results = []

    for _, row in df_gate.iterrows():
        symbol = row["Symbol"]
        ticker = yf.Ticker(symbol)

        # ② ウォッチリスト判定（過去2年平均利回りを使用）
        avg2y, max2y = get_dividend_yield_2years_stats(ticker)
        market_cap = row.get("MarketCap", None)
        size_category = get_size_category(market_cap)
        avg_growth_rate = row["AvgGrowthRate"]

        is_watch, watch_type = judge_watch(size_category, avg2y, avg_growth_rate, growth_min)
        if not is_watch:
            continue

        # ウォッチ対象のみ、残りの情報を取得
        dy = get_dividend_yield(ticker)
        sector_jp = get_sector(ticker)
        split_flag = get_split_info(ticker)
        current_price = get_current_price(ticker)
        growth_flg = row["CumulativeDividend"]
        buy_signal = get_buy_signal(
            size_category, dy, avg2y, max2y, row["TotalScore"], avg_growth_rate, growth_flg
        )
        valuation = (dy / avg2y) if (dy is not None and avg2y) else None

        results.append({
            "Symbol": symbol,
            "Company": row["Company"],
            "CurrentPrice": current_price,
            "TotalScore": row["TotalScore"],
            "DividendYield": dy,
            "AvgYield2Y": avg2y,
            "MaxYield2Y": max2y,
            "Valuation": valuation,          # 割安度 = 現在利回り ÷ 2年平均利回り
            "MarketCap": market_cap,
            "SizeCategory": size_category,
            "SectorJP": sector_jp,
            "SplitFlag": split_flag,
            "BuySignal": buy_signal,
            "WatchType": watch_type,         # 高利回り / 増配率
            "Problem": row["Problem"],
            "AvgGrowthRate": avg_growth_rate,
            "CumulativeDividend": growth_flg,
        })

    df_result = pd.DataFrame(results)
    if df_result.empty:
        print("ウォッチリスト該当なし")
        df_result.to_csv("yield_filtered_output.csv", index=False, encoding="utf-8-sig")
        return

    # 上限超過時は2年平均利回りの高い順に残す
    if len(df_result) > watch_max:
        df_result = (
            df_result.sort_values("AvgYield2Y", ascending=False)
            .head(watch_max)
            .reset_index(drop=True)
        )

    # ③ 今月の買い時
    picks = pick_monthly(df_result, pick_n)
    pick_set = set(picks)
    df_result["MonthlyPick"] = ["Y" if i in pick_set else "" for i in df_result.index]

    df_result["_tier"] = df_result["BuySignal"].map(BUY_TIERS).fillna(9)
    df_result["_pick"] = df_result["MonthlyPick"] == "Y"
    df_result = df_result.sort_values(
        ["_pick", "_tier", "Valuation"], ascending=[False, True, False]
    ).drop(columns=["_tier", "_pick"])

    df_picks = df_result[df_result["MonthlyPick"] == "Y"]

    df_result.to_csv("yield_filtered_output.csv", index=False, encoding="utf-8-sig")

    print(f"ウォッチリスト: {len(df_result)}件")
    print(df_result["BuySignal"].value_counts().to_string())
    print(f"今月の買い時: {len(df_picks)}件")
    print(df_picks[["Symbol", "Company", "SectorJP", "BuySignal", "DividendYield", "Valuation"]])


if __name__ == "__main__":
    main()