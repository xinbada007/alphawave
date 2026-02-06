#!/usr/bin/env python3
"""
设置OpenBB平台的API密钥配置
"""

import os
from openbb import obb
from alphaflow.utils.user_config import config_manager


def setup_api_keys(user_id: str = None):
    """
    设置各种API密钥以避免速率限制
    如果提供了user_id，则从该用户的配置加载API密钥
    """
    print("🔧 Setting up OpenBB API keys...")
    
    # 如果提供了用户ID，从用户配置中加载API密钥
    if user_id:
        user_config = config_manager.load_user_config(user_id)
        polygon_api_key = user_config.get("polygon_api_key", "")
        fmp_api_key = user_config.get("fmp_api_key", "")
        tiingo_api_key = user_config.get("tiingo_api_key", "")
        alphavantage_api_key = user_config.get("alphavantage_api_key", "")
        
        print(f"🔧 Loading API keys for user: {user_id}")
    else:
        # 从环境变量或默认值获取API密钥
        polygon_api_key = os.getenv("POLYGON_API_KEY", "YOUR_POLYGON_API_KEY_HERE")
        fmp_api_key = os.getenv("FMP_API_KEY", "YOUR_FMP_API_KEY_HERE")
        tiingo_api_key = os.getenv("TIINGO_API_KEY", "YOUR_TIINGO_API_KEY_HERE")
        alphavantage_api_key = os.getenv("ALPHAVANTAGE_API_KEY", "YOUR_ALPHAVANTAGE_API_KEY_HERE")
    
    # 配置API密钥
    try:
        if polygon_api_key and polygon_api_key != "YOUR_POLYGON_API_KEY_HERE" and polygon_api_key != "":
            obb.config.credentials.polygon_api_key = polygon_api_key
            print("✅ Polygon API key configured")
        else:
            print("⚠️ Polygon API key not provided, using free tier")
            
        if fmp_api_key and fmp_api_key != "YOUR_FMP_API_KEY_HERE" and fmp_api_key != "":
            obb.config.credentials.fmp_api_key = fmp_api_key
            print("✅ FMP API key configured")
        else:
            print("⚠️ FMP API key not provided, using free tier")
            
        if tiingo_api_key and tiingo_api_key != "YOUR_TIINGO_API_KEY_HERE" and tiingo_api_key != "":
            obb.config.credentials.tiingo_api_key = tiingo_api_key
            print("✅ Tiingo API key configured")
        else:
            print("⚠️ Tiingo API key not provided, using free tier")
            
        if alphavantage_api_key and alphavantage_api_key != "YOUR_ALPHAVANTAGE_API_KEY_HERE" and alphavantage_api_key != "":
            obb.config.credentials.av_api_key = alphavantage_api_key
            print("✅ Alpha Vantage API key configured")
        else:
            print("⚠️ Alpha Vantage API key not provided, using free tier")
            
    except AttributeError as e:
        print(f"⚠️ Could not set API key: {e}")
    
    # 保存配置
    try:
        obb.save_config()
        print("✅ Configuration saved")
    except Exception as e:
        print(f"⚠️ Could not save config: {e}")
    
    # 显示当前配置状态
    print("\n📋 Current Configuration:")
    try:
        print(f"  - Polygon: {'SET' if obb.config.credentials.polygon_api_key else 'NOT SET'}")
        print(f"  - FMP: {'SET' if obb.config.credentials.fmp_api_key else 'NOT SET'}")
        print(f"  - Tiingo: {'SET' if obb.config.credentials.tiingo_api_key else 'NOT SET'}")
        print(f"  - Alpha Vantage: {'SET' if obb.config.credentials.av_api_key else 'NOT SET'}")
    except:
        print("  - Unable to read current configuration")
    
    print("\n💡 Pro tip: Set your API keys as environment variables before running the main script:")
    print("   export POLYGON_API_KEY=your_actual_key_here")
    print("   export FMP_API_KEY=your_actual_key_here")
    print("   python main.py --symbols NVDA")
    
    if user_id:
        print(f"💡 Or set API keys for user '{user_id}' using the configuration utility")


if __name__ == "__main__":
    setup_api_keys()