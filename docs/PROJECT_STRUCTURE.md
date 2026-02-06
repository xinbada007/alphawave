# AlphaFlow 项目结构文档

## 目录结构

```
alphawave/                          # 项目根目录
├── alphaflow/                     # 核心框架代码
│   ├── core/                      # 核心基类和数据模型
│   │   ├── base.py                # 基础组件类
│   │   └── schema.py              # 数据模型定义
│   ├── components/                # 可插拔组件
│   │   ├── collectors/           # 数据收集器
│   │   │   ├── basic.py          # 基础收集器
│   │   │   ├── openbb_collector_updated.py # OpenBB收集器
│   │   │   ├── alltick_collector.py       # AllTick收集器
│   │   │   └── alltick_collector_flexible.py # 灵活版AllTick收集器
│   │   ├── processors/           # 数据处理器
│   │   │   └── technicals.py     # 技术指标处理器
│   │   └── visualizers/          # 数据可视化器
│   ├── engine/                    # 管道引擎
│   │   └── pipeline.py           # 研究管道
│   └── utils/                     # 工具函数
│       ├── cache.py              # 缓存工具
│       ├── quickchart.py         # 图表工具
│       └── user_config.py        # 用户配置工具
├── scripts/                       # 脚本文件
│   ├── configure_user.py         # 用户配置脚本
│   ├── setup_user_config.py      # 用户配置设置
│   ├── install_dependencies.py   # 依赖安装脚本
│   └── setup_openbb_config.py    # OpenBB配置脚本
├── tests/                         # 测试文件
│   ├── test_alltick_collector.py # AllTick收集器测试
│   ├── test_flexible_alltick.py  # 灵活版AllTick测试
│   └── [其他测试文件]
├── docs/                          # 文档
│   ├── AGENT.md                  # 协同开发文档
│   ├── DEPENDENCIES.md           # 依赖库文档
│   ├── TEAM_STRUCTURE.md         # 团队分工方案
│   ├── user_setup_guide.md       # 用户配置指南
│   ├── ALLTICK_INTEGRATION.md    # AllTick集成文档
│   ├── PROJECT_STRUCTURE.md      # 项目结构文档
│   └── [其他文档]
├── user_configs/                  # 用户配置
│   ├── secure_config_manager.py  # 安全配置管理
│   └── [用户配置文件]
├── main.py                        # 主程序入口
├── main_secure_user_support.py    # 支持多用户的主程序
├── run_alltick_analysis.py        # AllTick分析运行脚本
├── README.md                      # 项目说明
├── PROMPT.md                      # AlphaFlow协议
├── requirements.txt               # 依赖列表
└── setup_new_user.sh              # 新用户设置脚本
```

## 核心组件说明

### 1. alphaflow/core/
- **base.py**: 定义了所有组件的基类，包括`BaseCollector`、`BaseProcessor`等
- **schema.py**: 定义了数据模型，包括`ResearchPack`、`DataFrameModel`等

### 2. alphaflow/components/
- **collectors/**: 数据收集器，负责从不同数据源获取数据
- **processors/**: 数据处理器，负责对数据进行分析和处理
- **visualizers/**: 数据可视化器，负责生成图表和报告

### 3. alphaflow/engine/
- **pipeline.py**: 定义了研究管道，负责协调各个组件的执行顺序

### 4. alphaflow/utils/
- **cache.py**: 提供磁盘缓存功能
- **quickchart.py**: 提供图表生成功能
- **user_config.py**: 提供用户配置管理功能

## 使用指南

### 运行分析
```bash
# 基础分析
python3 main_secure_user_support.py --symbols AAPL --user-id my_user

# AllTick分析
python3 run_alltick_analysis.py --symbols AAPL --user-id my_user

# 配置用户API密钥
python3 scripts/configure_user.py --user-id my_user
```

### 测试
```bash
# 测试AllTick收集器
python3 tests/test_flexible_alltick.py
```

## 扩展性设计

### 添加新的数据收集器
1. 在`alphaflow/components/collectors/`目录下创建新收集器
2. 继承`BaseCollector`类
3. 实现`fetch_data`方法
4. 使用`ResearchPack`作为数据容器

### 添加新的数据处理器
1. 在`alphaflow/components/processors/`目录下创建新处理器
2. 继承`BaseProcessor`类
3. 实现`process`方法
4. 使用`ResearchPack`作为数据容器

## 安全性
- 用户API密钥使用加密存储
- 支持多用户隔离
- 敏感信息不在日志中明文显示