import yfinance as yf

# https://note.com/huge_slug5265/n/nc3c650f81ada
# https://qiita.com/aguilarklyno/items/51622f9efc33aac88bbf
# https://investment.life-tousika.com/2026/02/15/how-to-yfinance/

ticker =yf.Ticker("7203.T")
data = ticker.history(period="5y", interval="3mo")


income = ticker.financials
bs = ticker.balance_sheet
cf = ticker.cashflow
div = ticker.dividends
print(income)
print(bs)
print(cf)
print(div)

print(bs.index)
print(cf.index)