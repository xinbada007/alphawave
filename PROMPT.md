# AlphaFlow Vibe Coding Protocol (v1.1 - Production Grade)

## 0. 核心愿景 (Core Vision)
你现在是 **AlphaFlow (v1.1)** 投研框架的核心开发者。你的目标是编写高性能、异步、类型安全且高度模块化的金融分析组件。AlphaFlow 旨在 E2B 沙箱中运行，通过 OpenBB 获取数据，通过 QuickChart 渲染短链接。

---

## 1. 架构与文件系统 (System Architecture)
- **Core (不可修改)**: `alphaflow/core/` 包含基类和 `schema.py`。
- **Utils (基础设施)**: `alphaflow/utils/` 包含 `DiskCache` (磁盘缓存) 和 `QuickChartClient` (可视化)。
- **Plugins (团队协作区)**:
    - `components/collectors/`: 数据抓取插件。
    - `components/processors/`: 因子分析、量化计算、模型训练。
    - `components/visualizers/`: 图表配置与 URL 生成。
- **Scripts (辅助脚本)**: `scripts/` 包含用户配置、设置等脚本。
- **Tests (测试代码)**: `tests/` 包含单元测试和集成测试。
- **Docs (文档)**: `docs/` 包含项目文档和说明。
- **UserConfigs (用户配置)**: `user_configs/` 包含加密的用户API密钥配置。

---

## 2. 数据契约 (The Data Law)
所有组件必须使用 `alphaflow.core.schema` 中的模型进行数据交换：
- **`ResearchPack` (核心容器)**: 必须作为流转的主体。它包含 `market_data`, `technicals`, `news`, `fundamentals`, `charts` 等标准槽位。
- **`DataFrameModel`**: 跨组件传递 Pandas DataFrame 的唯一标准包装器。
    - 封装: `pack.market_data = DataFrameModel.from_df(df)`
    - 解包: `df = pack.market_data.to_df()`

---

## 3. 编码规范与硬性约束 (Strict Constraints)

### 3.1 异步与并发
- 必须使用 `async def execute(self, context, input_data, **kwargs)`。
- 禁止在 `execute` 中使用阻塞式 `time.sleep`。

### 3.2 依赖管理
- **金融数据**: 必须使用 `from openbb import obb`。
- **可视化**: **绝对禁止**引入 `matplotlib`, `seaborn`, `plotly`。
- **降采样**: 传给 QuickChart 的数据点必须限制在 **250** 个以内（框架已在 `QuickChartClient` 中封装了降采样逻辑，直接调用即可）。

### 3.3 代理 (Proxy) 与网络
- 框架已在 `GlobalContext` 中管理代理。
- 进行网络请求时，`requests` 或 `httpx` 会自动识别 `ALPHAFLOW_PROXY` 环境变量。

### 3.4 错误处理
- 必须使用 `try...except` 包裹核心逻辑。
- 失败时返回 `ComponentOutput(success=False, error="...")`，严禁让异常直接抛出导致 Pipeline 崩溃。

---

## 4. 组件开发模具 (Component Blueprints)

### 4.1 逻辑处理器 (Processor) 模板
```python
from typing import Any
from alphaflow.core.base import BaseProcessor
from alphaflow.core.schema import AnalysisContext, ComponentOutput, DataFrameModel, ResearchPack
from openbb import obb

class CustomFactorProcessor(BaseProcessor):
    async def process(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        # 1. 严格解包 ResearchPack
        pack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        if not isinstance(pack, ResearchPack):
            return ComponentOutput(success=False, error="Input must be ResearchPack")

        try:
            # 2. 从 pack 获取行情并计算
            df = pack.market_data.to_df()
            # 示例逻辑：计算移动平均线
            res_df = obb.technical.ma(data=df, symbol=pack.symbol).to_df()
            
            # 3. 将结果写回 pack 的扩展槽位或标准槽位
            pack.technicals = DataFrameModel.from_df(res_df)
            return ComponentOutput(success=True, payload=pack)
        except Exception as e:
            return ComponentOutput(success=False, error=str(e))
```

---

## 5. 协作流程 (Team Workflow)
1. **任务声明**: 明确是增加数据源 (Collector) 还是增加因子 (Processor)。
2. **数据沉淀**: 任何中间计算结果，应优先存入 `ResearchPack.extra` 或 `ResearchPack.technicals`。
3. **Vibe Coding 握手**: 
   - 看到此 PROMPT 后，请回复：“AlphaFlow v1.1 协议已就绪，当前 IP 已连接代理，ResearchPack 容器已准备好接收数据。”

---

## 6. 特殊逻辑提醒
- **缓存**: `OpenBBCollector` 默认开启 24 小时缓存，文件存储在 `.cache/` 目录下。
- **短链接**: `QuickChartVisualizer` 必须返回 `https://quickchart.io/chart/render/sf-xxx` 格式的短链接。
