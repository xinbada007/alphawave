# 🌊 AlphaFlow Framework (v1.1)
**工业级金融投研异步协作框架**

AlphaFlow 是一个专为 **Vibe Coding** 设计的插件化投研框架，旨在实现多人并行开发、数据深度解耦。

---

## 🏗️ 1. 协作架构 (Collaborative Architecture)

为了支持 5-7 人团队，AlphaFlow v1.2 将采集器进行了**水平切分**：

### 1.1 数据采集端 (Collectors)
- **股价采集 (Fixed)**: 基于 OpenBB/yfinance 的标准化获取。维护者需确保 OHLCV 的绝对准确。
- **经营分析 (Semi-Fixed)**: 抓取财报指标、经营数据。维护者需关注字段映射的完整性。
- **消息聚合 (Flexible)**: 依赖爬虫、搜索或社交媒体。允许高度灵活性和局部失效。

### 1.2 逻辑处理端 (Processors)
- **技术面分析**: 计算 RSI, MA 等标准因子。
- **量化策略/模型**: 基于 `ResearchPack` 进行深度特征工程。

---

## 🛠️ 2. 多人协作开发流程

### 角色分配示例：
- **开发者 A**: 编写 `market_data.py` (保证生肉供应)。
- **开发者 B**: 编写 `fundamental.py` (增加财报维度)。
- **开发者 C**: 编写 `rsi_processor.py` (增加动量因子)。

### Vibe Coding 操作指南：
1. **喂入协议**: 给 LLM 发送 `alphaflow/PROMPT.md`。
2. **定义任务**: "为 AlphaFlow 写一个 [Collector/Processor]。只负责处理 ResearchPack 中的 [某个字段]。"
3. **独立测试**: 运行 `main.py` 验证你的字段是否出现在最终的 JSON 报告中。

---

## 🔐 3. 多用户安全配置 (Multi-User Security)

### 3.1 用户API密钥管理
AlphaFlow现在支持多用户协同使用，每个用户可以配置自己的API密钥：

#### 设置用户配置
```bash
# 交互式设置用户API密钥
python3 configure_user.py --user-id <your_user_id>

# 查看用户配置（敏感信息会被隐藏）
python3 configure_user.py --user-id <your_user_id> --action show
```

#### 运行分析
```bash
# 使用指定用户配置运行分析
python3 main_secure_user_support.py --symbols NVDA AAPL TSLA --user-id <your_user_id>

# 使用AllTick API进行分析
python3 run_alltick_analysis.py --symbols AAPL GOOGL MSFT --user-id <your_user_id>

# 运行AllTick测试
python3 tests/test_flexible_alltick.py
```

### 3.2 安全特性
- **加密存储**: 用户API密钥使用加密算法进行安全存储
- **用户隔离**: 每个用户拥有独立的配置文件（`user_configs/<user_id>.json`）
- **环境变量支持**: 支持通过环境变量`CONFIG_PASSWORD`设置加密密码
- **兼容性**: 支持无加密库环境的降级运行

---

## 🔌 4. 关键特性 (Key Features)

- **🚀 自动降采样**: 无论数据量多大，`QuickChartClient` 会自动将其压缩至 250 点以内，保留趋势并确保 URL 永不超限。
- **🛡️ 异步容错**: 任何一个组件崩溃，Pipeline 会捕获异常并返回当前的 `ResearchPack`，不会中断整体流程。
- **💾 智能缓存**: `OpenBBCollector` 自带 24 小时磁盘缓存，避免因频繁调用 yfinance 导致的 `RateLimitError`。
- **🌐 全局代理**: 支持 SOCKS5 代理。只需在启动时传入 `--proxy`，所有底层库（OpenBB, Requests）都会自动走代理。
- **👥 多用户支持**: 支持多用户协同使用，每个用户可配置自己的API密钥

---

## 🚀 5. MVP 快速开始 (Usage)

### 环境准备
```bash
# 安装基础依赖
pip3 install -r requirements.txt

# 安装金融数据扩展
pip3 install openbb-yfinance openbb-equity openbb-technical

# 安装安全加密库（推荐）
pip3 install cryptography
```

### 首次运行设置
```bash
# 为用户设置API密钥
python3 scripts/configure_user.py --user-id my_user_id

# 运行基准测试
python3 main_secure_user_support.py --symbols NVDA --user-id my_user_id

# 运行AllTick分析
python3 run_alltick_analysis.py --symbols AAPL --user-id my_user_id
```

### 项目目录结构
```
alphawave/                 # AlphaFlow核心框架
├── alphaflow/            # 核心组件
│   ├── core/            # 核心基类和数据模型
│   ├── components/      # 可插拔组件
│   │   ├── collectors/  # 数据收集器
│   │   ├── processors/  # 数据处理器  
│   │   └── visualizers/ # 数据可视化器
│   ├── engine/          # 管道引擎
│   └── utils/           # 工具函数
├── scripts/             # 脚本文件
├── tests/               # 测试文件
├── docs/                # 文档
├── user_configs/        # 用户配置
├── main.py              # 主程序入口
├── main_secure_user_support.py # 支持多用户的主程序
├── run_alltick_analysis.py   # AllTick分析脚本
└── setup_new_user.sh         # 新用户设置脚本
```

### 预期输出
程序将输出一个包含全维度投研信息的 JSON 结构：
```json
{
  "symbol": "NVDA",
  "charts": { "main": "https://quickchart.io/chart/render/sf-xxx" },
  "fundamentals": { "pe_ratio": 75.2, ... },
  "news": [ ... ],
  "technicals": { "rsi": 65.4, ... }
}
```

---

## 🔌 4. 核心特性
- **🛡️ 强鲁棒性**: 经营面和消息面组件采用“静默失败”策略，确保核心股价分析不中断。
- **💾 共享缓存**: 所有 Collector 共享 `.cache` 目录，避免团队重复请求触发 API 限制。
- **🌐 统一代理**: 通过 `--proxy` 参数一键注入全局 SOCKS5 代理。
- **📊 智能压缩**: 自动将金融序列降采样至 250 点，保留最新价格，确保 QuickChart 短链接生成成功。

---

## ⚠️ 5. 开发者契约
1. **不破环数据总线**: 严禁在组件间传递非 `ResearchPack` 对象。
2. **防御性初始化**: 始终使用标准的解包逻辑处理 `input_data`。
3. **保持原子性**: 一个文件只解决一个问题，方便 AI 理解与维护。
