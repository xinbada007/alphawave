#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设置用户配置的脚本
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'user_configs'))

from secure_config_manager import SecureConfigManager

def setup_yellow_user():
    """设置yellow用户的配置"""
    # 创建安全配置管理器实例
    config_manager = SecureConfigManager(password="yellow_user_secure_password")
    
    # API密钥配置
    api_keys = {
        "polygon": "zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd",
        "fmp": "5u27af6jTiLZov0Kmqz2LZ9leNlKzguO",
        "tiingo": "",
        "alpha_vantage": "AED72KC95E69FL8Q",
        "openbb": ""
    }
    
    # 设置配置
    settings = {
        "default_provider": "polygon",
        "cache_enabled": True,
        "request_delay": 0.1
    }
    
    # 保存配置
    config_manager.save_user_config("yellow", api_keys, settings)
    
    print("yellow用户的加密配置已保存完成！")
    
    # 验证配置是否正确保存和可读取
    try:
        loaded_config = config_manager.load_user_config("yellow")
        print("✓ 配置验证成功！")
        print(f"  - Polygon API Key: {'*' * 20}{loaded_config['api_keys']['polygon'][-6:] if loaded_config['api_keys']['polygon'] else '未设置'}")
        print(f"  - FMP API Key: {'*' * 20}{loaded_config['api_keys']['fmp'][-6:] if loaded_config['api_keys']['fmp'] else '未设置'}")
        print(f"  - Alpha Vantage API Key: {'*' * 20}{loaded_config['api_keys']['alpha_vantage'][-6:] if loaded_config['api_keys']['alpha_vantage'] else '未设置'}")
    except Exception as e:
        print(f"✗ 配置验证失败: {e}")

if __name__ == "__main__":
    setup_yellow_user()