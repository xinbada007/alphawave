import akshare as ak
import pandas as pd

def deep_verify():
    symbol = "03690"
    
    # 1. Inspect Balance Sheet properly
    print("\n--- Balance Sheet Sample ---")
    df_bs = ak.stock_financial_hk_report_em(stock=symbol, symbol="资产负债表", indicator="报告期")
    if not df_bs.empty:
        # Show unique items and dates
        latest_date = df_bs['REPORT_DATE'].max()
        print("Latest Date found:", latest_date)
        subset = df_bs[df_bs['REPORT_DATE'] == latest_date]
        # Look for Total Assets (likely '资产总额' or similar)
        assets = subset[subset['STD_ITEM_NAME'].str.contains('资产', na=False)]
        print(assets[['STD_ITEM_NAME', 'AMOUNT']].head(5))

    # 2. Inspect Cash Flow properly
    print("\n--- Cash Flow Sample ---")
    df_cf = ak.stock_financial_hk_report_em(stock=symbol, symbol="现金流量表", indicator="报告期")
    if not df_cf.empty:
        latest_date = df_cf['REPORT_DATE'].max()
        print("Latest Date found:", latest_date)
        subset = df_cf[df_cf['REPORT_DATE'] == latest_date]
        cash = subset[subset['STD_ITEM_NAME'].str.contains('现金', na=False)]
        print(cash[['STD_ITEM_NAME', 'AMOUNT']].head(5))

if __name__ == "__main__":
    deep_verify()
