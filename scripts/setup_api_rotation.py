#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API轮询系统设置脚本
用于初始化和配置API轮询系统
"""

import sys
import os
import json
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')

from alphaflow.utils.api_rotator import api_rotator, add_api_key
from alphaflow.utils.multi_user_api_config import multi_user_config


def setup_api_rotation_system():
    """设置API轮询系统"""
    print("🚀 开始设置API轮询系统...")
    
    # 1. 初始化默认API密钥（如果存在）
    print("\n📋 检查并加载默认API密钥...")
    
    # 尝试从用户配置中加载现有密钥
    try:
        from user_configs.secure_config_manager import SecureConfigManager
        import os
        password = os.environ.get('CONFIG_PASSWORD', 'default_secure_password_for_demo')
        config_manager = SecureConfigManager(password=password)
        
        # 加载yellow用户的配置
        try:
            user_config = config_manager.load_user_config('yellow')
            api_keys = user_config.get('api_keys', {})
            
            for provider, key in api_keys.items():
                if key and key.strip():
                    add_api_key(provider, key, 'yellow_user')
                    print(f"  ✅ 添加 {provider} API密钥")
                    
        except Exception as e:
            print(f"  ⚠️  加载yellow用户配置失败: {e}")
            
    except ImportError as e:
        print(f"  ⚠️  未能加载用户配置管理器: {e}")
    
    # 2. 显示当前配置状态
    print("\n📊 当前API轮询系统状态:")
    stats = api_rotator.get_stats()
    
    if not stats:
        print("  未检测到任何API密钥")
    else:
        for provider, keys in stats.items():
            print(f"  {provider}: {len(keys)} 个密钥")
            for key_info in keys:
                print(f"    - {key_info['key_preview']} (所有者: {key_info['owner']}, 使用次数: {key_info['usage_count']})")
    
    # 3. 提供添加新密钥的选项
    print("\n💡 提示:")
    print("  - 运行 'python scripts/add_user_api_keys.py' 来添加新用户的API密钥")
    print("  - 查看 'API_KEY_COLLECTION_FORM.md' 了解需要哪些API密钥")
    print("  - 查看 'docs/API_ROTATION_GUIDE.md' 了解更多使用信息")
    
    print("\n✅ API轮询系统设置完成！")


def add_sample_keys():
    """添加示例密钥（仅用于演示）"""
    print("📝 添加示例API密钥...")
    
    sample_keys = {
        "alpha_vantage": "AED72KC95E69FL8Q",  # 来自MEMORY.md
        "polygon": "zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd",  # Massive API
        "fmp": "5u27af6jTiLZov0Kmqz2LZ9leNlKzguO",  # FMP API
        "alltick": "d512a2cb352dfb3b7d10c5ae0fe09b99-c-app"  # AllTick API
    }
    
    for provider, key in sample_keys.items():
        if key and key.strip():
            add_api_key(provider, key, 'project_default')
            print(f"  ✅ 添加 {provider} 示例密钥")


def show_api_rotation_info():
    """显示API轮询系统信息"""
    print("\n🔄 API轮询系统信息:")
    print("  功能:")
    print("    - 自动在多个API密钥之间轮询")
    print("    - 避免单一密钥的频率限制") 
    print("    - 支持多用户协作")
    print("    - 智能错误恢复")
    
    print("\n  已支持的提供商:")
    stats = api_rotator.get_stats()
    supported_providers = list(stats.keys()) if stats else []
    if supported_providers:
        for provider in supported_providers:
            count = len([k for k in stats[provider]])
            print(f"    - {provider} ({count} 个密钥)")
    else:
        print("    - 暂无配置的API密钥")
    
    print("\n  使用方法:")
    print("    1. 收集协作者的API密钥")
    print("    2. 使用 multi_user_config.add_user() 添加用户")
    print("    3. 系统会自动轮询使用不同的密钥")


if __name__ == "__main__":
    # 添加示例密钥
    add_sample_keys()
    
    # 设置API轮询系统
    setup_api_rotation_system()
    
    # 显示信息
    show_api_rotation_info()