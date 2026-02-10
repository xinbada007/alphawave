import asyncio
import argparse
import json
from alphaflow.core.schema import AnalysisContext
from alphaflow.core.context import GlobalContext
from alphaflow.engine.pipeline import ResearchPipeline

# 导入拆分后的 Collector
from alphaflow.components.collectors.market_data import EquityPriceCollector
from alphaflow.components.collectors.fundamental import FundamentalCollector
from alphaflow.components.collectors.news import NewsCollector

# 导入加工与展示组件
from alphaflow.components.processors.technicals import TechnicalProcessor
from alphaflow.components.visualizers.charting import QuickChartVisualizer

async def main():
    parser = argparse.ArgumentParser(description="AlphaFlow Production Pipeline")
    parser.add_argument("--symbols", nargs="+", default=["AAPL"], help="List of symbols")
    parser.add_argument("--proxy", type=str, help="Proxy URL (e.g., socks5://127.0.0.1:1080)")
    args = parser.parse_args()

    # 1. 配置全局环境
    context = AnalysisContext(symbols=args.symbols)
    global_ctx = GlobalContext()
    if args.proxy:
        global_ctx.set('PROXY', args.proxy)
        global_ctx.apply_proxy()
    
    # 2. 构建多维度投研管道
    # 架构理念：Collector 链式调用，不断丰富 ResearchPack 的维度
    pipeline = ResearchPipeline(context)
    
    (pipeline.add_step(EquityPriceCollector("MarketFetcher"))      # 维度 1: 股价 (必备)
             .add_step(FundamentalCollector("BizFetcher"))         # 维度 2: 经营面
             .add_step(NewsCollector("NewsFetcher"))               # 维度 3: 消息面
             .add_step(TechnicalProcessor("IndicatorProcessor"))   # 维度 4: 技术面加工
             .add_step(QuickChartVisualizer("ChartGen")))          # 维度 5: 可视化渲染

    # 3. 执行
    results = await pipeline.run()

    # 4. 结构化输出
    print("\n" + "=" * 50)
    print(f"📊 PIPELINE SUMMARY")
    print("=" * 50)

    for i, result in enumerate(results):
        step_name = pipeline.steps[i].name if i < len(pipeline.steps) else "Unknown"
        status = "✅" if result.success else "❌"
        err = f" ({result.error})" if result.error else ""
        print(f"  {status} Step {i+1}: {step_name}{err}")

    # 取最后一个成功的结果
    success_results = [r for r in results if r.success]
    if success_results:
        pack = success_results[-1].payload
        print(f"\n🚀 RESEARCH REPORT: {pack.symbol}")
        print("=" * 50)
        print(pack.model_dump_json(indent=2))
    else:
        print("\n❌ All steps failed. No report generated.")

if __name__ == "__main__":
    asyncio.run(main())
