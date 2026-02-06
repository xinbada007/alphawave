#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户API密钥配置工具
支持加密存储（推荐）和普通存储模式
"""

import json
import os
import getpass
import argparse
from typing import Dict


def has_cryptography():
    """检查是否安装了cryptography库"""
    try:
        import cryptography
        return True
    except ImportError:
        return False


def get_secure_config_manager():
    """获取安全配置管理器"""
    if has_cryptography():
        from user_configs.secure_config_manager import SecureConfigManager
        # 使用环境变量或默认密码
        password = os.environ.get('CONFIG_PASSWORD', 'default_secure_password_for_demo')
        return SecureConfigManager(password=password)
    else:
        # 如果没有cryptography库，使用基础加密
        from user_configs.secure_config_manager import SecureConfigManager
        # 使用环境变量或默认密码
        password = os.environ.get('CONFIG_PASSWORD', 'default_secure_password_for_demo')
        return SecureConfigManager(password=password)


def get_available_providers():
    """获取可用的数据提供商列表"""
    return ["polygon", "fmp", "yfinance", "tiingo", "alpha_vantage"]


def interactive_setup(user_id: str, use_encryption: bool = True):
    """交互式设置用户配置"""
    print(f"\n开始为用户 '{user_id}' 配置API密钥...")
    print("="*50)
    
    api_keys = {}
    
    # 获取各API密钥
    print("\n请输入API密钥（留空则跳过）:")
    
    providers = [
        ("polygon", "Polygon/Massive API密钥"),
        ("fmp", "Financial Modeling Prep API密钥"), 
        ("tiingo", "Tiingo API密钥"),
        ("alpha_vantage", "Alpha Vantage API密钥"),
        ("openbb", "OpenBB平台用户名（如需要）")
    ]
    
    for provider, description in providers:
        key = getpass.getpass(f"{description}: ")
        if key.strip():
            api_keys[provider] = key.strip()
        else:
            api_keys[provider] = ""  # 留空的设置为空字符串
    
    # 获取设置选项
    print(f"\n配置设置选项:")
    default_provider = input(f"默认数据提供商 (默认: polygon) [{'/'.join(get_available_providers())}]: ").strip()
    if not default_provider:
        default_provider = "polygon"
    
    cache_enabled_input = input("启用缓存 (Y/n，默认Y): ").strip().lower()
    cache_enabled = cache_enabled_input != 'n'
    
    try:
        request_delay = float(input("请求延迟 (秒，默认0.1): ") or "0.1")
    except ValueError:
        request_delay = 0.1
    
    settings = {
        "default_provider": default_provider,
        "cache_enabled": cache_enabled,
        "request_delay": request_delay
    }
    
    # 保存配置
    try:
        if use_encryption and has_cryptography():
            config_manager = get_secure_config_manager()
            config_manager.save_user_config(user_id, api_keys, settings)
            print(f"\n✓ 用户 '{user_id}' 的加密配置已保存到 user_configs/{user_id}.json")
        else:
            # 明文保存（不推荐，仅作为备选）
            config = {
                "api_keys": api_keys,
                "settings": settings
            }
            config_path = os.path.join("user_configs", f"{user_id}.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"\n✓ 用户 '{user_id}' 的配置已保存到 {config_path} (明文)")
        
        print(f"\n配置完成！您可以使用以下命令运行分析:")
        print(f"python main_with_user_support.py --symbols NVDA --user-id {user_id}")
        
    except Exception as e:
        print(f"✗ 保存配置失败: {e}")


def show_user_config(user_id: str):
    """显示用户配置（隐藏敏感信息）"""
    try:
        if has_cryptography():
            config_manager = get_secure_config_manager()
            config = config_manager.load_user_config(user_id)
        else:
            # 尝试加载明文配置
            config_path = os.path.join("user_configs", f"{user_id}.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        print(f"\n用户 '{user_id}' 的配置:")
        print("="*30)
        
        print("\nAPI密钥状态:")
        for key, value in config["api_keys"].items():
            if value:
                print(f"  {key}: 已设置 ({'*' * 20}{value[-6:]})")
            else:
                print(f"  {key}: 未设置")
        
        print("\n设置:")
        for key, value in config["settings"].items():
            print(f"  {key}: {value}")
            
    except FileNotFoundError:
        print(f"用户 '{user_id}' 的配置文件不存在")
    except Exception as e:
        print(f"读取配置失败: {e}")


def main():
    parser = argparse.ArgumentParser(description='用户API密钥配置工具')
    parser.add_argument('--user-id', required=True, help='用户ID')
    parser.add_argument('--action', choices=['setup', 'show', 'delete'], 
                       default='setup', help='操作类型: setup(设置)/show(查看)/delete(删除)')
    
    args = parser.parse_args()
    
    # 确保user_configs目录存在
    os.makedirs('user_configs', exist_ok=True)
    
    if args.action == 'setup':
        use_encryption = has_cryptography()
        if not use_encryption:
            print("! 注意: 未检测到cryptography库，将使用基础加密方式")
            print("建议运行: pip3 install cryptography 来获得更强的安全性")
        interactive_setup(args.user_id, use_encryption)
    elif args.action == 'show':
        show_user_config(args.user_id)
    elif args.action == 'delete':
        config_path = os.path.join("user_configs", f"{args.user_id}.json")
        try:
            os.remove(config_path)
            print(f"用户 '{args.user_id}' 的配置文件已删除")
        except FileNotFoundError:
            print(f"用户 '{args.user_id}' 的配置文件不存在")
        except Exception as e:
            print(f"删除配置文件失败: {e}")


if __name__ == "__main__":
    main()