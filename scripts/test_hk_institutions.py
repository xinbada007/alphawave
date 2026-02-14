import akshare as ak
import pandas as pd

def test_hk_institutions():
    symbol = "03690" 
    print("\n>>> Testing HK Major Shareholders for " + symbol)
    try:
        # 使用财务报表接口的“主要股东”子模块
        df = ak.stock_financial_hk_report_em(stock=symbol, symbol="主要股东", indicator="报告期")
        if not df.empty:
            print("✅ Success! Major Shareholders:")
            # 筛选最近一个日期的股东
            latest_date = df['REPORT_DATE'].max()
            print("Latest Date:", latest_date)
            print(df[df['REPORT_DATE'] == latest_date].head(10).to_string(index=False))
        else:
            print("No major shareholder data found.")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_hk_institutions()
