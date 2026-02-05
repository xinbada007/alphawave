from typing import Any, Dict, Optional
import os

class GlobalContext:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GlobalContext, cls).__new__(cls)
            cls._instance.config = {}
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        # 优先读取环境变量
        self.config['OPENBB_PAT'] = os.getenv('OPENBB_PAT', '')
        self.config['PROXY'] = os.getenv('ALPHAFLOW_PROXY', '')
        self.config['DEBUG'] = os.getenv('DEBUG', 'False').lower() == 'true'

    def apply_proxy(self):
        """将代理设置注入到系统环境变量，供 openbb, requests, httpx 使用"""
        proxy_url = self.config.get('PROXY')
        if proxy_url:
            os.environ['HTTP_PROXY'] = proxy_url
            os.environ['HTTPS_PROXY'] = proxy_url
            os.environ['ALL_PROXY'] = proxy_url
            if self.get('DEBUG'):
                print(f"[*] Proxy Applied: {proxy_url}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
