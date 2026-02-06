# 用户API密钥配置指南

## 概述
AlphaWave支持多用户协同使用，每个用户可以配置自己的API密钥以保证安全性和独立性。

## 安装依赖（首次使用前）

在使用前，请先安装必要的加密库：

```bash
pip3 install cryptography
```

如果无法安装cryptography，也可以使用基础版本（安全性较低）：

```bash
# 基础版本使用Python内置库，无需额外安装
```

## 用户配置流程

### 方法一：使用配置脚本（推荐）

1. 运行配置脚本：
```bash
python3 configure_user.py --user-id <your_user_id>
```

2. 按提示输入各种API密钥

### 方法二：手动创建配置文件

1. 在 `user_configs/` 目录下创建 `<your_user_id>.json` 文件
2. 按以下格式填写配置：

```json
{
  "api_keys": {
    "polygon": "your_polygon_api_key",
    "fmp": "your_fmp_api_key",
    "tiingo": "your_tiingo_api_key",
    "alpha_vantage": "your_alpha_vantage_api_key",
    "openbb": "your_openbb_username_if_needed"
  },
  "settings": {
    "default_provider": "polygon",
    "cache_enabled": true,
    "request_delay": 0.1
  }
}
```

## 安全说明

- 推荐使用加密存储方式（需安装cryptography）
- 如果使用明文存储，请确保配置文件权限安全
- 不要在公共仓库中提交包含真实API密钥的配置文件

## 使用示例

运行分析时指定用户ID：

```bash
python3 main_with_user_support.py --symbols AAPL,TSLA --user-id <your_user_id>
```

## 环境变量支持

您也可以通过环境变量设置加密密码：

```bash
export CONFIG_PASSWORD="your_secure_password"
python3 main_with_user_support.py --symbols AAPL --user-id <your_user_id>
```