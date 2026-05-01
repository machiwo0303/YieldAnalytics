import yfinance as yf
import pandas as pd

# ============================
# 配当利回り計算
# ============================
def get_dividend_yield(symbol):
    ticker = yf.Ticker(symbol)

    # 最新株価
    price = ticker.history(period="1d")["Close"].iloc[-1]

    # 直近1年の配当合計
    div = ticker.dividends
    last_year = pd.Timestamp.today().year - 1
    total_div = div[div.index.year >= last_year].sum()

    if price > 0:
        return total_div / price
    return None

# ============================
# メイン処理
# ============================
def main():
    df = pd.read_csv("scored_output.csv")

    # スコア上位だけに絞る（例：総合スコア60以上）
    df_top = df[df["TotalScore"] >= 60]

    results = []

    for _, row in df_top.iterrows():
        symbol = row["Symbol"]
        company = row["Company"]

        dy = get_dividend_yield(symbol)

        results.append({
            "Symbol": symbol,
            "Company": company,
            "TotalScore": row["TotalScore"],
            "DividendYield": dy
        })

    df_result = pd.DataFrame(results)

    # 利回りの高い順に並べる
    df_result = df_result.sort_values("DividendYield", ascending=False)

    df_result.to_csv("yield_filtered_output.csv", index=False, encoding="utf-8-sig")

    print(df_result)

if __name__ == "__main__":
    main()
