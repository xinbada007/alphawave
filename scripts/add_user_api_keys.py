#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加用户API密钥脚本
用于收集和添加协作者的API密钥到轮询系统
"""

import sys
import os
import json
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')

from alphaflow.utils.multi_user_api_config import multi_user_config
from alphaflow.utils.api_rotator import add_api_key


def collect_user_input():
    """收集用户输入"""
    print("🔐 添加新用户API密钥")
    print("="*50)
    
    user_id = input("请输入用户ID (例如: john_doe): ").strip()
    if not user_id:
        print("❌ 用户ID不能为空")
        return None
    
    name = input("请输入您的姓名: ").strip()
    if not name:
        print("❌ 姓名不能为空")
        return None
    
    email = input("请输入您的邮箱: ").strip()
    if not email:
        print("❌ 邮箱不能为空")
        return None
    
    print("\n请输入以下API密钥 (如不提供请留空):")
    
    api_keys = {}
    
    providers = [
        ("Alpha Vantage", "alphavantage.co"),
        ("Polygon", "polygon.io"), 
        ("Financial Modeling Prep", "financialmodelingprep.com"),
        ("Tiingo", "api.tiingo.com"),
        ("OpenBB", "my.openbb.co")
    ]
    
    for provider_name, website in providers:
        print(f"\n{provider_name} (网站: {website})")
        key = input(f"  API密钥: ").strip()
        if key:
            api_keys[provider_name.lower().replace(" ", "_").replace("-", "_")] = key
            print(f"  ✅ 已记录{provider_name} API密钥")
    
    return {
        "user_id": user_id,
        "name": name,
        "email": email,
        "api_keys": api_keys
    }


def add_user_to_system(user_data):
    """将用户添加到系统"""
    print(f"\n📋 正在添加用户 {user_data['name']} ({user_data['user_id']})...")
    
    # 添加用户到配置
    multi_user_config.add_user(
        user_id=user_data['user_id'],
        name=user_data['name'],
        email=user_data['email'],
        api_keys=user_data['api_keys']
    )
    
    # 将API密钥添加到轮询器
    for provider, key in user_data['api_keys'].items():
        if key.strip():
            add_api_key(provider, key, user_data['name'])
            print(f"  ✅ {provider} API密钥已添加到轮询系统")
    
    print(f"\n✅ 用户 {user_data['name']} 已成功添加到系统！")


def batch_add_users_from_file(file_path):
    """从文件批量添加用户"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            users_data = json.load(f)
        
        if isinstance(users_data, dict):
            users_data = [users_data]  # 单个用户转为列表
        
        print(f"📋 批量添加 {len(users_data)} 个用户...")
        
        for user_data in users_data:
            required_fields = ['user_id', 'name', 'email', 'api_keys']
            if all(field in user_data for field in required_fields):
                add_user_to_system(user_data)
            else:
                print(f"❌ 用户数据格式错误: {user_data}")
        
        print(f"\n✅ 批量添加完成！")
        
    except FileNotFoundError:
        print(f"❌ 文件 {file_path} 不存在")
    except json.JSONDecodeError:
        print(f"❌ 文件 {file_path} 不是有效的JSON格式")
    except Exception as e:
        print(f"❌ 批量添加失败: {e}")


def show_current_status():
    """显示当前状态"""
    print("\n📊 当前系统状态:")
    
    # 显示用户数量
    users = multi_user_config.get_users()
    print(f"  已注册用户: {len(users)} 个")
    
    # 显示API密钥统计
    stats = multi_user_config.get_api_rotator_stats()
    total_keys = sum(len(keys) for keys in stats.values())
    print(f"  总API密钥数: {total_keys} 个")
    
    print("\n  按提供商分布:")
    for provider, keys in stats.items():
        print(f"    - {provider}: {len(keys)} 个密钥")


def main():
    """主函数"""
    print("🔐 API密钥管理系统")
    print("="*60)
    
    while True:
        print("\n请选择操作:")
        print("  1. 手动添加用户API密钥")
        print("  2. 从文件批量添加用户")
        print("  3. 查看当前状态")
        print("  4. 退出")
        
        choice = input("\n请输入选择 (1-4): ").strip()
        
        if choice == '1':
            user_data = collect_user_input()
            if user_data:
                confirm = input(f"\n确认添加用户 {user_data['name']}? (y/N): ").strip().lower()
                if confirm == 'y':
                    add_user_to_system(user_data)
                else:
                    print("❌ 已取消添加")
        
        elif choice == '2':
            file_path = input("请输入JSON文件路径: ").strip()
            if file_path:
                confirm = input(f"确认从 {file_path} 批量添加用户? (y/N): ").strip().lower()
                if confirm == 'y':
                    batch_add_users_from_file(file_path)
                else:
                    print("❌ 已取消批量添加")
        
        elif choice == '3':
            show_current_status()
        
        elif choice == '4':
            print("\n👋 感谢使用API密钥管理系统！")
            break
        
        else:
            print("❌ 无效选择，请重试")


if __name__ == "__main__":
    main()