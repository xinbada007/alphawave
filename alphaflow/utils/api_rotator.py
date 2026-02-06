"""
API轮询器 - 用于在多个API密钥之间自动轮询以避免频率限制
"""
import random
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
import asyncio
from collections import defaultdict


@dataclass
class ApiKeyInfo:
    """API密钥信息"""
    key: str
    provider: str
    owner: str
    usage_count: int = 0
    last_used: Optional[datetime] = None
    rate_limit_remaining: int = 100  # 假设初始剩余调用次数
    reset_time: Optional[datetime] = None  # 重置时间
    api_type: str = "general"  # API类型：general, market_data, fundamental, news, sentiment等


class ApiRotator:
    """
    API轮询器 - 管理多个API密钥的轮询使用
    """
    
    def __init__(self):
        self.keys: Dict[str, List[ApiKeyInfo]] = defaultdict(list)  # provider -> keys
        self.current_index: Dict[str, int] = defaultdict(int)  # provider -> current index
        self.lock = threading.Lock()
        self.usage_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))  # provider -> key -> usage count
        
    def add_api_key(self, provider: str, key: str, owner: str):
        """添加API密钥"""
        with self.lock:
            api_info = ApiKeyInfo(key=key, provider=provider, owner=owner)
            self.keys[provider].append(api_info)
            print(f"✅ 添加 {provider} API密钥 (所有者: {owner})")
    
    def get_next_key(self, provider: str, api_type: str = "general") -> Optional[str]:
        """获取下一个可用的API密钥（轮询）"""
        with self.lock:
            if provider not in self.keys or not self.keys[provider]:
                return None
            
            # 筛选特定类型的API密钥
            filtered_keys = [key for key in self.keys[provider] 
                           if key.api_type == api_type or api_type == "general"]
            
            # 筛选未达到频率限制的密钥
            available_keys = [key for key in filtered_keys 
                            if key.rate_limit_remaining > 0 or 
                               (key.reset_time and key.reset_time < datetime.now())]
            
            if not available_keys:
                print(f"⚠️  {provider} 所有API密钥都达到频率限制")
                return None
            
            # 找到当前索引并获取密钥
            current_idx = self.current_index[provider]
            valid_keys = [key for key in self.keys[provider] if key in available_keys]
            
            if not valid_keys:
                return None
                
            selected_key = valid_keys[current_idx % len(valid_keys)]
            
            # 更新使用统计
            selected_key.usage_count += 1
            selected_key.last_used = datetime.now()
            selected_key.rate_limit_remaining -= 1
            
            # 更新索引供下次使用
            self.current_index[provider] = (current_idx + 1) % len(valid_keys)
            
            # 更新使用统计
            self.usage_stats[provider][selected_key.key] += 1
            
            return selected_key.key
    
    def get_next_key_by_types(self, provider: str, preferred_types: list) -> Optional[tuple]:
        """根据优先级获取指定类型的API密钥，返回(密钥, 类型)元组"""
        with self.lock:
            if provider not in self.keys or not self.keys[provider]:
                return None
            
            # 按照优先级顺序查找可用密钥
            for api_type in preferred_types:
                filtered_keys = [key for key in self.keys[provider] 
                               if key.api_type == api_type]
                
                available_keys = [key for key in filtered_keys 
                                if key.rate_limit_remaining > 0 or 
                                   (key.reset_time and key.reset_time < datetime.now())]
                
                if available_keys:
                    current_idx = self.current_index[provider]
                    valid_keys = [key for key in self.keys[provider] if key in available_keys]
                    
                    selected_key = valid_keys[current_idx % len(valid_keys)]
                    
                    # 更新使用统计
                    selected_key.usage_count += 1
                    selected_key.last_used = datetime.now()
                    selected_key.rate_limit_remaining -= 1
                    
                    # 更新索引供下次使用
                    self.current_index[provider] = (current_idx + 1) % len(valid_keys)
                    
                    # 更新使用统计
                    self.usage_stats[provider][selected_key.key] += 1
                    
                    return selected_key.key, api_type
            
            # 如果指定类型都不可用，返回任意可用密钥
            all_available = [key for key in self.keys[provider] 
                           if key.rate_limit_remaining > 0 or 
                              (key.reset_time and key.reset_time < datetime.now())]
            
            if all_available:
                current_idx = self.current_index[provider]
                selected_key = all_available[current_idx % len(all_available)]
                
                # 更新使用统计
                selected_key.usage_count += 1
                selected_key.last_used = datetime.now()
                selected_key.rate_limit_remaining -= 1
                
                # 更新索引供下次使用
                self.current_index[provider] = (current_idx + 1) % len(all_available)
                
                # 更新使用统计
                self.usage_stats[provider][selected_key.key] += 1
                
                return selected_key.key, selected_key.api_type
            
            print(f"⚠️  {provider} 所有API密钥都达到频率限制")
            return None
    
    def report_usage(self, provider: str, key: str, success: bool = True, reset_after: int = None):
        """报告API使用情况"""
        with self.lock:
            for api_key in self.keys[provider]:
                if api_key.key == key:
                    if not success:
                        # 如果失败，可能是达到限制，设置重置时间
                        if reset_after:
                            api_key.reset_time = datetime.now() + timedelta(seconds=reset_after)
                        else:
                            # 默认5分钟后重试
                            api_key.reset_time = datetime.now() + timedelta(minutes=5)
                    else:
                        # 成功调用，恢复一些限制（模拟）
                        if api_key.rate_limit_remaining < 100:
                            api_key.rate_limit_remaining = min(100, api_key.rate_limit_remaining + 1)
                    break
    
    def get_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        with self.lock:
            stats = {}
            for provider, keys in self.keys.items():
                provider_stats = []
                for key_info in keys:
                    provider_stats.append({
                        'key_preview': key_info.key[:10] + '...' if len(key_info.key) > 10 else key_info.key,
                        'owner': key_info.owner,
                        'usage_count': key_info.usage_count,
                        'remaining_calls': key_info.rate_limit_remaining,
                        'last_used': key_info.last_used.isoformat() if key_info.last_used else None,
                        'reset_time': key_info.reset_time.isoformat() if key_info.reset_time else None
                    })
                stats[provider] = provider_stats
            return stats
    
    def get_available_keys_count(self, provider: str) -> int:
        """获取指定提供商的可用密钥数量"""
        with self.lock:
            available = 0
            for key in self.keys[provider]:
                if key.rate_limit_remaining > 0 or (key.reset_time and key.reset_time < datetime.now()):
                    available += 1
            return available


# 全局API轮询器实例
api_rotator = ApiRotator()


def get_api_key(provider: str) -> Optional[str]:
    """获取API密钥的便捷函数"""
    return api_rotator.get_next_key(provider)


def report_api_usage(provider: str, key: str, success: bool = True, reset_after: int = None):
    """报告API使用情况的便捷函数"""
    api_rotator.report_usage(provider, key, success, reset_after)


def add_api_key(provider: str, key: str, owner: str):
    """添加API密钥的便捷函数"""
    api_rotator.add_api_key(provider, key, owner)


def get_api_stats():
    """获取API统计的便捷函数"""
    return api_rotator.get_stats()