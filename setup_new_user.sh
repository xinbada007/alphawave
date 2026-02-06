#!/bin/bash
# AlphaWave 新用户快速设置脚本

echo "🌊 欢迎使用 AlphaWave 金融分析框架!"
echo "====================================="

# 检查Python版本
echo "🔍 检查Python版本..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到python3，请先安装Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Python版本: $PYTHON_VERSION"

# 检查并安装依赖
echo ""
echo "📦 检查并安装依赖..."

# 检查是否已安装cryptography
if python3 -c "import cryptography" &> /dev/null; then
    echo "✅ cryptography 已安装"
else
    echo "🔧 安装 cryptography (用于API密钥加密)..."
    if pip3 install cryptography; then
        echo "✅ cryptography 安装成功"
    else
        echo "⚠️  cryptography 安装失败，将使用基础加密模式"
    fi
fi

# 检查是否已安装openbb
if python3 -c "import openbb" &> /dev/null; then
    echo "✅ openbb 已安装"
else
    echo "🔧 安装 openbb..."
    if pip3 install openbb; then
        echo "✅ openbb 安装成功"
    else
        echo "❌ openbb 安装失败"
        exit 1
    fi
fi

echo ""
echo "🔐 设置用户配置"
echo "------------------"
read -p "请输入您的用户ID: " USER_ID

if [ -z "$USER_ID" ]; then
    echo "❌ 用户ID不能为空"
    exit 1
fi

echo ""
echo "🔧 运行配置脚本为用户 '$USER_ID' 设置API密钥..."
python3 configure_user.py --user-id "$USER_ID"

echo ""
echo "✅ 设置完成!"
echo "🎉 您现在可以使用以下命令运行分析:"
echo "   python3 main_secure_user_support.py --symbols NVDA --user-id $USER_ID"
echo ""
echo "📚 查看更多文档:"
echo "   - README.md : 项目概述和使用说明"
echo "   - AGENT.md : 协同开发指南"
echo "   - DEPENDENCIES.md : 依赖库详情"
echo "   - user_setup_guide.md : 用户配置详细指南"