# 克隆自聚宽文章：https://www.joinquant.com/post/1399
# 标题：【量化课堂】多因子策略入门
# 作者：JoinQuant量化课堂

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import time, datetime, timedelta


# 完整融合策略：策略二主体 + 策略一防御层
def initialize(context):
    # 基础设置
    set_option('avoid_future_data', True)
    set_benchmark('399101.XSHE')
    set_option('use_real_price', True)
    set_slippage(PriceRelatedSlippage(0.002), type="stock")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,
            open_commission=0.0001,
            close_commission=0.0001,
            close_today_commission=0,
            min_commission=1,
        ),
        type="stock",
    )

    # 日志设置
    log.set_level('order', 'error')
    log.set_level('system', 'error')

    # ========== 策略二核心参数（完全保留） ==========
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

    # ========== 策略一防御参数（新增） ==========
    g.enable_extreme_defense = True  # 启用极端防御
    g.defense_mode = False  # 当前是否防御模式
    g.extreme_drop_threshold = 0.85  # 极端下跌阈值(15%跌幅)
    g.defense_position_ratio = 0.5  # 防御模式下仓位比例
    g.foreign_ETF = ['518880.XSHG', '513030.XSHG', '513100.XSHG']  # 策略一的外盘ETF

    # ========== 定时函数 ==========
    run_daily(prepare_stock_list, '9:05')
    run_weekly(weekly_adjustment, 2, '10:30')
    run_daily(sell_stocks, time='10:00')
    run_daily(check_extreme_market, '9:30')  # 新增：检查极端市场
    run_daily(trade_afternoon, time='14:20')
    run_daily(trade_afternoon, time='14:55')
    run_daily(close_account, '14:50')


# ========== 策略二完整函数 ==========
def prepare_stock_list(context):
    """准备股票列表"""
    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)

    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit', 'low_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []

    g.no_trading_today_signal = today_is_between(context)


def get_history_highlimit(context, stock_list, days=3 * 250, p=0.10):
    """涨停基因筛选"""
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close", "high_limit"],
        count=days,
        panel=False,
    )
    df = df[df["close"] == df["high_limit"]]
    grouped_result = df.groupby('code').size().reset_index(name='count')
    grouped_result = grouped_result.sort_values(by=["count"], ascending=False)
    result_list = grouped_result["code"].tolist()[:int(len(grouped_result) * p)]
    log.info(f"筛选前合计{len(grouped_result)}个， 筛选后合计{len(result_list)}个")
    return result_list


def get_start_point(context, stock_list, days=3 * 250):
    """启动点筛选"""
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["open", "low", "close", "high_limit"],
        count=days,
        panel=False,
    )
    stock_start_point = {}
    stock_price_bias = {}
    current_data = get_current_data()

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
        last_price = current_data[code].last_price
        bias = last_price / start_point
        stock_price_bias[code] = bias

    sorted_list = sorted(stock_price_bias.items(), key=lambda x: x[1], reverse=False)
    return [i[0] for i in sorted_list]


def get_stock_list(context):
    """主选股函数"""
    final_list = []
    yesterday = context.previous_date
    initial_list = get_all_securities("stock", yesterday).index.tolist()

    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)

    q = query(
        valuation.code, indicator.eps
    ).filter(
        valuation.code.in_(initial_list)
    ).order_by(
        valuation.market_cap.asc()
    )
    df = get_fundamentals(q)
    initial_list = df['code'].tolist()[:g.init_stock_count]

    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)

    initial_list = get_history_highlimit(context, initial_list, g.limit_days_window)
    initial_list = get_start_point(context, initial_list, g.limit_days_window)

    stock_list = get_stock_industry(initial_list)
    final_list = stock_list[:g.stock_num * 2]
    log.info('今日前10:%s' % final_list[:10])

    return final_list


def get_stock_industry(stock):
    """行业分散"""
    result = get_industry(security=stock)
    selected_stocks = []
    industry_list = []

    for stock_code, info in result.items():
        industry_name = info['sw_l2']['industry_name']
        if industry_name not in industry_list:
            industry_list.append(industry_name)
            selected_stocks.append(stock_code)
            if len(industry_list) == 10:
                break
    return selected_stocks


def weekly_adjustment(context):
    """周频调仓（加入防御判断）"""
    # 防御模式：如果市场极端下跌，调整策略
    if g.defense_mode:
        log.warning("防御模式激活，谨慎调仓")
        defense_adjustment(context)
        return

    # 正常执行策略二的调仓逻辑
    if g.no_trading_today_signal == False:
        close_no_trading_hold(context)
        g.not_buy_again = []
        g.target_list = get_stock_list(context)
        target_list = g.target_list[:g.stock_num * 2]
        log.info(str(target_list))

        # 调仓卖出
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.yesterday_HL_list):
                log.info("卖出[%s]" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("已持有[%s]" % (stock))

        # 调仓买入
        buy_security(context, target_list)

        # 记录已买入股票
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.not_buy_again.append(stock)


def sell_stocks(context):
    """止损函数"""
    if g.run_stoploss == True:
        if g.stoploss_strategy == 1:
            for stock in context.portfolio.positions.keys():
                if context.portfolio.positions[stock].price >= context.portfolio.positions[stock].avg_cost * 2:
                    order_target_value(stock, 0)
                    log.debug("收益100%止盈,卖出{}".format(stock))
                elif context.portfolio.positions[stock].price < context.portfolio.positions[
                    stock].avg_cost * g.stoploss_limit:
                    order_target_value(stock, 0)
                    log.debug("收益止损,卖出{}".format(stock))
                    g.reason_to_sell = 'stoploss'
        elif g.stoploss_strategy == 2:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date,
                                 frequency='daily', fields=['close', 'open'], count=1, panel=False)
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
        elif g.stoploss_strategy == 3:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date,
                                 frequency='daily', fields=['close', 'open'], count=1, panel=False)
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
            else:
                for stock in context.portfolio.positions.keys():
                    if context.portfolio.positions[stock].price < context.portfolio.positions[
                        stock].avg_cost * g.stoploss_limit:
                        order_target_value(stock, 0)
                        log.debug("收益止损,卖出{}".format(stock))
                        g.reason_to_sell = 'stoploss'


def trade_afternoon(context):
    """下午交易"""
    if g.no_trading_today_signal == False:
        check_limit_up(context)
        if g.HV_control == True:
            check_high_volume(context)
        huanshou(context)
        check_remain_amount(context)


def check_limit_up(context):
    """检查涨停股"""
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        for stock in g.yesterday_HL_list:
            if context.portfolio.positions[stock].closeable_amount > -100:
                current_data = get_price(stock, end_date=now_time, frequency='1m',
                                         fields=['close', 'high_limit'], skip_paused=False,
                                         fq='pre', count=1, panel=False, fill_paused=True)
                if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                    log.info("[%s]涨停打开，卖出" % (stock))
                    position = context.portfolio.positions[stock]
                    close_position(position)
                    g.reason_to_sell = 'limitup'
                else:
                    log.info("[%s]涨停，继续持有" % (stock))


def check_remain_amount(context):
    """检查剩余资金"""
    if g.reason_to_sell == 'limitup':
        g.hold_list = []
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.hold_list.append(stock)

        if len(g.hold_list) < g.stock_num:
            target_list = get_stock_list(context)
            target_list = filter_not_buy_again(target_list)
            target_list = target_list[:min(g.stock_num, len(target_list))]
            log.info('有余额可用' + str(round((context.portfolio.cash), 2)) + '元。' + str(target_list))
            buy_security(context, target_list)
        g.reason_to_sell = ''
    else:
        g.reason_to_sell = ''


def check_high_volume(context):
    """检查高成交量"""
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price == current_data[stock].high_limit:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        df_volume = get_bars(stock, count=g.HV_duration, unit='1d', fields=['volume'], include_now=True, df=True)
        if df_volume['volume'].values[-1] > g.HV_ratio * df_volume['volume'].values.max():
            position = context.portfolio.positions[stock]
            r = close_position(position)
            log.info(f"[{stock}]天量，卖出, close_position: {r}")
            g.reason_to_sell = 'limitup'


def huanshou(context):
    """换手率检查"""
    ss = []
    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0:
            continue
        r = rt / avg
        action, icon = '', ''
        if avg < 0.003:
            action, icon = '缩量', '❄️'
        elif rt > expand and r > 2:
            action, icon = '放量', '🔥'
        if action:
            position = context.portfolio.positions[stock]
            r = close_position(position)
            log.info(
                f"{action} {stock} {get_security_info(stock).display_name} 换手率:{rt:.2%}→均:{avg:.2%} 倍率:{r:.1f}x {icon} close_position: {r}")
            g.reason_to_sell = 'limitup'


def huanshoulv(context, stock, is_avg=False):
    """计算换手率"""
    if is_avg:
        end_date = context.previous_date
        df_volume = get_price(stock, end_date=end_date, frequency='daily', fields=['volume'], count=20)
        df_cap = get_valuation(stock, end_date=end_date, fields=['circulating_cap'], count=1)
        circulating_cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        df_volume['turnover_ratio'] = df_volume['volume'] / (circulating_cap * 10000)
        return df_volume['turnover_ratio'].mean()
    else:
        date_now = context.current_dt
        df_vol = get_price(stock, start_date=date_now.date(), end_date=date_now,
                           frequency='1m', fields=['volume'], skip_paused=False,
                           fq='pre', panel=True, fill_paused=False)
        volume = df_vol['volume'].sum()
        date_pre = context.previous_date
        df_circulating_cap = get_valuation(stock, end_date=date_pre, fields=['circulating_cap'], count=1)
        circulating_cap = df_circulating_cap['circulating_cap'].iloc[0] if not df_circulating_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        turnover_ratio = volume / (circulating_cap * 10000)
        return turnover_ratio


def buy_security(context, target_list, cash=0, buy_number=0):
    """买入函数"""
    position_count = len(context.portfolio.positions)
    target_num = g.stock_num

    # 防御模式下降低仓位
    if g.defense_mode:
        target_num = max(2, int(g.stock_num * g.defense_position_ratio))
        log.info(f"防御模式下目标持仓数: {target_num}")

    if cash == 0:
        cash = context.portfolio.total_value
    if buy_number == 0:
        buy_number = target_num
    bought_num = 0

    if target_num > position_count:
        value = cash / target_num
        for stock in target_list:
            if context.portfolio.positions[stock].total_amount == 0:
                if bought_num < buy_number:
                    if open_position(stock, value):
                        g.not_buy_again.append(stock)
                        bought_num += 1
                        if len(context.portfolio.positions) == target_num:
                            break


def order_target_value_(security, value):
    return order_target_value(security, value)


def open_position(security, value):
    order = order_target_value_(security, value)
    return order is not None and order.filled > 0


def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    return order is not None and order.status == OrderStatus.held and order.filled == order.amount


def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list


def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]


def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if (stock in context.portfolio.positions.keys()
                                              or last_prices[stock][-1] > current_data[stock].low_limit)]


def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    result = []
    for stock in stock_list:
        try:
            start_date = get_security_info(stock).start_date
            days_since_listed = (yesterday - start_date).days
            if days_since_listed >= 375:
                result.append(stock)
        except Exception as e:
            continue
    return result


def filter_not_buy_again(stock_list):
    return [stock for stock in stock_list if stock not in g.not_buy_again]


def today_is_between(context):
    today = context.current_dt.strftime('%m-%d')
    if g.pass_april is True:
        if (('04-01' <= today) and (today <= '04-30')) or (('01-01' <= today) and (today <= '01-30')):
            return True
        else:
            return False
    else:
        return False


def close_account(context):
    if g.no_trading_today_signal == True:
        if len(g.hold_list) != 0 and g.no_trading_hold_signal == False:
            for stock in g.hold_list:
                position = context.portfolio.positions[stock]
                if close_position(position):
                    log.info("卖出[%s]" % (stock))
                else:
                    log.info("卖出[%s]错误！！！！！" % (stock))
            buy_security(context, g.no_trading_buy)
            g.no_trading_hold_signal = True


def close_no_trading_hold(context):
    if g.no_trading_hold_signal == True:
        for stock in g.hold_list:
            position = context.portfolio.positions[stock]
            close_position(position)
            log.info("卖出[%s]" % (stock))
        g.no_trading_hold_signal = False


# ========== 策略一防御函数（新增） ==========
def check_extreme_market(context):
    """检查极端市场情况（策略一的防御思想）"""
    if not g.enable_extreme_defense:
        return

    yesterday = context.previous_date

    # 检查主要指数的短期表现
    indices_to_check = ['000300.XSHG', '000905.XSHG']
    extreme_drop_detected = False

    for index_code in indices_to_check:
        try:
            # 获取最近5个交易日数据
            index_data = get_price(index_code,
                                   end_date=yesterday,
                                   frequency='daily',
                                   fields=['close'],
                                   count=5)

            if len(index_data) < 5:
                continue

            # 计算5日涨跌幅
            start_price = index_data['close'][0]
            end_price = index_data['close'][-1]

            if start_price > 0:
                change_pct = (end_price - start_price) / start_price

                # 如果5日跌幅超过阈值
                if change_pct <= (g.extreme_drop_threshold - 1):  # g.extreme_drop_threshold=0.85, 对应15%跌幅
                    extreme_drop_detected = True
                    log.warning(f"指数{index_code}5日跌幅{change_pct * 100:.1f}%，触发极端下跌警报")
                    break
        except Exception as e:
            log.error(f"检查指数{index_code}时出错: {e}")

    # 检查是否可以退出防御模式
    if not extreme_drop_detected and g.defense_mode:
        # 检查市场是否恢复
        if check_market_recovery(context):
            g.defense_mode = False
            log.info("市场恢复，退出防御模式")

    # 进入防御模式
    if extreme_drop_detected and not g.defense_mode:
        g.defense_mode = True
        log.warning("=== 进入防御模式 ===")
        # 不立即执行防御动作，等调仓时处理


def check_market_recovery(context):
    """检查市场是否恢复"""
    yesterday = context.previous_date

    try:
        # 检查主要指数是否连续2日上涨
        index_data = get_price('000300.XSHG',
                               end_date=yesterday,
                               frequency='daily',
                               fields=['close'],
                               count=3)

        if len(index_data) < 3:
            return False

        # 最近2日连续上涨
        return (index_data['close'][-1] > index_data['close'][-2] and
                index_data['close'][-2] > index_data['close'][-3])
    except Exception as e:
        log.error(f"检查市场恢复时出错: {e}")
        return False


def defense_adjustment(context):
    """防御模式下的调仓逻辑"""
    log.warning("执行防御调仓")

    # 1. 减仓至防御仓位比例
    current_positions = list(context.portfolio.positions.keys())
    if len(current_positions) > 0:
        # 按持有时间排序，先卖出持有时间长的
        positions_info = []
        for stock in current_positions:
            # 这里简化处理，实际应该记录买入时间
            positions_info.append((stock, 1))  # 占位符

        # 计算需要卖出的数量
        target_position_count = max(2, int(len(current_positions) * g.defense_position_ratio))
        sell_count = len(current_positions) - target_position_count

        if sell_count > 0:
            # 卖出一部分股票（这里简化，卖前几只）
            for i in range(min(sell_count, len(positions_info))):
                stock, _ = positions_info[i]
                if order_target_value(stock, 0):
                    log.info(f"防御减仓卖出: {stock}")

    # 2. 如果有现金，考虑买入防御性资产（可选）
    available_cash = context.portfolio.cash
    if available_cash > context.portfolio.total_value * 0.2:
        # 可以考虑配置部分外盘ETF（策略一的思路）
        # 这里简化处理，可以买入少量黄金ETF作为防御
        if len(g.foreign_ETF) > 0:
            etf = g.foreign_ETF[0]  # 选择第一个ETF
            if check_trading_status(context, etf):
                buy_amount = min(available_cash * 0.3, context.portfolio.total_value * 0.1)
                if order_target_value(etf, buy_amount):
                    log.info(f"防御配置外盘ETF: {etf}, 金额: {buy_amount:.2f}")

    # 3. 记录防御状态
    log.info(f"防御调仓完成，当前持仓: {len(context.portfolio.positions)}只")


def check_trading_status(context, stock):
    """检查交易状态"""
    try:
        current_data = get_current_data()[stock]

        # 检查停牌
        if current_data.paused:
            return False

        # 检查涨跌停
        last_price = history(1, unit='1m', field='close', security_list=[stock])[stock][-1]

        if last_price >= current_data.high_limit * 0.998:
            return False

        if last_price <= current_data.low_limit * 1.002:
            return False

        return True

    except Exception as e:
        return False

# 主函数结束