"""
多时间框架市场分析器 (Multi-Timeframe Market Analyzer)
======================================================
满血版：集成了趋势绩效、风险回撤、量价异常、形态缺口四大模块

基于 pandas-ta-openbb 的专业级技术面分析组件。
"""

from __future__ import annotations

import importlib.metadata  # 🚨 [关键补丁]：提前把 metadata 加载进内存，修复 pandas-ta-openbb 在 Py3.13 的导入 Bug
import pandas as pd
import numpy as np
import pandas_ta as ta     # 现在它在底层调用 importlib.metadata 就不会报错了，df.ta 将成功注册！
from typing import Any, Dict, Optional

from alphaflow.core.schema import ResearchPack


class MultiTimeframeMarketAnalyzer:
    """
    基于 pandas-ta 的多时间框架市场动作分析器 (满血版)
    集成了: 趋势绩效、风险回撤、量价异常、形态缺口四大模块
    """
    
    DEFAULT_TIMEFRAMES = {"short": 30, "medium": 60, "semi_long": 120, "long": 260}
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.timeframes = self.config.get("timeframes", self.DEFAULT_TIMEFRAMES)
    
    def analyze(self, pack: ResearchPack) -> Dict[str, Any]:
        if not pack.market_data:
            return {}
        df = pack.market_data.to_df()
        if df.empty or len(df) < 50:
            return {}
        df = df.sort_index(ascending=True)
        
        # 1. 计算所有基础技术面与统计学指标
        df = self._compute_indicators(df)
        
        # 2. 生成多维度时间框架特征
        return self._analyze_timeframes(df)
    
    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if "close" not in df.columns:
            return df
        
        # --- 模块1：基础技术指标 ---
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.macd(append=True)
        
        # --- 模块2：波动率与日收益率 ---
        df['daily_return'] = df['close'].pct_change()
        
        # --- 模块3：量价特征 ---
        if 'volume' in df.columns:
            # 计算 20日日均成交量 (ADV)
            df['ADV_20'] = df['volume'].rolling(window=20).mean()
            # 计算成交量异动倍数
            df['volume_spike_ratio'] = df['volume'] / df['ADV_20']
            
        return df

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        if value is None or pd.isna(value) or np.isinf(value):
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _detect_unfilled_gap_down(self, df: pd.DataFrame) -> Optional[Dict[str, float]]:
        """检测最近是否存在未回补的向下跳空缺口 (Unfilled Gap Down)"""
        if len(df) < 2 or 'high' not in df.columns or 'low' not in df.columns:
            return None
            
        # 倒序遍历最近 20 天寻找缺口
        recent_df = df.tail(20)
        for i in range(1, len(recent_df)):
            prev_low = recent_df['low'].iloc[i-1]
            curr_high = recent_df['high'].iloc[i]
            
            # 发生向下跳空
            if curr_high < prev_low:
                # 检查后续所有的最高价，是否填补了这个缺口
                subsequent_highs = recent_df['high'].iloc[i:]
                if subsequent_highs.max() < prev_low:
                    return {
                        "gap_top": round(prev_low, 2),
                        "gap_bottom": round(curr_high, 2),
                        "status": "UNFILLED",
                        "days_ago": len(recent_df) - i
                    }
        return None

    def _analyze_drawdown_mechanics(self, df_slice: pd.DataFrame) -> Dict[str, float]:
        """模块二：风险与回撤 X 光 (Peak-to-Trough)"""
        if df_slice.empty: 
            return {"max_drawdown_pct": 0.0, "days_peak_to_trough": 0, "recovery_from_trough_pct": 0.0}
            
        # 找到最高点和其索引
        peak_idx = df_slice['high'].idxmax()
        peak_price = df_slice.loc[peak_idx, 'high']
        
        # 找到最高点之后的最低点(谷底)
        post_peak_df = df_slice.loc[peak_idx:]
        trough_idx = post_peak_df['low'].idxmin()
        trough_price = post_peak_df.loc[trough_idx, 'low']
        
        latest_close = df_slice['close'].iloc[-1]
        
        # 计算指标
        mdd_pct = ((trough_price / peak_price) - 1) * 100 if peak_price > 0 else 0
        
        # 确保索引是整数位置以计算"交易天数"
        peak_pos = df_slice.index.get_loc(peak_idx)
        trough_pos = df_slice.index.get_loc(trough_idx)
        days_p2t = max(0, trough_pos - peak_pos)
        
        # 反弹幅度
        recovery_pct = ((latest_close / trough_price) - 1) * 100 if trough_price > 0 else 0
        
        return {
            "max_drawdown_pct": round(mdd_pct, 2),
            "days_peak_to_trough": int(days_p2t),
            "recovery_from_trough_pct": round(recovery_pct, 2)
        }

    def _analyze_timeframes(self, df: pd.DataFrame) -> Dict[str, Any]:
        latest = df.iloc[-1]
        latest_close = self._safe_float(latest.get("close"), 0.0)
        tags = set()
        
        # ==========================================
        # 量价异常检测与定性打标 (Volume Anomalies)
        # ==========================================
        latest_vol_ratio = self._safe_float(latest.get("volume_spike_ratio"), 1.0)
        latest_daily_ret = self._safe_float(latest.get("daily_return"), 0.0)
        
        vol_data = {"volume_spike_ratio": round(latest_vol_ratio, 2)}
        if 'ADV_20' in latest.index:
            vol_data["adv_20"] = int(self._safe_float(latest['ADV_20']))
            
        if latest_vol_ratio > 1.5 and latest_daily_ret < -0.02:
            tags.add("[MASSIVE_DISTRIBUTION]")  # 放量暴跌
        elif latest_vol_ratio > 1.5 and latest_daily_ret > 0.02:
            tags.add("[MASSIVE_ACCUMULATION]")  # 天量抢筹
        elif latest_vol_ratio < 0.6 and latest_daily_ret < -0.01:
            tags.add("[LOW_CONVICTION_SELLOFF]")  # 缩量阴跌
            
        # ==========================================
        # 缺口检测 (Unfilled Gap)
        # ==========================================
        gap_info = self._detect_unfilled_gap_down(df)
        if gap_info:
            tags.add("[UNFILLED_GAP_DOWN]")

        # 分层计算
        short_res = self._calc_period_metrics(df, self.timeframes["short"], latest, tags)
        med_res = self._calc_period_metrics(df, self.timeframes["medium"], latest, tags)
        semi_long_res = self._calc_period_metrics(df, self.timeframes["semi_long"], latest, tags)
        long_res = self._calc_period_metrics(df, self.timeframes["long"], latest, tags)
        
        return {
            "technical_and_sentiment": {
                "market_summary": {
                    "latest_close": round(latest_close, 2),
                    "trend_tags": sorted(list(tags)),
                    "unfilled_gap_down": gap_info
                },
                "timeframes": {
                    "short_term_1m": short_res,
                    "medium_term_3m": med_res,
                    "semi_long_term_6m": semi_long_res,
                    "long_term_1y": long_res
                },
                "liquidity_and_volume": vol_data
            }
        }

    def _calc_period_metrics(self, df: pd.DataFrame, period_days: int, latest: pd.Series, tags: set) -> Dict[str, Any]:
        """通用的区间指标提取工厂，结构化输出 Performance, Risk, Technicals"""
        df_slice = df.tail(period_days)
        if df_slice.empty:
            return {"period_trading_days": period_days}

        
        latest_close = self._safe_float(latest.get("close"), 0.0)
        start_close = self._safe_float(df_slice.iloc[0].get("close"), 0.0)
        
        # 1. Performance (绩效与波动)
        ret_pct = ((latest_close / start_close) - 1) * 100 if start_close > 0 else 0
        volatility = self._safe_float(df_slice['daily_return'].std() * np.sqrt(252)) * 100
        
        # 相对位置分位
        high_period = self._safe_float(df_slice["high"].max())
        low_period = self._safe_float(df_slice["low"].min())
        pct_in_range = ((latest_close - low_period) / (high_period - low_period)) * 100 if high_period != low_period else 50.0

        # 2. Risk & Drawdown (调用专业的 Peak-to-Trough 引擎)
        risk_metrics = self._analyze_drawdown_mechanics(df_slice)
        
        # 3. 组装结果结构 (Nested JSON)
        result = {
            "period_trading_days": period_days,
            "performance": {
                "return_pct": round(ret_pct, 2),
                "annualized_volatility_pct": round(volatility, 2),
                "price_position_in_range_pct": round(pct_in_range, 2)
            },
            "risk_and_drawdown": risk_metrics,
            "technicals": {}
        }

        
        # 按需附加特定周期的均线与动量指标
        if period_days == self.timeframes["short"]:
            rsi = self._safe_float(latest.get("RSI_14"), 50.0)
            result["technicals"]["rsi_14"] = round(rsi, 2)
            if rsi < 30:
                tags.add("[RSI_OVERSOLD]")
            elif rsi > 70:
                tags.add("[RSI_OVERBOUGHT]")
            
        elif period_days == self.timeframes["medium"]:
            sma_50 = self._safe_float(latest.get("SMA_50"))
            if sma_50 > 0:
                dist = ((latest_close / sma_50) - 1) * 100
                result["technicals"]["distance_to_sma50_pct"] = round(dist, 2)
                tags.add("[ABOVE_SMA50]" if dist > 0 else "[BELOW_SMA50]")
                
        elif period_days == self.timeframes["long"]:
            sma_200 = self._safe_float(latest.get("SMA_200"))
            if sma_200 > 0:
                tags.add("[SECULAR_BULL_TREND]" if latest_close > sma_200 else "[SECULAR_BEAR_TREND]")

        return result
