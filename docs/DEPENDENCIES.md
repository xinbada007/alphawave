# AlphaWave 项目依赖库文档

## 核心依赖

### 必需依赖
| 库名 | 版本要求 | 用途 | 安装命令 |
|------|----------|------|----------|
| openbb | latest | 金融数据获取和分析 | `pip3 install openbb` |
| pandas | >=1.3.0 | 数据处理和分析 | `pip3 install pandas` |
| numpy | >=1.20.0 | 数值计算 | `pip3 install numpy` |
| requests | >=2.25.0 | HTTP请求处理 | `pip3 install requests` |
| pydantic | >=1.8.0 | 数据验证和序列化 | `pip3 install pydantic` |

### 安全相关依赖
| 库名 | 版本要求 | 用途 | 安装命令 |
|------|----------|------|----------|
| cryptography | >=3.4.0 | API密钥加密存储 | `pip3 install cryptography` |
| bcrypt | >=3.2.0 | 密码哈希（可选） | `pip3 install bcrypt` |

### 可视化依赖
| 库名 | 版本要求 | 用途 | 安装命令 |
|------|----------|------|----------|
| matplotlib | >=3.3.0 | 图表绘制 | `pip3 install matplotlib` |
| plotly | >=5.0.0 | 交互式图表 | `pip3 install plotly` |

## 开发依赖

### 测试工具
| 库名 | 版本要求 | 用途 | 安装命令 |
|------|----------|------|----------|
| pytest | >=6.0.0 | 单元测试 | `pip3 install pytest` |
| pytest-asyncio | >=0.15.0 | 异步测试 | `pip3 install pytest-asyncio` |

### 代码质量
| 库名 | 版本要求 | 用途 | 安装命令 |
|------|----------|------|----------|
| black | >=21.0.0 | 代码格式化 | `pip3 install black` |
| flake8 | >=3.9.0 | 代码风格检查 | `pip3 install flake8` |
| mypy | >=0.800 | 类型检查 | `pip3 install mypy` |

## 特殊依赖（本项目新增）

### 安全配置管理
| 库名 | 版本要求 | 用途 | 安装命令 |
|------|----------|------|----------|
| cryptography | >=3.4.0 | 用户API密钥加密存储 | `pip3 install cryptography` |

## 安装说明

### 生产环境安装
```bash
pip3 install openbb pandas numpy requests pydantic cryptography
```

### 完整开发环境安装
```bash
pip3 install openbb pandas numpy requests pydantic cryptography matplotlib plotly pytest pytest-asyncio black flake8 mypy
```

## 依赖管理最佳实践

### 1. 版本锁定
在生产环境中使用 `requirements.txt` 锁定依赖版本：
```txt
openbb==latest
pandas>=1.3.0,<2.0.0
numpy>=1.20.0,<2.0.0
requests>=2.25.0,<3.0.0
pydantic>=1.8.0,<2.0.0
cryptography>=3.4.0,<4.0.0
```

### 2. 虚拟环境
建议使用虚拟环境安装依赖：
```bash
python3 -m venv alphawave_env
source alphawave_env/bin/activate  # Linux/Mac
# 或
alphawave_env\Scripts\activate  # Windows
pip3 install -r requirements.txt
```

### 3. 安全注意事项
- `cryptography` 库用于加密存储用户API密钥
- 不要在代码中硬编码任何API密钥
- 使用环境变量或加密配置文件管理敏感信息

## 依赖更新策略

### 安全更新
- 优先更新安全相关的依赖（如 `cryptography`）
- 定期检查依赖库的安全公告

### 功能更新
- 测试新版本与现有功能的兼容性
- 逐步更新非关键依赖
- 保持核心依赖的稳定性

## 故障排除

### 常见问题
1. **cryptography安装失败**: 
   - 确保系统有编译工具
   - 尝试 `pip3 install --upgrade pip setuptools wheel`

2. **openbb安装问题**:
   - 检查Python版本是否兼容
   - 确保有足够的磁盘空间

### 降级选项
如果加密库无法安装，可使用基础加密（安全性较低）：
```bash
pip3 install cryptography || echo "使用基础加密功能"
```

---
*此文档随项目发展持续更新*