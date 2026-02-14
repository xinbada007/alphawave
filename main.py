import asyncio
import argparse
import requests

from alphaflow.components.collectors.market_data import MarketDataCollector
from alphaflow.core.schema import AnalysisContext
from alphaflow.core.context import GlobalContext
from alphaflow.engine.pipeline import ResearchPipeline

# 导入拆分后的 Collector (在代理设置后导入)
from alphaflow.components.collectors.fundamental import FundamentalCollector
from alphaflow.components.collectors.news import NewsCollector

# 导入加工与展示组件
from alphaflow.components.processors.technicals import TechnicalProcessor
from alphaflow.components.visualizers.charting import QuickChartVisualizer


def upload_to_file_io(pack_data: str) -> str:
    """使用 tmpfiles.org 将数据作为文本文件上传并返回短链接"""
    file_path = "last_research_pack.txt"
    try:
        # 1. 先存为文本文件作为备份
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(pack_data)

        # 2. 调用 tmpfiles.org API
        url = "https://tmpfiles.org/api/v1/upload"
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files, timeout=60)

        # 3. 解析返回: {"status":"success","data":{"url":"..."}}
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "success":
                # 注意：返回的 URL 是下载页链接
                return res_json.get("data", {}).get("url", "No URL in response")
            else:
                return f"Upload failed: {res_json.get('message', 'Unknown error')}"
        else:
            return f"Server Error {response.status_code}. Local backup: {file_path}"

    except Exception as e:
        return f"Upload error: {str(e)}. Data saved locally as {file_path}"


async def main():
    parser = argparse.ArgumentParser(description="AlphaFlow Production Pipeline")
    parser.add_argument(
        "--symbols", nargs="+", default=["AAPL"], help="List of symbols"
    )
    parser.add_argument(
        "--days", type=int, default=250, help="Number of trading days to fetch"
    )
    parser.add_argument(
        "--proxy", type=str, help="Proxy URL (e.g., socks5://127.0.0.1:1080)"
    )
    args = parser.parse_args()

    # 1. 配置全局环境
    context = AnalysisContext(
        symbols=args.symbols,
        metadata={"days": args.days},  # 将交易日需求存入元数据
    )
    global_ctx = GlobalContext()
    if args.proxy:
        global_ctx.set("PROXY", args.proxy)
        global_ctx.apply_proxy()

    # 2. 构建多维度投研管道
    # 架构理念：Collector 链式调用，不断丰富 ResearchPack 的维度
    pipeline = ResearchPipeline(context)

    (
        pipeline.add_step(
            MarketDataCollector("MarketDataFetcher", config={"provider": "yfinance"})
        ).add_step(FundamentalCollector("CoreDataFetcher"))
        # pipeline.add_step(
        #     FundamentalCollector("CoreDataFetcher")
        # ).add_step(  # 维度 1: 股价 + 经营面 (核心金融数据)
        #     NewsCollector("NewsFetcher")
        # )  # 维度 2: 消息面 (舆情与情绪)
        # .add_step(TechnicalProcessor("IndicatorProcessor"))  # 维度 3: 技术面加工
        # .add_step(QuickChartVisualizer("ChartGen"))
    )  # 维度 4: 可视化渲染

    # 3. 执行
    results = await pipeline.run()

    # 4. 结构化输出
    print("\n" + "=" * 10)
    print("📊 PIPELINE SUMMARY")
    print("=" * 10)

    for i, result in enumerate(results):
        step_name = pipeline.steps[i].name if i < len(pipeline.steps) else "Unknown"
        status = "✅" if result.success else "❌"
        err = f" ({result.error})" if result.error else ""
        print(f"  {status} Step {i + 1}: {step_name}{err}")

    # 取最后一个成功的结果
    success_results = [r for r in results if r.success]
    if success_results:
        pack = success_results[-1].payload
        name_str = f" ({pack.name})" if pack.name else ""

        print(f"\n🚀 ALPHAFLOW RESEARCH REPORT: {pack.symbol}{name_str}")
        print("=" * 10)

        # 1. 核心金融数据 (Fundamental Data)
        if pack.fundamentals:
            print("📊 [FUNDAMENTALS]")
            # 兼容不同 Provider 的命名 (marketCap vs market_cap)
            m_cap = pack.fundamentals.get("marketCap") or pack.fundamentals.get(
                "market_cap", "N/A"
            )
            pe = pack.fundamentals.get("peRatio") or pack.fundamentals.get(
                "pe_ratio", "N/A"
            )

            if isinstance(m_cap, (int, float)):
                m_cap = f"${m_cap:,.0f}"
            print(f"   Market Cap: {m_cap}")
            print(f"   PE Ratio  : {pe}")

        # 2. 市场情绪 (News Vibe - 深度利用 news.py)
        news_ov = pack.extra.get("news_overview", {})
        if news_ov:
            print("\n🎭 [MARKET VIBE]")
            sentiment = news_ov.get("综合情绪判定", "N/A")
            avg_score = news_ov.get("平均情感得分", 0)
            print(f"   Overall Sentiment: {sentiment}")
            print(f"   Sentiment Score  : {avg_score:+.4f}")

            conclusion = pack.extra.get("news_conclusion", "")
            if conclusion:
                # 打印结论的第一行（最核心的一句）
                main_concl = conclusion.split("\n")[0].strip()
                print(f"   Key Insight: {main_concl}")

        # 3. 技术指标 (Technicals)
        if pack.technicals:
            print("\n📈 [TECHNICAL INDICATORS]")
            df_tech = pack.technicals.to_df()
            if not df_tech.empty:
                latest = df_tech.iloc[-1]
                for col in ["rsi", "sma_20"]:
                    if col in latest:
                        print(f"   {col.upper():<7}: {latest[col]:.2f}")

        # 4. 可视化链接 (Visualizers)
        if pack.charts:
            print("\n🔗 [VISUALIZATION]")
            for name, url in pack.charts.items():
                print(f"   {name}: {url}")

        # 5. 原始数据上传 (Optimized for Cloud LLMs)
        print("\n📦 [DATA FOR CLOUD LLM]")
        print("-" * 10)
        full_json = pack.model_dump_json(indent=2)
        print("   Uploading full research pack to file.io...")
        short_link = upload_to_file_io(full_json)
        print(f"   SHORT LINK: {short_link}")
        print("   (Note: This link is valid for 60 mins.)")

        print("=" * 10)
        print(
            "Disclaimer: Analysis generated by AlphaFlow Agent. Not financial advice."
        )
    else:
        print("\n❌ All steps failed. No report generated.")


if __name__ == "__main__":
    asyncio.run(main())
