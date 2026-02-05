import asyncio
import argparse
import json
from alphaflow.core.schema import AnalysisContext
from alphaflow.core.context import GlobalContext
from alphaflow.engine.pipeline import ResearchPipeline
from alphaflow.components.collectors.basic import OpenBBCollector
from alphaflow.components.processors.technicals import RSIProcessor
from alphaflow.components.visualizers.charting import QuickChartVisualizer

async def main():
    parser = argparse.ArgumentParser(description="AlphaFlow CLI")
    parser.add_argument("--symbols", nargs="+", default=["AAPL"], help="List of symbols")
    parser.add_argument("--proxy", type=str, help="Proxy URL (e.g., socks5://127.0.0.1:1080)")
    args = parser.parse_args()

    # 1. 初始化上下文
    context = AnalysisContext(symbols=args.symbols)
    global_ctx = GlobalContext()
    
    if args.proxy:
        global_ctx.set('PROXY', args.proxy)
        global_ctx.apply_proxy()
    
    # 2. 构建管道
    pipeline = ResearchPipeline(context)
    
    (pipeline.add_step(OpenBBCollector("DataFetcher"))
             .add_step(RSIProcessor("TechAnalysis"))
             .add_step(QuickChartVisualizer("ChartGen")))

    # 3. 运行
    results = await pipeline.run()

    # 4. 输出结果 (给 LLM 看的)
    if results and results[-1].success:
        pack = results[-1].payload
        if hasattr(pack, 'model_dump_json'):
            print("\n--- FINAL RESEARCH PACK ---")
            # 导出为 JSON，方便大模型解析
            # 这里我们只展示概要，避免由于 DataFrame 太大导致输出溢出
            # 但实际上 ResearchPack 已经包含了所有信息
            print(pack.model_dump_json(indent=2))
        else:
             print(json.dumps(results[-1].dict(), default=str, indent=2))
    else:
        print("\n--- PIPELINE FAILED ---")
        for res in results:
            if not res.success:
                print(f"Error: {res.error}")

if __name__ == "__main__":
    asyncio.run(main())
