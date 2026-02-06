#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AlphaWave主程序 - 支持安全用户配置
"""

import argparse
import os
import sys
import asyncio
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 根据实际的模块结构调整导入
from alphaflow.engine.pipeline import ResearchPipeline
from alphaflow.core.context import GlobalContext
from alphaflow.core.schema import AnalysisContext
from alphaflow.components.collectors.openbb_collector_updated import OpenBBCollector
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


async def run_pipeline_async(args, user_settings):
    """异步运行管道"""
    # 创建全局上下文
    global_ctx = GlobalContext()
    
    # 设置提供商（优先使用命令行参数，然后是用户设置，最后是默认值）
    provider = args.provider or user_settings.get('default_provider', 'polygon')
    
    # 创建分析上下文
    context = AnalysisContext(
        symbols=args.symbols,
        global_context=global_ctx
    )
    
    # 构建管道
    pipeline = ResearchPipeline(context=context)
    
    # 添加数据收集器
    collector_config = {
        'provider': provider
    }
    collector = OpenBBCollector(name="DataFetcher", config=collector_config)
    pipeline.add_step(collector)
    
    # 添加技术指标计算器
    rsi_processor = RSIProcessor(name="TechAnalysis")
    pipeline.add_step(rsi_processor)
    
    # 运行管道
    results = await pipeline.run()
    
    return results


def main():
    parser = argparse.ArgumentParser(description='AlphaWave - 金融数据分析框架')
    parser.add_argument('--symbols', nargs='+', required=True, 
                       help='股票代码列表，例如: NVDA AAPL TSLA')
    parser.add_argument('--user-id', required=True, 
                       help='用户ID，用于加载对应的API密钥配置')
    parser.add_argument('--provider', default=None,
                       help='数据提供商 (polygon, fmp, yfinance等)')
    
    args = parser.parse_args()
    
    print(f"[*] 开始为用户 {args.user_id} 运行管道...")
    
    # 加载用户配置
    print("🔧 设置用户API密钥...")
    user_settings = setup_user_apis(args.user_id)
    
    # 运行异步管道
    results = asyncio.run(run_pipeline_async(args, user_settings))
    
    print("\n--- 最终研究包 ---")
    for result in results:
        print(result.__dict__)


if __name__ == "__main__":
    main()