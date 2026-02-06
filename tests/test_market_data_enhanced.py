#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试增强版市场数据收集器
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')

from alphaflow.core.context import GlobalContext
from alphaflow.core.schema import AnalysisContext
from alphaflow.components.collectors.market_data import EquityPriceCollector
from alphaflow.components.collectors.fundamental import FundamentalCollector


async def test_enhanced_market_data():
    """测试增强版市场数据收集器"""
    print("🧪 开始测试增强版市场数据收集器...")
    
    # 创建全局上下文
    global_ctx = GlobalContext()
    
    # 创建分析上下文
    context = AnalysisContext(
        symbols=['AAPL'],  # 使用苹果股票作为测试
        global_context=global_ctx
    )
    
    # 创建增强版市场数据收集器
    collector_config = {
        'provider': 'yfinance'  # 使用yfinance作为数据提供商
    }
    collector = EquityPriceCollector(name="EnhancedMarketDataTest", config=collector_config)
    
    print("🔍 执行数据获取...")
    result = await collector.execute(context)
    
    if result.success:
        print("✅ 增强版市场数据收集器执行成功!")
        pack = result.payload
        
        print(f"\n📊 研究包信息:")
        print(f"   - 股票代码: {pack.symbol}")
        
        # 检查市场数据
        if pack.market_data:
            df = pack.market_data.to_df()
            print(f"   - 市场数据形状: {df.shape}")
            if not df.empty:
                print(f"   - 数据列: {list(df.columns)}")
                if 'close' in df.columns:
                    print(f"   - 最近收盘价: {df['close'].iloc[-1] if len(df) > 0 else 'N/A'}")
                if 'vwap' in df.columns:
                    print(f"   - VWAP值: {df['vwap'].iloc[-1] if len(df) > 0 else 'N/A'}")
        else:
            print("   - 市场数据: 无")
        
        return True
    else:
        print(f"❌ 增强版市场数据收集器执行失败: {result.error}")
        return False


async def test_fundamental_data():
    """测试基本面数据收集器"""
    print("\n🧪 开始测试基本面数据收集器...")
    
    # 创建全局上下文
    global_ctx = GlobalContext()
    
    # 创建分析上下文
    context = AnalysisContext(
        symbols=['AAPL'],  # 使用苹果股票作为测试
        global_context=global_ctx
    )
    
    # 创建基本面数据收集器
    collector = FundamentalCollector(name="FundamentalTest")
    
    print("🔍 执行基本面数据获取...")
    result = await collector.execute(context)
    
    if result.success:
        print("✅ 基本面数据收集器执行成功!")
        pack = result.payload
        
        print(f"\n📊 基本面数据信息:")
        print(f"   - 股票代码: {pack.symbol}")
        
        # 检查基本面数据
        if pack.fundamentals:
            print(f"   - 基本面数据项数: {len(pack.fundamentals)}")
            if 'balance_sheet' in pack.fundamentals:
                print(f"   - 包含资产负债表数据")
            if 'income_statement' in pack.fundamentals:
                print(f"   - 包含利润表数据")
            if 'cash_flow' in pack.fundamentals:
                print(f"   - 包含现金流量表数据")
            if 'marketCap' in pack.fundamentals:
                print(f"   - 市值: {pack.fundamentals['marketCap']}")
        else:
            print("   - 基本面数据: 无")
        
        return True
    else:
        print(f"❌ 基本面数据收集器执行失败: {result.error}")
        return False


async def run_all_tests():
    """运行所有测试"""
    market_success = await test_enhanced_market_data()
    fundamental_success = await test_fundamental_data()
    
    print(f"\n{'='*50}")
    print("测试汇总:")
    print(f"  市场数据收集器: {'✅ 通过' if market_success else '⚠️  部分通过'}")
    print(f"  基本面数据收集器: {'✅ 通过' if fundamental_success else '⚠️  部分通过'}")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())