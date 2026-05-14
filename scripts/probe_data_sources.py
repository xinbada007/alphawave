"""
Phase 0: 数据可得性探针 (Data Availability Probe)
=================================================
对 Volume-Price Anomaly Profile 体系所需的全部上游数据源做一次冒烟测试，
输出 docs/data_availability_matrix.md 作为后续 Phase 1-7 的依据。

不写一行生产代码，仅做调研。
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------
# 探针结果数据结构
# ---------------------------------------------------------------
@dataclass
class ProbeResult:
    name: str
    market: str          # HK / CN / US / GLOBAL
    category: str        # price / event / flow / index
    status: str          # OK / PARTIAL / UNAVAILABLE / RATE_LIMITED / ERROR
    detail: str = ""
    sample_columns: List[str] = field(default_factory=list)
    rows_returned: int = 0
    elapsed_sec: float = 0.0


def _run(name: str, market: str, category: str, fn: Callable[[], Any]) -> ProbeResult:
    """统一执行 + 计时 + 异常包装。返回 ProbeResult。"""
    t0 = datetime.now()
    try:
        out = fn()
        elapsed = (datetime.now() - t0).total_seconds()
        if out is None:
            return ProbeResult(name, market, category, "UNAVAILABLE", "returned None", elapsed_sec=elapsed)
        # 如果返回 (status, detail, cols, rows)
        if isinstance(out, tuple) and len(out) == 4:
            status, detail, cols, rows = out
            return ProbeResult(name, market, category, status, detail, cols, rows, elapsed)
        return ProbeResult(name, market, category, "OK", str(out)[:120], elapsed_sec=elapsed)
    except Exception as e:
        elapsed = (datetime.now() - t0).total_seconds()
        msg = f"{type(e).__name__}: {str(e)[:200]}"
        return ProbeResult(name, market, category, "ERROR", msg, elapsed_sec=elapsed)


# ---------------------------------------------------------------
# AkShare 探针组
# ---------------------------------------------------------------
def probe_akshare(symbols: Dict[str, str]) -> List[ProbeResult]:
    """symbols: {"HK":"00700","CN":"600519"}"""
    import akshare as ak  # type: ignore

    results: List[ProbeResult] = []
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")

    # ============ HK 价格 ============
    def _hk_hist():
        df = ak.stock_hk_hist(symbol=symbols["HK"], period="daily",
                              start_date=start_date, end_date=end_date, adjust="qfq")
        cols = list(df.columns) if df is not None and not df.empty else []
        required = {"成交量", "成交额", "换手率", "振幅"}
        present = required & set(cols)
        if len(present) == len(required):
            return ("OK", f"all required fields present: {sorted(present)}", cols, len(df))
        if present:
            return ("PARTIAL", f"missing: {sorted(required - present)}", cols, len(df))
        return ("UNAVAILABLE", "no required fields", cols, len(df) if df is not None else 0)

    results.append(_run("ak.stock_hk_hist (turnover/amount/amplitude)", "HK", "price", _hk_hist))

    # ============ A 股价格 ============
    def _cn_hist():
        df = ak.stock_zh_a_hist(symbol=symbols["CN"], period="daily",
                                start_date=start_date, end_date=end_date, adjust="qfq")
        cols = list(df.columns) if df is not None and not df.empty else []
        required = {"成交量", "成交额", "换手率", "振幅"}
        present = required & set(cols)
        if len(present) == len(required):
            return ("OK", f"all required fields present", cols, len(df))
        return ("PARTIAL" if present else "UNAVAILABLE",
                f"missing: {sorted(required - present)}", cols, len(df))

    results.append(_run("ak.stock_zh_a_hist (turnover/amount/amplitude)", "CN", "price", _cn_hist))

    # ============ 指数 (港股 HSI) ============
    def _hk_index():
        # 多候选 API 兼容
        for fn_name in ["stock_hk_index_daily_em", "stock_hk_index_daily_sina"]:
            fn = getattr(ak, fn_name, None)
            if fn is None:
                continue
            try:
                df = fn(symbol="HSI")
                if df is not None and not df.empty:
                    return ("OK", f"via {fn_name}, last={df.iloc[-1].to_dict()}",
                            list(df.columns), len(df))
            except Exception as e:
                continue
        return ("UNAVAILABLE", "no HK index API works", [], 0)

    results.append(_run("HK Index (HSI) daily", "HK", "index", _hk_index))

    # ============ 指数 (沪深300) ============
    def _cn_index():
        df = ak.stock_zh_index_daily(symbol="sh000300")
        cols = list(df.columns) if df is not None and not df.empty else []
        if df is not None and not df.empty:
            return ("OK", f"rows={len(df)}", cols, len(df))
        return ("UNAVAILABLE", "empty", cols, 0)

    results.append(_run("CN Index (CSI300) daily", "CN", "index", _cn_index))

    # ============ HK 公告 (配售/供股/增发关键词来源) ============
    # 港股没有专用公告 API，使用 stock_news_em 作为降级路径——
    # 它能返回港股的新闻+公告中文文本流，标题已包含"回购/配售/增发"等关键词
    def _hk_notice():
        # 一级候选: stock_news_em (港股 + A 股通用，免参 .HK 后缀)
        try:
            df = ak.stock_news_em(symbol=symbols["HK"])
            if df is not None and not df.empty:
                return ("OK",
                        f"via stock_news_em (Chinese news+notice stream)",
                        list(df.columns), len(df))
        except Exception:
            pass
        # 二级候选: 历史候选 (一般已停用)
        for fn_name in ["stock_hk_notice_report", "stock_zh_a_disclosure_report_cninfo"]:
            fn = getattr(ak, fn_name, None)
            if fn is None:
                continue
            try:
                try:
                    df = fn(symbol=symbols["HK"])
                except TypeError:
                    df = fn()
                if df is not None and not df.empty:
                    return ("OK", f"via {fn_name}",
                            list(df.columns), len(df))
            except Exception:
                continue
        return ("UNAVAILABLE", "no HK notice/news API works", [], 0)

    results.append(_run("HK Corporate Notice / Announcement (news_em fallback)",
                        "HK", "event", _hk_notice))

    # ============ A 股公告 ============
    def _cn_notice():
        # akshare: stock_notice_report 需要参数 symbol="全部" 等
        for fn_name in ["stock_notice_report", "news_report_time_baidu"]:
            fn = getattr(ak, fn_name, None)
            if fn is None:
                continue
            try:
                try:
                    df = fn(symbol="全部", date=datetime.now().strftime("%Y%m%d"))
                except TypeError:
                    try:
                        df = fn(date=datetime.now().strftime("%Y%m%d"))
                    except TypeError:
                        df = fn()
                if df is not None and not df.empty:
                    return ("OK", f"via {fn_name}", list(df.columns), len(df))
            except Exception:
                continue
        return ("UNAVAILABLE", "no CN notice API works", [], 0)

    results.append(_run("CN Corporate Notice / Announcement", "CN", "event", _cn_notice))

    # ============ 南向持股 ============
    def _southbound():
        for fn_name in ["stock_hk_ggt_components_em", "stock_hsgt_hold_stock_em",
                        "stock_hk_hold_sgt"]:
            fn = getattr(ak, fn_name, None)
            if fn is None:
                continue
            try:
                df = fn()
                if df is not None and not df.empty:
                    return ("OK", f"via {fn_name}", list(df.columns), len(df))
            except Exception:
                continue
        return ("UNAVAILABLE", "no southbound API works", [], 0)

    results.append(_run("Southbound Holdings (HK Connect)", "HK", "flow", _southbound))

    # ============ 大宗交易 (A 股) ============
    def _cn_block():
        for fn_name in ["stock_dzjy_mrtj", "stock_dzjy_mrmx"]:
            fn = getattr(ak, fn_name, None)
            if fn is None:
                continue
            try:
                df = fn(start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    return ("OK", f"via {fn_name}, rows={len(df)}",
                            list(df.columns), len(df))
            except Exception:
                continue
        return ("UNAVAILABLE", "no CN block trade API works", [], 0)

    results.append(_run("CN Block Trade (大宗交易)", "CN", "flow", _cn_block))

    # ============ 龙虎榜 (A 股) ============
    def _cn_lhb():
        for fn_name in ["stock_lhb_detail_em", "stock_lhb_jgmx_sina"]:
            fn = getattr(ak, fn_name, None)
            if fn is None:
                continue
            try:
                df = fn(start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    return ("OK", f"via {fn_name}, rows={len(df)}",
                            list(df.columns), len(df))
            except Exception:
                continue
        return ("UNAVAILABLE", "no LHB API works", [], 0)

    results.append(_run("CN Dragon-Tiger List (龙虎榜)", "CN", "flow", _cn_lhb))

    return results


# ---------------------------------------------------------------
# OpenBB 探针组
# ---------------------------------------------------------------
def probe_openbb(symbols: Dict[str, str]) -> List[ProbeResult]:
    results: List[ProbeResult] = []
    try:
        from openbb import obb  # type: ignore
    except Exception as e:
        results.append(ProbeResult("OpenBB import", "US", "price", "ERROR",
                                   f"import failed: {e}"))
        return results

    start = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")

    def _us_hist():
        res = obb.equity.price.historical(symbol=symbols["US"], provider="yfinance",
                                          start_date=start)
        if not res or not res.results:
            return ("UNAVAILABLE", "empty", [], 0)
        first = res.results[0]
        d = first.dict() if hasattr(first, "dict") else vars(first)
        cols = list(d.keys())
        has_vwap = "vwap" in cols
        n = len(res.results)
        if has_vwap:
            return ("OK", f"vwap present, n={n}", cols, n)
        return ("PARTIAL", f"vwap missing; can fallback to typical_price (H+L+C)/3", cols, n)

    results.append(_run("OpenBB equity.price.historical (US, vwap?)", "US", "price", _us_hist))

    def _us_index():
        # SPY ETF 作为指数代理
        res = obb.equity.price.historical(symbol="SPY", provider="yfinance", start_date=start)
        if not res or not res.results:
            return ("UNAVAILABLE", "empty", [], 0)
        return ("OK", f"rows={len(res.results)}",
                list(res.results[0].dict().keys()), len(res.results))

    results.append(_run("US Index (SPY) daily via OpenBB", "US", "index", _us_index))

    return results


# ---------------------------------------------------------------
# 报告生成
# ---------------------------------------------------------------
PRIORITY = {
    # 必须项 (mandatory)
    ("HK", "price"): "MANDATORY",
    ("CN", "price"): "MANDATORY",
    ("HK", "index"): "MANDATORY",
    ("CN", "index"): "MANDATORY",
    # 重要项 (important)
    ("HK", "event"): "IMPORTANT",
    ("CN", "event"): "IMPORTANT",
    ("HK", "flow"): "IMPORTANT",
    # 可选项 (optional)
    ("CN", "flow"): "OPTIONAL",
    ("US", "price"): "OPTIONAL",
    ("US", "index"): "OPTIONAL",
}

STATUS_EMOJI = {
    "OK": "✅",
    "PARTIAL": "⚠️",
    "UNAVAILABLE": "❌",
    "RATE_LIMITED": "⏱️",
    "ERROR": "💥",
}


def render_markdown(results: List[ProbeResult], symbols: Dict[str, str]) -> str:
    lines: List[str] = []
    lines.append("# Data Availability Matrix (Phase 0 Probe Result)\n")
    lines.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n")
    lines.append(f"\n**Symbols probed:** HK=`{symbols['HK']}`, CN=`{symbols['CN']}`, US=`{symbols['US']}`\n")

    lines.append("\n## Summary Matrix\n")
    lines.append("| Status | Priority | Market | Category | Source | Rows | Detail |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        prio = PRIORITY.get((r.market, r.category), "OPTIONAL")
        emoji = STATUS_EMOJI.get(r.status, "?")
        detail = r.detail.replace("|", "\\|").replace("\n", " ")[:80]
        lines.append(f"| {emoji} {r.status} | {prio} | {r.market} | {r.category} "
                     f"| `{r.name}` | {r.rows_returned} | {detail} |")

    # 阻塞性判断
    lines.append("\n## Blocking Assessment\n")
    mandatory_failed = [r for r in results
                       if PRIORITY.get((r.market, r.category)) == "MANDATORY"
                       and r.status not in ("OK", "PARTIAL")]
    important_failed = [r for r in results
                       if PRIORITY.get((r.market, r.category)) == "IMPORTANT"
                       and r.status not in ("OK", "PARTIAL")]

    if not mandatory_failed:
        lines.append("✅ **All MANDATORY data sources OK or PARTIAL** — Phase 1-2 can proceed.\n")
    else:
        lines.append("🚫 **MANDATORY sources failed — BLOCKING:**\n")
        for r in mandatory_failed:
            lines.append(f"- `{r.name}` ({r.market}/{r.category}): {r.status} — {r.detail}")
        lines.append("\n→ Action: revisit with user before proceeding.\n")

    if important_failed:
        lines.append("\n⚠️ **IMPORTANT sources unavailable — graceful degradation required:**\n")
        for r in important_failed:
            lines.append(f"- `{r.name}` ({r.market}/{r.category}): {r.status} — Phase 3/5/7 must degrade.")

    # 字段级洞察
    lines.append("\n## Field-Level Findings\n")
    for r in results:
        if r.sample_columns:
            cols_short = ", ".join(r.sample_columns[:15])
            more = f" (+{len(r.sample_columns)-15} more)" if len(r.sample_columns) > 15 else ""
            lines.append(f"### {r.name}\n")
            lines.append(f"- **Status:** {STATUS_EMOJI.get(r.status,'?')} {r.status}")
            lines.append(f"- **Columns:** `{cols_short}`{more}")
            lines.append(f"- **Rows:** {r.rows_returned}")
            lines.append(f"- **Elapsed:** {r.elapsed_sec:.2f}s\n")

    # Phase 路由建议
    lines.append("\n## Recommended Phase Routing\n")
    lines.append(_phase_routing(results))

    return "\n".join(lines)


def _phase_routing(results: List[ProbeResult]) -> str:
    """根据探针结果给出每个 Phase 应否启动 / 降级。"""
    by_key = {(r.market, r.category): r for r in results}

    def ok(market: str, category: str) -> bool:
        r = by_key.get((market, category))
        return r is not None and r.status in ("OK", "PARTIAL")

    out: List[str] = []
    out.append("| Phase | Decision | Reason |")
    out.append("|---|---|---|")

    # Phase 1
    p1 = "GO" if ok("HK", "price") and ok("CN", "price") else "BLOCK"
    out.append(f"| **Phase 1** VolumeAnomalyProfiler | {p1} | depends on HK/CN price |")

    # Phase 2
    p2 = "GO" if ok("HK", "price") else "BLOCK"
    out.append(f"| **Phase 2** turnover/amount multidim | {p2} | depends on HK price w/ turnover |")

    # Phase 3
    if ok("HK", "event") and ok("CN", "event"):
        p3 = "GO (full)"
    elif ok("HK", "event") or ok("CN", "event"):
        p3 = "GO (partial — only working market)"
    else:
        p3 = "DEGRADE — keyword classifier ready, but no notice source; rely on news collector"
    out.append(f"| **Phase 3** Corporate Action Layer | {p3} | event APIs |")

    # Phase 4
    out.append(f"| **Phase 4** Distribution Patterns | GO | pure math, no extra deps |")

    # Phase 5
    p5 = "GO" if (ok("HK", "index") and ok("CN", "index")) else "DEGRADE"
    out.append(f"| **Phase 5** Market Relative | {p5} | index APIs |")

    # Phase 6
    out.append(f"| **Phase 6** Risk Scorer | GO (auto-redistribute weights for unavailable subscores) | depends on prior phases |")

    # Phase 7
    if ok("HK", "flow") and ok("CN", "flow"):
        p7 = "GO (full)"
    elif ok("HK", "flow") or ok("CN", "flow"):
        p7 = "GO (partial)"
    else:
        p7 = "SKIP — no flow data; entire phase optional anyway"
    out.append(f"| **Phase 7** Flow Signals | {p7} | southbound/block/LHB |")

    return "\n".join(out)


# ---------------------------------------------------------------
# 入口
# ---------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy", default=None)
    parser.add_argument("--hk", default="00700")
    parser.add_argument("--cn", default="600519")
    parser.add_argument("--us", default="MSFT")
    parser.add_argument("--out", default="docs/data_availability_matrix.md")
    parser.add_argument("--skip", choices=["akshare", "openbb"], action="append", default=[])
    args = parser.parse_args()

    # 代理注入
    if args.proxy:
        proxy = args.proxy.replace("socks5://", "socks5h://")
        for k in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                  "http_proxy", "https_proxy", "all_proxy"]:
            os.environ[k] = proxy
        print(f"[*] Proxy applied: {proxy}", flush=True)

    symbols = {"HK": args.hk, "CN": args.cn, "US": args.us}
    print(f"[*] Probing with symbols: {symbols}", flush=True)

    all_results: List[ProbeResult] = []

    if "akshare" not in args.skip:
        print("\n[*] Probing AkShare...", flush=True)
        # AkShare 多数接口走国内服务器，代理会反而拖慢/断连。
        # 临时清空代理（仅对 akshare 探针）。
        saved_proxies = {k: os.environ.pop(k, None) for k in
                         ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                          "http_proxy", "https_proxy", "all_proxy"]}
        try:
            for r in probe_akshare(symbols):
                emoji = STATUS_EMOJI.get(r.status, "?")
                print(f"  {emoji} [{r.market}/{r.category}] {r.name}: {r.status} ({r.elapsed_sec:.2f}s) — {r.detail[:80]}", flush=True)
                all_results.append(r)
        finally:
            for k, v in saved_proxies.items():
                if v is not None:
                    os.environ[k] = v

    if "openbb" not in args.skip:
        print("\n[*] Probing OpenBB...", flush=True)
        for r in probe_openbb(symbols):
            emoji = STATUS_EMOJI.get(r.status, "?")
            print(f"  {emoji} [{r.market}/{r.category}] {r.name}: {r.status} ({r.elapsed_sec:.2f}s) — {r.detail[:80]}", flush=True)
            all_results.append(r)

    # 写入 markdown
    md = render_markdown(all_results, symbols)
    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\n[*] Matrix written: {out_path}", flush=True)

    # 退出码反映必须项是否通过
    mandatory_failed = [r for r in all_results
                        if PRIORITY.get((r.market, r.category)) == "MANDATORY"
                        and r.status not in ("OK", "PARTIAL")]
    if mandatory_failed:
        print(f"\n🚫 {len(mandatory_failed)} MANDATORY sources failed.", flush=True)
        sys.exit(2)
    print("\n✅ All MANDATORY sources passed.", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
