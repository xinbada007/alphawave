"""
User configuration management for AlphaFlow multi-user support
"""
import os
import json
import base64
import hashlib
from pathlib import Path
from typing import Dict, Optional


class UserConfigManager:
    """
    Manages user-specific API keys and configurations
    Each user gets their own config file in user_configs/{user_id}.json
    """
    
    def __init__(self, config_dir="user_configs", use_encryption=True, password: str = None):
        self.config_dir = Path(config_dir)
        self.use_encryption = use_encryption
        self.config_dir.mkdir(exist_ok=True)
        
        # 如果启用加密，设置加密密钥
        if self.use_encryption:
            if password:
                self.password = password
            else:
                # 在实际应用中，应该从环境变量或其他安全源获取
                self.password = os.environ.get('CONFIG_PASSWORD', 'default_secure_password_for_demo')
                
            # 生成加密密钥
            self.key = hashlib.sha256(self.password.encode()).digest()
        
    def _ensure_config_dir(self):
        """确保配置目录存在"""
        self.config_dir.mkdir(exist_ok=True)
    
    def _simple_encrypt(self, data: str) -> str:
        """简单的XOR加密（仅作基本保护，非生产级）"""
        if not data or not self.use_encryption:
            return data
            
        # 将数据转换为字节
        data_bytes = data.encode('utf-8')
        key_bytes = self.key
        
        # XOR加密
        encrypted_bytes = bytearray()
        for i in range(len(data_bytes)):
            encrypted_bytes.append(data_bytes[i] ^ key_bytes[i % len(key_bytes)])
        
        # Base64编码以便存储
        return base64.b64encode(encrypted_bytes).decode('utf-8')
        
    def _simple_decrypt(self, encrypted_data: str) -> str:
        """简单的XOR解密"""
        if not encrypted_data or not self.use_encryption:
            return encrypted_data
            
        try:
            # Base64解码
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            key_bytes = self.key
            
            # XOR解密
            decrypted_bytes = bytearray()
            for i in range(len(encrypted_bytes)):
                decrypted_bytes.append(encrypted_bytes[i] ^ key_bytes[i % len(key_bytes)])
                
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            print(f"解密失败: {e}")
            # 尝试使用默认密码解密（向后兼容）
            try:
                # 使用默认密码解密（对应于之前创建的yellow配置）
                default_password = "yellow_user_secure_password"
                default_key = hashlib.sha256(default_password.encode()).digest()
                
                encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
                
                decrypted_bytes = bytearray()
                for i in range(len(encrypted_bytes)):
                    decrypted_bytes.append(encrypted_bytes[i] ^ default_key[i % len(default_key)])
                    
                return decrypted_bytes.decode('utf-8')
            except:
                return encrypted_data  # 返回原始数据作为fallback
        
    def get_user_config_path(self, user_id: str) -> Path:
        """Get the config file path for a specific user"""
        return self.config_dir / f"{user_id}.json"
        
    def save_user_config(self, user_id: str, api_keys: dict, settings: dict = None):
        """Save API keys for a specific user with optional encryption"""
        config = {
            "api_keys": {},
            "settings": settings or {}
        }
        
        # 加密API密钥（如果启用加密）
        for key, value in api_keys.items():
            if value:  # 如果值不为空，则加密存储（如果启用加密）
                config["api_keys"][key] = self._simple_encrypt(value)
            else:
                config["api_keys"][key] = value  # 空值不需要加密
                
        config_path = self.get_user_config_path(user_id)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            
    def load_user_config(self, user_id: str) -> dict:
        """Load API keys for a specific user, return empty dict if not found, with decryption if needed"""
        config_path = self.get_user_config_path(user_id)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                encrypted_config = json.load(f)
            
            # 如果配置包含加密数据，进行解密
            if "api_keys" in encrypted_config:
                # 解密API密钥
                decrypted_config = {
                    "api_keys": {},
                    "settings": encrypted_config.get("settings", {})
                }
                
                for key, encrypted_value in encrypted_config["api_keys"].items():
                    if encrypted_value:  # 如果加密值不为空，则解密
                        decrypted_config["api_keys"][key] = self._simple_decrypt(encrypted_value)
                    else:
                        decrypted_config["api_keys"][key] = encrypted_value  # 空值不需要解密
                        
                return decrypted_config
            else:
                # 向后兼容：旧格式配置文件
                return {"api_keys": encrypted_config, "settings": {}}
        return {"api_keys": {}, "settings": {}}
        
    def has_user_config(self, user_id: str) -> bool:
        """Check if a user has saved configuration"""
        config_path = self.get_user_config_path(user_id)
        return config_path.exists()


# Global instance with encryption enabled by default
config_manager = UserConfigManager(use_encryption=True)