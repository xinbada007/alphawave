import asyncio
from typing import List, Any, TypeVar, Generic, Optional
from alphaflow.core.base import BaseComponent
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack
from alphaflow.core.context import GlobalContext

# 🚀 V3 架构升级：泛型流水线类型变量
T_payload = TypeVar("T_payload")


class ResearchPipeline(Generic[T_payload]):
    """
    泛型核心执行引擎 (V3 架构升级)。
    
    负责按顺序执行组件，并管理数据流转。
    通过泛型参数 T_payload 保证全链路的类型安全。

    容错策略：
      - 单步失败不中断整条管道
      - 失败步骤的 payload 不传递给下游，改用上一次成功的 payload
      - 所有步骤执行完毕后，汇总成功/失败情况
    """

    def __init__(self, context: AnalysisContext):
        self.context = context
        # 组件列表可以是任何 Component，但运行时我们期待它们处理 T_payload
        self.steps: List[BaseComponent[T_payload]] = []
        self.global_ctx = GlobalContext()

    def add_step(self, component: BaseComponent[T_payload]) -> 'ResearchPipeline[T_payload]':
        """
        添加一个处理步骤，并保持类型链式调用。
        
        Returns:
            ResearchPipeline[T_payload]: 支持链式调用的流水线实例
        """
        self.steps.append(component)
        return self

    async def run(self, initial_payload: Optional[T_payload] = None) -> List[ComponentOutput[T_payload]]:
        """
        运行管道。
        Data Flow: Step 1 Output -> Step 2 Input -> ...
        
        返回的 List 中，每一个 Output 的 payload 都会被 IDE 推断为 T_payload (如 ResearchPack)。

        容错：单步失败时打印警告并继续，不中断后续步骤。
        
        Args:
            initial_payload: 初始输入数据（通常是 ResearchPack）
            
        Returns:
            List[ComponentOutput[T_payload]]: 所有步骤的执行结果列表
        """
        results: List[ComponentOutput[T_payload]] = []
        # 🚀 修正：last_good_data 始终保存最纯净的荷载对象 (如 ResearchPack 实例)
        last_good_data: Optional[T_payload] = initial_payload

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

                # 2. Execute —— 传入 last_good_data（而非上一步的原始输出）
                # 🚀 执行类型链：output 的类型被精确推断为 ComponentOutput[T_payload]
                output: ComponentOutput[T_payload] = await step.execute(
                    self.context, input_data=last_good_data
                )
                results.append(output)

                if output.success:
                    # ✅ 修正：提取纯净荷载（ResearchPack），而不是整个 Output 对象
                    last_good_data = output.payload
                    succeeded += 1
                    print(f"  {step_label} ✅ {step.name} succeeded.")
                else:
                    # ⚠️ 失败（组件自己返回了 success=False）
                    # 不更新 last_good_data，下一步继续用之前的数据
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
                # 🚀 修正：payload=last_good_data（始终是 T_payload 类型）
                results.append(ComponentOutput[T_payload](
                    success=False, 
                    error=err_msg, 
                    payload=last_good_data
                ))
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
