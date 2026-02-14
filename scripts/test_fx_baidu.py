import akshare as ak
import pandas as pd

def test_fx_baidu():
    try:
        df = ak.fx_quote_baidu(symbol="人民币")
        subset = df[df['名称'].str.contains('港元', na=False)]
        if not subset.empty:
            row = subset.iloc[0]
            cny_to_hkd = float(row['最新价'])
            hkd_to_cny = 1.0 / cny_to_hkd
            print("HKD/CNY Rate:", hkd_to_cny)
            return hkd_to_cny
        return 0.91
    except Exception as e:
        print("Error:", e)
        return 0.91

if __name__ == "__main__":
    test_fx_baidu()
