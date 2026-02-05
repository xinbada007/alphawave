import pandas as pd
import requests
import json
import urllib.parse
from typing import List, Dict, Any, Optional

class QuickChartClient:
    """
    智能 QuickChart 客户端。
    支持参数化配置和短链接生成。
    """
    def __init__(self, base_url="https://quickchart.io/chart", api_key: str = None, max_points: int = 250):
        self.base_url = base_url
        self.api_key = api_key
        self.max_points = max_points

    def _downsample(self, df: pd.DataFrame, max_points: int = None) -> pd.DataFrame:
        """
        智能降采样。
        """
        limit = max_points or self.max_points
        if len(df) <= limit:
            return df
        
        step = len(df) // limit
        if step < 1: step = 1
        
        sampled_df = df.iloc[::step].copy()
        
        # 确保包含最后一个最新点
        if sampled_df.index[-1] != df.index[-1]:
            sampled_df = pd.concat([sampled_df.iloc[:-1], df.iloc[-1:]])
            
        return sampled_df.head(limit)

    def create_chart_url(self, df: pd.DataFrame, 
                         title: str, 
                         target_col: str = 'close', 
                         chart_type: str = 'line',
                         override_max_points: int = None) -> str:
        """
        通过 POST 请求 QuickChart API 生成短链接。
        """
        # 1. 预处理：使用配置的限额
        limit = override_max_points or self.max_points
        sample_df = self._downsample(df, max_points=limit)
        
        # 2. 准备数据
        labels = []
        if isinstance(sample_df.index, pd.DatetimeIndex):
            labels = sample_df.index.strftime('%Y-%m-%d').tolist()
        else:
            if 'date' in sample_df.columns:
                 labels = pd.to_datetime(sample_df['date']).dt.strftime('%Y-%m-%d').tolist()
            else:
                 labels = sample_df.index.astype(str).tolist()

        data_values = sample_df[target_col].tolist()

        # 3. 构建配置
        chart_config = {
            "chart": {
                "type": chart_type,
                "data": {
                    "labels": labels,
                    "datasets": [{
                        "label": target_col.upper(),
                        "data": data_values,
                        "fill": False,
                        "borderColor": "blue",
                        "borderWidth": 2,
                        "pointRadius": 0
                    }]
                },
                "options": {
                    "title": {"display": True, "text": title},
                    "scales": {
                        "xAxes": [{"ticks": {"autoSkip": True, "maxTicksLimit": 10}}]
                    }
                }
            }
        }

        # 4. 调用 QuickChart API 生成短链接
        try:
            # 注意：这里我们使用 POST 接口 /chart/create
            response = requests.post(
                "https://quickchart.io/chart/create",
                json=chart_config,
                timeout=10
            )
            response.raise_for_status()
            res_data = response.json()
            
            if res_data.get("success"):
                return res_data.get("url")
            else:
                raise Exception(f"QuickChart Error: {res_data.get('error')}")
                
        except Exception as e:
            print(f"  [!] Short URL generation failed, falling back to GET: {e}")
            # 回退到 GET 模式（备用）
            json_str = json.dumps(chart_config["chart"])
            encoded_config = urllib.parse.quote(json_str)
            return f"{self.base_url}?c={encoded_config}&w=600&h=300"
