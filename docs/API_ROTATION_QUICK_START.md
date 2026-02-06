# API轮询系统快速入门

## 1. 系统概述
API轮询系统可以自动在多个API密钥之间轮询使用，有效避免单一密钥的频率限制问题。

## 2. 快速设置

### 查看当前状态
```bash
python scripts/setup_api_rotation.py
```

### 添加用户API密钥
```bash
python scripts/add_user_api_keys.py
```

## 3. 支持的API提供商

- Alpha Vantage
- Polygon.io  
- Financial Modeling Prep (FMP)
- Tiingo
- AllTick
- 其他OpenBB支持的提供商

## 4. 使用示例

### 在代码中使用API轮询
```python
from alphaflow.utils.api_rotator import get_api_key, report_api_usage

# 获取轮询后的API密钥
api_key = get_api_key("polygon")
if api_key:
    # 使用API密钥进行调用
    print(f"使用API密钥: {api_key[:10]}...")

# 报告API使用情况
report_api_usage("polygon", api_key, success=True)
```

## 5. 管理用户

### 添加新用户
```python
from alphaflow.utils.multi_user_api_config import multi_user_config

multi_user_config.add_user(
    user_id="new_user",
    name="New User",
    email="user@example.com", 
    api_keys={
        "alpha_vantage": "YOUR_AV_KEY",
        "polygon": "YOUR_POLYGON_KEY"
    }
)
```

## 6. 查看统计

### 查看API使用统计
```python
from alphaflow.utils.api_rotator import get_api_stats

stats = get_api_stats()
print(stats)
```

## 7. 测试系统

```bash
python tests/test_api_rotation.py
```

## 8. 文档参考

- `docs/API_ROTATION_GUIDE.md` - 详细使用指南
- `API_KEY_COLLECTION_FORM.md` - API密钥收集表单
- `docs/API_ROTATION_FEATURES.md` - 功能详解

## 9. 高级功能

### 装饰器使用
```python
from alphaflow.utils.api_rotation_decorator import api_rotation

@api_rotation(provider="alpha_vantage")
def fetch_data(symbol, api_key):
    # api_key参数会自动注入
    pass
```

## 10. 最佳实践

1. **收集多样化的API密钥**: 从不同协作者获取
2. **监控使用情况**: 定期检查统计信息
3. **配合缓存使用**: 减少不必要的API调用
4. **处理错误情况**: 实现适当的错误处理机制

现在您的系统已经支持API轮询功能，可以有效避免频率限制问题！