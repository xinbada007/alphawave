import akshare as ak
import pandas as pd
import os

def investigate_meituan_duplicates():
    stock_code = "03690" 
    print(f"\n>>> Investigating Meituan (03690) duplicates for 2025-06-30...")
    
    try:
        # 获取原始数据，不进行任何清洗
        df = ak.stock_financial_hk_report_em(
            stock=stock_code, 
            symbol="利润表", 
            indicator="报告期" 
        )

        if df.empty:
            print("❌ No data.")
            return

        # 筛选出 2025-06-30 的记录
        # 注意：这里可能需要匹配字符串或日期对象，具体看 API 返回
        df['REPORT_DATE_STR'] = df['REPORT_DATE'].astype(str)
        target_date = "2025-06-30"
        
        # 看看这一天有多少行
        # 东方财富港股接口通常返回的是长表：一个 REPORT_DATE 对应几十行（每个科目一行）
        # 如果有两条记录，意味着同一个科目（如“营业额”）在同一天出现了两次
        
        subset = df[df['REPORT_DATE_STR'].str.contains(target_date)]
        
        if subset.empty:
            print(f"❌ No records found for {target_date}. Available dates: {df['REPORT_DATE_STR'].unique()[:5]}")
            return

        print(f"Found {len(subset)} total rows for {target_date}.")
        
        # 统计每个科目的出现次数
        item_counts = subset['STD_ITEM_NAME'].value_counts()
        duplicates = item_counts[item_counts > 1]
        
        if not duplicates.empty:
            print(f"\nDuplicate Items found: {duplicates.index.tolist()[:3]} ...")
            
            # 取一个重复的科目（例如“营业额”或“收益”）深入查看
            example_item = duplicates.index[0]
            print(f"\n--- Detailed Comparison for Item: [{example_item}] on {target_date} ---")
            
            # 打印该科目下所有行，展示所有列
            rows = subset[subset['STD_ITEM_NAME'] == example_item]
            
            # 东方财富接口的关键列通常包括: 
            # 'REPORT_DATE', 'STD_ITEM_NAME', 'AMOUNT', 'CURRENCY', 'COMPANY_TYPE' 等
            print(rows.to_string())
            
            # 检查是否有币种或报表类型列
            potential_diff_cols = ['CURRENCY', 'UNIT', 'COMPANY_TYPE', 'REPORT_TYPE', 'ORG_TYPE']
            existing_diff_cols = [c for c in potential_diff_cols if c in df.columns]
            if existing_diff_cols:
                print(f"\nPotential differentiating columns: {existing_diff_cols}")
                print(rows[existing_diff_cols])
        else:
            print("\nNo duplicate STD_ITEM_NAME for the same date. The 'duplicate' in previous test might be a misunderstanding of the long-form data.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    investigate_meituan_duplicates()
