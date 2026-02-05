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

### 第一步：同步“宪法” (Handshake)
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

## 🔌 3. 关键特性 (Key Features)

- **🚀 自动降采样**: 无论数据量多大，`QuickChartClient` 会自动将其压缩至 250 点以内，保留趋势并确保 URL 永不超限。
- **🛡️ 异步容错**: 任何一个组件崩溃，Pipeline 会捕获异常并返回当前的 `ResearchPack`，不会中断整体流程。
- **💾 智能缓存**: `OpenBBCollector` 自带 24 小时磁盘缓存，避免因频繁调用 yfinance 导致的 `RateLimitError`。
- **🌐 全局代理**: 支持 SOCKS5 代理。只需在启动时传入 `--proxy`，所有底层库（OpenBB, Requests）都会自动走代理。

---

## 🚀 4. MVP 快速开始 (Usage)

### 环境准备
```bash
pip install -r requirements.txt
# 确保安装了 OpenBB 必备扩展
pip install openbb-yfinance openbb-equity openbb-technical
```

### 运行基准测试 (MVP)
```bash
python main.py --symbols NVDA --proxy socks5://127.0.0.1:10800
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

## ⚠️ 5. 开发注意事项 (Constraints)
1. **禁止绘图**: 严禁在代码中引入 `matplotlib` 或 `plotly`。
2. **强制 Pydantic**: 必须返回 `ComponentOutput` 对象。
3. **最新数据**: 框架已优化降采样算法，确保无论如何压缩，**最新的价格点**永远会被保留在图表末尾。
4. **扩展性**: 团队成员若要增加自定义数据，请统一放入 `ResearchPack.extra` 字典中。
