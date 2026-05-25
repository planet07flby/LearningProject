import pandas as pd
import baostock as bs


# TODO: 登录登出逻辑

def to_bs(code, start, end, freq='D', adj='qfq'):
    # 适配bs的api格式
    code = str(code)
    if code[0] in ['6']:
        code = 'sh.' + code
    elif code[0] in ['0', '2', '3']:
        code = 'sz.' + code
    else:
        code = 'bj.' + code
    start_date = pd.to_datetime(start).strftime('%Y-%m-%d')
    end_date = pd.to_datetime(end).strftime('%Y-%m-%d')
    freq = {'D':'d','W':'w','M':'m','5':'5','15':'15','30':'30','60':'60'}.get(freq, 'd')
    adjustflag = {'qfq':'2','hfq':'1', None:'3'}.get(adj, '2')
    return code, start_date, end_date, freq, adjustflag

# 历史日/周/月线K线数据
def get_data(code, start, end, freq='D', adj='qfq'):
    try:
        code, start_date, end_date, freq, adjustflag = to_bs(code, start, end, freq, adj)
        bs.login()
        rs = bs.query_history_k_data_plus(code, 'date,code,open,high,low,close,preclose,pctChg,volume,amount', start_date=start_date, end_date=end_date, frequency=freq, adjustflag=adjustflag)
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        if not data_list:  # 无数据直接返回空 DataFrame
            return pd.DataFrame()
        df = pd.DataFrame(data_list, columns=rs.fields)
        df.rename(columns={'pctChg':'pct_chg','volume':'vol'},inplace=True)
        df['vol'] = df['vol'].astype(float) / 100
        df['amount'] = df['amount'].astype(float) / 10000
        order = ['code', 'date', 'open', 'high', 'low', 'close', 'preclose', 'pct_chg', 'vol', 'amount']
        df = df[order]
        if df.empty or df is None:
            return pd.DataFrame()
        return df
    finally:
        bs.logout()

# 历史分钟K线数据
def get_minute_data(code, start, end, freq='5', adj='qfq'):
    try:
        code, start_date, end_date, freq, adjustflag = to_bs(code, start, end, freq, adj)
        bs.login()
        rs = bs.query_history_k_data_plus(code, 'date,time,code,open,high,low,close,volume,amount', start_date=start_date, end_date=end_date, frequency=freq, adjustflag=adjustflag)
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        if not data_list:  # 无数据直接返回空 DataFrame
            return pd.DataFrame()
        df = pd.DataFrame(data_list, columns=rs.fields)
        df.rename(columns={'volume':'vol'},inplace=True)
        df['vol'] = df['vol'].astype(float) / 100
        df['amount'] = df['amount'].astype(float) / 10000
        order = ['code', 'date', 'time', 'open', 'high', 'low', 'close', 'vol', 'amount']
        df = df[order]
        if df.empty or df is None:
            return pd.DataFrame()
        return df
    finally:
        bs.logout()