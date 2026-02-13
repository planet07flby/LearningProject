# strategy.py
"""
纯策略逻辑文件 - 不包含任何回测引擎代码
所有函数都是纯业务逻辑，接收context参数并操作g对象
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any


# 注意：这里没有 from jqdata import *
# 所有数据获取通过 context.data_api 或全局函数

def initialize(context):
    """初始化策略参数"""
    # 创建g对象（策略全局变量）
    context.g = type('G', (), {})()
    g = context.g

    # ========== 策略二核心参数 ==========
    g.no_trading_today_signal = False
    g.pass_april = True
    g.run_stoploss = True
    g.hold_list = []
    g.yesterday_HL_list = []
    g.target_list = []
    g.not_buy_again = []
    g.stock_num = 6
    g.up_price = 20
    g.limit_days_window = 3 * 250
    g.init_stock_count = 1000
    g.reason_to_sell = ''
    g.stoploss_strategy = 3
    g.stoploss_limit = 0.91
    g.stoploss_market = 0.93
    g.HV_control = False
    g.HV_duration = 120
    g.HV_ratio = 0.9
    g.stockL = []
    g.no_trading_buy = []
    g.no_trading_hold_signal = False

    # ========== 策略一防御参数 ==========
    g.enable_extreme_defense = True
    g.defense_mode = False
    g.extreme_drop_threshold = 0.85
    g.defense_position_ratio = 0.5
    g.foreign_ETF = ['518880.XSHG', '513030.XSHG', '513100.XSHG']

    print(f"策略初始化完成，参数: stock_num={g.stock_num}")


def prepare_stock_list(context):
    """准备股票列表"""
    g = context.g
    # 获取持仓列表
    g.hold_list = []
    for stock, position in context.portfolio.positions.items():
        g.hold_list.append(stock)

    if g.hold_list:
        # 使用context.data_api获取数据
        df = context.data_api.get_price(
            g.hold_list,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close', 'high_limit', 'low_limit'],
            count=1
        )
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code) if not df.empty else []
    else:
        g.yesterday_HL_list = []

    g.no_trading_today_signal = today_is_between(context)


def get_history_highlimit(context, stock_list, days=3 * 250, p=0.10):
    """涨停基因筛选"""
    g = context.g
    df = context.data_api.get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close", "high_limit"],
        count=days,
    )

    if df.empty:
        return []

    df = df[df["close"] == df["high_limit"]]
    grouped_result = df.groupby('code').size().reset_index(name='count')
    grouped_result = grouped_result.sort_values(by=["count"], ascending=False)
    result_list = grouped_result["code"].tolist()[:int(len(grouped_result) * p)]
    context.log(f"筛选前合计{len(grouped_result)}个，筛选后合计{len(result_list)}个")
    return result_list


def get_start_point(context, stock_list, days=3 * 250):
    """启动点筛选"""
    g = context.g
    df = context.data_api.get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["open", "low", "close", "high_limit"],
        count=days,
    )

    if df.empty:
        return []

    stock_start_point = {}
    stock_price_bias = {}

    # 注意：这里需要current_data，但current_data需要在调用前设置
    current_data = getattr(context, 'current_data', {})

    for code, group in df.groupby('code'):
        group = group.sort_values('time')
        limit_hit_rows = group[group['close'] == group['high_limit']]

        if not limit_hit_rows.empty:
            latest_limit_hit = limit_hit_rows.iloc[-1]
            latest_limit_index = latest_limit_hit.name
            previous_rows = group[group.index <= latest_limit_index].iloc[::-1]

            for idx, row in previous_rows.iterrows():
                if row['close'] < row['open']:
                    stock_start_point[code] = row['low']
                    break

    for code, start_point in stock_start_point.items():
        last_price = current_data.get(code, {}).get('last_price', 0)
        if last_price > 0 and start_point > 0:
            bias = last_price / start_point
            stock_price_bias[code] = bias

    sorted_list = sorted(stock_price_bias.items(), key=lambda x: x[1], reverse=False)
    return [i[0] for i in sorted_list]


def get_stock_list(context):
    """主选股函数"""
    g = context.g
    final_list = []
    yesterday = context.previous_date

    # 获取全市场股票
    initial_list = context.data_api.get_all_securities(["stock"], yesterday)

    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(context, initial_list)
    initial_list = filter_paused_stock(context, initial_list)

    # 获取财务数据排序
    q = {
        'table': 'valuation',
        'fields': ['code', 'market_cap'],
        'filters': [('code', 'in', initial_list)],
        'order_by': ('market_cap', 'asc'),
        'limit': g.init_stock_count
    }
    df = context.data_api.get_fundamentals(q, date=yesterday)

    if df is not None and not df.empty:
        initial_list = df['code'].tolist()

    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)

    initial_list = get_history_highlimit(context, initial_list, g.limit_days_window)
    initial_list = get_start_point(context, initial_list, g.limit_days_window)

    stock_list = get_stock_industry(context, initial_list)
    final_list = stock_list[:g.stock_num * 2]
    context.log('今日前10:%s' % str(final_list[:10]))

    return final_list


def get_stock_industry(context, stock):
    """行业分散"""
    g = context.g
    result = context.data_api.get_industry(stock)
    selected_stocks = []
    industry_list = []

    for stock_code, info in result.items():
        if 'sw_l2' in info:
            industry_name = info['sw_l2']['industry_name']
            if industry_name not in industry_list:
                industry_list.append(industry_name)
                selected_stocks.append(stock_code)
                if len(industry_list) == 10:
                    break
    return selected_stocks


def weekly_adjustment(context):
    """周频调仓"""
    g = context.g
    # 防御模式：如果市场极端下跌，调整策略
    if getattr(g, 'defense_mode', False):
        context.log.warning("防御模式激活，谨慎调仓")
        defense_adjustment(context)
        return

    # 正常执行策略二的调仓逻辑
    if not g.no_trading_today_signal:
        close_no_trading_hold(context)
        g.not_buy_again = []
        g.target_list = get_stock_list(context)
        target_list = g.target_list[:g.stock_num * 2]
        context.log(str(target_list))

        # 调仓卖出
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.yesterday_HL_list):
                context.log("卖出[%s]" % (stock))
                context.order_target_value(stock, 0)
            else:
                context.log("已持有[%s]" % (stock))

        # 调仓买入
        buy_security(context, target_list)

        # 记录已买入股票
        for stock in context.portfolio.positions.keys():
            g.not_buy_again.append(stock)


def sell_stocks(context):
    """止损函数"""
    g = context.g
    if not g.run_stoploss:
        return

    if g.stoploss_strategy in [2, 3]:
        # 大盘止损
        index_stocks = context.data_api.get_index_stocks('399101.XSHE')
        stock_df = context.data_api.get_price(
            index_stocks,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close', 'open'],
            count=1
        )
        if not stock_df.empty:
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                context.log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    context.order_target_value(stock, 0)
                return

    if g.stoploss_strategy in [1, 3]:
        # 个股止损
        for stock, position in context.portfolio.positions.items():
            if position.price < position.avg_cost * g.stoploss_limit:
                context.order_target_value(stock, 0)
                context.log.debug("收益止损,卖出{}".format(stock))
                g.reason_to_sell = 'stoploss'


def trade_afternoon(context):
    """下午交易"""
    g = context.g
    if not g.no_trading_today_signal:
        check_limit_up(context)
        if g.HV_control:
            check_high_volume(context)
        huanshou(context)
        check_remain_amount(context)


def check_limit_up(context):
    """检查涨停股"""
    g = context.g
    now_time = context.current_dt
    if g.yesterday_HL_list:
        for stock in g.yesterday_HL_list:
            if stock in context.portfolio.positions:
                position = context.portfolio.positions[stock]
                if position.closeable_amount > 0:
                    current_data = context.data_api.get_price(
                        stock,
                        end_date=now_time,
                        frequency='1m',
                        fields=['close', 'high_limit'],
                        count=1
                    )
                    if not current_data.empty:
                        if current_data.iloc[0]['close'] < current_data.iloc[0]['high_limit']:
                            context.log.info("[%s]涨停打开，卖出" % (stock))
                            context.order_target_value(stock, 0)
                            g.reason_to_sell = 'limitup'
                        else:
                            context.log.info("[%s]涨停，继续持有" % (stock))


def check_remain_amount(context):
    """检查剩余资金"""
    g = context.g
    if g.reason_to_sell == 'limitup':
        g.hold_list = list(context.portfolio.positions.keys())

        if len(g.hold_list) < g.stock_num:
            target_list = get_stock_list(context)
            target_list = filter_not_buy_again(context, target_list)
            target_list = target_list[:min(g.stock_num, len(target_list))]
            context.log.info('有余额可用' + str(round(context.portfolio.cash, 2)) + '元。' + str(target_list))
            buy_security(context, target_list)
        g.reason_to_sell = ''
    else:
        g.reason_to_sell = ''


def buy_security(context, target_list, cash=0, buy_number=0):
    """买入函数"""
    g = context.g
    position_count = len(context.portfolio.positions)
    target_num = g.stock_num

    # 防御模式下降低仓位
    if g.defense_mode:
        target_num = max(2, int(g.stock_num * g.defense_position_ratio))
        context.log.info(f"防御模式下目标持仓数: {target_num}")

    if cash == 0:
        cash = context.portfolio.total_value
    if buy_number == 0:
        buy_number = target_num
    bought_num = 0

    if target_num > position_count:
        value = cash / target_num
        for stock in target_list:
            if stock not in context.portfolio.positions:
                if bought_num < buy_number:
                    if context.order_target_value(stock, value):
                        g.not_buy_again.append(stock)
                        bought_num += 1
                        if len(context.portfolio.positions) == target_num:
                            break


def check_extreme_market(context):
    """检查极端市场情况"""
    g = context.g
    if not g.enable_extreme_defense:
        return

    yesterday = context.previous_date
    indices_to_check = ['000300.XSHG', '000905.XSHG']
    extreme_drop_detected = False

    for index_code in indices_to_check:
        try:
            index_data = context.data_api.get_price(
                index_code,
                end_date=yesterday,
                frequency='daily',
                fields=['close'],
                count=5
            )

            if len(index_data) < 5:
                continue

            start_price = index_data['close'].iloc[0]
            end_price = index_data['close'].iloc[-1]

            if start_price > 0:
                change_pct = (end_price - start_price) / start_price
                if change_pct <= (g.extreme_drop_threshold - 1):
                    extreme_drop_detected = True
                    context.log.warning(f"指数{index_code}5日跌幅{change_pct * 100:.1f}%，触发极端下跌警报")
                    break
        except Exception as e:
            context.log.error(f"检查指数{index_code}时出错: {e}")

    # 检查是否可以退出防御模式
    if not extreme_drop_detected and g.defense_mode:
        if check_market_recovery(context):
            g.defense_mode = False
            context.log.info("市场恢复，退出防御模式")

    # 进入防御模式
    if extreme_drop_detected and not g.defense_mode:
        g.defense_mode = True
        context.log.warning("=== 进入防御模式 ===")


def check_market_recovery(context):
    """检查市场是否恢复"""
    yesterday = context.previous_date
    try:
        index_data = context.data_api.get_price(
            '000300.XSHG',
            end_date=yesterday,
            frequency='daily',
            fields=['close'],
            count=3
        )
        if len(index_data) < 3:
            return False
        return (index_data['close'].iloc[-1] > index_data['close'].iloc[-2] and
                index_data['close'].iloc[-2] > index_data['close'].iloc[-3])
    except Exception as e:
        context.log.error(f"检查市场恢复时出错: {e}")
        return False


def defense_adjustment(context):
    """防御模式下的调仓逻辑"""
    g = context.g
    context.log.warning("执行防御调仓")

    # 减仓至防御仓位比例
    current_positions = list(context.portfolio.positions.keys())
    if current_positions:
        target_position_count = max(2, int(len(current_positions) * g.defense_position_ratio))
        sell_count = len(current_positions) - target_position_count

        if sell_count > 0:
            # 简单策略：卖出一部分股票
            for i, stock in enumerate(current_positions):
                if i < sell_count:
                    if context.order_target_value(stock, 0):
                        context.log.info(f"防御减仓卖出: {stock}")

    # 配置防御性资产
    available_cash = context.portfolio.cash
    if available_cash > context.portfolio.total_value * 0.2 and g.foreign_ETF:
        etf = g.foreign_ETF[0]
        buy_amount = min(available_cash * 0.3, context.portfolio.total_value * 0.1)
        if context.order_target_value(etf, buy_amount):
            context.log.info(f"防御配置外盘ETF: {etf}, 金额: {buy_amount:.2f}")

    context.log.info(f"防御调仓完成，当前持仓: {len(context.portfolio.positions)}只")


# ========== 辅助过滤函数 ==========
def filter_paused_stock(context, stock_list):
    """过滤停牌股"""
    g = context.g
    current_data = getattr(context, 'current_data', {})
    return [s for s in stock_list if not current_data.get(s, {}).get('paused', False)]


def filter_st_stock(context, stock_list):
    """过滤ST股"""
    current_data = getattr(context, 'current_data', {})
    return [s for s in stock_list
            if not current_data.get(s, {}).get('is_st', False)
            and 'ST' not in current_data.get(s, {}).get('name', '')
            and '*' not in current_data.get(s, {}).get('name', '')
            and '退' not in current_data.get(s, {}).get('name', '')]


def filter_kcbj_stock(stock_list):
    """过滤科创板/北交所"""
    return [s for s in stock_list
            if not (s[0] == '4' or s[0] == '8' or s[:2] == '68')]


def filter_limitup_stock(context, stock_list):
    """过滤涨停股"""
    g = context.g
    last_prices = {}
    for stock in stock_list:
        df = context.data_api.get_price(stock, end_date=context.previous_date, frequency='1m', fields=['close'],
                                        count=1)
        if not df.empty:
            last_prices[stock] = df['close'].iloc[-1]

    current_data = getattr(context, 'current_data', {})
    return [s for s in stock_list
            if s in context.portfolio.positions.keys()
            or (s in last_prices and s in current_data
                and last_prices[s] < current_data[s].get('high_limit', float('inf')))]


def filter_limitdown_stock(context, stock_list):
    """过滤跌停股"""
    g = context.g
    last_prices = {}
    for stock in stock_list:
        df = context.data_api.get_price(stock, end_date=context.previous_date, frequency='1m', fields=['close'],
                                        count=1)
        if not df.empty:
            last_prices[stock] = df['close'].iloc[-1]

    current_data = getattr(context, 'current_data', {})
    return [s for s in stock_list
            if s in context.portfolio.positions.keys()
            or (s in last_prices and s in current_data
                and last_prices[s] > current_data[s].get('low_limit', 0))]


def filter_new_stock(context, stock_list):
    """过滤次新股"""
    g = context.g
    yesterday = context.previous_date
    result = []
    for stock in stock_list:
        info = context.data_api.get_security_info(stock)
        if info:
            days_since_listed = (yesterday - info['start_date']).days
            if days_since_listed >= 375:
                result.append(stock)
    return result


def filter_not_buy_again(context, stock_list):
    """过滤已买入"""
    g = context.g
    return [s for s in stock_list if s not in g.not_buy_again]


def today_is_between(context):
    """检查是否在空仓期"""
    g = context.g
    if not g.pass_april:
        return False
    today = context.current_dt.strftime('%m-%d')
    return ('04-01' <= today <= '04-30') or ('01-01' <= today <= '01-30')


def close_account(context):
    """收盘处理"""
    g = context.g
    if g.no_trading_today_signal and g.hold_list and not g.no_trading_hold_signal:
        for stock in g.hold_list:
            context.order_target_value(stock, 0)
            context.log.info("卖出[%s]" % (stock))
        buy_security(context, g.no_trading_buy)
        g.no_trading_hold_signal = True


def close_no_trading_hold(context):
    """清除非交易持仓"""
    g = context.g
    if g.no_trading_hold_signal:
        for stock in g.hold_list:
            context.order_target_value(stock, 0)
            context.log.info("卖出[%s]" % (stock))
        g.no_trading_hold_signal = False


# 换手率相关函数（简化版，需要根据实际数据完善）
def huanshou(context):
    """换手率检查"""
    g = context.g
    pass


def huanshoulv(context, stock, is_avg=False):
    """计算换手率"""
    g = context.g
    return 0.0