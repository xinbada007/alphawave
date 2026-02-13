import os
import sys
import json
import asyncio
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List

# 确保可以导入项目内部模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- 0. 提前处理代理 (Early Proxy Setup) ---
def pre_setup_proxy():
    # 尝试从环境变量获取代理
    proxy_url = os.getenv('ALPHAFLOW_PROXY')
    
    # 也可以从命令行解析 --proxy (虽然主要还是靠环境变量)
    for i, arg in enumerate(sys.argv):
        if arg == "--proxy" and i + 1 < len(sys.argv):
            proxy_url = sys.argv[i+1]
            break
    
    if proxy_url:
        if proxy_url.startswith("socks5://"):
            proxy_url = proxy_url.replace("socks5://", "socks5h://")
        for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
            os.environ[key] = proxy_url
        print(f"[*] Probe Proxy Applied: {proxy_url}")

# 必须在导入 OpenBB 之前设置代理
pre_setup_proxy()

from openbb import obb

async def probe_provider(provider: str, symbol: str = "AAPL"):
    print(f"\n{'='*60}")
    print(f"🚀 ALPHAFLOW PROVIDER PROBE: [{provider.upper()}] for {symbol}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 1. 扫描元数据地图
    all_paths = obb.reference.get("paths", {})
    relevant_paths = []

    print(f"[*] Scanning OpenBB reference for {provider} compatible paths...")
    for path, info in all_paths.items():
        # 仅关注股票相关的核心维度
        if not any(cat in path for cat in ["/equity/", "/fundamental/", "/price/"]):
            continue
            
        # 检查该路径是否支持此 provider
        params_str = str(info.get("parameters", {}))
        if provider in params_str:
            relevant_paths.append(path)

    print(f"[*] Found {len(relevant_paths)} potentially compatible paths.\n")

    report = {
        "provider": provider,
        "symbol": symbol,
        "discovery_time": datetime.now().isoformat(),
        "capabilities": []
    }

    # 2. 逐个路径进行深度探测
    for path in sorted(relevant_paths):
        print(f"🔍 Probing: {path} ...", end="", flush=True)
        
        try:
            # 动态调用 OpenBB 路径
            parts = path.strip("/").split("/")
            target = obb
            for part in parts:
                target = getattr(target, part)
            
            # 执行请求
            try:
                res = target(symbol=symbol, provider=provider)
            except Exception:
                # 尝试不带参数或带其他参数，这里为了通用性进行简化
                try:
                    res = target(provider=provider)
                except:
                    raise Exception("Endpoint requires complex parameters")

            # 3. 价值提取与对比
            df = res.to_df()
            raw_results = res.results
            extra_data = res.extra if hasattr(res, 'extra') else {}

            # 提取原始字段名 (通过 Pydantic 模型或字典)
            raw_fields = []
            if raw_results and len(raw_results) > 0:
                item = raw_results[0]
                if hasattr(item, 'model_dump'):
                    raw_fields = list(item.model_dump().keys())
                elif hasattr(item, 'dict'):
                    raw_fields = list(item.dict().keys())
                elif hasattr(item, '__dict__'):
                    raw_fields = list(item.__dict__.keys())
                elif isinstance(item, dict):
                    raw_fields = list(item.keys())

            df_fields = list(df.columns)
            hidden_fields = [f for f in raw_fields if f not in df_fields]

            path_info = {
                "path": path,
                "status": "success",
                "df_rows": len(df),
                "df_cols": len(df_fields),
                "raw_field_count": len(raw_fields),
                "hidden_fields": hidden_fields,
                "extra_keys": list(extra_data.keys()) if extra_data else []
            }
            report["capabilities"].append(path_info)
            print(f" ✅ [{len(raw_fields)} fields]")

            if hidden_fields:
                print(f"     └─ 💎 Found {len(hidden_fields)} hidden fields")

        except Exception as e:
            print(f" ❌ Skip: {str(e)[:40]}...")
            report["capabilities"].append({"path": path, "status": "skipped", "reason": str(e)})

    # 4. 生成报告文件
    output_file = f"probe_{provider}_{symbol}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"🏁 PROBE COMPLETE!")
    print(f"Detailed map saved to: {output_file}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    provider_to_probe = sys.argv[1] if len(sys.argv) > 1 else "yfinance"
    target_symbol = sys.argv[2] if len(sys.argv) > 2 else "AAPL"
    asyncio.run(probe_provider(provider_to_probe, target_symbol))
