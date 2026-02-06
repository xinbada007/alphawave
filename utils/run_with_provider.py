#!/usr/bin/env python3
"""
修改版的运行脚本，强制使用特定提供商
"""

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
    parser = argparse.ArgumentParser(description="AlphaFlow CLI with Provider Selection")
    parser.add_argument("--symbols", nargs="+", default=["AAPL"], help="List of symbols")
    parser.add_argument("--provider", type=str, default="yfinance", choices=["yfinance", "polygon", "fmp", "av"], help="Data provider to use")
    parser.add_argument("--proxy", type=str, help="Proxy URL (e.g., socks5://127.0.0.1:1080)")
    args = parser.parse_args()

    print(f"🚀 Running AlphaFlow with provider: {args.provider}")
    print(f"📊 Symbols: {args.symbols}")

    # 1. 初始化上下文
    context = AnalysisContext(symbols=args.symbols)
    global_ctx = GlobalContext()
    
    if args.proxy:
        global_ctx.set('PROXY', args.proxy)
        global_ctx.apply_proxy()
    
    # 2. 构建管道
    pipeline = ResearchPipeline(context)
    
    # 设置提供商参数
    collector = OpenBBCollector("DataFetcher")
    collector.provider = args.provider  # 尝试设置提供商
    
    (pipeline.add_step(collector)
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