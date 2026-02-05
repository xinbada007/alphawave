import asyncio
from typing import List, Any
from alphaflow.core.base import BaseComponent
from alphaflow.core.schema import AnalysisContext, ComponentOutput
from alphaflow.core.context import GlobalContext

class ResearchPipeline:
    """
    AlphaFlow 核心执行引擎。
    负责按顺序执行组件，并管理数据流转。
    """
    def __init__(self, context: AnalysisContext):
        self.context = context
        self.steps: List[BaseComponent] = []
        self.global_ctx = GlobalContext()

    def add_step(self, component: BaseComponent):
        """添加一个处理步骤"""
        self.steps.append(component)
        return self # 支持链式调用

    async def run(self, initial_payload: Any = None) -> List[ComponentOutput]:
        """
        运行管道。
        Data Flow: Step 1 Output -> Step 2 Input -> ...
        """
        results = []
        current_payload = initial_payload

        print(f"[*] Starting Pipeline for symbols: {self.context.symbols}")

        for step in self.steps:
            print(f"  -> Running step: {step.name}...")
            try:
                # 1. Setup
                step.setup()
                
                # 2. Execute
                output: ComponentOutput = await step.execute(self.context, input_data=current_payload)
                results.append(output)

                if output.success:
                    # 将成功的 payload 传递给下一步
                    # 注意：组件需要自己知道如何解析上一步的 payload
                    current_payload = output.payload
                else:
                    print(f"  [!] Step {step.name} failed: {output.error}")
                    # 策略：如果一步失败，通常后续无法进行，这里选择中断
                    break
                
                # 3. Teardown
                step.teardown()

            except Exception as e:
                err_msg = f"Pipeline Crash at {step.name}: {str(e)}"
                print(err_msg)
                results.append(ComponentOutput(success=False, error=err_msg))
                break
        
        print("[*] Pipeline Finished.")
        return results
