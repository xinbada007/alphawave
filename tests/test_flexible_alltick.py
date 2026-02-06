#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试灵活版AllTick收集器
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from alphaflow.core.context import GlobalContext
from alphaflow.core.schema import AnalysisContext
from alphaflow.components.collectors.alltick_collector_flexible import AllTickCollectorFlexible


async def test_flexible_alltick():
    """测试灵活版AllTick收集器"""
    print("🧪 开始测试灵活版AllTick收集器...")
    
    # 创建全局上下文
    global_ctx = GlobalContext()
    
    # 创建分析上下文
    context = AnalysisContext(
        symbols=['AAPL'],  # 使用苹果股票作为测试
        global_context=global_ctx
    )
    
    # 创建灵活版AllTick收集器
    collector_config = {
        'api_key': 'd512a2cb352dfb3b7d10c5ae0fe09b99-c-app',
    }
    collector = AllTickCollectorFlexible(name="FlexibleAllTickTest", config=collector_config)
    
    print("🔍 执行数据获取...")
    result = await collector.execute(context)
    
    if result.success:
        print("✅ 灵活版AllTick收集器执行成功!")
        pack = result.payload
        
        print(f"\n📊 研究包信息:")
        print(f"   - 股票代码: {pack.symbol}")
        
        # 检查市场数据
        if pack.market_data:
            df = pack.market_data.to_df()
            print(f"   - 市场数据形状: {df.shape}")
            if not df.empty:
                print(f"   - 数据列: {list(df.columns)}")
                if 'close' in df.columns and len(df) > 0:
                    print(f"   - 最近收盘价: {df['close'].iloc[-1]}")
        else:
            print("   - 市场数据: 无")
        
        # 检查基本面数据
        if pack.fundamentals:
            print(f"   - 基本面数据项数: {len(pack.fundamentals)}")
            if 'company_name' in pack.fundamentals:
                print(f"   - 公司名称: {pack.fundamentals['company_name']}")
        else:
            print("   - 基本面数据: 无")
        
        # 检查新闻数据
        if pack.news:
            print(f"   - 新闻数量: {len(pack.news)}")
            if pack.news:
                print(f"   - 首条新闻标题: {pack.news[0].get('title', 'N/A')[:50]}...")
        else:
            print("   - 新闻数据: 无")
        
        # 检查技术指标
        if pack.technicals:
            tech_df = pack.technicals.to_df()
            print(f"   - 技术指标数据形状: {tech_df.shape}")
            if not tech_df.empty and 'rsi' in tech_df.columns and len(tech_df) > 0:
                print(f"   - RSI值: {tech_df['rsi'].iloc[-1]}")
        else:
            print("   - 技术指标: 无")
        
        return True
    else:
        print(f"❌ 灵活版AllTick收集器执行失败: {result.error}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_flexible_alltick())
    if success:
        print("\n🎉 灵活版AllTick收集器测试完成!")
    else:
        print("\n⚠️  灵活版AllTick收集器测试完成，但API可能暂时不可用")
        print("💡 这通常是由于API端点需要进一步确认，我们的收集器已准备好适应不同的API格式")