import akshare as ak
import pandas as pd

def audit_akshare_hk_metrics(code: str = "00700"):
    print(f"--- 正在获取腾讯控股 ({code}) 的所有实时财务指标 ---")
    
    try:
        # 获取接口数据
        df = ak.stock_hk_financial_indicator_em(symbol=code)
        
        if df.empty:
            print("错误：未获取到数据，请检查网络或代码。")
            return

        # 获取第一行（最新数据）并转为字典
        # 使用 strip() 清理可能存在的空格
        all_metrics = {str(k).strip(): v for k, v in df.iloc[0].to_dict().items()}

        print(f"\n共发现 {len(all_metrics)} 个字段：\n")
        print("-" * 50)
        
        # 按照 Key 排序打印，方便你查找
        for key in sorted(all_metrics.keys()):
            value = all_metrics[key]
            print(f"{key:25} | {value}")
            
        print("-" * 50)
        
        # 特别关注：检查我们“降维打击”方案需要的锚点
        target_anchors = ["市盈率", "市净率", "市销率", "市现率", "总市值(港元)"]
        print("\n[锚点对齐检查]:")
        for anchor in target_anchors:
            if anchor in all_metrics:
                print(f"✅ 发现锚点 [{anchor}]: {all_metrics[anchor]}")
            else:
                print(f"❌ 缺失锚点 [{anchor}]")

    except Exception as e:
        print(f"发生异常: {e}")

if __name__ == "__main__":
    audit_akshare_hk_metrics("00700")