import asyncio
import os
from openbb import obb
import pandas as pd

async def test_hk_estimates():
    # 尝试去掉前导 0 的格式
    symbol = "3690.HK"
    print("\n>>> Trying symbol: " + symbol + " via yfinance...")
    
    try:
        obb_any: any = obb
        res = await asyncio.to_thread(
            obb_any.equity.estimates.consensus,
            symbol=symbol,
            provider="yfinance"
        )
        
        if res and res.results:
            data = [it.dict() for it in res.results]
            df = pd.DataFrame(data)
            print("✅ Success for " + symbol + "!")
            print(df.to_string(index=False))
        else:
            print("⚠️ Still no data for " + symbol + ".")
            
    except Exception as e:
        print("❌ Error:", e)

if __name__ == "__main__":
    asyncio.run(test_hk_estimates())
