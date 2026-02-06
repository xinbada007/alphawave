import asyncio
import argparse
import json
from alphaflow.core.schema import AnalysisContext
from alphaflow.core.context import GlobalContext
from alphaflow.engine.pipeline import ResearchPipeline
from alphaflow.components.collectors.basic import OpenBBCollector
from alphaflow.components.processors.technicals import RSIProcessor
from alphaflow.components.visualizers.charting import QuickChartVisualizer
from alphaflow.utils.user_config import config_manager


async def main():
    parser = argparse.ArgumentParser(description="AlphaFlow CLI with Provider Override")
    parser.add_argument("--symbols", nargs="+", default=["AAPL"], help="List of symbols")
    parser.add_argument("--provider", type=str, default="polygon", help="Data provider (polygon, fmp, yfinance)")
    parser.add_argument("--proxy", type=str, help="Proxy URL (e.g., socks5://127.0.0.1:1080)")
    parser.add_argument("--user-id", type=str, help="User ID to load specific API keys configuration")
    args = parser.parse_args()

    # Setup OpenBB API keys based on user
    try:
        from setup_openbb_config import setup_api_keys
        if args.user_id:
            setup_api_keys(user_id=args.user_id)
        else:
            setup_api_keys()
    except ImportError:
        print("⚠️ OpenBB config setup not found, proceeding with default settings")

    # 1. 初始化上下文
    context = AnalysisContext(symbols=args.symbols)
    global_ctx = GlobalContext()
    
    # Store provider in global context so collectors can access it
    global_ctx.set('DATA_PROVIDER', args.provider)
    
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