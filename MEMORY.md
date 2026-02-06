# MEMORY.md - AlphaFlow项目长期记忆

## 项目概述
AlphaFlow是一个金融数据分析框架，支持多用户协作和API轮询以避免频率限制。

## 核心功能
- 数据收集：支持多种数据源（市场数据、基本面数据）
- 技术分析：RSI、MACD、KDJ等技术指标计算
- 可视化：图表生成和报告输出
- 多用户：支持团队协作和API密钥共享

## API轮询系统
### 2026-02-06 实现的API轮询功能
- 解决API访问频率限制问题
- 支持多用户API密钥管理
- 自动在多个API密钥间轮询使用
- 智能错误恢复和回退机制

### 支持的API提供商
- Alpha Vantage: AED72KC95E69FL8Q
- Polygon via Massive API: zKymT6Pvn7zUf01xuL8bGwKd0moZ1bMd
- Financial Modeling Prep: 5u27af6jTiLZov0Kmqz2LZ9leNlKzguO
- AllTick: d512a2cb352dfb3b7d10c5ae0fe09b99-c-app

### 系统架构
- ApiRotator: API密钥轮询器
- MultiUserApiConfig: 多用户配置管理
- api_rotation_decorator: API轮询装饰器
- 更新的收集器: market_data.py, fundamental.py

## 关键文件
- alphaflow/utils/api_rotator.py: API轮询核心
- alphaflow/utils/multi_user_api_config.py: 多用户管理
- alphaflow/components/collectors/: 数据收集器
- scripts/add_user_api_keys.py: 用户管理脚本
- API_KEY_COLLECTION_FORM.md: API密钥收集表单
- docs/: 详细文档

## 工作流程
1. 用户提供API密钥
2. 系统将密钥加入轮询池
3. 请求时自动选择可用密钥
4. 监控使用情况和错误
5. 自动处理频率限制和错误恢复