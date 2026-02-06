# 项目重组说明

## 文件整理

### 1. 根目录文件迁移
- **文档文件**:
  - `API_KEY_COLLECTION_FORM.md` → `docs/`
  - `API_ROTATION_QUICK_START.md` → `docs/`
  - `GEMINI.md` → `docs/`
  - `MEMORY.md` → 根目录（保持不变，重要记忆文件）

### 2. 目录结构
```
alphaflow/
├── components/
│   ├── collectors/           # 数据收集器
│   │   ├── basic.py         # 基础收集器
│   │   ├── market_data.py   # 市场数据收集器
│   │   ├── fundamental.py   # 基本面数据收集器
│   │   ├── news.py          # 新闻收集器
│   │   ├── news_sentiment.py # 舆情收集器
│   │   ├── openbb_collector_updated.py # OpenBB收集器
│   │   ├── alltick_collector.py # AllTick收集器
│   │   └── alltick_collector_flexible.py # AllTick灵活收集器
│   ├── processors/          # 数据处理器
│   │   └── technicals.py    # 技术指标处理器
│   └── visualizers/         # 可视化器
├── core/                    # 核心模块
│   ├── base.py              # 基础类
│   └── schema.py            # 数据结构定义
├── engine/                  # 引擎
│   └── pipeline.py          # 异步管道
└── utils/                   # 工具函数
    ├── api_rotator.py       # API轮询器
    ├── api_rotation_decorator.py # API轮询装饰器
    ├── multi_user_api_config.py # 多用户API配置管理
    ├── cache.py             # 缓存工具
    └── quickchart.py        # 图表工具
docs/                        # 文档
├── API_ROTATION_GUIDE.md    # API轮询使用指南
├── API_ROTATION_FEATURES.md # API轮询功能详解
├── TIINGO_API_INTEGRATION.md # Tiingo API集成
├── ENHANCED_DATA_COLLECTORS.md # 增强收集器文档
├── MARKET_DATA_UPDATES.md   # 市场数据更新
├── PROJECT_STRUCTURE.md     # 项目结构文档
├── RESTRUCTURE_LOG.md       # 重构日志
├── PROJECT_REORGANIZATION.md # 本文件
└── ...
scripts/                     # 脚本
├── setup_api_rotation.py    # API轮询设置脚本
├── add_user_api_keys.py     # 添加用户API密钥脚本
├── configure_user.py        # 用户配置脚本
├── setup_user_config.py     # 用户配置设置
├── setup_new_user.sh        # 新用户设置脚本
└── ...
tests/                       # 测试
├── test_api_rotation.py     # API轮询测试
├── test_market_data_enhanced.py # 市场数据测试
├── test_alltick_collector.py # AllTick收集器测试
├── test_flexible_alltick.py # AllTick灵活收集器测试
└── ...
user_configs/               # 用户配置
├── config_manager.py        # 配置管理器
├── secure_config_manager.py # 安全配置管理器
├── simple_encryption.py     # 简单加密
├── yellow.json              # Yellow用户配置
└── ...
archive/                     # 归档文件
```

### 3. 移除的文件
- `alphaflow/components/collectors/enhanced_fundamental.py` (多余文件)
- `alphaflow/components/collectors/enhanced_market_data.py` (多余文件)

## API轮询系统改进

### 1. 更泛化的API轮询
- 支持API类型分类 (general, market_data, fundamental, news, sentiment等)
- 支持按类型优先级获取API密钥
- 改进错误处理和回退机制

### 2. 舆情数据收集器
- 新增 `news_sentiment.py` 收集器
- 展示API轮询在舆情分析中的应用
- 支持多种新闻提供商的API轮询

### 3. 保持独立的收集器
- `market_data.py` 和 `fundamental.py` 保持独立
- 因为它们获取不同类型的数据，职责不同
- 但都使用相同的API轮询机制