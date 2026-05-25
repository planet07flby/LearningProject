import tushare as ts
import pandas as pd
import time

# 辅助函数: 处理code适配ts_code
def to_ts_code(code):
    if code[0] in [6]:
        code = code + '.SH'
    elif code[0] in [0, 2, 3]:
        code = code + '.SZ'
    else:
        code = code + '.BJ'
    return code

# TODO: api token设置逻辑

# 历史日/周/月线K线数据
# code: 000001,'000001' freq: 'D' 'W' 'M' start: '20200101' end: '20200131' if_fq: 'qfq'前复权 'hfq'后复权 None不复权
# code date open high low close preclose change pct_chg vol(手) amount(万)
def get_data(code, start, end, freq='D', adj='qfq'):
    pro = ts.pro_api()
    ts_code = to_ts_code(str(code))

    def fetch_data(frequency):
        if frequency in ['D']:
            df = ts.pro_bar(ts_code=ts_code, start_date=start, end_date=end, freq=frequency, adj=adj)
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.sort_values(by='trade_date', ascending=True).reset_index(drop=True)
            df['amount'] = df['amount'] / 10
            df.rename(columns={'ts_code':'code','trade_date':'time','pre_close':'preclose'}, inplace=True)
            df.drop('change', axis=1, inplace=True, errors='ignore')
            order = ['code', 'date', 'open', 'high', 'low', 'close', 'preclose', 'pct_chg', 'vol', 'amount']
            df = df[order]
            return df
        elif frequency in ['W', 'M']:
            df = pro.stk_week_month(ts_code=ts_code, start_date=start, end_date=end, freq=frequency, adj=adj)
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.sort_values(by='trade_date', ascending=True).reset_index(drop=True)
            df['amount'] = df['amount'] / 10
            df.rename(columns={'ts_code': 'code', 'trade_date': 'time', 'pre_close': 'preclose'}, inplace=True)
            df.drop('change', axis=1, inplace=True, errors='ignore')
            order = ['code', 'date', 'open', 'high', 'low', 'close', 'preclose', 'pct_chg', 'vol', 'amount']
            df = df[order]
            return df
        else:
            return pd.DataFrame()

    df = fetch_data(freq)
    if df is None or df.empty:
        time.sleep(0.2)
        df = fetch_data(freq)
        if df is None or df.empty:
            return pd.DataFrame()
    return df

