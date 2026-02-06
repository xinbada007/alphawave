#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用AllTick API进行股票分析的主程序
"""

import argparse
import os
import sys
import asyncio
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from alphaflow.engine.pipeline import ResearchPipeline
from alphaflow.core.context import GlobalContext
from alphaflow.core.schema import AnalysisContext
from alphaflow.components.collectors.alltick_collector import AllTickCollector
from alphaflow.components.processors.technicals import RSIProcessor
from alphaflow.utils.quickchart import QuickChartClient


def get_user_config(user_id: str) -> Dict[str, Any]:
    """获取用户配置，优先使用加密配置"""
    try:
        # 尝试使用加密配置管理器
        from user_configs.secure_config_manager import SecureConfigManager
        password = os.environ.get('CONFIG_PASSWORD', 'default_secure_password_for_demo')
        config_manager = SecureConfigManager(password=password)
        config = config_manager.load_user_config(user_id)
        return config
    except ImportError:
        # 如果没有加密模块，尝试使用普通JSON文件
        import json
        config_path = os.path.join("user_configs", f"{user_id}.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            raise FileNotFoundError(f"找不到用户 {user_id} 的配置文件")


def setup_user_apis(user_id: str):
    """根据用户配置设置API密钥"""
    try:
        user_config = get_user_config(user_id)
        api_keys = user_config.get("api_keys", {})
        settings = user_config.get("settings", {})
        
        # 设置API密钥（通过环境变量或OpenBB设置）
        for key_type, key_value in api_keys.items():
            if key_value:  # 只设置非空的密钥
                env_var_name = f"{key_type.upper()}_API_KEY"
                os.environ[env_var_name] = key_value
                print(f"🔧 设置 {key_type} API 密钥")
        
        print("📋 当前配置:")
        print(f"  - 默认提供商: {settings.get('default_provider', 'polygon')}")
        print(f"  - 缓存启用: {settings.get('cache_enabled', True)}")
        
        return settings
        
    except Exception as e:
        print(f"⚠️  加载用户配置失败: {e}")
        print("💡 提示: 请使用 configure_user.py 脚本设置您的API密钥")
        return {}


async def run_alltick_pipeline(symbols, user_id):
    """运行AllTick分析管道"""
    print(f"[*] 开始为用户 {user_id} 运行AllTick分析...")
    
    # 加载用户配置
    user_settings = setup_user_apis(user_id)
    
    # 创建全局上下文
    global_ctx = GlobalContext()
    
    # 创建分析上下文
    context = AnalysisContext(
        symbols=symbols,
        global_context=global_ctx
    )
    
    # 构建管道
    pipeline = ResearchPipeline(context=context)
    
    # 获取用户API密钥
    user_config = get_user_config(user_id)
    alltick_api_key = user_config['api_keys'].get('alltick')
    
    if not alltick_api_key:
        print("⚠️  未找到AllTick API密钥，请先配置")
        return None
    
    # 添加AllTick数据收集器
    collector_config = {
        'api_key': alltick_api_key,
        'base_url': 'https://api.alltickdata.com'
    }
    collector = AllTickCollector(name="AllTickDataCollector", config=collector_config)
    pipeline.add_step(collector)
    
    # 添加技术指标计算器
    rsi_processor = RSIProcessor(name="TechAnalysis")
    pipeline.add_step(rsi_processor)
    
    # 运行管道
    results = await pipeline.run()
    
    return results


def main():
    parser = argparse.ArgumentParser(description='AlphaWave - 使用AllTick API进行金融数据分析')
    parser.add_argument('--symbols', nargs='+', required=True, 
                       help='股票代码列表，例如: NVDA AAPL TSLA')
    parser.add_argument('--user-id', required=True, 
                       help='用户ID，用于加载对应的API密钥配置')
    
    args = parser.parse_args()
    
    print(f"[*] 开始为用户 {args.user_id} 分析股票: {', '.join(args.symbols)}")
    
    # 运行异步管道
    results = asyncio.run(run_alltick_pipeline(args.symbols, args.user_id))
    
    if results:
        print("\n--- AllTick分析结果 ---")
        for i, result in enumerate(results):
            if hasattr(result, 'payload'):
                pack = result.payload
                print(f"\n📊 股票 {i+1}: {pack.symbol}")
                
                # 显示市场数据
                if pack.market_data:
                    df = pack.market_data.to_df()
                    print(f"   市场数据: {df.shape[0]} 条记录")
                    if not df.empty and 'close' in df.columns:
                        latest_close = df['close'].iloc[-1] if len(df) > 0 else 'N/A'
                        print(f"   最新价格: {latest_close}")
                
                # 显示基本面数据
                if pack.fundamentals:
                    company_name = pack.fundamentals.get('company_name', 'N/A')
                    sector = pack.fundamentals.get('sector', 'N/A')
                    print(f"   公司: {company_name} ({sector})")
                
                # 显示新闻
                if pack.news:
                    print(f"   新闻条数: {len(pack.news)}")
                
                # 显示技术指标
                if pack.technicals:
                    tech_df = pack.technicals.to_df()
                    if not tech_df.empty and 'rsi' in tech_df.columns:
                        rsi = tech_df['rsi'].iloc[-1] if len(tech_df) > 0 else 'N/A'
                        print(f"   RSI指标: {rsi}")
            
            if hasattr(result, 'success') and not result.success:
                print(f"   ❌ 步骤失败: {result.error}")


if __name__ == "__main__":
    main()