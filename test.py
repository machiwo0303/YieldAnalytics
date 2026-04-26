import yfinance as yf

# https://note.com/huge_slug5265/n/nc3c650f81ada
# https://qiita.com/aguilarklyno/items/51622f9efc33aac88bbf
# https://investment.life-tousika.com/2026/02/15/how-to-yfinance/

stock =yf.Ticker("7203.T")
data = stock.history(period="5y", interval="3mo")

print(stock.income_stmt)
print(stock.cashflow)
print(stock.dividends)
print(data.head())