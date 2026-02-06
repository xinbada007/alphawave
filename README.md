# 🌊 AlphaFlow Framework (v1.1)
**工业级金融投研异步协作框架**

AlphaFlow 是一个专为 **Vibe Coding**（AI 辅助编程）设计的模块化投研框架。它在 E2B 沙箱中运行，深度集成 OpenBB Platform v4 数据，并通过 QuickChart 生成极简的投研图表短链接。

---

## 🏗️ 1. 架构核心 (Core Philosophy)

### 1.1 核心组件
- **Core (内核)**: 定义了数据法典 (`schema.py`) 和组件契约 (`base.py`)。**禁止修改**。
- **ResearchPack (万能容器)**: 跨组件流转的唯一数据对象。包含行情、技术面、新闻、基本面以及图表 URL。
- **Engine (引擎)**: 异步并行调度器，负责管理 Pipeline 生命周期和容错。

### 1.2 数据流转标准
```text
Collector -> [ResearchPack] -> Processor -> [ResearchPack] -> Visualizer -> [Final JSON]
```
所有组件必须将 `DataFrame` 封装进 `DataFrameModel` 才能在 `ResearchPack` 中传递。

---

## 🛠️ 2. 开发者指南 (Vibe Coding 流程)

团队成员应遵循以下步骤利用 LLM 进行开发：

### 第一步：同步"宪法" (Handshake)
将项目根目录下的 `PROMPT.md` 内容复制并发送给你的 LLM（如 Claude 3.5 或 GPT-4o）。
> **LLM 应回复**: "AlphaFlow v1.1 协议已就绪..."

### 第二步：指令描述 (Tasking)
向 LLM 描述你的业务需求。
> **示例指令**: "帮我写一个 AlphaFlow Processor。利用 OpenBB 计算 20 日布林带 (Bollinger Bands)，并将结果存入 ResearchPack 的 extra 槽位。"

### 第三步：代码部署
将生成的代码保存到对应的插件目录：
- 数据源 -> `alphaflow/components/collectors/`
- 计算逻辑 -> `alphaflow/components/processors/`
- 可视化 -> `alphaflow/components/visualizers/`

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
python3 configure_user.py --user-id my_user_id

# 运行基准测试
python3 main_secure_user_support.py --symbols NVDA --user-id my_user_id
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

## ⚠️ 6. 开发注意事项 (Constraints)
1. **禁止绘图**: 严禁在代码中引入 `matplotlib` 或 `plotly`。
2. **强制 Pydantic**: 必须返回 `ComponentOutput` 对象。
3. **最新数据**: 框架已优化降采样算法，确保无论如何压缩，**最新的价格点**永远会被保留在图表末尾。
4. **扩展性**: 团队成员若要增加自定义数据，请统一放入 `ResearchPack.extra` 字典中。
5. **安全性**: 所有用户敏感信息必须加密存储，不得在代码或日志中明文显示。

---

## 📚 7. 项目文档

- `AGENT.md`: 协同开发文档和最佳实践
- `DEPENDENCIES.md`: 详细的依赖库说明
- `user_setup_guide.md`: 用户配置指南
- `TEAM_STRUCTURE.md`: 团队分工方案

---

## 👥 8. 团队分工 (Team Structure)

### 核心角色分配
- **核心负责人** (1人): 项目整体规划、架构设计、代码审查
- **数据获取组** (2人): 负责股票数据获取（项目重点）
  - 数据源工程师: 集成和维护数据提供商接口
  - 数据质量工程师: 确保数据准确性和一致性
- **功能开发组** (1人): 技术指标计算和可视化
- **安全运维组** (1人): 系统安全和运维保障

### 关键绩效指标
- 数据获取成功率 > 99%
- API响应时间 < 2秒
- 数据准确性 > 99.5%
- 系统可用性 > 99.5%
- API密钥零泄露事件

详情请参阅 `TEAM_STRUCTURE.md` 文件。