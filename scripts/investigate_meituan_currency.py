import akshare as ak
import pandas as pd
import os

def investigate_meituan_currency():
    stock_code = "03690" 
    print("\n>>> Investigating Meituan (03690) Currency and Scaling...")
    
    try:
        # 1. Check analysis indicators
        print("\n--- [stock_financial_hk_analysis_indicator_em] ---")
        df_analysis = ak.stock_financial_hk_analysis_indicator_em(symbol=stock_code, indicator="报告期")
        if not df_analysis.empty:
            df_analysis['REPORT_DATE'] = pd.to_datetime(df_analysis['REPORT_DATE'])
            latest_analysis = df_analysis.sort_values(by='REPORT_DATE', ascending=False).iloc[0]
            print("Latest Report Date:", latest_analysis['REPORT_DATE'].strftime('%Y-%m-%d'))
            
            # Print all columns to look for currency info
            # print("Columns available:", df_analysis.columns.tolist())
            
            # Check for specific currency columns
            cur_cols = [c for c in df_analysis.columns if '币' in c or 'CURRENCY' in str(c).upper()]
            if cur_cols:
                print("Currency info found in columns:")
                for col in cur_cols:
                    print(f"  {col}: {latest_analysis[col]}")
            else:
                print("No explicit currency column found in analysis indicators.")
            
            # Print basic values
            print("BASIC_EPS:", latest_analysis.get('BASIC_EPS'))
            print("BPS:", latest_analysis.get('BPS'))
            print("OPERATE_INCOME:", latest_analysis.get('OPERATE_INCOME'))

        # 2. Check raw report data for currency
        print("\n--- [stock_financial_hk_report_em] ---")
        df_report = ak.stock_financial_hk_report_em(stock=stock_code, symbol="利润表", indicator="报告期")
        if not df_report.empty:
            df_report['REPORT_DATE'] = pd.to_datetime(df_report['REPORT_DATE'])
            latest_date = df_report['REPORT_DATE'].max()
            subset = df_report[df_report['REPORT_DATE'] == latest_date]
            
            print("Latest Report Date:", latest_date.strftime('%Y-%m-%d'))
            
            # Check for CURRENCY or similar
            if 'CURRENCY' in subset.columns:
                print("Currencies listed in report:", subset['CURRENCY'].unique().tolist())
            
            # Look for "营业额" or "收益" to check magnitude
            rev_row = subset[subset['STD_ITEM_NAME'].str.contains('营业额|收益', na=False)]
            if not rev_row.empty:
                print("Revenue Example Row:")
                print(rev_row.iloc[0].to_dict())

    except Exception as e:
        print("❌ Error:", e)

if __name__ == "__main__":
    investigate_meituan_currency()
