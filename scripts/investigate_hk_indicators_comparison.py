import akshare as ak
import pandas as pd

def compare_hk_indicators():
    symbol = "03690"
    print("\n>>> Deep Comparing HK Indicator Interfaces for Meituan (03690)")

    # 1. Historical Analysis
    print("\n--- [1] stock_financial_hk_analysis_indicator_em ---")
    try:
        df_hist = ak.stock_financial_hk_analysis_indicator_em(symbol=symbol, indicator="报告期")
        if not df_hist.empty:
            latest = df_hist.iloc[0]
            print("Date:", latest.get('REPORT_DATE'))
            print("Declared Currency:", latest.get('CURRENCY'))
            print("OPERATE_INCOME:", latest.get('OPERATE_INCOME'))
            print("BASIC_EPS:", latest.get('BASIC_EPS'))
    except Exception as e:
        print("Error hist:", e)

    # 2. Snapshot Indicators
    print("\n--- [2] stock_hk_financial_indicator_em ---")
    try:
        df_spot = ak.stock_hk_financial_indicator_em(symbol=symbol)
        if not df_spot.empty:
            latest = df_spot.iloc[0].to_dict()
            print("Key Fields with Units:")
            for k, v in latest.items():
                if any(x in str(k) for x in ["元", "币", "收益", "市值"]):
                    print(f"  {k}: {v}")
    except Exception as e:
        print("Error spot:", e)

if __name__ == "__main__":
    compare_hk_indicators()
