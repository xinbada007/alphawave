import json
import os
import hashlib
from cryptography.fernet import Fernet
from typing import Dict, Optional


class SecureUserConfigManager:
    """
    安全的用户配置管理器，使用加密存储API密钥
    """
    
    def __init__(self, config_dir: str = "user_configs"):
        self.config_dir = config_dir
        self._ensure_config_dir()
        
        # 使用主机唯一标识符生成密钥（实际应用中可能需要更安全的方法）
        self.key = self._generate_key()
        self.cipher_suite = Fernet(self.key)
        
    def _ensure_config_dir(self):
        """确保配置目录存在"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
            
    def _generate_key(self) -> bytes:
        """基于环境变量或主机信息生成加密密钥"""
        # 在实际部署中，建议从环境变量获取密钥
        secret_key = os.environ.get('CONFIG_ENCRYPTION_KEY', 'default_fallback_key_for_demo')
        # 使用SHA256哈希确保密钥长度符合要求
        key = hashlib.sha256(secret_key.encode()).digest()[:32]  # 32字节密钥
        # Base64编码以符合Fernet要求
        encoded_key = base64.urlsafe_b64encode(key)
        return encoded_key
        
    def _encrypt(self, data: str) -> str:
        """加密数据"""
        encrypted_data = self.cipher_suite.encrypt(data.encode())
        return encrypted_data.decode()
        
    def _decrypt(self, encrypted_data: str) -> str:
        """解密数据"""
        decrypted_data = self.cipher_suite.decrypt(encrypted_data.encode())
        return decrypted_data.decode()
        
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
        
import base64