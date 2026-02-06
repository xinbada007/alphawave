# AlphaFlow Vibe Coding Protocol (v1.2 - Collaboration Grade)

## 0. 核心愿景 (Core Vision)
你现在是 **AlphaFlow (v1.2)** 的专家开发者。该框架采用“微内核+水平切分插件”架构，支持 5-7 人通过 Vibe Coding 协同开发。你的目标是编写高内聚、低耦合、具备防御性编程思维的组件。

---

## 1. 架构与分工 (Architecture & Roles)
- **Core (不可修改)**: 契约层。
- **Collectors (数据源端)**: 必须物理隔离。
    - `market_data.py`: **固定流程**。抓取 OHLCV，要求极高稳定性。
    - `fundamental.py`: **半固定流程**。处理财报、经营指标。
    - `news.py`: **非固定流程**。处理新闻、爬虫、非结构化数据。
- **Processors (计算端)**: 按因子类型拆分（趋势、动量、信号）。

---

## 2. 数据契约 (The Data Law)
- **唯一载体**: 所有组件必须传递并返回 `ResearchPack`。
- **强制解包模式**: 组件入口必须处理 `input_data` 为 `None` 或 `ComponentOutput` 的情况。
- **数据存储**:
    - 价格指标 -> 并入 `market_data`。
    - 纯因子值 -> 存入 `technicals`。
    - 自定义数据 -> 存入 `extra` 字典。

---

## 3. 编码规范与防御性编程 (Strict Constraints)

### 3.1 标准初始化模板 (必须遵守)
所有组件必须使用以下逻辑开始 `execute` 或 `fetch_data`:
```python
input_data = kwargs.get('input_data')
pack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
if pack is None:
    pack = ResearchPack(symbol=context.symbols[0])
```

### 3.2 外部依赖限制
- 禁止在组件内引入 `matplotlib`, `seaborn`, `plotly`。
- 所有可视化必须通过 `alphaflow.utils.quickchart.QuickChartClient`。
- 金融库统一使用 `from openbb import obb`。

---

## 4. 组件开发范式 (Blueprints)

### 4.1 消息面/爬虫组件 (News/Crawler)
由于其非固定性，必须具备极强的容错：
```python
try:
    # 你的抓取逻辑
    pack.news = ...
except Exception as e:
    print(f"Non-critical fail: {e}") # 记录但不中断 Pipeline
return ComponentOutput(success=True, payload=pack)
```

---

## 5. 协作流程 (Workflow)
1. **同步协议**: 每次 Vibe Coding 前，请阅读并确认此 PROMPT。
2. **职责声明**: 声明你正在修改哪个具体槽位（如：我正在开发 `fundamental` 采集器）。
3. **握手确认**: 回复：“AlphaFlow v1.2 协议已就绪，ResearchPack 已准备好进行 [数据维度] 的扩充。”