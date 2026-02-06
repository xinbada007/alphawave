#!/usr/bin/env python3
"""
Multi-User Configuration Guide for AlphaWave
"""

print("""
# 🌊 AlphaWave Multi-User Configuration Guide

AlphaWave has been enhanced to support multiple users, each with their own API keys.

## 📋 Configuration Commands

### 1. Set API Keys for a User
```bash
python configure_user.py --user-id <your_user_id> --action set
```

### 2. View Your Current Configuration
```bash
python configure_user.py --user-id <your_user_id> --action show
```

### 3. List All Users with Configurations
```bash
python configure_user.py --user-id dummy --action list
```

## 🚀 Running AlphaWave with User Configuration

```bash
# Run with your user-specific API keys
python main_with_user_support.py --symbols NVDA --user-id <your_user_id>

# Run with specific provider
python main_with_user_support.py --symbols NVDA --provider polygon --user-id <your_user_id>

# Run with proxy and user configuration
python main_with_user_support.py --symbols NVDA --user-id <your_user_id> --proxy socks5://127.0.0.1:10800
```

## 🏗️ How It Works

1. Each user has their own configuration file stored in `user_configs/<user_id>.json`
2. When running AlphaWave with `--user-id`, the system loads that user's API keys
3. The system automatically configures OpenBB with the appropriate keys before running the pipeline
4. All existing functionality remains intact, but now with user-specific configurations

## 🔐 Supported API Keys per User

- Polygon API Key
- FMP API Key
- Tiingo API Key
- Alpha Vantage API Key

Each user can have different API keys for different services, allowing for personalized usage limits and quotas.
""")