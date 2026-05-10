"""
VWAP Enricher - 从成交额/成交量派生会计意义上的日 VWAP
=========================================================
适用场景：
- AkShare 港股/A 股原始数据返回 amount(成交额) + volume(成交量) 但缺 vwap 列
- OpenBB 美股原生有 vwap，由 can_apply 守卫自动跳过

公式：
    vwap = amount / volume

其中 volume = 0（停牌日/仙股零成交）时，结果为 NaN（避免 inf）。

注：这是会计意义上的"成交均价"，等价于全日成交流的 VWAP，
比 typical_price (H+L+C)/3 更精确（后者是无法获取真实 VWAP 时的退化近似）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import DerivedColumnEnricher


class VwapFromAmountEnricher(DerivedColumnEnricher):
    """从 amount/volume 派生 vwap。"""

    output_column = "vwap"
    required_inputs = frozenset({"amount", "volume"})

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        # volume=0 替换为 NaN，避免除零产生 inf；统一 float64 dtype
        # 注：使用 np.nan (而非 pd.NA)，因为 pd.NA → float64 的 astype 会抛
        # TypeError，只有 np.nan 与传统 numpy float64 兼容。
        import numpy as np
        vol_safe = df["volume"].replace(0, np.nan)
        vwap = (df["amount"] / vol_safe).astype("float64")
        return df.assign(vwap=vwap)
