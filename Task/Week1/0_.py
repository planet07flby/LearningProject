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

def run_portfolio_strategy(time_begin, time_end, portfolio=sample, initial_capital=100000):
    import matplotlib.pyplot as plt
    daily_value = []
    sery = pd.date_range(start=time_begin, end=time_end, freq='B', normalize=True)

    # 初始化每只股票的持仓（以股数为单位）
    positions = {cod: 0 for cod in portfolio}

    for current_date in sery:
        daily_delta = 0.0
        for cod in portfolio:
            df_stock = dict_stock.get(cod)
            if df_stock is None:
                continue
            try:
                row = df_stock.loc[current_date]
            except KeyError:
                continue

            cross_val = int(row['cross']) if not pd.isna(row['cross']) else 0
            price = float(row['close'])

            if cross_val == 1:  # 买入：只有买入时增加持仓并记录现金流出
                positions[cod] += vol
                daily_delta -= price * vol  # 买入为现金流出
                print(f" 在 {current_date.date()} 买入 {cod}, 价格 {price}")
            elif cross_val == -1:  # 卖出：仅在有足够持仓时卖出
                if positions.get(cod) >= vol:
                    positions[cod] -= vol
                    daily_delta += price * vol  # 卖出为现金流入
                    print(f" 在 {current_date.date()} 卖出 {cod}, 价格 {price}")
                else:
                    # 忽略无仓位的卖出信号（可选打印）
                    # print(f" 在 {current_date.date()} 忽略卖出 {cod}（无仓位）")
                    pass
        daily_value.append(daily_delta)

    cum_cash = pd.Series(np.cumsum(daily_value), index=sery)
    port_value = initial_capital + cum_cash
    ret_pct = (port_value / initial_capital - 1) * 100
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(port_value.index, port_value, color='skyblue', label='Portfolio Value')
    ax1.set_ylabel('Value')
    ax1.grid(True)

    ax2 = ax1.twinx()
    ax2.plot(ret_pct.index, ret_pct, color='orange', linestyle='--', label='Return %')
    ax2.set_ylabel('Return (%)')

    ax1.set_xlabel('Date')
    ax1.set_title('Portfolio Value and Return')
    fig.legend(loc='upper left', bbox_to_anchor=(0.1, 0.9))
    plt.show()



run_portfolio_strategy('20240101','20241231',sample)