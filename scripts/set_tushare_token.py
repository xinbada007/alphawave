#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设置 Tushare Token（加密存储）

用法:
    python scripts/set_tushare_token.py your_token_here
"""
import sys
sys.path.insert(0, '.')

from alphaflow.components.collectors.tushare_config import set_tushare_token

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/set_tushare_token.py <token>")
        print("Example: python scripts/set_tushare_token.py 9a94dea09fff...")
        sys.exit(1)
    
    token = sys.argv[1]
    set_tushare_token(token)
