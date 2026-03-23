import pandas as pd
import tushare as ts
import numpy as np
import time

pro = ts.pro_api('b7bf12884a6ba2a5b33717fea342a6e8d3ab2fa80b5bb8ff6682e20f')
df = pro.index_weight(index_code='000300.SH', start_date='20230101', end_date='20251231')

hs300_code_list = df['con_code'].drop_duplicates().to_list()
dict_stock = {}
for code in hs300_code_list:
    hs300_daily = pro.daily(ts_code=str(code), start_date='20230101', end_date='20251231', fields='ts_code,trade_date,open,close')
    hs300_daily['trade_date'] = pd.to_datetime(hs300_daily['trade_date'], format='%Y%m%d')
    hs300_daily.sort_values(by=['trade_date'], inplace=True, ascending=True)
    hs300_daily.set_index('trade_date', inplace=True)

    hs300_daily['ma5'] = hs300_daily['close'].rolling(window=5).mean()
    hs300_daily['ma20'] = hs300_daily['close'].rolling(window=20).mean()
    valid = hs300_daily['ma5'].notna() & hs300_daily['ma20'].notna()
    signal = (hs300_daily['ma5'] > hs300_daily['ma20']).astype('Int64')
    signal[~valid] = pd.NA

    cross = signal.diff()
    hs300_daily['cross'] = cross.fillna(0).astype(int).values
    if hs300_daily.empty:
        print('fail!')
        break
    time.sleep(0.12)
    dict_stock[code] = hs300_daily
print('dict_stock is ready!')

sample = hs300_code_list[:5]
vol = 100  # 股

def run_portfolio_strategy(time_begin, time_end, portfolio=sample, initial_capital=200000):
    import matplotlib.pyplot as plt
    t = pd.date_range(start=time_begin, end=time_end, freq='B', normalize=True)

    # positions = {cod: pd.DataFrame([],index=t,columns=['date','price','vol']) for cod in portfolio}  # 每个个股动态持仓记录
    cum_return = pd.Series(np.zeros(len(t)), index=t)  # 累计收益率数组
    vol_sum = {cod: 0 for cod in portfolio}  # 个股动态持仓数量(股)
    cost = {cod: 0.00 for cod in portfolio}  # 个股动态持仓成本(元)

    for current_date in t:
        delta = 0
        for cod in portfolio:
            df_stock = dict_stock.get(cod)
            try:
                row = df_stock.loc[current_date]
            except KeyError:
                continue

            cross_val = int(row['cross']) if not pd.isna(row['cross']) else 0
            price = float(row['close'])
            if cross_val == 1:  # 买入
                vol_sum[cod] += vol
                cost[cod] = (cost[cod]*(vol_sum[cod]-vol) + price*vol)/vol_sum[cod]   # 更新持仓成本
                print(f" 在 {current_date.date()} 买入 {cod}, 价格 {price}")
            elif cross_val == -1:  # 卖出
                if  vol_sum[cod] >= vol:
                    vol_sum[cod] -= vol
                    cost[cod] = (cost[cod]*(vol_sum[cod]+vol) - price*vol)/vol_sum[cod] if vol_sum[cod] > 0 else 0  # 更新持仓成本
                    print(f" 在 {current_date.date()} 卖出 {cod}, 价格 {price}")
                else:
                    pass

            delta += vol_sum[cod]*(price-cost[cod])
        cum_ret = delta/initial_capital
        cum_return[current_date] = cum_ret

    plt.plot(cum_return.index, cum_return.values)
    plt.title('Cumulative Return of Portfolio')
    plt.xlabel('Date')
    plt.ylabel('Cumulative Return')
    plt.grid()
    plt.show()

run_portfolio_strategy('20240101','20241231',sample)