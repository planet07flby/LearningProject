import pandas as pd
import tushare as ts
import numpy as np
import time
import matplotlib.pyplot as plt

pro = ts.pro_api('b7bf12884a6ba2a5b33717fea342a6e8d3ab2fa80b5bb8ff6682e20f')
df = pro.index_weight(index_code='000300.SH', start_date='20230101', end_date='20251231')

hs300_code_list = df['con_code'].drop_duplicates().to_list()
dict_stock = {}
for code in hs300_code_list:
    hs300_daily = pro.daily(ts_code=str(code), start_date='20230101', end_date='20251231', fields='ts_code,trade_date,open,close')
    hs300_daily['ma5'] = hs300_daily['close'].rolling(window=5).mean()
    hs300_daily['ma20'] = hs300_daily['close'].rolling(window=20).mean()
    signal = pd.Series(np.where((hs300_daily['ma5'] - hs300_daily['ma20'])>0, 1, 0))
    cross = signal.diff().fillna(0)
    hs300_daily['cross'] = cross
    if hs300_daily.empty:
        print('fail!')
        break
    time.sleep(0.12)
    dict_stock[code] = hs300_daily
print('dict_stock is ready!')

sample = hs300_code_list[:10]
volume = 100  # 股

def run_portfolio_strategy(portfolio=sample,time_begin=20240101,time_end=20241231):
    for code in portfolio:
        df1 = dict_stock[code]
        df1 = df1[(df1['trade_date']>=str(time_begin)) & (df1['trade_date']<=str(time_end))]
        buy_price = df1[df1['cross']==1]['close'].values
        sell_price = df1[df1['cross']==-1]['close'].values
        if len(buy_price)==0 or len(sell_price)==0:
            buy_price = None
            sell_price = None
        if len(buy_price) > len(sell_price):
            buy_price = buy_price[:len(sell_price)]
        elif len(buy_price) < len(sell_price):
            sell_price = sell_price[:len(buy_price)]

        yearly_return = (sell_price - buy_price).sum()*volume
        yearly_return_ratio = yearly_return / (buy_price.sum()*volume)
        print(f'{code} 年化收益: {yearly_return}元, 年化收益率: {yearly_return_ratio}%')
    print('over')