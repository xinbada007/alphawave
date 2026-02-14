import akshare as ak
import pandas as pd

symbol = "00700"
print(f"--- Deep Inspecting Analysis Indicators for {symbol} ---")
try:
    # 尝试使用 symbol 参数
    df = ak.stock_financial_hk_analysis_indicator_em(symbol=symbol)
    if not df.empty:
        print(f"Success! Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
except Exception as e:
    print(f"Error: {e}")
