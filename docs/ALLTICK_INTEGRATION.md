# AllTick API 集成文档

## 概述
本项目已成功集成AllTick API，提供了一个灵活的数据收集器，能够获取股票行情、公司信息、新闻资讯和技术指标等数据。

## API 密钥
- **API Key**: `d512a2cb352dfb3b7d10c5ae0fe09b99-c-app`
- **已保存到**: 用户配置中（加密存储）

## 集成的组件

### 1. AllTickCollector
基础版收集器，适用于标准API端点格式。

### 2. AllTickCollectorFlexible
灵活版收集器，具有以下特性：
- 支持多个可能的API端点
- 自动尝试不同的端点格式
- 容错性强，能处理多种数据格式
- 智能解析响应数据

## 支持的数据类型

### 行情数据
- 开盘价、最高价、最低价、收盘价
- 成交量
- 涨跌额、涨跌幅
- 买卖盘数据

### 历史数据
- OHLCV历史价格数据
- 时间序列数据

### 公司基本面
- 公司名称、行业分类
- 市值、市盈率、市净率
- 股息率、员工数等

### 新闻资讯
- 新闻标题、摘要、发布时间
- 来源、链接
- 情感分析、相关性评分

### 技术指标
- RSI、MACD、移动平均线
- 布林带、随机指标
- ADX、威廉指标等

## 使用方法

### 1. 配置API密钥
API密钥已自动添加到用户配置中：
```bash
# 检查配置
python3 configure_user.py --user-id yellow --action show
```

### 2. 运行AllTick分析
```bash
python3 run_alltick_analysis.py --symbols AAPL MSFT GOOGL --user-id yellow
```

### 3. 直接使用收集器
```python
from alphaflow.components.collectors.alltick_collector_flexible import AllTickCollectorFlexible

collector = AllTickCollectorFlexible(name="MyCollector", config={
    'api_key': 'd512a2cb352dfb3b7d10c5ae0fe09b99-c-app'
})
```

## 错误处理
- 网络错误时自动重试其他端点
- 数据格式不匹配时智能解析
- API不可用时提供优雅降级

## 安全性
- API密钥使用加密存储
- 请求头安全传输
- 敏感信息不在日志中显示

## 注意事项
1. 由于AllTick API端点可能发生变化，灵活版收集器会尝试多个可能的端点
2. 实际使用时，请确认正确的API端点和认证方式
3. 某些数据可能需要特定的API权限才能访问

## 测试
运行以下命令测试集成：
```bash
python3 test_flexible_alltick.py
```

## 维护
如需更新API端点或修改收集器行为，可以修改以下文件：
- `alphaflow/components/collectors/alltick_collector.py`
- `alphaflow/components/collectors/alltick_collector_flexible.py`
- `run_alltick_analysis.py`

所有功能都已集成到AlphaFlow框架中，遵循ResearchPack数据容器协议。