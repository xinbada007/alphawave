# 🌊 AlphaFlow Framework (v1.2)
**工业级金融投研异步协作框架**

AlphaFlow 是一个专为 **Vibe Coding**（AI 辅助编程）设计的模块化投研框架。它在 E2B 沙箱中运行，深度集成 OpenBB Platform v4 和 AkShare 数据，并通过 QuickChart 生成极简的投研图表短链接。

**v1.2 核心升级：** 实现了**Market Data**与**Fundamental**的彻底解耦，引入了**Fetcher 策略模式**，原生支持**港股/A股 (AkShare)**与**美股 (OpenBB)**的无缝切换与全维度数据榨取。

---

## 🏗️ 1. 协作架构 (Collaborative Architecture)

为了支持 5-7 人团队的高效协作，AlphaFlow v1.2 将采集器与处理器进行了深度**水平切分**，并引入了“增量式 Payload 链”设计。

### 1.1 数据采集端 (Collectors) - `alphaflow/components/collectors/`
- **股价采集 (MarketDataCollector)**: 
    - **职责**: 专职负责 OHLCV 及交易统计数据（换手率、振幅、VWAP）的获取。
    - **策略模式**: 
        - `AkSharePriceFetcher`: 港股/A股原生支持，字段全量映射。
        - `OpenBBPriceFetcher`: 美股/全球市场支持，保留 Split/Dividend 原始数据。
- **经营分析 (FundamentalCollector)**: 
    - **职责**: 获取财报（IS/BS/CF）及估值指标（PE/PB/ROE）。
    - **解耦**: 不再自行抓取价格，而是复用上游 `ResearchPack.market_data`，实现了“一次抓取，多次复用”。
- **消息聚合 (NewsCollector)**: 
    - **职责**: 处理新闻、公告、社交媒体等非结构化数据。允许局部失效，采用“静默失败”策略。

### 1.2 逻辑处理端 (Processors) - `alphaflow/components/processors/`
- **技术指标分析**: `technicals.py`。负责从 `ResearchPack` 中读取行情并计算 RSI, SMA 等因子，实现数据增广。
- **因子/模型分析**: 支持团队成员扩展自定义因子（如动量、价值、AI 特征工程）。

---

## 🛠️ 2. 多人协作开发流程 (Vibe Coding)

### 角色分配与分工：
- **开发者 A (基建)**: 维护 `MarketDataCollector`，确保 Fetcher 策略能覆盖更多市场，并处理 API 频率限制。
- **开发者 B (量化)**: 编写 `FundamentalCollector` 和 `TechnicalProcessor`，专注于指标计算与因子挖掘。
- **开发者 C (舆情)**: 开发爬虫或接入新的新闻/推特数据源。

### 操作指南：
1. **同步协议**: 向你的 LLM 发送 `docs/GEMINI.md` 或 `PROMPT.md`。
2. **定义任务**: "为 AlphaFlow 写一个 [Collector/Processor]。只负责处理 ResearchPack 中的 [特定槽位]。"
3. **独立测试**: 运行 `main.py` 验证你的字段是否出现在最终的 JSON 报告中。

---

## 🔐 3. 安全与多用户管理 (Security & Multi-User)

AlphaFlow 继承了强大的安全特性，支持多用户协同使用，并对敏感 API 密钥进行加密管理和轮询使用。

### 3.1 用户配置管理
```bash
# 设置/更新用户API密钥（交互式）
python3 scripts/configure_user.py --user-id <user_id>

# 查看配置状态
python3 scripts/configure_user.py --user-id <user_id> --action show
```

### 3.2 API轮询系统
AlphaFlow实现了智能API轮询机制，可自动在多个API密钥间轮询使用，有效避免频率限制。

---

## 🔌 4. 核心特性 (Key Features)

- **📦 ResearchPack**: 统一的万能数据包，所有组件以此为契约进行数据交换。
- **🔄 策略路由**: 自动根据 Symbol 后缀（`.HK`, `.SH`, `.SZ`）路由到 AkShare，其他路由到 OpenBB。
- **🔍 深度榨取**: 不仅获取 OHLC，还捕获 `turnover_rate` (换手率), `amplitude` (振幅), `vwap` (成交均价) 等深度特征。
- **🛡️ 强鲁棒性**: 针对仙股/零成交场景有防御性填充逻辑；针对 API 缺失字段有 Fallback 估算机制（如 MCAP 估算）。
- **💾 智能缓存**: `DiskCache` 机制缓存 24 小时数据，提升响应速度。
- **🌐 统一代理**: 通过 `--proxy` 参数或环境变量 `ALPHAFLOW_PROXY` 一键注入全局 SOCKS5 代理。

---

## 🚀 5. 快速开始 (Getting Started)

### 环境准备
```bash
pip3 install -r requirements.txt
# 确保安装 OpenBB 核心扩展
pip3 install openbb-yfinance openbb-equity openbb-technical akshare
```

### 运行基准测试
```bash
# 港股 (AkShare)
python3 main.py --symbols 0700.HK --proxy socks5://127.0.0.1:10800

# 美股 (OpenBB)
python3 main.py --symbols NVDA --proxy socks5://127.0.0.1:10800
```

### 目录结构预览
```text
/data/alphawave/
├── alphaflow/            # 核心框架目录
│   ├── core/            # 数据契约 (schema.py) 与基类 (base.py)
│   ├── components/      # 插件化组件
│   │   ├── collectors/  # [MarketData, Fundamental, News]
│   │   ├── processors/  # [Technicals]
│   │   └── visualizers/ # [Charting]
│   ├── engine/          # 异步执行引擎 (pipeline.py)
│   └── utils/           # 基础设施
├── main.py              # 极简入口 (支持 v1.2 拆分架构)
├── PROMPT.md            # Vibe Coding 开发者协议
└── README.md            # 本说明文件
```

---

## ⚠️ 6. 开发者契约
1. **类型安全**: 严禁在组件间直接传递原始 DataFrame，必须使用 `DataFrameModel`。
2. **初始化规范**: 必须在 `fetch_data` 开始处包含标准的解包逻辑。
3. **职责边界**: 一个 Collector 只负责一个数据维度。`MarketData` 负责 OHLCV，`Fundamental` 负责财报，互不越界。
