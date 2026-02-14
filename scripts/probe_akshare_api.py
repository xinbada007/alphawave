import akshare as ak
import pandas as pd

print("--- AkShare API Discovery ---")
all_funcs = dir(ak)
hk_financial_funcs = [f for f in all_funcs if "hk" in f and "financial" in f]
print(f"Found HK Financial APIs: {hk_financial_funcs}")

symbol = "00700"
for func_name in ["stock_financial_hk_report_em", "stock_hk_financial_indicator_em"]:
    if func_name in all_funcs:
        print(f"\nTesting {func_name} for {symbol}...")
        try:
            func = getattr(ak, func_name)
            # Some APIs might need different params, but let's try the common ones
            res = func(symbol=symbol)
            print(f"Success! Result Type: {type(res)}")
            if isinstance(res, pd.DataFrame):
                print(f"Columns: {res.columns.tolist()[:10]}...")
                print(f"Shape: {res.shape}")
            elif isinstance(res, dict):
                print(f"Dict Keys: {res.keys()}")
        except Exception as e:
            print(f"Failed: {e}")

