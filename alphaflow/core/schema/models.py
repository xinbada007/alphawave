from pydantic import BaseModel, Field, ConfigDict
from typing import Any, ClassVar, Dict, List, Optional, Set
import pandas as pd
import time
import io
from datetime import datetime

# --- 基础数据契约 ---


class DataFrameModel(BaseModel):
    """
    用于在组件间安全传递 DataFrame 的包装器。
    我们不直接传递 pd.DataFrame 对象，因为 Pydantic 默认不支持它。
    这里采用 records 格式的 JSON 结构作为中间态，或者直接持有 dict。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data_json: str = Field(..., description="DataFrame serialized to JSON records")
    schema_meta: Dict[str, str] = Field(
        default_factory=dict, description="Column types metadata"
    )
    # 🌟 新增：记住索引的名字，这是还原时间序列的钥匙
    index_names: List[str] = Field(default_factory=list, description="Names of the original index columns")

    @classmethod
    def from_df(cls, df: pd.DataFrame) -> "DataFrameModel":
        """从 Pandas DataFrame 创建，完美保留索引和类型"""
        
        # 1. 如果不是默认的 RangeIndex (0, 1, 2...)，说明它是有业务意义的索引，必须保留
        if not isinstance(df.index, pd.RangeIndex):
            idx_names: List =[]
            
            # 遍历所有索引层级，强制转为纯字符串，消灭 Hashable 警告
            for i, n in enumerate(df.index.names):
                if n is not None:
                    idx_names.append(str(n))
                else:
                    # 贴心优化：如果是单一且无名的索引
                    if len(df.index.names) == 1:
                        # 如果是时间序列，命名为 "date"；普通索引命名为 "index"
                        name = "date" if isinstance(df.index, pd.DatetimeIndex) else "index"
                        idx_names.append(name)
                    else:
                        # 如果是多重索引且部分无名，命名为 "level_0", "level_1"...
                        idx_names.append(f"level_{i}")
            
            # 赋回清洗后的字符串名字，并推入列中
            df.index.names = idx_names
            df = df.reset_index()
        else:
            idx_names =[]

        # 2. 生成元数据与序列化
        return cls(
            data_json=df.to_json(orient="records", date_format="iso"),
            schema_meta={str(col): str(dtype) for col, dtype in df.dtypes.items()},
            index_names=idx_names
        )

    # 核心列（必须为数值类型，否则后续 TA 计算会崩溃）
    CORE_NUMERIC_COLUMNS: ClassVar[Set[str]] = {"close", "open", "high", "low", "volume", "adj_close", "adjusted_close"}

    def to_df(self, symbol: str = "UNKNOWN") -> pd.DataFrame:
        """
        还原为 Pandas DataFrame，精确恢复类型与索引
        
        Args:
            symbol: 股票代码，用于错误日志追踪
        """
        if not self.data_json or self.data_json == "[]":
            return pd.DataFrame()

        # 1. 加载基础数据
        df = pd.read_json(io.StringIO(self.data_json), orient="records")

        # 2. 精准恢复数据类型
        for col, dtype_str in self.schema_meta.items():
            if col not in df.columns:
                continue

            dtype_str_lower = dtype_str.lower()
            is_core_column = col.lower() in self.CORE_NUMERIC_COLUMNS
            
            try:
                if "datetime" in dtype_str_lower:
                    # 恢复时间类型
                    df[col] = pd.to_datetime(df[col])
                elif "int" in dtype_str_lower:
                    # 🌟 核心修复：使用 'Int64' (大写I) 允许存在 NaN，而不是暴力 fillna(0)
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                elif "float" in dtype_str_lower:
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
                else:
                    # 其他类型 (如 object/string)
                    df[col] = df[col].astype(dtype_str)
            except Exception as e:
                # 核心列转换失败：打印带 symbol 和 column 的严重警告
                if is_core_column:
                    print(f"🚨 CRITICAL [{symbol}] Failed to restore core column '{col}' to {dtype_str}: {e}")
                    # 尝试强制清理不可见字符后重试
                    try:
                        # 移除可能的不可见字符和非数字字符
                        df[col] = df[col].astype(str).str.replace(r"[^\d.\-]", "", regex=True)
                        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
                        print(f"   ↳ Fallback succeeded for '{col}'")
                    except Exception as fallback_error:
                        print(f"   ↳ Fallback also failed: {fallback_error}")
                        # 核心列失败不应该默默 continue，直接抛出
                        raise RuntimeError(
                            f"CRITICAL: Failed to restore core column '{col}' for {symbol}. "
                            f"This will break downstream TA calculations. Original error: {e}"
                        )
                else:
                    print(f" Warning: Failed to cast column '{col}' to {dtype_str}: {e}")
                continue

        # 3. 🌟 核心修复：把当初的列重新扶正为 Index
        if self.index_names and all(name in df.columns for name in self.index_names):
            df = df.set_index(self.index_names)

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
    payload: Any = Field(
        default_factory=lambda: {}, description="Component output payload"
    )


# --- 具体业务契约 ---


class MarketData(BaseModel):
    """市场数据标准格式"""

    symbol: str
    price_data: DataFrameModel  # 必须包含 OHLCV
    provider: str


class SignalData(BaseModel):
    """信号/分析结果标准格式"""

    symbol: str
    indicator_data: DataFrameModel  # 包含计算后的指标列
    signals: Dict[str, Any]  # 如 {"action": "buy", "score": 80}


class ResearchPack(BaseModel):
    """
    万能投研数据包。
    设计目标：高可扩展性，支持团队成员随意塞入新维度。
    """

    symbol: str
    name: Optional[str] = None  # 公司名称
    timestamp: float = Field(default_factory=time.time)
    readable_timestamp: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="Human readable time for debugging and LLM",
    )

    # 结构化数据
    market_data: Optional[DataFrameModel] = None  # OHLCV 时间序列
    market_metrics: Optional[Dict[str, Any]] = None  # 市场快照指标：市值、PE、PB、PS、EPS等
    market_data_meta: Optional[Dict[str, Any]] = None  # 市场数据元信息：provider、columns等
    technicals: Optional[DataFrameModel] = None  # 技术指标时间序列（保留兼容性）
    technical_summary: Optional[Dict[str, Any]] = None  # 技术面汇总（当前快照，非时间序列）
    fundamentals: Optional[Dict[str, Any]] = Field(default_factory=lambda: {})  # 财务数据


    # 非结构化/文本数据
    news: List[Dict[str, Any]] = Field(default_factory=list)

    # 扩展槽位：团队成员可以往这里塞任何自定义 JSON
    extra: Dict[str, Any] = Field(default_factory=dict)

    # 展示层
    charts: Dict[str, str] = Field(default_factory=dict)  # {"main": "http://..."}
