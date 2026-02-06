#!/usr/bin/env python3
"""
测试使用我们拥有的API密钥配置OpenBB
"""

from openbb import obb
import os

def test_api_configuration():
    print("🔧 Testing API Configuration for AlphaWave")
    print("="*50)
    
    # 设置我们拥有的API密钥
    os.environ["OPENBB_POLYGON_API_KEY"] = "zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd"
    os.environ["OPENBB_FMP_API_KEY"] = "5u27af6jTiLZov0Kmqz2LZ9leNlKzguO"
    os.environ["OPENBB_AV_API_KEY"] = "AED72KC95E69FL8Q"
    
    # 尝试配置OpenBB
    try:
        # 尝试使用Polygon API (现在称为Massive API)
        print("Attempting to set Polygon/Massive API key...")
        obb.config.credentials.polygon_api_key = "zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd"
        print("✅ Polygon API key set")
    except Exception as e:
        print(f"❌ Failed to set Polygon API key: {e}")
    
    try:
        # 尝试使用FMP API
        print("Attempting to set FMP API key...")
        obb.config.credentials.fmp_api_key = "5u27af6jTiLZov0Kmqz2LZ9leNlKzguO"
        print("✅ FMP API key set")
    except Exception as e:
        print(f"❌ Failed to set FMP API key: {e}")
    
    try:
        # 尝试使用Alpha Vantage API
        print("Attempting to set Alpha Vantage API key...")
        obb.config.credentials.av_api_key = "AED72KC95E69FL8Q"
        print("✅ Alpha Vantage API key set")
    except Exception as e:
        print(f"❌ Failed to set Alpha Vantage API key: {e}")
    
    print("\n📋 Testing data fetch with different providers...")
    
    # 测试使用不同提供商获取数据
    providers_to_test = ['polygon', 'fmp', 'yfinance', 'av']
    
    for provider in providers_to_test:
        try:
            print(f"\nTesting {provider.upper()} provider...")
            # 尝试获取简单的股票数据
            data = obb.equity.price.historical("NVDA", provider=provider)
            if data and not data.to_dataframe().empty:
                print(f"✅ {provider.upper()} provider working!")
                df = data.to_dataframe()
                print(f"   Retrieved {len(df)} records")
                print(f"   Latest price: {df['close'].iloc[-1] if len(df) > 0 else 'N/A'}")
                return provider  # 返回第一个工作的提供商
            else:
                print(f"⚠️ {provider.upper()} provider returned no data")
        except Exception as e:
            print(f"❌ {provider.upper()} provider failed: {e}")
    
    print("\n⚠️ All providers failed - likely due to API plan limitations")
    print("💡 For Polygon/Massive: Free tier may not support all international/advanced data")
    print("💡 For FMP: Legacy endpoints may require paid plan")
    print("💡 For Alpha Vantage: May have specific symbol restrictions")
    
    return None

def run_simple_test():
    """
    尝试运行一个简单的测试，绕过复杂的管道
    """
    print("\n🔧 Attempting simplified test...")
    
    try:
        # 尝试使用我们已知可用的接口
        from openbb import obb
        
        # 使用Alpha Vantage获取数据 (这是我们之前验证过的)
        print("Trying Alpha Vantage with known working symbol...")
        data = obb.equity.price.historical(
            symbol="XIACF",  # 小米集团OTC代码 (我们之前验证过这个工作)
            provider="av"
        )
        
        if data:
            df = data.to_dataframe()
            if not df.empty:
                print(f"✅ Successfully retrieved data: {len(df)} records")
                print(f"   Latest close: {df['close'].iloc[-1]}")
                return True
            else:
                print("⚠️ Alpha Vantage returned empty dataframe")
        else:
            print("⚠️ Alpha Vantage returned no data")
    except Exception as e:
        print(f"❌ Simplified test failed: {e}")
    
    return False

if __name__ == "__main__":
    print("AlphaWave API Configuration Test")
    print("="*60)
    
    working_provider = test_api_configuration()
    simple_success = run_simple_test()
    
    print(f"\n🏁 Test Summary:")
    print(f"- Working provider: {working_provider or 'None found'}")
    print(f"- Simple test: {'Success' if simple_success else 'Failed'}")
    
    if working_provider:
        print(f"\n💡 Recommendation: Use --provider {working_provider} flag with main.py")
    else:
        print("\n⚠️  Issue: API plan limitations preventing access to required data")
        print("💡 Solutions:")
        print("   1. Upgrade API plans for full access")
        print("   2. Use available symbols that work with free tiers")
        print("   3. Configure proxy server for rate limit circumvention")
        print("   4. Implement retry logic with delays")