#!/usr/bin/env python3
"""
直接测试API密钥是否有效
"""

import os
import time

def test_api_directly():
    """
    直接使用API密钥测试
    """
    print("🔧 Testing API Keys Directly")
    print("="*50)
    
    # 使用环境变量设置API密钥
    os.environ["OPENBB_POLYGON_API_KEY"] = "zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd"
    os.environ["OPENBB_FMP_API_KEY"] = "5u27af6jTiLZov0Kmqz2LZ9leNlKzguO"
    os.environ["OPENBB_AV_API_KEY"] = "AED72KC95E69FL8Q"
    
    print("Testing with Massive API (formerly Polygon)...")
    
    # 测试Massive API (原Polygon) 直接调用
    import requests
    
    # 测试Massive API
    massive_api_key = "zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd"
    massive_url = f"https://api.massive.com/v2/quotes/extended?ticker=AAPL&apiKey={massive_api_key}"
    
    try:
        response = requests.get(massive_url)
        print(f"Massive API response: {response.status_code}")
        if response.status_code == 200:
            print("✅ Massive API is accessible")
        elif response.status_code == 401 or response.status_code == 403:
            print("❌ Massive API authentication failed")
        else:
            print(f"⚠️ Massive API returned status: {response.status_code}")
    except Exception as e:
        print(f"❌ Massive API request failed: {e}")
    
    # 测试Alpha Vantage API
    print("\nTesting Alpha Vantage API...")
    av_api_key = "AED72KC95E69FL8Q"
    av_url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey={av_api_key}"
    
    try:
        response = requests.get(av_url)
        print(f"Alpha Vantage response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if 'Global Quote' in data:
                print("✅ Alpha Vantage API is accessible")
                if data['Global Quote']:
                    print(f"   Sample data: {data['Global Quote']}")
            else:
                print("⚠️ Alpha Vantage returned unexpected format")
        else:
            print(f"⚠️ Alpha Vantage returned status: {response.status_code}")
    except Exception as e:
        print(f"❌ Alpha Vantage request failed: {e}")
    
    # 测试FMP API
    print("\nTesting FMP API...")
    fmp_api_key = "5u27af6jTiLZov0Kmqz2LZ9leNlKzguO"
    fmp_url = f"https://financialmodelingprep.com/api/v3/quote/AAPL?apikey={fmp_api_key}"
    
    try:
        response = requests.get(fmp_url)
        print(f"FMP response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                print("✅ FMP API is accessible")
                print(f"   Sample data: {data[0]}")
            else:
                print("⚠️ FMP returned unexpected format")
        elif response.status_code == 403:
            print("❌ FMP API requires paid plan (legacy endpoint issue)")
        else:
            print(f"⚠️ FMP returned status: {response.status_code}")
    except Exception as e:
        print(f"❌ FMP request failed: {e}")
    
    print("\n💡 Key findings:")
    print("- If Massive/Polygon API is accessible, upgrade your plan for international data")
    print("- If Alpha Vantage works, consider using OTC symbols like 'NVDCY' for NVDA")
    print("- If FMP returns 403, you need a paid plan for current endpoints")
    print("- Rate limiting occurs at the yfinance level, not necessarily your API keys")

def suggest_alternative_approach():
    """
    提供替代方案
    """
    print("\n🔄 Suggested Alternative Approaches:")
    print("1. Use OTC symbols: NVDA -> NVDCY, TSLA -> TSLA, etc.")
    print("2. Use proxy server to bypass geo-restrictions")
    print("3. Add delays between requests to avoid rate limits")
    print("4. Use cached data instead of live fetch")
    print("5. Consider running from different IP location")

if __name__ == "__main__":
    test_api_directly()
    suggest_alternative_approach()