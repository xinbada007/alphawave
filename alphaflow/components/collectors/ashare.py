from typing import Any, Dict, Optional
import pandas as pd
import tushare as ts
import asyncio
from datetime import datetime, timedelta
from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack, DataFrameModel
from alphaflow.components.collectors.tushare_config import get_tushare_token


class AshareCollector(BaseCollector):
    """
    A股行情采集器 - 基于Tushare
    获取前复权OHLCV数据，输出格式与yfinance/OpenBB保持一致
    
    Token 配置（加密存储）:
        from alphaflow.components.collectors.tushare_config import set_tushare_token
        set_tushare_token("your_token_here")
    """
    
    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """
        标准化A股代码格式
        
        规则:
        - 6位纯数字: 根据首数字自动添加后缀
          * 0, 1, 3 开头 -> .SZ (深圳)
          * 4, 8 开头 -> .BJ (北京)
          * 其他 -> .SH (上海)
        - 已带后缀: 转为大写标准格式
        
        Examples:
            >>> AshareCollector.normalize_symbol("600036")      # -> "600036.SH"
            >>> AshareCollector.normalize_symbol("600036.SH")   # -> "600036.SH"
            >>> AshareCollector.normalize_symbol("600036.sh")   # -> "600036.SH"
            >>> AshareCollector.normalize_symbol("000333")      # -> "000333.SZ"
            >>> AshareCollector.normalize_symbol("430047")      # -> "430047.BJ"
        """
        if not symbol or not isinstance(symbol, str):
            raise ValueError(f"Invalid symbol: {symbol}")
        
        symbol = symbol.strip().upper()
        
        # 有效的交易所后缀
        VALID_EXCHANGES = {"SZ", "SH", "BJ"}
        
        # 如果已经包含后缀，验证后缀是否有效
        if "." in symbol:
            parts = symbol.split(".")
            if len(parts) == 2 and len(parts[0]) == 6:
                exchange = parts[1]
                if exchange not in VALID_EXCHANGES:
                    raise ValueError(f"Invalid exchange suffix '{exchange}', expected one of: {VALID_EXCHANGES}")
                return f"{parts[0]}.{exchange}"
            else:
                raise ValueError(f"Invalid symbol format: {symbol}")
        
        # 纯数字代码，根据规则添加后缀
        if len(symbol) != 6 or not symbol.isdigit():
            raise ValueError(f"Invalid symbol format, expected 6 digits: {symbol}")
        
        first_digit = symbol[0]
        
        if first_digit in ("0", "1", "3"):
            # 深圳: 0,1开头为主板/中小板, 3开头为创业板
            return f"{symbol}.SZ"
        elif first_digit in ("4", "8"):
            # 北京: 4,8开头为北交所/新三板
            return f"{symbol}.BJ"
        else:
            # 上海: 6开头为主板, 其他如5开头也为上海
            return f"{symbol}.SH"
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.pro = None
        self._init_tushare()
    
    def _init_tushare(self):
        """初始化Tushare API（自动解密）"""
        token = get_tushare_token()
        ts.set_token(token)
        self.pro = ts.pro_api()
    
    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        input_data = kwargs.get("input_data")
        pack = (
            input_data.payload
            if isinstance(input_data, ComponentOutput)
            else input_data
        )
        if pack is None:
            pack = ResearchPack(symbol=context.symbols[0])
        
        # 标准化代码格式
        symbol = self.normalize_symbol(pack.symbol)
        pack.symbol = symbol  # 更新为标准化后的代码
        target_days = context.metadata.get("days", 250)
        
        print(f"  [Ashare] Fetching market data for {symbol}...")
        
        # 获取行情数据
        df = await self._get_price_data(symbol, target_days)
        
        if df is not None and not df.empty:
            pack.market_data = DataFrameModel.from_df(df)
            print(f"  [Ashare] Successfully fetched {len(df)} records for {symbol}")
        else:
            print(f"  [Ashare] Warning: No data returned for {symbol}")
        
        return ComponentOutput(success=True, payload=pack)
    
    async def _get_price_data(self, symbol: str, days: int) -> Optional[pd.DataFrame]:
        """
        获取A股前复权行情数据，输出格式与yfinance/OpenBB保持一致
        
        标准列名: open, high, low, close, volume, amount, typical_price
        索引: date (datetime格式)
        """
        # 计算起始日期（多取50%确保数据完整）
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(days * 1.5))
        start_date_str = start_date.strftime("%Y%m%d")
        
        try:
            # 使用Tushare获取前复权日线数据
            df = await asyncio.to_thread(
                ts.pro_bar,
                ts_code=symbol,
                adj="qfq",  # 前复权
                start_date=start_date_str,
                freq="D"
            )
            
            if df is None or df.empty:
                return None
            
            # 标准化列名 (与yfinance/OpenBB保持一致)
            column_mapping = {
                "trade_date": "date",
                "open": "open",
                "high": "high", 
                "low": "low",
                "close": "close",
                "vol": "volume",  # Tushare用vol，标准化为volume
                "amount": "amount"
            }
            df = df.rename(columns=column_mapping)
            
            # 确保所有标准列都存在
            standard_cols = ["date", "open", "high", "low", "close", "volume"]
            for col in standard_cols:
                if col not in df.columns:
                    print(f"  [Ashare] Warning: Missing column {col}")
            
            # 转换日期格式并设为索引
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            
            # 按日期排序
            df = df.sort_index(ascending=True)
            
            # 只保留最近N天
            df = df.tail(days)
            
            # 确保数值类型正确
            numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            
            # 添加与yfinance兼容的列
            # dividend和split_ratio（Tushare不提供，设为默认值）
            df["dividend"] = 0.0
            df["split_ratio"] = 1.0
            
            # typical_price (用于技术分析)
            df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3
            
            # 索引格式化为字符串日期（与fundamental.py一致）
            df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
            
            return df
            
        except Exception as e:
            print(f"  [Ashare] Error fetching data for {symbol}: {e}")
            return None
