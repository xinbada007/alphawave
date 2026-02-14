import akshare as ak
import pandas as pd

symbol = "00700"
print(f"--- Deep Probing AkShare HK Reports for {symbol} ---")

indicators = ["利润表", "资产负债表", "现金流量表"]
for ind in indicators:
    print(f"\n[Testing Indicator: {ind}]")
    try:
        df = ak.stock_financial_hk_report_em(stock=symbol, indicator=ind)
        print(f"Success! Shape: {df.shape}")
        if not df.empty:
            print(f"Index (Rows): {df.index.tolist()[:5]}")
            print(f"Columns: {df.columns.tolist()[:10]}...")
            # 展示第一行前五个数据
            print(f"Sample Data:\n{df.iloc[:2, :5]}")
    except Exception as e:
        print(f"Failed: {e}")

print("\n[Testing Profile: stock_hk_company_profile_em]")
try:
    df_profile = ak.stock_hk_company_profile_em(symbol=symbol)
    print(f"Success! Columns: {df_profile.columns.tolist()}")
except Exception as e:
    print(f"Failed: {e}")

