import json
import os
import base64
from typing import Dict, Optional
from cryptography.fernet import Fernet


class SimpleSecureConfigManager:
    """
    简单的安全配置管理器，使用Fernet加密存储API密钥
    """
    
    def __init__(self, config_dir: str = "user_configs", encryption_key: str = None):
        self.config_dir = config_dir
        self._ensure_config_dir()
        
        # 如果没有提供加密密钥，则生成一个
        if encryption_key:
            # 假设传入的是URL安全的base64编码密钥
            self.key = base64.urlsafe_b64decode(encryption_key.ljust(43, '='))
        else:
            # 生成一个新的密钥
            self.key = Fernet.generate_key()
        
        # 确保密钥是正确的格式
        if isinstance(self.key, bytes) and len(self.key) != 32:
            # 如果不是32字节，重新生成
            self.key = Fernet.generate_key()
            
        # 确保key是Fernet兼容的格式
        if isinstance(self.key, bytes):
            self.cipher_suite = Fernet(self.key)
        else:
            # 如果key不是bytes类型，生成新的
            self.key = Fernet.generate_key()
            self.cipher_suite = Fernet(self.key)
        
    def _ensure_config_dir(self):
        """确保配置目录存在"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
            
    def _encrypt(self, data: str) -> str:
        """加密数据"""
        if not data:
            return data
        encrypted_data = self.cipher_suite.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
        
    def _decrypt(self, encrypted_data: str) -> str:
        """解密数据"""
        if not encrypted_data:
            return encrypted_data
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self.cipher_suite.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception as e:
            print(f"解密失败: {e}")
            return encrypted_data  # 返回原始数据作为fallback
            
    def save_user_config(self, user_id: str, api_keys: Dict[str, str], settings: Dict = None):
        """保存加密的用户配置"""
        config = {
            "api_keys": {},
            "settings": settings or {}
        }
        
        # 加密API密钥
        for key, value in api_keys.items():
            if value:  # 如果值不为空，则加密存储
                config["api_keys"][key] = self._encrypt(value)
            else:
                config["api_keys"][key] = value  # 空值不需要加密
                
        config_path = os.path.join(self.config_dir, f"{user_id}.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            
    def load_user_config(self, user_id: str) -> Dict:
        """加载并解密用户配置"""
        config_path = os.path.join(self.config_dir, f"{user_id}.json")
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"用户配置文件不存在: {config_path}")
            
        with open(config_path, 'r', encoding='utf-8') as f:
            encrypted_config = json.load(f)
            
        # 解密API密钥
        decrypted_config = {
            "api_keys": {},
            "settings": encrypted_config.get("settings", {})
        }
        
        for key, encrypted_value in encrypted_config["api_keys"].items():
            if encrypted_value:  # 如果加密值不为空，则解密
                decrypted_config["api_keys"][key] = self._decrypt(encrypted_value)
            else:
                decrypted_config["api_keys"][key] = encrypted_value  # 空值不需要解密
                
        return decrypted_config
        
    def update_user_api_key(self, user_id: str, key_type: str, value: str):
        """更新特定用户的API密钥"""
        try:
            # 尝试加载现有配置
            config = self.load_user_config(user_id)
        except FileNotFoundError:
            # 如果配置不存在，创建新配置
            config = {"api_keys": {}, "settings": {}}
            
        config["api_keys"][key_type] = value
        self.save_user_config(user_id, config["api_keys"], config["settings"])
        
    def get_encryption_key(self) -> str:
        """返回可用于解密的密钥（以base64格式）"""
        return base64.urlsafe_b64encode(self.key).decode()