import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import jqdatasdk as jq
from typing import Dict, List, Callable
import copy


class BacktestEngine:
    def __init__(self,
                 start_date: str,
                 end_date: str,
                 initial_cash: float = 1000000,
                 benchmark: str = '399101.XSHE'):

        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.initial_cash = initial_cash
        self.benchmark = benchmark

        # 回测状态
        self.current_date = None
        self.portfolio = {
            'cash': initial_cash,
            'positions': {},  # {stock_code: {'amount': int, 'avg_cost': float}}
            'total_value': initial_cash,
            'history': []
        }

        # 策略函数
        self.initialize_func = None
        self.daily_funcs = []  # [(time, func)]

        # 数据缓存
        self.price_cache = {}
        self.fundamentals_cache = {}

    def initialize(self, func: Callable):
        """注册initialize函数"""
        self.initialize_func = func

    def run_daily(self, func: Callable, time: str):
        """注册每日运行函数"""
        self.daily_funcs.append((time, func))

    def run(self):
        """运行回测"""
        # 调用initialize
        context = self._create_context()
        if self.initialize_func:
            self.initialize_func(context)

        # 生成交易日序列
        trading_days = jq.get_trade_days(self.start_date, self.end_date)

        # 逐日回测
        for day in trading_days:
            self.current_date = day
            context.current_dt = datetime.combine(day, datetime.min.time())
            context.previous_date = self._get_previous_trading_day(day)

            # 更新市场数据
            self._update_market_data(context, day)

            # 按时间顺序执行daily函数
            for run_time, func in sorted(self.daily_funcs):
                # 这里简化处理，实际应该按具体时间执行
                if '9:05' in run_time:
                    func(context)
                elif '10:00' in run_time:
                    func(context)
                # ... 其他时间点

            # 记录每日净值
            self._record_daily_value(day)

        return self.portfolio['history']

    def _create_context(self):
        """创建类似聚宽的context对象"""

        class Context:
            pass

        context = Context()
        context.portfolio = self._create_portfolio_proxy()
        context.current_dt = None
        context.previous_date = None
        return context

    def _create_portfolio_proxy(self):
        """创建portfolio代理对象"""

        class PortfolioProxy:
            def __init__(self, engine):
                self._engine = engine

            @property
            def cash(self):
                return self._engine.portfolio['cash']

            @property
            def total_value(self):
                return self._engine.portfolio['total_value']

            @property
            def positions(self):
                # 返回类似聚宽的positions字典
                return self._engine.portfolio['positions']

        return PortfolioProxy(self)

    def _get_previous_trading_day(self, date):
        """获取上一个交易日"""
        days = jq.get_trade_days(date - timedelta(days=10), date)
        if len(days) > 1:
            return days[-2]
        return date

    def _update_market_data(self, context, date):
        """更新市场数据到context"""
        # 这里可以添加当前价格等数据
        pass

    def _record_daily_value(self, date):
        """记录每日资产总值"""
        self.portfolio['history'].append({
            'date': date,
            'total_value': self.portfolio['total_value']
        })

    # ========== 订单函数 ==========
    def order_target_value(self, security, value):
        """调仓到目标市值"""
        if value < 0:
            return None

        current_position = self.portfolio['positions'].get(security, {'amount': 0, 'avg_cost': 0})
        current_value = current_position['amount'] * self._get_current_price(security)

        if abs(current_value - value) < 0.01:
            return None

        if value == 0:
            # 清仓
            if current_position['amount'] > 0:
                self.portfolio['cash'] += current_value
                del self.portfolio['positions'][security]
                print(f"{self.current_date} 清仓 {security}")
        else:
            # 调仓
            if security not in self.portfolio['positions']:
                # 新开仓
                price = self._get_current_price(security)
                amount = int(value / price / 100) * 100  # 整手
                if amount > 0:
                    self.portfolio['positions'][security] = {
                        'amount': amount,
                        'avg_cost': price
                    }
                    self.portfolio['cash'] -= amount * price
                    print(f"{self.current_date} 买入 {security} {amount}股 @ {price:.2f}")

        # 更新总资产
        self._update_total_value()
        return True

    def _get_current_price(self, security):
        """获取当前价格"""
        try:
            data = jq.get_price(security,
                                start_date=self.current_date,
                                end_date=self.current_date,
                                frequency='daily',
                                fields=['close'])
            if not data.empty:
                return data['close'].iloc[-1]
        except:
            pass
        return 0.0

    def _update_total_value(self):
        """更新总资产"""
        stock_value = 0
        for stock, pos in self.portfolio['positions'].items():
            stock_value += pos['amount'] * self._get_current_price(stock)
        self.portfolio['total_value'] = self.portfolio['cash'] + stock_value


# ========== 全局函数（替代聚宽API） ==========
def get_price(security, end_date=None, frequency='daily', fields=None,
              count=None, skip_paused=False, fq='pre', panel=False, **kwargs):
    """模拟聚宽的get_price函数"""
    if end_date is None:
        end_date = datetime.now()

    # 处理start_date/count
    if count is not None:
        start_date = jq.get_trade_days(end_date - timedelta(days=count * 2), end_date)[-count]
    else:
        start_date = kwargs.get('start_date', end_date - timedelta(days=30))

    df = jq.get_price(security,
                      start_date=start_date,
                      end_date=end_date,
                      frequency=frequency,
                      fields=fields,
                      skip_paused=skip_paused,
                      fq=fq,
                      panel=False)
    return df


def get_fundamentals(query_object, date=None):
    """模拟聚宽的get_fundamentals"""
    # 简化版，实际需要根据query_object构造
    # JQData有类似功能，需要具体实现
    pass


def get_current_data():
    """获取当前快照数据"""

    class DataProxy:
        def __init__(self):
            self._data = {}

        def __getitem__(self, stock):
            # 返回一个对象，有is_st, paused等属性
            class StockInfo:
                pass

            return StockInfo()

    return DataProxy()


def get_all_securities(types, date):
    """获取所有股票"""
    return jq.get_all_securities(types, date)


def get_industry(security):
    """获取行业信息"""
    return jq.get_industry(security)


def get_valuation(security, end_date, fields, count=1):
    """获取估值数据"""
    # JQData有get_fundamentals可以获取
    pass