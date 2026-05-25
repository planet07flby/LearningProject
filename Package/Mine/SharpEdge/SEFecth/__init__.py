# 包
import SETushare as SETushare
import SEBaostock as SEBaostock


def use(package):

    if package in ["tushare","ts"]:
        return SETushare
    elif package in ['baostock','bs']:
        return SEBaostock
    elif package in []:
        return None


# code: 000001,'000001' freq: 'D' 'W' 'M' start: '20200101' end: '20200131' adj: 'qfq'前复权 'hfq'后复权 None不复权
# code date open high low close preclose pct_chg vol(手) amount(万)
def get_data(code, start, end, adj, freq='D', package='bs'):
    module = use(package)
    return module.get_data(code, start, end, freq, adj)


# 这里freq只支持'5','15','30','60'
def get_minute_data(code, start, end, freq='5', adj='qfq'):
    return SEBaostock.get_minute_data(code, start, end, freq, adj)