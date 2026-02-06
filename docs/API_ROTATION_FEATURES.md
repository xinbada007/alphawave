# AlphaFlow API轮询功能详解

## 功能概述
AlphaFlow框架现在支持API密钥轮询功能，可自动在多个API密钥之间轮询使用，有效避免频率限制问题。

## 核心组件

### 1. API轮询器 (ApiRotator)
- **位置**: `alphaflow/utils/api_rotator.py`
- **功能**: 
  - 管理多个API密钥的轮询使用
  - 跟踪每个密钥的使用情况
  - 自动处理频率限制和错误恢复
  - 提供使用统计信息

### 2. 多用户API配置管理器
- **位置**: `alphaflow/utils/multi_user_api_config.py`
- **功能**:
  - 管理多个用户的API密钥
  - 安全存储和检索API密钥
  - 提供用户信息管理

### 3. API轮询装饰器
- **位置**: `alphaflow/utils/api_rotation_decorator.py`
- **功能**:
  - 提供装饰器简化API轮询使用
  - 自动处理密钥切换和错误恢复

## 集成的收集器

### Market Data Collector
- 自动轮询不同提供商的API密钥
- 支持Polygon、FMP、Alpha Vantage等
- 优先使用付费提供商，回退到免费提供商

### Fundamental Data Collector  
- 自动轮询基本面数据API密钥
- 支持FMP、Alpha Vantage等
- 按优先级尝试不同提供商

## 使用方法

### 1. 添加API密钥
```python
from alphaflow.utils.api_rotator import add_api_key

add_api_key("polygon", "YOUR_API_KEY", "Your Name")
```

### 2. 获取轮询后的API密钥
```python
from alphaflow.utils.api_rotator import get_api_key

api_key = get_api_key("polygon")
```

### 3. 添加用户
```python
from alphaflow.utils.multi_user_api_config import multi_user_config

multi_user_config.add_user(
    user_id="user123",
    name="John Doe", 
    email="john@example.com",
    api_keys={
        "alpha_vantage": "KEY",
        "polygon": "KEY"
    }
)
```

### 4. 运行设置脚本
```bash
python scripts/setup_api_rotation.py
```

### 5. 手动添加用户
```bash
python scripts/add_user_api_keys.py
```

## 支持的API提供商

- **Alpha Vantage**: 股票、外汇、加密货币数据
- **Polygon.io**: 实时和历史市场数据  
- **Financial Modeling Prep**: 财务报表和基本面数据
- **Tiingo**: 历史股票和加密货币数据
- **AllTick**: 市场数据和基本面数据
- **其他OpenBB支持的提供商**

## 优势

1. **频率限制缓解**: 通过多密钥轮询分散请求压力
2. **高可用性**: 单个密钥失效不影响整体系统
3. **负载均衡**: 自动在多个密钥间分配请求
4. **错误恢复**: 智能处理API调用失败
5. **多用户支持**: 支持团队协作使用
6. **安全存储**: 加密存储API密钥

## 最佳实践

1. **收集多样化的API密钥**: 从不同协作者获取密钥
2. **监控使用情况**: 定期检查API密钥使用统计
3. **合理配置缓存**: 结合缓存策略减少API调用
4. **错误处理**: 实现适当的重试和回退机制

## 文档资源

- `API_KEY_COLLECTION_FORM.md`: API密钥收集表单
- `API_ROTATION_GUIDE.md`: 详细使用指南
- `scripts/add_user_api_keys.py`: 用户添加脚本
- `tests/test_api_rotation.py`: 测试脚本