#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AlphaWave依赖安装脚本
"""

import subprocess
import sys
import os


def install_cryptography():
    """安装cryptography库"""
    print("正在安装cryptography库...")
    
    try:
        # 尝试使用pip3
        result = subprocess.run([sys.executable.replace('python', 'pip3'), 'install', 'cryptography'], 
                              capture_output=True, text=True, check=True)
        print("✓ cryptography库安装成功!")
        return True
    except subprocess.CalledProcessError:
        print("✗ pip3安装失败，尝试使用python -m pip...")
        
        try:
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'cryptography'], 
                                  capture_output=True, text=True, check=True)
            print("✓ cryptography库安装成功!")
            return True
        except subprocess.CalledProcessError:
            print("✗ 安装cryptography库失败")
            print("错误信息:", result.stderr if 'result' in locals() else "未知错误")
            return False


def check_cryptography():
    """检查cryptography是否已安装"""
    try:
        import cryptography
        print("✓ cryptography库已安装")
        return True
    except ImportError:
        print("✗ cryptography库未安装")
        return False


def install_all_dependencies():
    """安装所有依赖"""
    print("检查并安装AlphaWave依赖...")
    print("-" * 40)
    
    # 检查并安装cryptography
    if not check_cryptography():
        print("需要安装cryptography库以支持加密功能")
        response = input("是否现在安装? (Y/n): ").strip().lower()
        if response != 'n':
            if install_cryptography():
                print("\n✓ 所有依赖安装完成!")
            else:
                print("\n⚠️  部分依赖安装失败，系统将以基础模式运行")
        else:
            print("\n⚠️  跳过依赖安装，系统将以基础模式运行")
    else:
        print("\n✓ 所有依赖已就绪!")


if __name__ == "__main__":
    install_all_dependencies()