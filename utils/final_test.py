#!/usr/bin/env python3
"""
最终测试：使用已配置的API密钥运行AlphaWave
"""

import os
from openbb import obb

def configure_api_keys():
    """配置API密钥"""
    print("🔧 Configuring API keys...")
    
    # 设置API密钥
    user_settings = obb.user
    user_settings.credentials.polygon_api_key = 'zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd'
    user_settings.credentials.fmp_api_key = '5u27af6jTiLZov0Kmqz2LZ9leNlKzguO'
    user_settings.credentials.av_api_key = 'AED72KC95E69FL8Q'
    
    print("✅ API keys configured successfully")
    
    # 验证是否可以获取数据
    print("🔍 Testing data access...")
    try:
        res = obb.equity.price.historical(symbol='NVDA', provider='polygon')
        df = res.to_df()
        print(f"✅ Success! Retrieved {len(df)} records for NVDA")
        print(f"Latest close price: {df['close'].iloc[-1]}")
        return True
    except Exception as e:
        print(f"❌ Data fetch failed: {e}")
        return False

def run_original_main():
    """运行原始的main.py"""
    import sys
    import asyncio
    
    # 临时修改sys.argv以模拟命令行参数
    original_argv = sys.argv
    sys.argv = ['final_test.py', '--symbols', 'NVDA']
    
    try:
        # 导入并运行main函数
        from main import main
        print("\\n🚀 Running AlphaWave with configured API keys...")
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Error running AlphaWave: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 恢复原始argv
        sys.argv = original_argv

if __name__ == "__main__":
    print("🎯 Final Test: AlphaWave with Proper API Configuration")
    print("="*60)
    
    success = configure_api_keys()
    
    if success:
        print("\\n✅ API configuration successful!")
        print("The core issue was that OpenBB needed to be configured with the API keys")
        print("in the runtime environment rather than just through environment variables.")
        print("\\n💡 Note: Alpha Vantage API key AED72KC95E69FL8Q works well for stock data")
        print("   Massive API key zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd enables Polygon/Massive access")
        print("   Both were necessary to overcome rate limiting issues")
        
        # 运行AlphaWave
        run_original_main()
    else:
        print("\\n❌ API configuration failed")
        
    print("\\n🏁 Test completed")