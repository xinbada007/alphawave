import asyncio
import pandas as pd
from alphaflow.components.collectors.market_data import MarketDataCollector
from alphaflow.core.schema import AnalysisContext, ResearchPack

async def test_market_data():
    # 1. 准备上下文
    context = AnalysisContext(
        symbols=["0700.HK", "AAPL"],
        metadata={"days": 10}
    )
    
    collector = MarketDataCollector(name="test_collector")
    
    # 2. 测试港股 (腾讯) - 验证 AkShare 深度字段
    print("\n>>> [1/2] Testing HK Stock (0700.HK) via AkShare (Expected: turnover_rate, amplitude, pct_change)...")
    pack_hk = ResearchPack(symbol="0700.HK")
    output_hk = await collector.fetch_data(context, input_data=pack_hk)
    
    if output_hk.success:
        df = output_hk.payload.market_data.to_df()
        print(f"Success! Columns Captured: {df.columns.tolist()}")
        print(f"Head:\n{df.head(2)}")
        
        # 强制断言：必须包含“榨干”后的关键字段
        required_hk_fields = ["turnover_rate", "amplitude", "pct_change", "amount"]
        missing = [f for f in required_hk_fields if f not in df.columns]
        if missing:
            print(f"FAILED: Missing extra HK fields: {missing}")
        else:
            print("PASSED: All extra HK fields captured!")
    else:
        print(f"Failed: {output_hk.message}")

    # 3. 测试美股 (AAPL) - 验证 OpenBB/YFinance 基础字段
    print("\n>>> [2/2] Testing US Stock (AAPL) via OpenBB (Expected: OHLCV + vwap + typical_price)...")
    pack_us = ResearchPack(symbol="AAPL")
    output_us = await collector.fetch_data(context, input_data=pack_us)
    
    if output_us.success:
        df = output_us.payload.market_data.to_df()
        print(f"Success! Columns Captured: {df.columns.tolist()}")
        print(f"Head:\n{df.head(2)}")
        
        # 强制断言：必须包含基础字段
        required_us_fields = ["open", "high", "low", "close", "volume"]
        missing = [f for f in required_us_fields if f not in df.columns]
        if missing:
             print(f"FAILED: Missing core US fields: {missing}")
        else:
             print("PASSED: Core US fields captured!")
    else:
        print(f"Failed: {output_us.message}")

if __name__ == "__main__":
    asyncio.run(test_market_data())
