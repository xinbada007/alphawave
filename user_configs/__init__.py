"""
User configuration management for AlphaWave multi-user support
"""
import os
import json
from pathlib import Path


class UserConfigManager:
    """
    Manages user-specific API keys and configurations
    Each user gets their own config file in user_configs/{user_id}.json
    """
    
    def __init__(self, config_dir="user_configs"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
    def get_user_config_path(self, user_id: str) -> Path:
        """Get the config file path for a specific user"""
        return self.config_dir / f"{user_id}.json"
        
    def save_user_config(self, user_id: str, api_keys: dict):
        """Save API keys for a specific user"""
        config_path = self.get_user_config_path(user_id)
        with open(config_path, 'w') as f:
            json.dump(api_keys, f, indent=2)
            
    def load_user_config(self, user_id: str) -> dict:
        """Load API keys for a specific user, return empty dict if not found"""
        config_path = self.get_user_config_path(user_id)
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        return {}
        
    def has_user_config(self, user_id: str) -> bool:
        """Check if a user has saved configuration"""
        config_path = self.get_user_config_path(user_id)
        return config_path.exists()


# Global instance
config_manager = UserConfigManager()