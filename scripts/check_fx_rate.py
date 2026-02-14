import akshare as ak
import pandas as pd

def inspect_fx():
    df = ak.fx_spot_quote()
    print("Columns:", df.columns.tolist())
    print(df.head(10))

if __name__ == "__main__":
    inspect_fx()
