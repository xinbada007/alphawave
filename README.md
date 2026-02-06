# 🌊 AlphaFlow Framework (v1.2)
**工业级金融投研异步协作框架**

AlphaFlow 是一个专为 **Vibe Coding**（AI 辅助编程）设计的模块化投研框架。它在 E2B 沙箱中运行，深度集成 OpenBB Platform v4 数据，并通过 QuickChart 生成极简的投研图表短链接。本框架核心理念是“水平切分、职责单一、全量数据包流转”。

---

## 🏗️ 1. 协作架构 (Collaborative Architecture)

为了支持 5-7 人团队的高效协作，AlphaFlow v1.2 将采集器与处理器进行了深度**水平切分**，确保每个组件逻辑独立、易于 AI 编写。

### 1.1 数据采集端 (Collectors) - `alphaflow/components/collectors/`
- **股价采集 (Fixed)**: `market_data.py`。基于 OpenBB/yfinance 获取标准化 OHLCV 数据。维护者需确保核心行情绝对准确。
- **经营分析 (Semi-Fixed)**: `fundamental.py`。获取 PE/PB/ROE 及财报快照。维护者需关注字段映射的完整性。
- **消息聚合 (Flexible)**: `news.py`。处理新闻、公告、社交媒体等非结构化数据。允许局部失效，采用“静默失败”策略。

### 1.2 逻辑处理端 (Processors) - `alphaflow/components/processors/`
- **技术指标分析**: `technicals.py`。负责从 `ResearchPack` 中读取行情并计算 RSI, SMA 等因子，实现数据增广。
- **因子/模型分析**: 支持团队成员扩展自定义因子（如动量、价值、AI 特征工程）。

---

## 🛠️ 2. 多人协作开发流程 (Vibe Coding)

### 角色分配与分工：
- **开发者 A (基建)**: 维护核心股价采集，解决频率限制和缓存逻辑。
- **开发者 B (量化)**: 编写技术指标和量化逻辑组件。
- **开发者 C (舆情)**: 开发爬虫或接入新的新闻/推特数据源。

### 操作指南：
1. **同步协议**: 向你的 LLM 发送 `alphaflow/PROMPT.md`。
2. **定义任务**: "为 AlphaFlow 写一个 [Collector/Processor]。只负责处理 ResearchPack 中的 [特定槽位]。"
3. **独立测试**: 运行 `main.py` 验证你的字段是否出现在最终的 JSON 报告中。

---

## 🔐 3. 安全与多用户管理 (Security & Multi-User)

AlphaFlow 继承了强大的安全特性，支持多用户协同使用，并对敏感 API 密钥进行加密管理。

### 3.1 用户配置管理
```bash
# 设置/更新用户API密钥（交互式）
python3 scripts/configure_user.py --user-id <user_id>

# 查看配置状态
python3 scripts/configure_user.py --user-id <user_id> --action show
```

### 3.2 运行分析
```bash
# 使用主程序运行
python3 main.py --symbols NVDA --proxy socks5://...

# 使用多用户安全版运行
python3 main_secure_user_support.py --symbols AAPL --user-id <user_id>
```

---

## 🔌 4. 核心特性 (Key Features)

- **📦 ResearchPack**: 统一的万能数据包，所有组件以此为契约进行数据交换。
- **🛡️ 强鲁棒性**: 采用异步 Pipeline 模式，非核心组件报错不中断流程，保证“生肉（股价）”始终能被处理。
- **💾 智能缓存**: `DiskCache` 机制缓存 24 小时数据，规避 API 频率限制，提升团队协作响应速度。
- **🌐 统一代理**: 通过 `--proxy` 参数或环境变量 `ALPHAFLOW_PROXY` 一键注入全局 SOCKS5 代理。
- **📊 智能压缩**: 自动将金融序列降采样至 250 点，保留最新价格，确保 QuickChart 短链接生成 100% 成功。

---

## 🚀 5. 快速开始 (Getting Started)

### 环境准备
```bash
pip3 install -r requirements.txt
# 确保安装 OpenBB 核心扩展
pip3 install openbb-yfinance openbb-equity openbb-technical
```

### 运行基准测试
```bash
python3 main.py --symbols NVDA --proxy socks5://127.0.0.1:10800
```

### 目录结构预览
```text
/data/openbb/
├── alphaflow/            # 核心框架目录
│   ├── core/            # 数据契约 (schema.py) 与基类 (base.py)
│   ├── components/      # 插件化组件 (Collectors, Processors, Visualizers)
│   ├── engine/          # 异步执行引擎 (pipeline.py)
│   └── utils/           # 基础设施 (cache.py, quickchart.py)
├── main.py              # 极简入口 (支持 v1.2 拆分架构)
├── main_secure_user_support.py # 安全增强入口
├── PROMPT.md            # Vibe Coding 开发者协议
└── README.md            # 本说明文件
```

---

## ⚠️ 6. 开发者契约
1. **类型安全**: 严禁在组件间直接传递原始 DataFrame，必须使用 `DataFrameModel`。
2. **初始化规范**: 必须在 `execute` 开始处包含标准的解包逻辑（见 `PROMPT.md`）。
3. **职责边界**: 一个 Collector 只负责一个数据维度，一个 Processor 只负责一类算法，保持代码高度内聚。