"""
安全的用户配置管理器，使用加密存储API密钥
注意：这不是生产级别的加密，仅作基本保护
"""
import os
import json
import base64
import hashlib
from pathlib import Path
from typing import Dict, Optional


class SecureUserConfigManager:
    """
    使用简单加密算法的安全配置管理器
    注意：这不是生产级别的加密，仅作基本保护
    """
    
    def __init__(self, config_dir: str = "user_configs", password: str = None):
        self.config_dir = Path(config_dir)
        self._ensure_config_dir()
        
        # 使用密码生成密钥，如果没有提供密码则使用默认值（实际使用时应从环境变量获取）
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
        if not data:
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
        if not encrypted_data:
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
                config["api_keys"][key] = self._simple_encrypt(value)
            else:
                config["api_keys"][key] = value  # 空值不需要加密
                
        config_path = self.config_dir / f"{user_id}.json"
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            
    def load_user_config(self, user_id: str) -> Dict:
        """加载并解密用户配置"""
        config_path = self.config_dir / f"{user_id}.json"
        
        if not config_path.exists():
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
                decrypted_config["api_keys"][key] = self._simple_decrypt(encrypted_value)
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