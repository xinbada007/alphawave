import os
import pickle
import time
import hashlib
from typing import Any, Optional

class DiskCache:
    """
    一个简单的磁盘缓存工具，用于存储 DataFrame 或 API 响应。
    默认存储在项目根目录的 .cache 文件夹下。
    """
    def __init__(self, cache_dir=".cache", expiry_seconds=3600):
        self.cache_dir = cache_dir
        self.expiry_seconds = expiry_seconds
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def _get_hash(self, key: str) -> str:
        return hashlib.md5(key.encode()).hexdigest()

    def set(self, key: str, value: Any):
        hash_key = self._get_hash(key)
        file_path = os.path.join(self.cache_dir, f"{hash_key}.pkl")
        with open(file_path, "wb") as f:
            pickle.dump({
                "timestamp": time.time(),
                "data": value
            }, f)

    def get(self, key: str) -> Optional[Any]:
        hash_key = self._get_hash(key)
        file_path = os.path.join(self.cache_dir, f"{hash_key}.pkl")
        
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, "rb") as f:
                cached = pickle.load(f)
                
            # 检查是否过期
            if time.time() - cached["timestamp"] > self.expiry_seconds:
                return None
                
            return cached["data"]
        except Exception:
            return None
