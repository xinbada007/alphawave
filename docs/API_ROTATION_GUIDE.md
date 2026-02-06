# API轮询系统使用指南

## 概述
本文档介绍如何使用AlphaFlow框架中的API轮询系统，该系统可以自动在多个API密钥之间轮询，以避免频率限制。

## 系统架构

### 1. API轮询器 (ApiRotator)
- 管理多个API密钥的轮询使用
- 跟踪每个密钥的使用情况和剩余调用次数
- 自动处理频率限制和错误恢复

### 2. 多用户API配置管理器 (MultiUserApiConfig)
- 管理多个用户的API密钥
- 提供安全的密钥存储和检索

### 3. API轮询装饰器 (api_rotation_decorator)
- 提供装饰器以简化API轮询的使用
- 自动处理密钥切换和错误恢复

## 使用方法

### 1. 添加API密钥到轮询器

```python
from alphaflow.utils.api_rotator import add_api_key

# 添加API密钥
add_api_key("alpha_vantage", "YOUR_API_KEY_HERE", "User Name")
add_api_key("polygon", "YOUR_POLYGON_KEY", "User Name")
add_api_key("fmp", "YOUR_FMP_KEY", "User Name")
```

### 2. 获取轮询后的API密钥

```python
from alphaflow.utils.api_rotator import get_api_key

# 获取下一个可用的API密钥
api_key = get_api_key("alpha_vantage")
if api_key:
    print(f"使用API密钥: {api_key}")
```

### 3. 使用装饰器进行API轮询

```python
from alphaflow.utils.api_rotation_decorator import api_rotation

@api_rotation(provider="alpha_vantage")
def fetch_stock_data(symbol, api_key):
    # 使用提供的api_key进行API调用
    # api_key参数会自动注入
    pass
```

### 4. 报告API使用情况

```python
from alphaflow.utils.api_rotator import report_api_usage

# 报告API调用成功
report_api_usage("alpha_vantage", "KEY_USED", success=True)

# 报告API调用失败
report_api_usage("alpha_vantage", "KEY_USED", success=False)
```

## 集成到收集器

API轮询系统已经集成到以下收集器中：

### Market Data Collector
- 自动轮询不同的市场数据API密钥
- 支持Polygon、FMP、Alpha Vantage等提供商
- 优先使用付费提供商，回退到免费提供商

### Fundamental Data Collector
- 自动轮询不同的基本面数据API密钥
- 支持FMP、Alpha Vantage等提供商
- 按优先级尝试不同提供商

## 配置多用户API密钥

### 添加用户
```python
from alphaflow.utils.multi_user_api_config import multi_user_config

# 添加用户及其API密钥
multi_user_config.add_user(
    user_id="user123",
    name="John Doe", 
    email="john@example.com",
    api_keys={
        "alpha_vantage": "AV_API_KEY",
        "polygon": "POLYGON_API_KEY",
        "fmp": "FMP_API_KEY"
    }
)
```

### 查看统计信息
```python
# 获取API使用统计
stats = multi_user_config.get_api_rotator_stats()
print(stats)
```

## 最佳实践

### 1. 密钥管理
- 定期轮换API密钥
- 监控密钥使用情况
- 确保有足够的备用密钥

### 2. 错误处理
- 实现适当的重试机制
- 处理API调用失败的情况
- 记录和监控错误率

### 3. 性能优化
- 合理设置缓存策略
- 批量处理API请求
- 监控API响应时间

## 安全考虑

### 1. 密钥存储
- API密钥在内存中加密存储
- 避免在日志中记录完整密钥
- 定期审查密钥访问权限

### 2. 访问控制
- 限制API密钥的使用范围
- 实施适当的速率限制
- 监控异常使用模式

## 监控和维护

### 1. 使用统计
- 定期检查API密钥使用统计
- 识别高使用率的密钥
- 优化轮询策略

### 2. 健康检查
- 定期验证API密钥的有效性
- 监控API服务的可用性
- 处理API提供商的变化

## 故障排除

### 常见问题
1. **所有API密钥都达到限制**: 系统会自动等待重置时间后重试
2. **API密钥无效**: 系统会跳过无效密钥，使用下一个可用密钥
3. **网络问题**: 实现了重试机制和回退策略

### 调试方法
```python
from alphaflow.utils.api_rotator import api_rotator

# 查看当前状态
stats = api_rotator.get_stats()
print(stats)

# 查看可用密钥数量
available_count = api_rotator.get_available_keys_count("alpha_vantage")
print(f"Available keys: {available_count}")
```

## 扩展性

系统设计为可扩展：
- 支持添加新的API提供商
- 可以实现不同的轮询策略
- 支持复杂的负载均衡算法