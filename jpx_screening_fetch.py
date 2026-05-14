import yfinance as yf
import pandas as pd
import sys

# -----------------------------
# Helper: find correct row name
# -----------------------------
def find_row(df, candidates):
    if df is None or df.empty:
        return None
    for c in candidates:
        if c in df.index:
            return df.loc[c]
    return None

# -----------------------------
# Safe dividend fetch
# -----------------------------
def safe_get_dividends(ticker, symbol):
    try:
        div = ticker.get_dividends()
    except Exception as e:
        print(f"[WARN] Failed to fetch dividends for {symbol}: {e}")
        return pd.Series(dtype=float)

    # tz-aware → tz-naive
    if not div.empty:
        idx = pd.DatetimeIndex(div.index)
        if idx.tz is not None:
            idx = idx.tz_convert(None)
        div.index = idx

    return div

# -----------------------------
# Main processing function
# -----------------------------
def process_stock(symbol):
    ticker = yf.Ticker(symbol)

    # Basic info
    info = ticker.info
    company_name = info.get("longName", "Unknown")
    roe = info.get("returnOnEquity")
    eps = info.get("trailingEps")
    market_cap = info.get("marketCap")

    # Financial statements
    try:
        income = ticker.financials
    except:
        income = pd.DataFrame()

    try:
        bs = ticker.balance_sheet
    except:
        bs = pd.DataFrame()

    try:
        cf = ticker.cashflow
    except:
        cf = pd.DataFrame()

    # Dividends (safe)
    div = safe_get_dividends(ticker, symbol)

    # Equity / Assets row detection
    equity_candidates = [
        "Total Stockholder Equity",
        "Total Equity",
        "Stockholders Equity",
        "Total Shareholder Equity",
        "Shareholders Equity",
    ]
    assets_candidates = ["Total Assets", "Total assets"]

    equity_row = find_row(bs, equity_candidates)
    assets_row = find_row(bs, assets_candidates)

    # -----------------------------
    # Financial Data (up to 4 years)
    # -----------------------------
    financial_dict = {}

    if income is not None and not income.empty:
        years = income.columns

        for year in years:
            y = year.year
            financial_dict[y] = {
                "Revenue": income.loc["Total Revenue"].get(year) if "Total Revenue" in income.index else None,
                "EquityRatio": None,
                "OperatingCF": None,
                "Cash": None,
            }

            # Equity Ratio
            equity = equity_row.get(year) if equity_row is not None else None
            assets = assets_row.get(year) if assets_row is not None else None
            financial_dict[y]["EquityRatio"] = (equity / assets) if (equity and assets) else None

            # Operating Cash Flow
            if "Operating Cash Flow" in cf.index:
                financial_dict[y]["OperatingCF"] = cf.loc["Operating Cash Flow"].get(year)

            # Cash
            if "Cash And Cash Equivalents" in bs.index:
                financial_dict[y]["Cash"] = bs.loc["Cash And Cash Equivalents"].get(year)

    # -----------------------------
    # Dividend Data (past 10 years)
    # -----------------------------
    current_year = pd.Timestamp.today().year
    years_for_output = list(range(current_year - 10, current_year + 1))

    output_rows = []

    for y in years_for_output:
        total_div = div[div.index.year == y].sum() if not div.empty else 0
        count = len(div[div.index.year == y]) if not div.empty else 0

        fin = financial_dict.get(y, {})

        row = {
            "Symbol": symbol,
            "Company": company_name,
            "Year": y,
            "Revenue": fin.get("Revenue"),
            "EquityRatio": fin.get("EquityRatio"),
            "OperatingCF": fin.get("OperatingCF"),
            "Cash": fin.get("Cash"),
            "Dividend": total_div,
            "Count": count,
            "ROE": roe,
            "EPS": eps,
            "MarketCap": market_cap,
        }

        output_rows.append(row)

    print(f"\n=== {symbol} {company_name} ===")
    print(pd.DataFrame(output_rows).to_string(index=False))

    return output_rows


# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py topix_core30.csv")
        sys.exit(1)

    csv_file = sys.argv[1]
    df_codes = pd.read_csv(csv_file, usecols=[0], header=None, names=["code"])

    all_rows = []

    for code in df_codes["code"]:
        symbol = f"{code}.T"
        rows = process_stock(symbol)
        all_rows.extend(rows)

    df_output = pd.DataFrame(all_rows)
    df_output.to_csv("output_financial_dividend_merged.csv", index=False, encoding="utf-8-sig")

    print("\nCSV saved: output_financial_dividend_merged.csv")
