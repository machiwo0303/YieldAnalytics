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


# ============================
# industry → 東証33業種
# ============================
def normalize_industry_name(industry: str) -> str:
    s = industry.strip()
    s = s.replace("—", "-").replace("–", "-")
    while "  " in s:
        s = s.replace("  ", " ")
    return s


industry_map_jp = {
    # 電気機器
    "Electronic Components": "電気機器",
    "Semiconductors": "電気機器",
    "Computer Hardware": "電気機器",
    "Consumer Electronics": "電気機器",
    "Electrical Equipment & Parts": "電気機器",
    "Electronics & Computer Distribution": "電気機器",

    # その他製品
    "Furnishings, Fixtures & Appliances": "その他製品",
    "Household Products": "その他製品",
    "Household & Personal Products": "その他製品",

    # 輸送用機器
    "Auto Manufacturers": "輸送用機器",
    "Auto Parts": "輸送用機器",
    "Auto & Truck Dealerships": "輸送用機器",

    # 機械
    "Machinery": "機械",
    "Industrial Machinery": "機械",
    "Specialty Industrial Machinery": "機械",
    "Farm & Heavy Construction Machinery": "機械",
    "Building Products & Equipment": "機械",

    # 鉄鋼・非鉄
    "Steel": "鉄鋼",
    "Aluminum": "非鉄金属",
    "Other Precious Metals & Mining": "非鉄金属",

    # ガラス・土石
    "Building Materials": "ガラス・土石製品",

    # 化学
    "Chemicals": "化学",
    "Specialty Chemicals": "化学",

    # ゴム
    "Rubber & Plastics": "ゴム製品",

    # 繊維
    "Textile Manufacturing": "繊維製品",
    "Apparel Manufacturing": "繊維製品",

    # パルプ・紙
    "Packaging & Containers": "パルプ・紙",

    # エネルギー
    "Oil & Gas": "石油・石炭製品",
    "Oil & Gas Refining": "石油・石炭製品",
    "Coal": "鉱業",

    # 電気・ガス
    "Utilities - Regulated Electric": "電気・ガス業",
    "Utilities - Regulated Gas": "電気・ガス業",

    # 建設・不動産
    "Construction": "建設業",
    "Engineering & Construction": "建設業",
    "Residential Construction": "建設業",
    "Real Estate - Development": "不動産業",
    "Real Estate - Diversified": "不動産業",
    "Real Estate Services": "不動産業",

    # 金融
    "Banks - Regional": "銀行業",
    "Banks - Diversified": "銀行業",
    "Insurance - Life": "保険業",
    "Insurance - Property & Casualty": "保険業",
    "Capital Markets": "証券、商品先物取引業",
    "Financial Conglomerates": "その他金融業",
    "Credit Services": "その他金融業",
    "Asset Management": "その他金融業",
    "Rental & Leasing Services": "その他金融業",

    # 物流
    "Marine Shipping": "海運業",
    "Trucking": "陸運業",
    "Airlines": "空運業",
    "Integrated Freight & Logistics": "倉庫・運輸関連業",
    "Industrial Distribution": "倉庫・運輸関連業",

    # 小売
    "Retail": "小売業",
    "Department Stores": "小売業",
    "Grocery Stores": "小売業",
    "Internet Retail": "小売業",
    "Specialty Retail": "小売業",
    "Pharmaceutical Retailers": "小売業",

    # 食品
    "Food Products": "食料品",
    "Beverages - Non-Alcoholic": "食料品",
    "Packaged Foods": "食料品",
    "Confectioners": "食料品",

    # 医薬品・精密
    "Biotechnology": "医薬品",
    "Drug Manufacturers": "医薬品",
    "Drug Manufacturers - General": "医薬品",
    "Medical Devices": "精密機器",
    "Medical Instruments & Supplies": "精密機器",

    # 情報通信
    "Telecom Services": "情報・通信業",
    "Software - Application": "情報・通信業",
    "Software - Infrastructure": "情報・通信業",
    "IT Services": "情報・通信業",
    "Information Technology Services": "情報・通信業",
    "Internet Content & Information": "情報・通信業",
    "Electronic Gaming & Multimedia": "情報・通信業",
    "Health Information Services": "情報・通信業",

    # サービス業
    "Leisure": "サービス業",
    "Restaurants": "サービス業",
    "Professional Services": "サービス業",
    "Specialty Business Services": "サービス業",
    "Staffing & Employment Services": "サービス業",
    "Consulting Services": "サービス業",
    "Security & Protection Services": "サービス業",

    # 精密機器
    "Scientific & Technical Instruments": "精密機器",

    # 半導体製造装置
    "Semiconductor Equipment & Materials": "電気機器",

    # コングロマリット
    "Conglomerates": "その他製品",

    # エンタメ
    "Entertainment": "サービス業",

    # 環境
    "Pollution & Treatment Controls": "サービス業",

    # 廃棄物
    "Waste Management": "サービス業",
}


def get_sector_jp(symbol):
    ticker = yf.Ticker(symbol)
    info = ticker.info

    industry = info.get("industry", None)
    if industry is None:
        return "Unknown"

    norm = normalize_industry_name(industry)
    return industry_map_jp.get(norm, norm)


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
# 買い時判定（◎〇△×）
# ============================
def get_buy_signal(size_category, dy, avg2y, max2y, total_score):
    if dy is None:
        return "×"

    is_micro = (size_category == "超小型")

    # ×：平均利回り以下
    if avg2y is not None and dy < avg2y:
        return "×"

    # ×：利回りが低すぎる
    if dy < 0.0375:
        return "△"
    # ×：利回りが低すぎる
    if dy < 0.03:
        return "×"
    if total_score >= 90: # スコアが90点以上で下記を満たす場合優遇
        # ◎：超大型で6%以上
        if size_category == "超大型" and dy >= 0.06:
            return "◎"
        # ◎：大型で7%以上
        if size_category == "超大型" and dy >= 0.07:
            return "◎"
        # ◎：中型で8%以上
        if size_category == "超大型" and dy >= 0.08:
            return "◎"
    
        # 〇：小型で9%以上
        if size_category == "小型" and dy >= 0.09:
            return "〇"

    # 〇：平均利回りの1.35倍以上
    if avg2y is not None and dy >= avg2y * 1.35:
        if not is_micro:
            return "◎"

    # 〇：過去最高利回り以上（割安）
    if max2y is not None and dy >= max2y:
        if not is_micro:
            return "◎"
    # 〇：平均利回りの1.2倍以上
    if avg2y is not None and dy >= avg2y * 1.2:
        if not is_micro:
            return "〇"

    # 〇：過去最高利回りの80%以上（割安）
    if max2y is not None and dy >= max2y * 0.8:
        if not is_micro:
            return "〇"

    # △：超小型は△
    if is_micro:
        return "△"

    # △：平均以上なら監視候補
    if avg2y is None or dy >= avg2y:
        return "△"

    return "×"


# ============================
# メイン処理
# ============================
def main():
    df = pd.read_csv("scored_output.csv")
    df_top = df[df["TotalScore"] >= 80]

    results = []

    for _, row in df_top.iterrows():
        symbol = row["Symbol"]
        company = row["Company"]

        dy = get_dividend_yield(symbol)
        avg2y, max2y = get_dividend_yield_2years_stats(symbol)

        market_cap = row.get("MarketCap", None)
        size_category = get_size_category(market_cap)
        sector_jp = get_sector_jp(symbol)

        # ★ 分割フラグ（補正は2年利回り関数内で実施済み）
        split_flag = get_split_info(symbol)

        # ★ TotalScore 80以上は無条件採用
        if row["TotalScore"] < 80:
            if not meets_yield_threshold(size_category, dy):
                continue

        buy_signal = get_buy_signal(size_category, dy, avg2y, max2y, row["TotalScore"])

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
            "BuySignal": buy_signal
        })

    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values("DividendYield", ascending=False)
    df_result.to_csv("yield_filtered_output.csv", index=False, encoding="utf-8-sig")

    print(df_result)


if __name__ == "__main__":
    main()
