import akshare as ak
import pandas as pd

symbol = "00700"
print(f"--- Probing capital structure for {symbol} ---")

# 1. 检查实时行情是否有流通字段
try:
    spot = ak.stock_hk_spot_em()
    row = spot[spot['代码'] == symbol]
    if not row.empty:
        print("\n[Spot Interface Data]")
        print(row.to_dict(orient='records')[0])
except: pass

# 2. 检查详细指标接口
try:
    m_df = ak.stock_hk_financial_indicator_em(symbol=symbol)
    if not m_df.empty:
        print("\n[Financial Indicator Interface Data]")
        print(m_df.iloc[0].to_dict())
except: pass
