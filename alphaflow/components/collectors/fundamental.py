from typing import Any, Dict
import os
from openbb import obb
from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack
from alphaflow.utils.cache import DiskCache
from alphaflow.utils.api_rotator import get_api_key, report_api_usage


class FundamentalCollector(BaseCollector):
    """
    【增强版基本面分析器】
    职责：获取财报指标、经营数据、财务报表等全面基本面信息。
    Vibe Coding 特性：半固定流程，易于扩展指标字段，API轮询。
    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        super().__init__(name, config)
        self.cache = DiskCache(expiry_seconds=3600 * 24)  # 24小时缓存

    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        # 1. 标准解包
        input_data = kwargs.get('input_data')
        pack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        if pack is None:
            pack = ResearchPack(symbol=context.symbols[0])

        try:
            print(f"  [Fundamental] Fetching comprehensive metrics for {pack.symbol}...")
            
            # 选择基本面数据提供商（优先使用付费提供商）
            providers = ["fmp", "alpha_vantage", "yfinance"]  # 按优先级排序
            
            # 1. 获取基本面指标
            metrics_cache_key = f"fundamental_metrics_{pack.symbol}"
            metrics_data = self.cache.get(metrics_cache_key)
            
            if metrics_data is None:
                metrics_success = False
                for provider in providers:
                    try:
                        api_key = None
                        if provider in ['fmp', 'alpha_vantage']:
                            # 获取API密钥
                            api_key = get_api_key(provider)
                            if api_key:
                                # 临时设置环境变量
                                original_key = os.environ.get(f"{provider.upper()}_API_KEY")
                                os.environ[f"{provider.upper()}_API_KEY"] = api_key
                        
                        # 执行API调用
                        metrics_res = obb.equity.fundamental.metrics(symbol=pack.symbol, provider=provider)
                        metrics_df = metrics_res.to_df()
                        
                        if api_key:
                            # 恢复原始环境变量
                            if original_key is not None:
                                os.environ[f"{provider.upper()}_API_KEY"] = original_key
                            else:
                                os.environ.pop(f"{provider.upper()}_API_KEY", None)
                            # 报告API使用情况
                            report_api_usage(provider, api_key, success=True)
                        
                        if not metrics_df.empty:
                            metrics_data = metrics_df.iloc[0].to_dict()
                            self.cache.set(metrics_cache_key, metrics_data)
                            metrics_success = True
                            print(f"  [Fundamental] Metrics fetched via {provider}")
                            break
                    except Exception as e:
                        if api_key:
                            report_api_usage(provider, api_key, success=False)
                        print(f"  [!] Metrics fetch failed with {provider}: {e}")
                        
                        # 恢复环境变量（如果设置了的话）
                        if api_key:
                            if original_key is not None:
                                os.environ[f"{provider.upper()}_API_KEY"] = original_key
                            else:
                                os.environ.pop(f"{provider.upper()}_API_KEY", None)
                
                if not metrics_success:
                    print(f"  [!] All metrics providers failed, using empty data")
                    metrics_data = {}
            else:
                print(f"  [Fundamental] Using cached metrics for {pack.symbol}")
            
            # 2. 获取资产负债表（年度）
            balance_sheet_cache_key = f"balance_sheet_{pack.symbol}"
            balance_sheet_data = self.cache.get(balance_sheet_cache_key)
            
            if balance_sheet_data is None:
                bs_success = False
                for provider in providers:
                    try:
                        api_key = None
                        if provider in ['fmp', 'alpha_vantage']:
                            # 获取API密钥
                            api_key = get_api_key(provider)
                            if api_key:
                                # 临时设置环境变量
                                original_key = os.environ.get(f"{provider.upper()}_API_KEY")
                                os.environ[f"{provider.upper()}_API_KEY"] = api_key
                        
                        # 执行API调用
                        bs_res = obb.equity.fundamental.balance(symbol=pack.symbol, provider=provider)
                        bs_df = bs_res.to_df()
                        
                        if api_key:
                            # 恢复原始环境变量
                            if original_key is not None:
                                os.environ[f"{provider.upper()}_API_KEY"] = original_key
                            else:
                                os.environ.pop(f"{provider.upper()}_API_KEY", None)
                            # 报告API使用情况
                            report_api_usage(provider, api_key, success=True)
                        
                        if not bs_df.empty:
                            # 获取最新一期的资产负债表数据
                            latest_bs = bs_df.iloc[0].to_dict()
                            balance_sheet_data = latest_bs
                            self.cache.set(balance_sheet_cache_key, balance_sheet_data)
                            bs_success = True
                            print(f"  [Fundamental] Balance sheet fetched via {provider}")
                            break
                    except Exception as e:
                        if api_key:
                            report_api_usage(provider, api_key, success=False)
                        print(f"  [!] Balance sheet fetch failed with {provider}: {e}")
                        
                        # 恢复环境变量（如果设置了的话）
                        if api_key:
                            if original_key is not None:
                                os.environ[f"{provider.upper()}_API_KEY"] = original_key
                            else:
                                os.environ.pop(f"{provider.upper()}_API_KEY", None)
                
                if not bs_success:
                    print(f"  [!] All balance sheet providers failed, using empty data")
                    balance_sheet_data = {}
            else:
                print(f"  [Fundamental] Using cached balance sheet for {pack.symbol}")
            
            # 3. 获取利润表（年度）
            income_statement_cache_key = f"income_statement_{pack.symbol}"
            income_statement_data = self.cache.get(income_statement_cache_key)
            
            if income_statement_data is None:
                income_success = False
                for provider in providers:
                    try:
                        api_key = None
                        if provider in ['fmp', 'alpha_vantage']:
                            # 获取API密钥
                            api_key = get_api_key(provider)
                            if api_key:
                                # 临时设置环境变量
                                original_key = os.environ.get(f"{provider.upper()}_API_KEY")
                                os.environ[f"{provider.upper()}_API_KEY"] = api_key
                        
                        # 执行API调用
                        income_res = obb.equity.fundamental.income(symbol=pack.symbol, provider=provider)
                        income_df = income_res.to_df()
                        
                        if api_key:
                            # 恢复原始环境变量
                            if original_key is not None:
                                os.environ[f"{provider.upper()}_API_KEY"] = original_key
                            else:
                                os.environ.pop(f"{provider.upper()}_API_KEY", None)
                            # 报告API使用情况
                            report_api_usage(provider, api_key, success=True)
                        
                        if not income_df.empty:
                            # 获取最新一期的利润表数据
                            latest_income = income_df.iloc[0].to_dict()
                            income_statement_data = latest_income
                            self.cache.set(income_statement_cache_key, income_statement_data)
                            income_success = True
                            print(f"  [Fundamental] Income statement fetched via {provider}")
                            break
                    except Exception as e:
                        if api_key:
                            report_api_usage(provider, api_key, success=False)
                        print(f"  [!] Income statement fetch failed with {provider}: {e}")
                        
                        # 恢复环境变量（如果设置了的话）
                        if api_key:
                            if original_key is not None:
                                os.environ[f"{provider.upper()}_API_KEY"] = original_key
                            else:
                                os.environ.pop(f"{provider.upper()}_API_KEY", None)
                
                if not income_success:
                    print(f"  [!] All income statement providers failed, using empty data")
                    income_statement_data = {}
            else:
                print(f"  [Fundamental] Using cached income statement for {pack.symbol}")
            
            # 4. 获取现金流量表（年度）
            cash_flow_cache_key = f"cash_flow_{pack.symbol}"
            cash_flow_data = self.cache.get(cash_flow_cache_key)
            
            if cash_flow_data is None:
                cf_success = False
                for provider in providers:
                    try:
                        api_key = None
                        if provider in ['fmp', 'alpha_vantage']:
                            # 获取API密钥
                            api_key = get_api_key(provider)
                            if api_key:
                                # 临时设置环境变量
                                original_key = os.environ.get(f"{provider.upper()}_API_KEY")
                                os.environ[f"{provider.upper()}_API_KEY"] = api_key
                        
                        # 执行API调用
                        cf_res = obb.equity.fundamental.cash(symbol=pack.symbol, provider=provider)
                        cf_df = cf_res.to_df()
                        
                        if api_key:
                            # 恢复原始环境变量
                            if original_key is not None:
                                os.environ[f"{provider.upper()}_API_KEY"] = original_key
                            else:
                                os.environ.pop(f"{provider.upper()}_API_KEY", None)
                            # 报告API使用情况
                            report_api_usage(provider, api_key, success=True)
                        
                        if not cf_df.empty:
                            # 获取最新一期的现金流量表数据
                            latest_cf = cf_df.iloc[0].to_dict()
                            cash_flow_data = latest_cf
                            self.cache.set(cash_flow_cache_key, cash_flow_data)
                            cf_success = True
                            print(f"  [Fundamental] Cash flow fetched via {provider}")
                            break
                    except Exception as e:
                        if api_key:
                            report_api_usage(provider, api_key, success=False)
                        print(f"  [!] Cash flow fetch failed with {provider}: {e}")
                        
                        # 恢复环境变量（如果设置了的话）
                        if api_key:
                            if original_key is not None:
                                os.environ[f"{provider.upper()}_API_KEY"] = original_key
                            else:
                                os.environ.pop(f"{provider.upper()}_API_KEY", None)
                
                if not cf_success:
                    print(f"  [!] All cash flow providers failed, using empty data")
                    cash_flow_data = {}
            else:
                print(f"  [Fundamental] Using cached cash flow for {pack.symbol}")
            
            # 5. 合并所有基本面数据
            all_fundamental_data = {}
            all_fundamental_data.update(metrics_data or {})
            all_fundamental_data.update({"balance_sheet": balance_sheet_data})
            all_fundamental_data.update({"income_statement": income_statement_data})
            all_fundamental_data.update({"cash_flow": cash_flow_data})
            
            # 存储到pack中
            pack.fundamentals = all_fundamental_data
            
            print(f"  [Fundamental] Successfully fetched fundamental data for {pack.symbol}")
            return ComponentOutput(success=True, payload=pack)
            
        except Exception as e:
            # 基本面抓取失败不应导致 Pipeline 中断
            print(f"  [!] Fundamental Data collection error: {e}")
            return ComponentOutput(success=True, payload=pack)
