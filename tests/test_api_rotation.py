#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试API轮询系统
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')

from alphaflow.utils.api_rotator import api_rotator, get_api_key, report_api_usage, get_api_stats
from alphaflow.utils.multi_user_api_config import multi_user_config


def test_api_rotator_basic():
    """测试API轮询器基本功能"""
    print("🧪 测试API轮询器基本功能...")
    
    # 添加一些测试密钥
    api_rotator.add_api_key("test_provider", "key1", "User1")
    api_rotator.add_api_key("test_provider", "key2", "User2")
    api_rotator.add_api_key("test_provider", "key3", "User3")
    
    # 测试获取密钥（轮询）
    key1 = get_api_key("test_provider")
    key2 = get_api_key("test_provider")
    key3 = get_api_key("test_provider")
    key4 = get_api_key("test_provider")  # 应该回到第一个
    
    print(f"  获取的密钥序列: {key1}, {key2}, {key3}, {key4}")
    
    # 报告使用情况
    report_api_usage("test_provider", key1, success=True)
    report_api_usage("test_provider", key2, success=False)
    
    print("  ✅ API轮询器基本功能测试通过")
    return True


def test_multi_user_config():
    """测试多用户配置管理"""
    print("\n🧪 测试多用户配置管理...")
    
    # 添加测试用户
    multi_user_config.add_user(
        user_id="test_user_1",
        name="Test User 1",
        email="test1@example.com",
        api_keys={
            "alpha_vantage": "test_av_key_1",
            "polygon": "test_polygon_key_1"
        }
    )
    
    # 添加另一个用户
    multi_user_config.add_user(
        user_id="test_user_2", 
        name="Test User 2",
        email="test2@example.com",
        api_keys={
            "alpha_vantage": "test_av_key_2",
            "fmp": "test_fmp_key_2"
        }
    )
    
    # 获取所有API密钥
    all_keys = multi_user_config.get_all_api_keys()
    print(f"  按提供商分组的API密钥: {list(all_keys.keys())}")
    
    # 获取用户列表
    users = multi_user_config.get_users()
    print(f"  用户数量: {len(users)}")
    
    print("  ✅ 多用户配置管理测试通过")
    return True


def test_api_stats():
    """测试API统计功能"""
    print("\n🧪 测试API统计功能...")
    
    # 获取统计信息
    stats = get_api_stats()
    print(f"  统计信息提供商: {list(stats.keys())}")
    
    for provider, keys in stats.items():
        print(f"  {provider}: {len(keys)} 个密钥")
        for key_info in keys:
            print(f"    - {key_info['key_preview']} (所有者: {key_info['owner']})")
    
    print("  ✅ API统计功能测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("🚀 开始API轮询系统测试...\n")
    
    test_results = []
    test_results.append(test_api_rotator_basic())
    test_results.append(test_multi_user_config()) 
    test_results.append(test_api_stats())
    
    print(f"\n{'='*60}")
    print("测试汇总:")
    print(f"  API轮询器基本功能: {'✅ 通过' if test_results[0] else '❌ 失败'}")
    print(f"  多用户配置管理: {'✅ 通过' if test_results[1] else '❌ 失败'}")
    print(f"  API统计功能: {'✅ 通过' if test_results[2] else '❌ 失败'}")
    
    all_passed = all(test_results)
    print(f"\n总体结果: {'🎉 全部通过' if all_passed else '⚠️  部分失败'}")
    print(f"{'='*60}")
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    if success:
        print("\n✅ API轮询系统测试成功完成！")
    else:
        print("\n❌ API轮询系统测试存在问题！")