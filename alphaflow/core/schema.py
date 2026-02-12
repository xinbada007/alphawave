from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, List, Optional, Union
import pandas as pd
import json
import time
import io

# --- 基础数据契约 ---

class DataFrameModel(BaseModel):
    """
    用于在组件间安全传递 DataFrame 的包装器。
    我们不直接传递 pd.DataFrame 对象，因为 Pydantic 默认不支持它。
    这里采用 records 格式的 JSON 结构作为中间态，或者直接持有 dict。
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    data_json: str = Field(..., description="DataFrame serialized to JSON records")
    schema_meta: Dict[str, str] = Field(default_factory=dict, description="Column types metadata")

    @classmethod
    def from_df(cls, df: pd.DataFrame) -> 'DataFrameModel':
        """从 Pandas DataFrame 创建"""
        return cls(
            data_json=df.to_json(orient='records', date_format='iso'),
            schema_meta={col: str(dtype) for col, dtype in df.dtypes.items()}
        )

    def to_df(self) -> pd.DataFrame:
        """还原为 Pandas DataFrame"""
        if not self.data_json:
            return pd.DataFrame()
        df = pd.read_json(io.StringIO(self.data_json), orient='records')
        # 尝试自动修复日期格式，因为 JSON 会把日期变成字符串
        for col in df.columns:
            if 'date' in col.lower() or 'time' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col])
                except:
                    pass
        return df

class AnalysisContext(BaseModel):
    """
    全链路上下文，贯穿整个 Pipeline。
    """
    symbols: List[str]
    timeframe: str = "1d"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ComponentOutput(BaseModel):
    """所有组件的标准输出"""
    success: bool = True
    error: Optional[str] = None
    payload: Any = Field(default_factory=dict) # 允许 Any 类型，增加灵活性


# --- 具体业务契约 ---

class MarketData(BaseModel):
    """市场数据标准格式"""
    symbol: str
    price_data: DataFrameModel # 必须包含 OHLCV
    provider: str

class SignalData(BaseModel):
    """信号/分析结果标准格式"""
    symbol: str
    indicator_data: DataFrameModel # 包含计算后的指标列
    signals: Dict[str, Any] # 如 {"action": "buy", "score": 80}

class ResearchPack(BaseModel):
    """
    万能投研数据包。
    设计目标：高可扩展性，支持团队成员随意塞入新维度。
    """
    symbol: str
    name: Optional[str] = None # 公司名称
    timestamp: float = Field(default_factory=time.time)
    
    # 结构化数据
    market_data: Optional[DataFrameModel] = None
    technicals: Optional[DataFrameModel] = None
    fundamentals: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    # 非结构化/文本数据
    news: List[Dict[str, Any]] = Field(default_factory=list)
    financials: Dict[str, Any] = Field(default_factory=dict)
    
    # 扩展槽位：团队成员可以往这里塞任何自定义 JSON
    extra: Dict[str, Any] = Field(default_factory=dict)
    
    # 展示层
    charts: Dict[str, str] = Field(default_factory=dict) # {"main": "http://..."}
