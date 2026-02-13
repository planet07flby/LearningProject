# config.py
"""策略配置文件"""

# 回测时间范围
START_DATE = '2024-11-06'
END_DATE = '2025-11-13'

# 资金配置
INITIAL_CASH = 1000000  # 初始资金
BENCHMARK = '399101.XSHE'  # 基准指数（深证综指）

# JQData账号（需要注册）
JQ_USERNAME = '17821197073'
JQ_PASSWORD = 'planet07XXX'

# 回测设置
PLOT_RESULTS = True  # 是否绘制图表
OUTPUT_CSV = True    # 是否输出CSV文件
CACHE_DATA = True    # 是否缓存数据

# 策略参数（可选，可以在strategy.py中硬编码，也可以这里覆盖）
STOCK_NUM = 6
STOPLOSS_LIMIT = 0.91