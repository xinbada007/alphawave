import os
from user_configs.secure_config_manager import SecureConfigManager


# 全局加密管理器实例
_config_manager = None

def _get_config_manager():
    """获取 SecureConfigManager 实例（懒加载）"""
    global _config_manager
    if _config_manager is None:
        password = os.environ.get('CONFIG_PASSWORD', 'alphaflow_key')
        _config_manager = SecureConfigManager(
            config_dir="user_configs",
            password=password
        )
    return _config_manager


def get_tushare_token() -> str:
    """
    获取 Tushare Token（自动解密）
    
    从加密配置文件 user_configs/tushare.json 读取
    如未配置，抛出异常提示用户设置
    """
    try:
        config = _get_config_manager().load_user_config("tushare")
        token = config.get("api_keys", {}).get("token")
        if token:
            return token
    except FileNotFoundError:
        raise FileNotFoundError(
            "Tushare token 未配置。请先运行:\n"
            "  python scripts/set_tushare_token.py <your_token>\n"
            "或:\n"
            "  from alphaflow.utils.tushare_config import set_tushare_token\n"
            "  set_tushare_token('your_token')"
        )
    
    raise ValueError("Tushare token 未在配置文件中找到")


def set_tushare_token(token: str) -> None:
    """设置并加密保存 Tushare Token"""
    _get_config_manager().save_user_config("tushare", {
        "api_keys": {"token": token},
        "settings": {}
    })
    print(f"✓ Tushare token 已加密保存到 user_configs/tushare.json")
