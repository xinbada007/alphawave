# AlphaFlow 增强版数据收集器文档

## 概述
本文档介绍了 AlphaFlow 框架中的增强版数据收集器，包括增强版市场数据收集器和基本面数据收集器。

## 增强版市场数据收集器 (Enhanced Market Data Collector)

### 文件路径
`alphaflow/components/collectors/market_data.py`

### 功能特性
- **多提供商支持**: 支持指定数据提供商（如 yfinance、polygon 等），具备自动回退机制
- **智能缓存**: 使用 DiskCache 实现 24 小时数据缓存，提高性能并减少 API 调用
- **VWAP 计算**: 额外计算成交量加权平均价 (Volume Weighted Average Price)
- **错误恢复**: 当指定提供商不可用时，自动回退到 yfinance
- **标准化数据**: 确保 OHLCV 数据格式一致

### 配置选项
```python
collector_config = {
    'provider': 'yfinance'  # 指定数据提供商
}
```

## 增强版基本面数据收集器 (Enhanced Fundamental Collector)

### 文件路径
`alphaflow/components/collectors/fundamental.py`

### 功能特性
- **全面基本面数据**: 获取完整的财务报表数据
  - 基本面指标 (metrics)
  - 资产负债表 (balance sheet)
  - 利润表 (income statement)  
  - 现金流量表 (cash flow)
- **智能缓存**: 使用 DiskCache 缓存各类基本面数据
- **错误容错**: 单个数据源失败不影响整体流程
- **数据整合**: 将各类基本面数据整合到统一的数据结构中

## 使用方法

### 1. 使用增强版市场数据收集器
```python
from alphaflow.components.collectors.market_data import EquityPriceCollector

collector_config = {
    'provider': 'polygon'  # 可选: yfinance, polygon 等
}
collector = EquityPriceCollector(name="MyMarketCollector", config=collector_config)
```

### 2. 使用增强版基本面数据收集器
```python
from alphaflow.components.collectors.fundamental import FundamentalCollector

collector = FundamentalCollector(name="MyFundamentalCollector")
```

## 数据结构

### 市场数据 (market_data)
- OHLCV 数据 (开盘价、最高价、最低价、收盘价、成交量)
- VWAP (成交量加权平均价，如可用)

### 基本面数据 (fundamentals)
```python
{
    # 基本面指标
    'marketCap': 1234567890,
    'peRatio': 25.5,
    'pbRatio': 3.2,
    # ...
    
    # 资产负债表
    'balance_sheet': {
        'totalAssets': 1234567890,
        'totalLiabilities': 987654321,
        # ...
    },
    
    # 利润表
    'income_statement': {
        'revenue': 1234567890,
        'netIncome': 987654321,
        # ...
    },
    
    # 现金流量表
    'cash_flow': {
        'operatingCashFlow': 1234567890,
        'freeCashFlow': 987654321,
        # ...
    }
}
```

## 遵循的规范
- 符合 AlphaFlow v1.2 协议
- 使用标准解包逻辑
- 遵循 ResearchPack 数据容器规范
- 实现异步处理
- 使用 DataFrameModel 封装 DataFrame

## 错误处理
- 实现静默失败机制
- 不会因单个数据源问题中断整个 Pipeline
- 提供详细的错误日志