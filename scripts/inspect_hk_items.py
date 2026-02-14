import akshare as ak
import pandas as pd

symbol = "00700"
print(f"--- Inspecting all unique items for {symbol} ---")
try:
    df = ak.stock_financial_hk_report_em(stock=symbol, indicator="利润表")
    if not df.empty:
        items = sorted(df['STD_ITEM_NAME'].unique().tolist())
        print(f"Total unique items: {len(items)}")
        print("\n[Income Related]")
        for i in items:
            if any(k in i for k in ["收益", "营业", "溢利", "利润", "盈利", "收入"]):
                print(f" - {i}")
        
        print("\n[Equity Related]")
        for i in items:
            if any(k in i for k in ["权益", "净资产", "股本"]):
                print(f" - {i}")
except Exception as e:
    print(f"Error: {e}")
