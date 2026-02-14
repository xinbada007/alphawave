import tushare as ts
import akshare as ak
import datetime
import os
from tabulate import tabulate
from tqdm import tqdm
import pandas as pd
import time
from scipy.stats import percentileofscore
import numpy as np
import math
import random


daily_dir = os.path.join("data", "daily")
weekly_dir = os.path.join("data", "weekly") # 新增周线数据目录
timeslp = 15

def get_pro():
    TOEKN_PATH = os.path.expanduser("./.tushare.token")

    if not os.path.exists(daily_dir):
        # 目录不存在，创建目录
        os.makedirs(os.path.join(daily_dir))

    with open(TOEKN_PATH, "r") as f:
        token = f.read().strip()
        ts.set_token(token=token)
        pro = ts.pro_api(token=token)
        return pro

def get_trade_cal(pro):
    start_date = "20240101"
    end_date = datetime.datetime.now().strftime("%Y%m%d")
    cal_date_df = pro.trade_cal(
            exchange="SSE",
            is_open="1",
            start_date=start_date,
            end_date=end_date,
            fields="cal_date",
        )
    cal_date_list = list(cal_date_df["cal_date"])
    start_date = cal_date_list[300]
    end_date = cal_date_list[0]
    prev_date = cal_date_list[1]
    print("start:", start_date, "end:", end_date)
    return start_date, end_date ,prev_date

def get_hk_hold_df(pro,prev_date):
    #hk_hold_df = pro.hk_hold(trade_date=prev_date,exchange="HK")
    #hk_hold_df = hk_hold_df[["ts_code","name","vol","ratio"]]
    #hk_hold_df = hk_hold_df[hk_hold_df["ratio"]>=1]
    hk_hold_df = pd.read_csv("GGTBDZQMD.csv", dtype={"证券代码": str})
    hk_hold_df["ts_code"] = hk_hold_df["证券代码"].apply(lambda x: f"{x}.HK")
    hk_hold_df["name"] = hk_hold_df["中文简称(参考)"]
    hk_hold_df.to_csv("./hk_hold.csv", index=False)
    print(len(hk_hold_df))
    print(hk_hold_df.head())
    return hk_hold_df

def get_fund_basic_df(pro):
    fund_basic_df = pro.fund_basic(market='E')
    fund_basic_df = fund_basic_df[fund_basic_df["delist_date"].isna()]
    fund_basic_df = fund_basic_df[fund_basic_df["status"]=="L"]
    fund_basic_df = fund_basic_df[fund_basic_df["name"].str.contains("LOF")==False ]
    fund_basic_df = fund_basic_df[["ts_code","name","management","m_fee","c_fee","benchmark"]]
    fund_basic_df["fee"] = (fund_basic_df["m_fee"] + fund_basic_df["c_fee"])*100
    fund_basic_df["fee"] = fund_basic_df["fee"].astype(int)
    print(len(fund_basic_df))
    fund_basic_df = fund_basic_df.groupby('benchmark').apply(
        lambda x: x[x['fee'] == x['fee'].min()],
        include_groups=True
    ).reset_index(drop=True)
    fund_basic_df.to_csv("./fund_basic.csv", index=False)
    print(len(fund_basic_df))
    print(tabulate(fund_basic_df.head(),headers="keys"))
    return fund_basic_df

def get_stock_basic_df(pro):
    stock_basic_df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_status,list_date')
    stock_basic_df = stock_basic_df[stock_basic_df["name"].str.contains("ST")==False ]
    stock_basic_df = stock_basic_df[stock_basic_df["name"].str.contains("退")==False ]
    stock_basic_df.to_csv("./stock_basic.csv", index=False)
    print(len(stock_basic_df))
    print(tabulate(stock_basic_df.head(),headers="keys"))
    return stock_basic_df

def get_stock_daily(pro,stock_basic_df,start,end,asset='E'):
    for c in tqdm(list(stock_basic_df["ts_code"]), desc="Processing"):
        chunk_filename = os.path.join(daily_dir, f"{c}.parquet")
        if os.path.exists(chunk_filename):
            exist_df = pd.read_parquet(chunk_filename)
            if exist_df["trade_date"].iloc[-1] >= end:
                continue
        try:
            c_df = ts.pro_bar(ts_code=c, adj="qfq", start_date=start,asset=asset)
            if c_df is None or c_df.empty:
                print(c, ", empty")
                continue
            c_df = c_df.sort_values(by="trade_date", ascending=True, ignore_index=True)
            c_df.to_parquet(chunk_filename, index=False)
            time.sleep(0.2)
        except Exception as e:
            print(c, ", empty ",e)
            time.sleep(1)


def get_fund_daily(pro,stock_basic_df,start,end):
    progress_bar = tqdm(list(stock_basic_df["ts_code"]))
    for c in progress_bar:
        c_symbol = c.split(".")[0]
        if c_symbol.startswith("16"):
            continue
        progress_bar.set_description(f"Processing {c}")
        chunk_filename = os.path.join(daily_dir, f"{c}.parquet")
        if os.path.exists(chunk_filename):
            exist_df = pd.read_parquet(chunk_filename)
            if exist_df["trade_date"].iloc[-1] >= end:
                continue
        try:
            # c_df = pro.hk_daily_adj(ts_code=c, start_date=start, end_date=end)
            # if c_df is None or c_df.empty:
            #     print(c, ", empty")
            #     continue
            # c_df = c_df.sort_values(by="trade_date", ascending=True, ignore_index=True)
            # c_df.to_parquet(chunk_filename, index=False)
            # time.sleep(2)
            c_df = ak.fund_etf_hist_em(symbol=c_symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
            c_df["ts_code"] = c
            if c_df is None or "日期" not in c_df.columns:
                print(f"Failed to get fund data for {trade_date}")
                print(code, trade_date)
                continue
            # c_df["日期"] = c_df["日期"].apply(
            #     lambda x: x.strftime("%Y%m%d")
            # )
            c_df['日期'] = pd.to_datetime(c_df['日期']).dt.strftime('%Y%m%d')
            c_df = c_df.rename(
                columns={
                    "日期": "trade_date",
                    "开盘": "open",
                    "收盘": "close",
                    "最高": "high",
                    "最低": "low",
                    "成交量": "vol",
                    "成交额": "amount",
                    "振幅": "amplitude",
                    "涨跌幅": "pct_chg",
                    "涨跌额": "change",
                    "换手率": "turnover_rate",
                }
            )
            c_df = c_df.sort_values(by="trade_date", ascending=True, ignore_index=True)
            c_df.to_parquet(chunk_filename, index=False)
            SLEEP_SECOND = random.randint(timeslp, timeslp+10)
            time.sleep(SLEEP_SECOND)
        except Exception as e:
            print(c, ", empty ",e)
            SLEEP_SECOND = random.randint(timeslp, timeslp+10)
            time.sleep(SLEEP_SECOND)

def get_hk_daily(pro,hk_hold_df,start,end):
    progress_bar = tqdm(list(hk_hold_df["ts_code"]))
    for c in progress_bar:
        c_symbol = c.split(".")[0]
        progress_bar.set_description(f"Processing {c}")
        chunk_filename = os.path.join(daily_dir, f"{c}.parquet")
        if os.path.exists(chunk_filename):
            exist_df = pd.read_parquet(chunk_filename)
            if exist_df["trade_date"].iloc[-1] >= end:
                continue
        try:
            # c_df = pro.hk_daily_adj(ts_code=c, start_date=start, end_date=end)
            # if c_df is None or c_df.empty:
            #     print(c, ", empty")
            #     continue
            # c_df = c_df.sort_values(by="trade_date", ascending=True, ignore_index=True)
            # c_df.to_parquet(chunk_filename, index=False)
            # time.sleep(2)
            c_df = ak.stock_hk_hist(symbol=c_symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
            c_df["ts_code"] = c_symbol + ".HK"
            if c_df is None or "日期" not in c_df.columns:
                print(f"Failed to get HK data for {trade_date}")
                print(code, trade_date)
                continue
            c_df["日期"] = c_df["日期"].apply(
                lambda x: x.strftime("%Y%m%d")
            )
            c_df = c_df.rename(
                columns={
                    "日期": "trade_date",
                    "开盘": "open",
                    "收盘": "close",
                    "最高": "high",
                    "最低": "low",
                    "成交量": "vol",
                    "成交额": "amount",
                    "振幅": "amplitude",
                    "涨跌幅": "pct_chg",
                    "涨跌额": "change",
                    "换手率": "turnover_rate",
                }
            )
            c_df = c_df.sort_values(by="trade_date", ascending=True, ignore_index=True)
            c_df.to_parquet(chunk_filename, index=False)
            SLEEP_SECOND = random.randint(timeslp, timeslp+10)
            time.sleep(SLEEP_SECOND)
        except Exception as e:
            print(c, ", empty ",e)
            SLEEP_SECOND = random.randint(timeslp, timeslp+10)
            time.sleep(SLEEP_SECOND)

def is_lower_shadow_candle(open_price, high_price, low_price, close_price, body_shadow_ratio=2.0, upper_shadow_limit_ratio=1.0):
    """
    识别一条K线是否为长下影线K线（如锤子线）。

    参数:
    open_price (float): 开盘价
    high_price (float): 最高价
    low_price (float): 最低价
    close_price (float): 收盘价
    body_shadow_ratio (float): 下影线与实体最小比例，默认为2.0，表示下影线至少是实体的2倍。
    upper_shadow_limit_ratio (float): 上影线与实体最大比例，默认为1.0，表示上影线长度应小于实体长度。

    返回:
    bool: 如果是下影线K线则返回 True，否则返回 False。
    """
    # 计算实体、上影线、下影线的长度
    body_size = abs(open_price - close_price)
    upper_shadow = high_price - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low_price

    # 规则1：必须有下影线
    if lower_shadow <= 0:
        return False

    # 规则2：处理实体非常小或为0的情况 (十字星)
    # 如果实体为0，我们要求下影线足够长（例如，是总振幅的一半以上）
    if body_size < 1e-6: # 使用一个很小的数来判断浮点数是否接近0
        total_range = high_price - low_price
        if total_range > 1e-6:
             # 对于十字星，要求下影线显著，上影线很短
            return lower_shadow / total_range > 0.6 and upper_shadow / total_range < 0.1
        else:
            return False # K线没有波动

    # 规则3：下影线足够长
    condition1 = lower_shadow >= body_size * body_shadow_ratio

    # 规则4：上影线足够短
    condition2 = upper_shadow < body_size * upper_shadow_limit_ratio

    return condition1 and condition2

def calculate_atr(df, period=14):
    """
    计算给定DataFrame的ATR(平均真实波幅)指标。
    :param df: pandas DataFrame，必须包含 'high', 'low', 'close' 列。
    :param period: ATR的计算周期，默认为14。
    :return: 返回添加了 'atr' 列的 DataFrame。
    """
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = np.abs(df['high'] - df['close'].shift())
    df['low_close'] = np.abs(df['low'] - df['close'].shift())
    
    # TR (True Range) 是三者中的最大值
    df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    
    # ATR 是 TR 的移动平均
    df['atr'] = df['tr'].rolling(window=period, min_periods=1).mean()
    
    # 删除中间计算列
    df.drop(['high_low', 'high_close', 'low_close', 'tr'], axis=1, inplace=True)
    
    return df

def daily_to_weekly(df):
    """
    将日线数据转换为周线数据
    """
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.set_index('trade_date')
    # 重采样到每周
    weekly_df = df.resample('W').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'vol': 'sum'
    })
    # 移除周末等没有交易数据的行
    weekly_df = weekly_df.dropna()
    weekly_df['trade_date'] = weekly_df.index
    return weekly_df

def calculate_single_indicator(df, ts_code, name, annualize_factor):
    """
    计算单个股票/基金的指标，返回一个字典
    """
    if df.empty:
        return None

    vol2 = df["vol"].tail(2).mean()
    close = df["close"].iloc[-1]
    vol_per100 = percentileofscore(df["vol"], vol2)
    price_per100 = percentileofscore(df["close"], close)
    lower_shadow1 = is_lower_shadow_candle(df["open"].iloc[-1], df["high"].iloc[-1], df["low"].iloc[-1], df["close"].iloc[-1])
    lower_shadow2 = is_lower_shadow_candle(df["open"].iloc[-2], df["high"].iloc[-2], df["low"].iloc[-2], df["close"].iloc[-2])
    lower = lower_shadow1 or lower_shadow2

    df['ma60'] = df['close'].rolling(window=60).mean()
    latest_ma60 = df['ma60'].iloc[-1]

    df = calculate_atr(df.copy(), period=14) # 传入副本避免修改原始df
    latest_atr14 = df['atr'].iloc[-1]

    # 确保有足够的数据计算斜率
    if len(df.tail(25).close) >= 2:
        y = np.log(df.tail(25).close)
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        annualized_returns = math.pow(math.exp(slope), annualize_factor) - 1
        r_squared = 1 - (
            sum((y - (slope * x + intercept)) ** 2) / ((len(y) - 1) * np.var(y, ddof=1))
        ) if len(y) > 1 and np.var(y, ddof=1) != 0 else 0 # 避免除以零
        score = annualized_returns * r_squared
    else:
        slope = np.nan
        intercept = np.nan
        annualized_returns = np.nan
        r_squared = np.nan
        score = np.nan


    return {
        "ts_code": ts_code,
        "name": name,
        "close": close,
        "vol_per100": vol_per100,
        "price_per100": price_per100,
        "lower_shadow": lower,
        "ma60": latest_ma60,
        "atr14": latest_atr14,
        "score": score,
    }


def calc_indicator(hk_hold_df, fund_basic_df, stock_basic_df, end):
    all_daily_data = []
    all_weekly_data = []

    for basic_df in [hk_hold_df, fund_basic_df, stock_basic_df]:
        basic_df = basic_df.set_index("ts_code")
        for c in tqdm(list(basic_df.index), desc="Processing"):
            try:
                chunk_filename = os.path.join(daily_dir, f"{c}.parquet")
                if not os.path.exists(chunk_filename):
                    continue
                c_df = pd.read_parquet(chunk_filename)
                c_df_end_date = c_df["trade_date"].iloc[-1]
                if c_df_end_date < end:
                    print(f"Skipping {c}, last trade date {c_df_end_date} does not match end date {end}.")
                    continue

                stock_name = basic_df.loc[c, "name"]

                # --- 计算日线指标 ---
                daily_indicators = calculate_single_indicator(c_df.copy(), c, stock_name, annualize_factor=250)
                if daily_indicators:
                    all_daily_data.append(daily_indicators)

                # --- 日线转周线并保存 ---
                weekly_c_df = daily_to_weekly(c_df.copy())
                weekly_chunk_filename = os.path.join(weekly_dir, f"{c}.parquet")
                weekly_c_df.to_parquet(weekly_chunk_filename, index=False)

                # --- 计算周线指标 ---
                weekly_indicators = calculate_single_indicator(weekly_c_df.copy(), c, stock_name, annualize_factor=52)
                if weekly_indicators:
                    all_weekly_data.append(weekly_indicators)

            except Exception as e:
                print(f"Error processing {c}: {e}")
                continue

    daily_indicator_df = pd.DataFrame(all_daily_data)
    daily_indicator_df.to_csv("./daily_indicator.csv", index=False)

    weekly_indicator_df = pd.DataFrame(all_weekly_data)
    weekly_indicator_df.to_csv("./weekly_indicator.csv", index=False)

def get_daily_basic(pro,stock_basic_df, end):
    df = pro.daily_basic(ts_code='', trade_date=end)
    df = df.set_index("ts_code")
    df = df.join(stock_basic_df.set_index("ts_code")[["name"]])
    df.to_csv("./daily_basic.csv")

def get_hot_df():
    #东财人气
    stock_hot_rank_em_df = ak.stock_hot_rank_em()
    stock_hot_rank_em_df['ts_code'] = stock_hot_rank_em_df['代码'].str.slice(2) + '.' + stock_hot_rank_em_df['代码'].str.slice(0, 2)
    stock_hot_rank_em_df = stock_hot_rank_em_df.set_index("ts_code")
    #东财飙升
    stock_hot_up_em_df = ak.stock_hot_up_em()
    stock_hot_up_em_df['ts_code'] = stock_hot_up_em_df['代码'].str.slice(2) + '.' + stock_hot_up_em_df['代码'].str.slice(0, 2)
    stock_hot_up_em_df = stock_hot_up_em_df.set_index("ts_code")

    #东财港股
    stock_hk_hot_rank_em_df = ak.stock_hk_hot_rank_em()
    stock_hk_hot_rank_em_df['ts_code'] = stock_hk_hot_rank_em_df['代码'] + '.HK'

    hk_hold_df = pd.read_csv("GGTBDZQMD.csv", dtype={"证券代码": str})
    hk_hold_df["ts_code"] = hk_hold_df["证券代码"].apply(lambda x: f"{x}.HK")
    stock_hk_hot_rank_em_df = stock_hk_hot_rank_em_df.set_index("ts_code")
    stock_hk_hot_rank_em_df = stock_hk_hot_rank_em_df[stock_hk_hot_rank_em_df.index.isin(hk_hold_df["ts_code"])]
    
    hot_df = pd.concat(
                [
                    stock_hot_rank_em_df,
                    stock_hk_hot_rank_em_df,
                    stock_hot_up_em_df,
                ],
                ignore_index=False,
            )
    hot_df.to_csv("./hot.csv", index=True)

def main():
    pro = get_pro()
    start,end,prev_date = get_trade_cal(pro)
    hk_hold_df = get_hk_hold_df(pro,prev_date)
    fund_basic_df = get_fund_basic_df(pro)
    stock_basic_df = get_stock_basic_df(pro)
    get_stock_daily(pro,stock_basic_df,start,end)
    get_fund_daily(pro,fund_basic_df,start,end)
    get_hk_daily(pro,hk_hold_df,start,end)
    calc_indicator(hk_hold_df,fund_basic_df,stock_basic_df,end)
    get_daily_basic(pro,stock_basic_df, end)
    get_hot_df()
    print("Data collection completed successfully.")


if __name__ == "__main__":
    main()
