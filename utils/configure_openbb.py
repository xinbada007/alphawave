#!/usr/bin/env python3
"""
正确配置OpenBB API密钥
"""

import os
from openbb import obb

def configure_openbb_credentials():
    """
    使用正确的方法配置OpenBB API密钥
    """
    print("🔧 Configuring OpenBB API Credentials")
    print("="*50)
    
    # 设置环境变量（这是OpenBB推荐的方法）
    os.environ["OPENBB_POLYGON_API_KEY"] = "zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd"
    os.environ["OPENBB_FMP_API_KEY"] = "5u27af6jTiLZov0Kmqz2LZ9leNlKzguO"
    os.environ["OPENBB_AV_API_KEY"] = "AED72KC95E69FL8Q"
    
    print("✅ Environment variables set")
    
    # 通过obb.user更新凭证（使用正确的方法）
    try:
        # 获取当前用户配置
        current_user = obb.user.model_copy()
        
        # 更新API密钥
        current_user.credentials.polygon_api_key = "zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd"
        current_user.credentials.fmp_api_key = "5u27af6jTiLZov0Kmqz2LZ9leNlKzguO"
        current_user.credentials.av_api_key = "AED72KC95E69FL8Q"
        
        # 保存配置
        current_user.save()
        
        print("✅ OpenBB credentials configured successfully")
        
        # 验证配置
        print("\n📋 Verifying configuration...")
        print(f"Polygon API key: {'SET' if current_user.credentials.polygon_api_key else 'NOT SET'}")
        print(f"FMP API key: {'SET' if current_user.credentials.fmp_api_key else 'NOT SET'}")
        print(f"AV API key: {'SET' if current_user.credentials.av_api_key else 'NOT SET'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to configure credentials: {e}")
        print("💡 Alternative approach: Use environment variables directly")
        return False

def test_data_access():
    """
    测试数据访问
    """
    print("\n🔍 Testing data access...")
    
    # 测试不同的提供商
    providers = ['polygon', 'fmp', 'yfinance']
    test_symbol = 'AAPL'  # 使用通用符号进行测试
    
    for provider in providers:
        try:
            print(f"\nTesting {provider.upper()} provider...")
            data = obb.equity.price.historical(test_symbol, provider=provider)
            
            if data:
                df = data.to_dataframe()
                if not df.empty:
                    print(f"✅ {provider.upper()} provider: SUCCESS")
                    print(f"   Records retrieved: {len(df)}")
                    print(f"   Latest close: {df['close'].iloc[-1] if len(df) > 0 else 'N/A'}")
                    return provider
                else:
                    print(f"⚠️ {provider.upper()} provider: Empty dataset")
            else:
                print(f"⚠️ {provider.upper()} provider: No data returned")
                
        except Exception as e:
            print(f"❌ {provider.upper()} provider: {str(e)[:100]}...")
    
    return None

def run_alpha_wave_with_config():
    """
    运行alphawave主程序（配置后）
    """
    print("\n🚀 Running AlphaWave with configured credentials...")
    
    # 通过环境变量传递配置
    import subprocess
    import sys
    
    env = os.environ.copy()
    env["OPENBB_POLYGON_API_KEY"] = "zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd"
    env["OPENBB_FMP_API_KEY"] = "5u27af6jTiLZov0Kmqz2LZ9leNlKzguO"
    env["OPENBB_AV_API_KEY"] = "AED72KC95E69FL8Q"
    
    try:
        result = subprocess.run([
            sys.executable, "main.py", "--symbols", "AAPL"
        ], cwd="/root/workspace/alphawave", env=env, capture_output=True, text=True, timeout=60)
        
        print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        print("Return code:", result.returncode)
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("⚠️ Command timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ Error running AlphaWave: {e}")
        return False

if __name__ == "__main__":
    print("OpenBB API Configuration Tool")
    print("="*60)
    
    # 配置API密钥
    config_success = configure_openbb_credentials()
    
    if config_success:
        # 测试数据访问
        working_provider = test_data_access()
        
        if working_provider:
            print(f"\n🎉 Success! {working_provider.upper()} provider is working.")
            print("You should now be able to run AlphaWave with better data access.")
        else:
            print("\n⚠️ Warning: No providers are working with current API plan.")
            print("The issue may be related to API plan limitations for certain data types.")
    else:
        print("\n⚠️ Configuration failed, trying direct environment variable approach...")
        
        # 设置环境变量并尝试运行
        os.environ["OPENBB_POLYGON_API_KEY"] = "zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd"
        os.environ["OPENBB_FMP_API_KEY"] = "5u27af6jTiLZov0Kmqz2LZ9leNlKzguO"
        os.environ["OPENBB_AV_API_KEY"] = "AED72KC95E69FL8Q"
        
        print("Environment variables set. You can now run AlphaWave directly.")
    
    print(f"\n💡 To run AlphaWave: cd /root/workspace/alphawave && python main.py --symbols NVDA")