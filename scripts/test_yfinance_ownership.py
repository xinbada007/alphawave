import asyncio
from openbb import obb
import pandas as pd

try:
    import pytest
    pytestmark = pytest.mark.skip(reason="manual network smoke script; run directly when needed")
except ImportError:
    pytestmark = []

async def test_hk_ownership():
    symbol = "3690.HK"
    print("\n>>> Fetching yfinance Share Stats for " + symbol)
    try:
        obb_any: any = obb
        res = await asyncio.to_thread(
            obb_any.equity.ownership.share_statistics,
            symbol=symbol,
            provider="yfinance"
        )
        if res and res.results:
            df = pd.DataFrame([it.dict() for it in res.results])
            print("✅ Success!")
            print(df.to_string(index=False))
        else:
            print("⚠️ No data.")
    except Exception as e:
        print("❌ Error:", e)

if __name__ == "__main__":
    asyncio.run(test_hk_ownership())
