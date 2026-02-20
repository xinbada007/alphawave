import asyncio
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

async def test_akshare_hk_hist():
    # --- 修改这里 ---
    symbol = "01810"  # 小米集团 (注意使用5位代码)
    # ----------------
    
    days = 5
    start_date = (datetime.now() - timedelta(days=int(days * 1.8))).strftime("%Y%m%d")
    
    print(f"请求参数: symbol={symbol}, start_date={start_date}")
    
    try:
        df = await asyncio.to_thread(
            ak.stock_hk_hist,
            symbol=symbol, 
            period="daily",
            start_date=start_date,
            adjust="qfq",
        )
        
        if df is None or df.empty:
            print("返回数据为空!")
            return
            
        print("前5行数据:")
        print(df.head())

    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            print(f"【错误】无法获取数据。请检查股票代码 '{symbol}' 是否正确，或该股票是否已退市/暂停上市。")
        else:
            print(f"Type Error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_akshare_hk_hist())