import asyncio
from typing import List, Any
from alphaflow.core.base import BaseComponent
from alphaflow.core.schema import AnalysisContext, ComponentOutput
from alphaflow.core.context import GlobalContext


class ResearchPipeline:
    """
    AlphaFlow 核心执行引擎。
    负责按顺序执行组件，并管理数据流转。

    容错策略：
      - 单步失败不中断整条管道
      - 失败步骤的 payload 不传递给下游，改用上一次成功的 payload
      - 所有步骤执行完毕后，汇总成功/失败情况
    """

    def __init__(self, context: AnalysisContext):
        self.context = context
        self.steps: List[BaseComponent] = []
        self.global_ctx = GlobalContext()

    def add_step(self, component: BaseComponent):
        """添加一个处理步骤"""
        self.steps.append(component)
        return self  # 支持链式调用

    async def run(self, initial_payload: Any = None) -> List[ComponentOutput]:
        """
        运行管道。
        Data Flow: Step 1 Output -> Step 2 Input -> ...

        容错：单步失败时打印警告并继续，不中断后续步骤。
        """
        results: List[ComponentOutput] = []
        # last_good_payload: 始终保存"最近一次成功步骤"的输出
        # 当某步失败时，下一步仍然可以拿到之前的数据继续工作
        last_good_payload: Any = initial_payload

        succeeded = 0
        failed = 0
        failed_steps: List[str] = []

        print(f"[*] Starting Pipeline for symbols: {self.context.symbols}")
        print(f"    Total steps: {len(self.steps)}")
        print()

        for i, step in enumerate(self.steps, 1):
            step_label = f"[{i}/{len(self.steps)}]"
            print(f"  {step_label} Running step: {step.name}...")

            try:
                # 1. Setup
                step.setup()

                # 2. Execute —— 传入 last_good_payload（而非上一步的原始输出）
                output: ComponentOutput = await step.execute(
                    self.context, input_data=last_good_payload
                )
                results.append(output)

                if output.success:
                    # ✅ 成功：更新 payload，传递给下一步
                    last_good_payload = output
                    succeeded += 1
                    print(f"  {step_label} ✅ {step.name} succeeded.")
                else:
                    # ⚠️ 失败（组件自己返回了 success=False）
                    # 不更新 last_good_payload，下一步继续用之前的数据
                    failed += 1
                    failed_steps.append(step.name)
                    print(f"  {step_label} ⚠️  {step.name} failed: {output.error}")
                    print(f"       → Continuing with previous data...")

                # 3. Teardown
                step.teardown()

            except Exception as e:
                # 💥 异常（组件代码崩溃）
                err_msg = f"{type(e).__name__}: {str(e)}"
                failed += 1
                failed_steps.append(step.name)
                results.append(ComponentOutput(success=False, error=err_msg))
                print(f"  {step_label} 💥 {step.name} crashed: {err_msg}")
                print(f"       → Continuing with previous data...")
                # 不 break，继续执行后续步骤

        # ====== 汇总 ======
        print()
        print(f"[*] Pipeline Finished.")
        print(f"    Results: {succeeded} succeeded, {failed} failed out of {len(self.steps)} steps.")
        if failed_steps:
            print(f"    Failed steps: {failed_steps}")
        print()

        return results
