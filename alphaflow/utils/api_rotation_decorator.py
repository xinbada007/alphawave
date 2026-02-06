"""
API轮询装饰器 - 用于在函数调用时自动轮询API密钥
"""
import functools
import time
from typing import Callable, Any
from .api_rotator import get_api_key, report_api_usage


def api_rotation(provider: str, api_type: str = "general", fallback_on_fail: bool = True, preferred_types: list = None):
    """
    API轮询装饰器
    
    Args:
        provider: API提供商名称
        api_type: API类型 (general, market_data, fundamental, news, sentiment等)
        fallback_on_fail: 失败时是否尝试其他密钥
        preferred_types: 优先使用的API类型列表
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 获取API密钥
            api_key = None
            used_type = api_type
            
            if preferred_types:
                # 使用类型优先级获取密钥
                result = get_api_key_by_types(provider, preferred_types)
                if result:
                    api_key, used_type = result
            else:
                # 使用普通方式获取密钥
                from .api_rotator import api_rotator
                api_key = api_rotator.get_next_key(provider, api_type)
            
            if not api_key:
                if fallback_on_fail:
                    # 如果没有可用密钥，尝试等待后重试
                    print(f"⚠️  {provider} 没有可用的API密钥，稍后重试...")
                    time.sleep(5)
                    if preferred_types:
                        result = get_api_key_by_types(provider, preferred_types)
                        if result:
                            api_key, used_type = result
                    else:
                        api_key = api_rotator.get_next_key(provider, api_type)
                    
                    if not api_key:
                        raise Exception(f"No available API keys for {provider}")
                else:
                    raise Exception(f"No available API keys for {provider}")
            
            print(f"🔄 使用 {provider} {used_type} 类型API密钥: {api_key[:10]}...")
            
            # 将API密钥和类型添加到参数中
            import inspect
            sig = inspect.signature(func)
            try:
                # 检查函数是否接受api_key和api_type参数
                bound_args = sig.bind_partial(*args, **kwargs)
                # 更新参数
                updated_kwargs = dict(kwargs)
                updated_kwargs['api_key'] = api_key
                updated_kwargs['api_type'] = used_type
            except TypeError:
                # 如果函数签名不匹配，仍然尝试传递参数
                updated_kwargs = dict(kwargs)
                updated_kwargs['api_key'] = api_key
                updated_kwargs['api_type'] = used_type
            
            # 尝试调用函数
            try:
                result = func(*args, **updated_kwargs)
                # 报告成功使用
                report_api_usage(provider, api_key, success=True)
                return result
            except Exception as e:
                print(f"❌ API调用失败: {str(e)}")
                # 报告失败使用
                report_api_usage(provider, api_key, success=False)
                
                # 如果启用了失败回退，尝试再次获取新密钥并重试
                if fallback_on_fail and "rate limit" in str(e).lower():
                    print(f"🔄 尝试使用另一个{provider}密钥重试...")
                    time.sleep(2)  # 等待一会儿再试
                    new_api_key = None
                    if preferred_types:
                        result = get_api_key_by_types(provider, preferred_types)
                        if result:
                            new_api_key, _ = result
                    else:
                        new_api_key = api_rotator.get_next_key(provider, api_type)
                    
                    if new_api_key and new_api_key != api_key:
                        try:
                            print(f"🔄 重试使用 {provider} API密钥: {new_api_key[:10]}...")
                            updated_kwargs['api_key'] = new_api_key
                            result = func(*args, **updated_kwargs)
                            report_api_usage(provider, new_api_key, success=True)
                            return result
                        except Exception as retry_e:
                            report_api_usage(provider, new_api_key, success=False)
                            raise retry_e
                
                raise e
        
        return wrapper
    return decorator


def get_api_key_by_types(provider: str, preferred_types: list) -> tuple:
    """
    根据优先级获取指定类型的API密钥
    
    Args:
        provider: API提供商名称
        preferred_types: 优先使用的API类型列表
        
    Returns:
        (api_key, api_type) 元组，如果没有可用密钥则返回None
    """
    from .api_rotator import api_rotator
    return api_rotator.get_next_key_by_types(provider, preferred_types)


# 针对OpenBB的特殊处理装饰器
def openbb_api_rotation(provider_name: str):
    """
    专门针对OpenBB的API轮询装饰器
    OpenBB会在环境变量中查找API密钥
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import os
            
            # 获取API密钥
            api_key = get_api_key(provider_name)
            if not api_key:
                raise Exception(f"No available API keys for {provider_name}")
            
            print(f"🔄 为 {provider_name} 设置API密钥...")
            
            # 临时设置环境变量
            original_key = os.environ.get(f"{provider_name.upper()}_API_KEY")
            os.environ[f"{provider_name.upper()}_API_KEY"] = api_key
            
            try:
                result = func(*args, **kwargs)
                report_api_usage(provider_name, api_key, success=True)
                return result
            except Exception as e:
                report_api_usage(provider_name, api_key, success=False)
                raise e
            finally:
                # 恢复原始环境变量
                if original_key is not None:
                    os.environ[f"{provider_name.upper()}_API_KEY"] = original_key
                elif f"{provider_name.upper()}_API_KEY" in os.environ:
                    del os.environ[f"{provider_name.upper()}_API_KEY"]
        
        return wrapper
    return decorator


# 便捷函数：直接获取API密钥而不使用装饰器
def get_rotated_api_key(provider: str) -> str:
    """
    直接获取轮询后的API密钥
    
    Args:
        provider: API提供商名称
        
    Returns:
        API密钥字符串
    """
    api_key = get_api_key(provider)
    if not api_key:
        raise Exception(f"No available API keys for {provider}")
    
    print(f"🔄 获取 {provider} API密钥: {api_key[:10]}...")
    return api_key