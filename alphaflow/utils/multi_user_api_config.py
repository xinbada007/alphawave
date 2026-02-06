"""
多用户API配置管理器 - 用于管理多个用户的API密钥
"""
import json
import os
from typing import Dict, List, Optional
from pathlib import Path
from .api_rotator import api_rotator, add_api_key


class MultiUserApiConfig:
    """
    多用户API配置管理器
    """
    
    def __init__(self, config_file: str = "multi_user_api_config.json"):
        self.config_file = config_file
        self.config_dir = Path("user_configs")
        self.config_dir.mkdir(exist_ok=True)
        self.config_path = self.config_dir / config_file
        
    def load_config(self) -> Dict:
        """加载配置"""
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"users": {}, "api_keys": {}}
    
    def save_config(self, config: Dict):
        """保存配置"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    def add_user(self, user_id: str, name: str, email: str, api_keys: Dict[str, str] = None):
        """添加用户"""
        config = self.load_config()
        
        config["users"][user_id] = {
            "name": name,
            "email": email,
            "added_at": str(self._get_timestamp()),
            "api_keys": api_keys or {}
        }
        
        # 将API密钥添加到轮询器
        if api_keys:
            for provider, key in api_keys.items():
                if key.strip():  # 只添加非空密钥
                    add_api_key(provider, key, name)
        
        self.save_config(config)
        print(f"✅ 用户 {name} ({user_id}) 已添加")
    
    def add_user_api_key(self, user_id: str, provider: str, api_key: str):
        """为用户添加API密钥"""
        config = self.load_config()
        
        if user_id not in config["users"]:
            print(f"❌ 用户 {user_id} 不存在")
            return False
        
        if "api_keys" not in config["users"][user_id]:
            config["users"][user_id]["api_keys"] = {}
        
        config["users"][user_id]["api_keys"][provider] = api_key
        
        # 将API密钥添加到轮询器
        add_api_key(provider, api_key, config["users"][user_id]["name"])
        
        self.save_config(config)
        print(f"✅ 用户 {user_id} 的 {provider} API密钥已添加")
        return True
    
    def get_all_api_keys(self) -> Dict[str, List[Dict]]:
        """获取所有API密钥（按提供商分组）"""
        config = self.load_config()
        provider_keys = {}
        
        for user_id, user_data in config["users"].items():
            if "api_keys" in user_data:
                for provider, key in user_data["api_keys"].items():
                    if provider not in provider_keys:
                        provider_keys[provider] = []
                    provider_keys[provider].append({
                        "user_id": user_id,
                        "user_name": user_data["name"],
                        "api_key": key
                    })
        
        return provider_keys
    
    def get_users(self) -> Dict:
        """获取所有用户信息"""
        config = self.load_config()
        return config["users"]
    
    def get_api_rotator_stats(self):
        """获取API轮询器统计"""
        return api_rotator.get_stats()
    
    def _get_timestamp(self):
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now()
    
    def generate_api_key_request_form(self) -> str:
        """生成API密钥请求表单"""
        form_text = """
# API密钥收集表单

请各位协作者提供以下API密钥，以便我们实现API轮询以避免频率限制：

## 需要的API密钥清单

### 1. Alpha Vantage
- **用途**: 股票、外汇和加密货币数据
- **申请网站**: https://www.alphavantage.co/support/#api-key
- **获取方式**: 免费注册，立即获得API密钥
- **使用场景**: 基本股票数据、技术指标

### 2. Polygon.io
- **用途**: 实时和历史市场数据
- **申请网站**: https://polygon.io/
- **获取方式**: 注册账户，获取API密钥
- **使用场景**: 实时数据、股票、期货、外汇

### 3. Financial Modeling Prep (FMP)
- **用途**: 财务数据、财务报表、股票数据
- **申请网站**: https://financialmodelingprep.com/developer
- **获取方式**: 免费注册，邮件验证后获得API密钥
- **使用场景**: 财务报表、基本面数据

### 4. Tiingo
- **用途**: 历史股票和加密货币数据
- **申请网站**: https://api.tiingo.com/
- **获取方式**: 免费注册，通过邮件获取API密钥
- **使用场景**: 历史数据、回测

### 5. OpenBB
- **用途**: 综合金融数据平台
- **申请网站**: https://my.openbb.co/
- **获取方式**: 注册账户，获取API密钥
- **使用场景**: 综合数据源

### 6. AllTick
- **用途**: 市场数据和基本面数据
- **API密钥**: d512a2cb352dfb3b7d10c5ae0fe09b99-c-app (预设密钥)
- **使用场景**: 作为备用数据源

## 请提供的信息

请每位协作者提供以下信息：

```
姓名: [您的姓名]
邮箱: [您的邮箱]
API密钥:
  - Alpha Vantage: [您的密钥]
  - Polygon: [您的密钥]
  - FMP: [您的密钥]
  - Tiingo: [您的密钥]
  - OpenBB: [您的密钥]
```

## 说明

- 所有API密钥将被安全存储
- 我们将使用轮询机制，自动在不同的API密钥之间切换
- 这将显著减少频率限制问题
- 您的密钥只用于项目数据获取
- 我们会定期监控API使用情况

请将以上信息发送给我，我将为您配置API轮询系统。
"""
        return form_text


# 全局实例
multi_user_config = MultiUserApiConfig()


def initialize_default_keys():
    """初始化默认API密钥"""
    # 添加项目中已有的API密钥
    default_keys = {
        "alltick": "d512a2cb352dfb3b7d10c5ae0fe09b99-c-app",
        "alpha_vantage": "AED72KC95E69FL8Q",  # 从MEMORY.md获取
        "polygon": "zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd",  # Massive API
        "fmp": "5u27af6jTiLZov0Kmqz2LZ9leNlKzguO",  # FMP API
        "tiingo": "dec443b34083c7a97bd36916d09adf18260cf807"  # Yellow's Tiingo API
    }
    
    for provider, key in default_keys.items():
        if key.strip():
            add_api_key(provider, key, "Project_Default")
    
    print("✅ 默认API密钥已加载到轮询器")


# 初始化默认密钥
initialize_default_keys()