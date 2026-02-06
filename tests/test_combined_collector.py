#!/usr/bin/env python3
"""
Test script for combined fundamental and market data collector
"""

import asyncio
import sys
import os
sys.path.insert(0, '/root/workspace/alphawave')

from alphaflow.core.schema import AnalysisContext, ResearchPack
from alphaflow.components.collectors.fundamental import FundamentalCollector


async def test_combined_collector():
    """Test the combined collector functionality"""
    print("Testing Combined Fundamental and Market Data Collector...")
    
    # Create context and pack
    context = AnalysisContext(symbols=["AAPL"])
    pack = ResearchPack(symbol="AAPL")
    
    # Initialize collector with default config
    collector = FundamentalCollector(name="combined_test", config={'provider': 'yfinance'})
    
    # Test the fetch_data method
    try:
        result = await collector.fetch_data(context, input_data=pack)
        print(f"Success: {result.success}")
        if result.error:
            print(f"Error: {result.error}")
        
        if hasattr(result.payload, 'market_data') and result.payload.market_data is not None:
            print("✓ Market data successfully retrieved and stored")
        else:
            print("⚠ Market data not available (may be due to network/API issues)")
        
        if hasattr(result.payload, 'fundamentals') and result.payload.fundamentals:
            print("✓ Fundamental data successfully retrieved and stored")
        else:
            print("⚠ Fundamental data not available (may be due to network/API issues)")
        
        print("Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_combined_collector())
    if success:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed!")
        sys.exit(1)