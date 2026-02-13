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
            # 自动修复: 对于 SOCKS5 代理，强烈建议使用 socks5h:// 以强制远程 DNS 解析
            # 这通常能解决由于本地 DNS 污染或限制导致的超时问题
            if proxy_url.startswith("socks5://"):
                proxy_url = proxy_url.replace("socks5://", "socks5h://")
            
            # 注入环境变量 (支持大小写，增加兼容性)
            for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
                os.environ[key] = proxy_url
                
            # 强制打印（即便不是 DEBUG 模式），因为代理配置非常关键
            print(f"[*] Network Proxy Applied: {proxy_url}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
