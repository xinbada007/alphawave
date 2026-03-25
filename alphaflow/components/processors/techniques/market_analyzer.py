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
from alphaflow.components.processors.techniques.technical_tag_config import (
    TechnicalTagConfig,
    TechnicalTagPresets,
)


class MultiTimeframeMarketAnalyzer:
    """
    基于 pandas-ta 的多时间框架市场动作分析器 (满血版)
    集成了: 趋势绩效、风险回撤、量价异常、形态缺口四大模块
    """
    
    @property
    def target_slot(self) -> str:
        """自描述：技术面情绪数据存到 technical_and_sentiment"""
        return "technical_and_sentiment"
    
    DEFAULT_TIMEFRAMES = {
    "short": 21,       # 黄金甜点 1：短期情绪与期权周期
    "medium": 63,      # 黄金甜点 2：中期波段与财报周期
    "semi_long": 126,  # 黄金甜点 3：半年趋势与宏观定价
    "long": 252        # 黄金甜点 4：长期牛熊与 52 周极值
}

    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.timeframes = self.config.get("timeframes", self.DEFAULT_TIMEFRAMES)
        # 技术面标签配置
        self._tag_config = TechnicalTagConfig(self.config.get("tag_config"))
    
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
            
            # --- 模块3.1：资金流向指标 (CMF) ---
            df.ta.cmf(length=21, append=True)
            
            # --- 模块3.2：上涨/下跌日成交量比 ---
            df['up_volume'] = np.where(df['daily_return'] > 0, df['volume'], 0)
            df['down_volume'] = np.where(df['daily_return'] < 0, df['volume'], 0)
            df['up_vol_ma20'] = df['up_volume'].rolling(window=20).mean()
            df['down_vol_ma20'] = df['down_volume'].rolling(window=20).mean()
            df['up_down_ratio'] = df['up_vol_ma20'] / df['down_vol_ma20'].replace(0, np.nan)
            
        return df
    
    def _get_cmf_tag(self, cmf_value: float) -> Dict[str, str]:
        """CMF 5档梯度语义映射 (中立化表达)"""
        cfg = self._tag_config
        if cmf_value >= cfg.CMF_STRONGLY_POSITIVE:
            return {"tag": "[CMF_STRONGLY_POSITIVE]", "status": f">= {cfg.CMF_STRONGLY_POSITIVE}"}
        elif cmf_value >= cfg.CMF_MILDLY_POSITIVE:
            return {"tag": "[CMF_MILDLY_POSITIVE]", "status": f">= {cfg.CMF_MILDLY_POSITIVE}"}
        elif cmf_value >= cfg.CMF_MILDLY_NEGATIVE:
            return {"tag": "[CMF_NEAR_ZERO]", "status": "Neutral"}
        elif cmf_value >= cfg.CMF_STRONGLY_NEGATIVE:
            return {"tag": "[CMF_MILDLY_NEGATIVE]", "status": f"<= {cfg.CMF_MILDLY_NEGATIVE}"}
        else:
            return {"tag": "[CMF_STRONGLY_NEGATIVE]", "status": f"<= {cfg.CMF_STRONGLY_NEGATIVE}"}
    
    def _get_up_down_vol_tag(self, ratio: float) -> Dict[str, str]:
        """Up/Down Volume Ratio 3档梯度语义映射 (中立化表达)"""
        cfg = self._tag_config
        if ratio >= cfg.UP_DOWN_RATIO_HIGH_THRESHOLD:
            return {"tag": "[UP_DAY_VOLUME_HIGH]", "status": f">= {cfg.UP_DOWN_RATIO_HIGH_THRESHOLD}"}
        elif ratio <= cfg.UP_DOWN_RATIO_LOW_THRESHOLD:
            return {"tag": "[DOWN_DAY_VOLUME_HIGH]", "status": f"<= {cfg.UP_DOWN_RATIO_LOW_THRESHOLD}"}
        else:
            return {"tag": "[VOLUME_RATIO_NEUTRAL]", "status": "Neutral"}

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
        
        vol_data: Dict[str, Any] = {"volume_spike_ratio": round(latest_vol_ratio, 2)}
        if 'ADV_20' in latest.index:
            vol_data["adv_20"] = int(self._safe_float(latest['ADV_20']))
            
        # --- CMF 资金流向 (带 NaN 兜底，去归因化) ---
        raw_cmf = latest.get("CMF_21")
        if raw_cmf is None or pd.isna(raw_cmf):
            cmf_value = 0.0
            cmf_tag = {"tag": "[INSUFFICIENT_DATA]", "status": "Not enough trading days"}
        else:
            cmf_value = self._safe_float(raw_cmf, 0.0)
            cmf_tag = self._get_cmf_tag(cmf_value)
        vol_data["money_flow_metrics"] = {
            "indicator": "Chaikin Money Flow (CMF_21)",
            "value": round(cmf_value, 4),
            "threshold_status": cmf_tag["status"],
            "action_tag": cmf_tag["tag"]
        }
        if cmf_tag["tag"] in ["[CMF_STRONGLY_POSITIVE]", "[CMF_STRONGLY_NEGATIVE]"]:
            tags.add(cmf_tag["tag"])
            
        # --- Up/Down Volume Ratio (带 NaN 兜底) ---
        raw_ratio = latest.get("up_down_ratio")
        if raw_ratio is None or pd.isna(raw_ratio):
            up_down_ratio = 1.0
            up_down_tag = {"tag": "[INSUFFICIENT_DATA]", "status": "Not enough trading days for ratio"}
        else:
            up_down_ratio = self._safe_float(raw_ratio, 1.0)
            up_down_tag = self._get_up_down_vol_tag(up_down_ratio)
        vol_data["up_down_volume_ratio"] = {
            "value": round(up_down_ratio, 2),
            "implication": f"{up_down_tag['tag']} ({up_down_tag['status']})"
        }
        if up_down_tag["tag"] not in ["[VOLUME_RATIO_NEUTRAL]", "[INSUFFICIENT_DATA]"]:
            tags.add(up_down_tag["tag"])
            
        # --- 使用配置文件的量价异常检测 (纯物理判断) ---
        cfg = self._tag_config
        if latest_vol_ratio > cfg.VOLUME_SPIKE_MULTIPLIER and latest_daily_ret < cfg.VOLUME_SPIKE_DROP_THRESHOLD:
            tags.add("[VOL_SPIKE_PRICE_DOWN]")  # 放量且收跌
        elif latest_vol_ratio > cfg.VOLUME_SPIKE_MULTIPLIER and latest_daily_ret > cfg.VOLUME_SPIKE_RALLY_THRESHOLD:
            tags.add("[VOL_SPIKE_PRICE_UP]")  # 放量且收涨
        elif latest_vol_ratio < cfg.VOLUME_CONTRACTION_MULTIPLIER and latest_daily_ret < cfg.VOLUME_CONTRACTION_DROP_THRESHOLD:
            tags.add("[VOL_CONTRACTION_PRICE_DOWN]")  # 缩量且收跌
            
        # ==========================================
        # 缺口检测 (Unfilled Gap)
        # ==========================================
        gap_info = self._detect_unfilled_gap_down(df)
        if gap_info:
            tags.add("[UNFILLED_GAP_DOWN]")

        # 分层计算 - 传入明确的 tier_name 标识符
        short_res = self._calc_period_metrics(df, self.timeframes["short"], "short", latest, tags)
        med_res = self._calc_period_metrics(df, self.timeframes["medium"], "medium", latest, tags)
        semi_long_res = self._calc_period_metrics(df, self.timeframes["semi_long"], "semi_long", latest, tags)
        long_res = self._calc_period_metrics(df, self.timeframes["long"], "long", latest, tags)

        
        return {
            "technical_and_sentiment": {
                "market_summary": {
                    "latest_close": round(latest_close, 2),
                    "trend_tags": sorted(list(tags)),
                    "unfilled_gap_down": gap_info
                },
                "timeframes": {
                    "short_term": short_res,
                    "medium_term": med_res,
                    "semi_long_term": semi_long_res,
                    "long_term": long_res
                },

                "liquidity_and_volume": vol_data
            }
        }

    def _calc_period_metrics(self, df: pd.DataFrame, period_days: int, tier_name: str, latest: pd.Series, tags: set) -> Dict[str, Any]:
        """通用的区间指标提取工厂，结构化输出 Performance, Risk, Technicals"""
        df_slice = df.tail(period_days)
        actual_days = len(df_slice)
        if df_slice.empty:
            return {"period_trading_days": actual_days}

        
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
            "period_trading_days": actual_days,
            "performance": {
                "return_pct": round(ret_pct, 2),
                "annualized_volatility_pct": round(volatility, 2),
                "price_position_in_range_pct": round(pct_in_range, 2)
            },
            "risk_and_drawdown": risk_metrics,
            "technicals": {}
        }

        
        # 按需附加特定周期的均线与动量指标 - 根据 tier_name 分发
        if tier_name == "short":
            cfg = self._tag_config
            rsi = self._safe_float(latest.get("RSI_14"), 50.0)
            result["technicals"]["rsi_14"] = round(rsi, 2)
            if rsi < cfg.RSI_OVERSOLD_THRESHOLD:
                tags.add("[RSI_OVERSOLD]")
            elif rsi > cfg.RSI_OVERBOUGHT_THRESHOLD:
                tags.add("[RSI_OVERBOUGHT]")
            
        elif tier_name == "medium":
            cfg = self._tag_config
            sma_50 = self._safe_float(latest.get("SMA_50"))
            if sma_50 > 0:
                dist = ((latest_close / sma_50) - 1) * 100
                result["technicals"]["distance_to_sma50_pct"] = round(dist, 2)
                tags.add("[ABOVE_SMA50]" if dist > cfg.SMA_DISTANCE_THRESHOLD else "[BELOW_SMA50]")
                
        elif tier_name == "semi_long":
            # 补全 MACD 柱状图
            macd_h = self._safe_float(latest.get("MACDh_12_26_9"), 0.0)
            result["technicals"]["macd_histogram"] = round(macd_h, 4)
            
        elif tier_name == "long":
            # 补全 SMA200 的距离
            sma_200 = self._safe_float(latest.get("SMA_200"))
            if sma_200 > 0:
                dist_200 = ((latest_close / sma_200) - 1) * 100
                result["technicals"]["distance_to_sma200_pct"] = round(dist_200, 2)
                tags.add("[ABOVE_200_DAY_MA]" if latest_close > sma_200 else "[BELOW_200_DAY_MA]")


        return result

