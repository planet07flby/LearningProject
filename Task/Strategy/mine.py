#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
五福 v3.4.1.1 动量滤波ETF轮动策略 - Backtrader + Tushare 完整复刻版
修复版：解决回测起点、未来数据、数据源缺失等问题
"""

import numpy as np
import math
import pandas as pd
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

import backtrader as bt
import tushare as ts


# ==================== 配置参数 ====================
class StrategyParams:
    """策略参数配置类，与原策略 g.xxx 一一对应"""

    # ===== 持仓参数 =====
    holdings_num = 1
    defensive_etf = "511880"
    min_money = 10

    # ===== 动量参数 =====
    lookback_days = 25
    min_score_threshold = 0
    max_score_threshold = 5
    score_threshold_ratio = 0.9

    use_short_momentum_period = False
    short_momentum_lookback = 21
    short_momentum_min_score = 0
    short_momentum_max_score = 6

    # ===== 过滤开关与阈值 =====
    enable_r2_filter = True
    r2_threshold = 0.4

    enable_volume_check = True
    volume_lookback = 5
    volume_threshold = 1.8

    enable_loss_filter = True
    loss_threshold = 0.97

    enable_premium_filter = False
    max_premium_rate = 30

    # ===== 滤波器参数 =====
    normal_filter_type = 'laplace'
    laplace_s_param = 0.05
    laplace_min_slope_pct = 0.0005
    laplace_max_deviation_pct = 0.03

    range_filter_type = 'gaussian'
    gaussian_sigma = 1.2
    gaussian_min_slope_pct = 0.0003
    gaussian_max_deviation_pct = 0.02

    # ===== 震荡期参数 =====
    enable_range_bound_mode = True
    current_filter = 'laplace'
    risk_state = 'normal'
    lookback_high_low_days = 20
    risk_benchmark = "000300.SH"

    enable_bias_trigger = True
    bias_threshold = 0.08
    ma_period = 20
    enable_rsi_trigger = True
    rsi_overbought = 70
    rsi_pullback = 65
    enable_stop_loss_trigger = True

    enable_low_point_rise_trigger = True
    low_point_rise_threshold = 0.04
    enable_stable_signal_trigger = True
    drawdown_recovery = 0.02
    max_range_bound_days = 20
    stable_days = 0

    filter_switch_cooldown = 3

    use_fixed_stop_loss = True
    fixed_stop_loss_threshold = 0.95

    verbose_log = True

    backtest_start = '2012-01-01'
    backtest_end = '2026-04-04'


# ==================== 数据获取模块（带本地缓存）====================
class TushareDataFetcher:
    CACHE_ROOT = r"D:\code\LearningProject\Data\ETF"

    def __init__(self, token: str):
        self.token = token
        ts.set_token(token)
        self.pro = ts.pro_api()
        os.makedirs(self.CACHE_ROOT, exist_ok=True)
        self.cache = {}

    def _get_cache_path(self, code: str, start_date: str, end_date: str, data_type: str = 'daily') -> str:
        start_clean = start_date.replace('-', '')
        end_clean = end_date.replace('-', '')
        filename = f"{code}_{start_clean}_{end_clean}_{data_type}.csv"
        return os.path.join(self.CACHE_ROOT, filename)

    def get_etf_daily(self, code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        cache_path = self._get_cache_path(code, start_date, end_date, 'daily')
        cache_key = f"etf_{code}_{start_date}_{end_date}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        if os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                self.cache[cache_key] = df
                print(f"从本地缓存加载 {code} 数据，共 {len(df)} 行")
                return df
            except Exception as e:
                print(f"读取缓存失败 {cache_path}: {e}")

        try:
            suffix = ".SH" if code.startswith('51') else ".SZ"
            df = self.pro.fund_daily(ts_code=f"{code}{suffix}",
                                     start_date=start_date.replace('-', ''),
                                     end_date=end_date.replace('-', ''),
                                     fields='trade_date,open,high,low,close,vol,amount')
            if df is not None and not df.empty:
                df['trade_date'] = pd.to_datetime(df['trade_date'])
                df = df.sort_values('trade_date')
                df.set_index('trade_date', inplace=True)
                df.to_csv(cache_path)
                print(f"下载并缓存 {code} 数据，共 {len(df)} 行 -> {cache_path}")
                self.cache[cache_key] = df
                return df
        except Exception as e:
            print(f"获取ETF数据失败 {code}: {e}")
        return None

    def get_index_daily(self, code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        cache_path = self._get_cache_path(code, start_date, end_date, 'index')
        cache_key = f"idx_{code}_{start_date}_{end_date}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        if os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                self.cache[cache_key] = df
                print(f"从本地缓存加载指数 {code} 数据，共 {len(df)} 行")
                return df
            except Exception as e:
                print(f"读取指数缓存失败 {cache_path}: {e}")

        try:
            df = self.pro.index_daily(ts_code=code,
                                      start_date=start_date.replace('-', ''),
                                      end_date=end_date.replace('-', ''),
                                      fields='trade_date,open,high,low,close')
            if df is not None and not df.empty:
                df['trade_date'] = pd.to_datetime(df['trade_date'])
                df = df.sort_values('trade_date')
                df.set_index('trade_date', inplace=True)
                df.to_csv(cache_path)
                print(f"下载并缓存指数 {code} 数据 -> {cache_path}")
                self.cache[cache_key] = df
                return df
        except Exception as e:
            print(f"获取指数数据失败 {code}: {e}")
        return None

    def get_etf_nav(self, code: str, date: str) -> Optional[float]:
        cache_key = f"nav_{code}_{date}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        try:
            suffix = ".SH" if code.startswith('51') else ".SZ"
            df = self.pro.fund_nav(ts_code=f"{code}{suffix}",
                                   start_date=date.replace('-', ''),
                                   end_date=date.replace('-', ''))
            if df is not None and not df.empty:
                nav = df['nav'].iloc[0]
                if pd.notna(nav) and nav > 0:
                    self.cache[cache_key] = nav
                    return nav
        except Exception as e:
            if not hasattr(self, '_nav_warned'):
                print(f"警告：获取净值失败 {code} {date}，可能积分不足，溢价率过滤将跳过该ETF。错误: {e}")
                self._nav_warned = True
        return None

    def get_full_etf_list(self) -> List[str]:
        cache_path = os.path.join(self.CACHE_ROOT, "etf_list.csv")
        if os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path)
                codes = df['code'].tolist()
                print(f"从本地缓存加载ETF列表，共 {len(codes)} 只")
                return codes
            except:
                pass
        try:
            df = self.pro.fund_basic(market='E')
            if df is not None and not df.empty:
                codes = []
                for ts_code in df['ts_code'].tolist():
                    code = ts_code.split('.')[0]
                    if code.isdigit() and len(code) == 6:
                        codes.append(code)
                pd.DataFrame({'code': codes}).to_csv(cache_path, index=False)
                print(f"下载并缓存ETF列表，共 {len(codes)} 只")
                return codes
        except Exception as e:
            print(f"获取ETF列表失败: {e}")
        return []

# ==================== Backtrader数据适配器 ====================
class PandasDataWithMulti(bt.feeds.PandasData):
    params = (
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'vol'),
        ('openinterest', -1),
    )


# ==================== 核心算法模块 ====================
class MomentumScoreCalculator:
    @staticmethod
    def calculate(price_series: np.ndarray, lookback_days: int) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if len(price_series) < lookback_days + 1:
            return None, None, None

        recent_prices = price_series[-(lookback_days + 1):]
        y = np.log(recent_prices)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        W = weights ** 2

        W_sum = np.sum(W)
        x_bar = np.sum(W * x) / W_sum
        y_bar = np.sum(W * y) / W_sum

        dx = x - x_bar
        dy = y - y_bar

        variance_x = np.sum(W * dx ** 2)
        if variance_x == 0:
            return 0, 0, 0

        slope = np.sum(W * dx * dy) / variance_x
        intercept = y_bar - slope * x_bar

        annualized_returns = math.exp(slope * 250) - 1

        y_pred = slope * x + intercept
        ss_res = np.sum(weights * (y - y_pred) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        momentum_score = annualized_returns * r_squared
        return momentum_score, annualized_returns, r_squared


class FilterCalculator:
    @staticmethod
    def laplace_filter_last_two(price: np.ndarray, s: float = 0.05) -> Tuple[float, float]:
        n = len(price)
        if n == 0:
            return 0, 0
        if n == 1:
            return price[0], price[0]

        alpha = 1 - np.exp(-s)
        prev = price[0]
        prev_prev = price[0]

        for i in range(1, n):
            curr = alpha * price[i] + (1 - alpha) * prev
            prev_prev, prev = prev, curr

        return prev, prev_prev

    @staticmethod
    def gaussian_filter_last_two(price: np.ndarray, sigma: float = 1.2) -> Tuple[float, float]:
        n = len(price)
        if n == 0:
            return 0, 0
        if n == 1:
            return price[0], price[0]

        idx_1 = np.arange(n)
        weights_1 = np.exp(-((idx_1 + 1) ** 2) / (2 * sigma ** 2))[::-1]
        weights_1 /= np.sum(weights_1)
        g1 = np.sum(price * weights_1)

        idx_2 = np.arange(n - 1)
        weights_2 = np.exp(-((idx_2 + 1) ** 2) / (2 * sigma ** 2))[::-1]
        weights_2 /= np.sum(weights_2)
        g2 = np.sum(price[:-1] * weights_2)

        return g1, g2

    @staticmethod
    def evaluate(price_series: np.ndarray, current_price: float, filter_type: str,
                 laplace_s: float, gaussian_sigma: float, slope_threshold: float = 0.002) -> Tuple[
        float, float, float, float, bool, str]:
        if len(price_series) < 10:
            return 0, 0, 0, 0, False, filter_type

        if filter_type == 'laplace':
            f_now, f_prev = FilterCalculator.laplace_filter_last_two(price_series, s=laplace_s)
        else:
            f_now, f_prev = FilterCalculator.gaussian_filter_last_two(price_series, sigma=gaussian_sigma)

        slope_abs = f_now - f_prev
        slope_pct = (f_now / f_prev - 1) if f_prev > 0 else 0
        deviation_pct = (current_price / f_now - 1) if f_now > 0 else 0

        passed = (current_price > f_now) and (slope_abs > slope_threshold)

        return f_now, f_prev, slope_pct, deviation_pct, passed, filter_type


class RSICalculator:
    @staticmethod
    def calculate(close: np.ndarray, period: int = 14) -> Optional[float]:
        if len(close) < period + 1:
            return None
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))


# ==================== Backtrader策略类 ====================
class FiveBlessStrategy(bt.Strategy):
    params = (
        ('params', StrategyParams()),
        ('etf_data_dict', {}),
        ('etf_names_dict', {}),
        ('defensive_code', '511880'),
        ('risk_benchmark_data', None),
        ('fetcher', None),
    )

    def __init__(self):
        self.value_history = []
        self.pcfg = self.params.params
        self.current_filter = self.pcfg.current_filter
        self.risk_state = self.pcfg.risk_state
        self.current_holding = None
        self.stop_loss_triggered_today = False
        self.range_bound_start_date = None
        self.range_bound_days_count = 0
        self.last_switch_date = None
        self.stable_days = 0
        self.previous_drawdown = None
        self.previous_rsi = None
        self.max_portfolio_value = 0
        self.drawdown_records = []

        self.etf_data_dict = self.params.etf_data_dict
        self.etf_names_dict = self.params.etf_names_dict
        self.defensive_code = self.params.defensive_code
        self.risk_benchmark_data = self.params.risk_benchmark_data
        self.fetcher = self.params.fetcher

        self.datafeeds = {}
        for data in self.datas:
            if hasattr(data, '_name') and data._name:
                self.datafeeds[data._name] = data

        self.ranked_etfs = []
        self.target_etfs = []
        self.order = None

        self._init_range_bound_status()

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入执行 {order.data._name} 价格:{order.executed.price:.3f} 数量:{order.executed.size}')
            else:
                self.log(f'卖出执行 {order.data._name} 价格:{order.executed.price:.3f} 数量:{order.executed.size}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'订单失败: {order.Status[order.status]}')
        self.order = None

    def _init_range_bound_status(self):
        if not self.pcfg.enable_range_bound_mode:
            return
        if self.risk_benchmark_data is None or len(self.risk_benchmark_data) < self.pcfg.ma_period:
            return
        close = self.risk_benchmark_data['close'].values
        high = self.risk_benchmark_data['high'].values
        low = self.risk_benchmark_data['low'].values
        current_price = close[-1]
        recent_high = np.max(high[-self.pcfg.lookback_high_low_days:])
        recent_low = np.min(low[-self.pcfg.lookback_high_low_days:])
        ma = np.mean(close[-self.pcfg.ma_period:])
        bias = (current_price - ma) / ma if ma > 0 else 0
        current_rsi = RSICalculator.calculate(close, period=14)

        should_enter = False
        signals = []
        if self.pcfg.enable_bias_trigger and bias > self.pcfg.bias_threshold:
            should_enter = True
            signals.append(f"乖离率{bias:.2%}>{self.pcfg.bias_threshold:.0%}")
        if self.pcfg.enable_rsi_trigger and current_rsi is not None and len(close) >= 15:
            prev_rsi = RSICalculator.calculate(close[:-1], period=14)
            if prev_rsi is not None and prev_rsi > self.pcfg.rsi_overbought and current_rsi < self.pcfg.rsi_pullback:
                should_enter = True
                signals.append(f"RSI超买回落{prev_rsi:.1f}->{current_rsi:.1f}")

        if should_enter:
            self.current_filter = 'gaussian'
            self.risk_state = 'range_bound'
            self.range_bound_start_date = self.risk_benchmark_data.index[-1]
            self.range_bound_days_count = 0
            self.log(f"【首次运行】初始化进入震荡期：{' ; '.join(signals)}")
        else:
            self.current_filter = 'laplace'
            self.risk_state = 'normal'
            self.previous_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
            self.previous_rsi = current_rsi

    def _check_range_bound_enter(self, current_date):
        if not self.pcfg.enable_range_bound_mode:
            return
        if self.risk_state == 'range_bound':
            return
        if self.last_switch_date is not None:
            days_since_switch = (current_date - self.last_switch_date).days
            if days_since_switch < self.pcfg.filter_switch_cooldown:
                return

        risk_signals = []
        if self.risk_benchmark_data is not None and len(self.risk_benchmark_data) >= self.pcfg.ma_period:
            close = self.risk_benchmark_data['close'].values
            current_price = close[-1]
            if self.pcfg.enable_bias_trigger:
                ma = np.mean(close[-self.pcfg.ma_period:])
                bias = (current_price - ma) / ma if ma > 0 else 0
                if bias > self.pcfg.bias_threshold:
                    risk_signals.append("乖离率过大")
            if self.pcfg.enable_rsi_trigger:
                current_rsi = RSICalculator.calculate(close, period=14)
                if len(close) >= 15 and current_rsi is not None:
                    prev_rsi = RSICalculator.calculate(close[:-1], period=14)
                    if prev_rsi is not None and prev_rsi > self.pcfg.rsi_overbought and current_rsi < self.pcfg.rsi_pullback:
                        risk_signals.append("RSI超买回落")
        if self.pcfg.enable_stop_loss_trigger and self.stop_loss_triggered_today:
            risk_signals.append("今日触发止损")
            self.stop_loss_triggered_today = False

        if risk_signals:
            self.current_filter = 'gaussian'
            self.risk_state = 'range_bound'
            self.last_switch_date = current_date
            self.range_bound_start_date = current_date
            self.range_bound_days_count = 0
            self.stable_days = 0
            self.log(f"🔔 【进入震荡期】{' ; '.join(risk_signals)}")

    def _check_range_bound_exit(self, current_date):
        if not self.pcfg.enable_range_bound_mode:
            return
        if self.risk_state != 'range_bound':
            return
        if self.risk_benchmark_data is None or len(self.risk_benchmark_data) < self.pcfg.lookback_high_low_days:
            return

        close = self.risk_benchmark_data['close'].values
        high = self.risk_benchmark_data['high'].values
        low = self.risk_benchmark_data['low'].values
        current_price = close[-1]
        recent_high = np.max(high[-self.pcfg.lookback_high_low_days:])
        recent_low = np.min(low[-self.pcfg.lookback_high_low_days:])
        current_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        ma = np.mean(close[-self.pcfg.ma_period:])
        current_rsi = RSICalculator.calculate(close, period=14)

        if self.pcfg.enable_stable_signal_trigger:
            stable_signal_count = 0
            if current_price > ma:
                stable_signal_count += 1
            if len(close) >= 2 and close[-1] > close[-2]:
                stable_signal_count += 1
            if self.previous_drawdown is not None and current_drawdown < self.previous_drawdown:
                stable_signal_count += 1
            if current_rsi is not None and self.previous_rsi is not None and current_rsi > self.previous_rsi:
                stable_signal_count += 1
            if current_drawdown < self.pcfg.drawdown_recovery and stable_signal_count >= 2:
                self.stable_days += 1
            else:
                self.stable_days = 0

        self.previous_drawdown = current_drawdown
        self.previous_rsi = current_rsi

        range_bound_days = 0
        if self.range_bound_start_date is not None:
            range_bound_days = (current_date - self.range_bound_start_date).days
        low_point_rise_cond = self.pcfg.enable_low_point_rise_trigger and rise_from_low >= self.pcfg.low_point_rise_threshold
        stable_signal_cond = self.pcfg.enable_stable_signal_trigger and self.stable_days >= 2
        force_cond = range_bound_days >= self.pcfg.max_range_bound_days

        if low_point_rise_cond or stable_signal_cond or force_cond:
            if self.last_switch_date is not None:
                days_since_switch = (current_date - self.last_switch_date).days
                if days_since_switch < self.pcfg.filter_switch_cooldown:
                    return
            self.current_filter = 'laplace'
            self.risk_state = 'normal'
            self.last_switch_date = current_date
            self.range_bound_start_date = None
            self.range_bound_days_count = 0
            self.stable_days = 0
            self.log("🔔 【退出震荡期】切回正常期拉普拉斯滤波")

    # ========== 修复点1：_calculate_etf_metrics 使用截取后的数据 ==========
    def _calculate_etf_metrics(self, code: str, df: pd.DataFrame, current_date) -> Optional[Dict]:
        # 截取到当前日期为止的数据，避免未来函数
        df_until_today = df[df.index <= pd.Timestamp(current_date)]
        if len(df_until_today) < self.pcfg.lookback_days + 5:
            return None

        close_series = df_until_today['close'].values
        volume_series = df_until_today['vol'].values
        current_price = close_series[-1]
        today_vol = volume_series[-1]

        momentum_score, annual_ret, r_squared = MomentumScoreCalculator.calculate(
            close_series, self.pcfg.lookback_days
        )
        if momentum_score is None:
            return None

        short_momentum_score = None
        if self.pcfg.use_short_momentum_period:
            short_momentum_score, _, _ = MomentumScoreCalculator.calculate(
                close_series, self.pcfg.short_momentum_lookback
            )

        passed_momentum = (self.pcfg.min_score_threshold <= momentum_score <= self.pcfg.max_score_threshold)
        passed_short_momentum = (short_momentum_score is not None and
                                 self.pcfg.short_momentum_min_score <= short_momentum_score <= self.pcfg.short_momentum_max_score)

        volume_ratio = None
        if len(volume_series) >= self.pcfg.volume_lookback + 1:
            avg_volume = np.mean(volume_series[-(self.pcfg.volume_lookback + 1):-1])
            if avg_volume > 0:
                volume_ratio = today_vol / avg_volume
        passed_volume = (volume_ratio is not None and volume_ratio < self.pcfg.volume_threshold)

        passed_loss = True
        if len(close_series) >= 4:
            day_ratios = [
                close_series[-1] / close_series[-2],
                close_series[-2] / close_series[-3],
                close_series[-3] / close_series[-4]
            ]
            if min(day_ratios) < self.pcfg.loss_threshold:
                passed_loss = False

        filter_now, filter_prev, slope_pct, deviation_pct, passed_filter, filter_name = FilterCalculator.evaluate(
            close_series, current_price, self.current_filter,
            self.pcfg.laplace_s_param, self.pcfg.gaussian_sigma, 0.002
        )

        passed_r2 = r_squared > self.pcfg.r2_threshold

        passed_premium = True
        if self.pcfg.enable_premium_filter and self.fetcher is not None:
            last_date = df_until_today.index[-1].strftime('%Y-%m-%d')
            nav = self.fetcher.get_etf_nav(code, last_date)
            if nav is not None and nav > 0:
                premium_rate = (current_price - nav) / nav * 100
                passed_premium = (premium_rate <= self.pcfg.max_premium_rate)
                if self.pcfg.verbose_log and not passed_premium:
                    self.log(f"溢价率过滤 {code} 溢价率={premium_rate:.2f}% > {self.pcfg.max_premium_rate}%")
            else:
                passed_premium = True

        return {
            'code': code,
            'name': self.etf_names_dict.get(code, code),
            'momentum_score': momentum_score,
            'short_momentum_score': short_momentum_score,
            'r_squared': r_squared,
            'volume_ratio': volume_ratio,
            'current_price': current_price,
            'passed_momentum': passed_momentum,
            'passed_short_momentum': passed_short_momentum,
            'passed_r2': passed_r2,
            'passed_volume': passed_volume,
            'passed_loss': passed_loss,
            'passed_premium': passed_premium,
            'passed_filter': passed_filter,
            'filter_name': filter_name,
            'filter_slope_pct': slope_pct,
            'filter_deviation_pct': deviation_pct,
        }

    # ========== 修复点2：_rank_etfs 增加 current_date 参数 ==========
    def _rank_etfs(self, current_date):
        all_metrics = []
        for code, df in self.etf_data_dict.items():
            metrics = self._calculate_etf_metrics(code, df, current_date)  # 传入 current_date
            if metrics is None:
                continue

            if not metrics['passed_momentum']:
                continue
            if self.pcfg.enable_r2_filter and not metrics['passed_r2']:
                continue
            if self.pcfg.enable_volume_check and not metrics['passed_volume']:
                continue
            if self.pcfg.enable_loss_filter and not metrics['passed_loss']:
                continue
            if self.pcfg.enable_premium_filter and not metrics['passed_premium']:
                continue
            if self.pcfg.enable_range_bound_mode and not metrics['passed_filter']:
                continue

            all_metrics.append(metrics)

        if not all_metrics:
            self.ranked_etfs = []
            return

        sort_key = 'short_momentum_score' if self.pcfg.use_short_momentum_period else 'momentum_score'
        for m in all_metrics:
            if m.get(sort_key) is None:
                m[sort_key] = float('-inf')
        all_metrics.sort(key=lambda x: x[sort_key], reverse=True)

        top_10 = all_metrics[:10]

        if len(top_10) >= self.pcfg.holdings_num:
            reference_score = top_10[self.pcfg.holdings_num - 1][sort_key]
            score_threshold = reference_score * self.pcfg.score_threshold_ratio
            candidate_pool = [m for m in top_10 if m[sort_key] >= score_threshold]
        else:
            candidate_pool = top_10[:]

        if self.current_holding:
            candidate_dict = {m['code']: m for m in candidate_pool}
            if self.current_holding in candidate_dict:
                retained = [candidate_dict[self.current_holding]]
                need = self.pcfg.holdings_num - len(retained)
                if need > 0:
                    remaining = [m for m in candidate_pool if m['code'] != self.current_holding]
                    final_result = retained + remaining[:need]
                else:
                    final_result = retained[:self.pcfg.holdings_num]
            else:
                final_result = candidate_pool[:self.pcfg.holdings_num]
        else:
            final_result = candidate_pool[:self.pcfg.holdings_num]

        self.ranked_etfs = final_result

        if self.pcfg.verbose_log and final_result:
            best = final_result[0]
            self.log(
                f"【排名】第一名 {best['name']}({best['code']}) "
                f"score={best[sort_key]:.4f} R²={best['r_squared']:.3f} "
                f"滤波={best['filter_name']} 斜率={best['filter_slope_pct']:.3%}"
            )

    def _execute_trades(self):
        if self.ranked_etfs:
            target_code = self.ranked_etfs[0]['code']
        else:
            target_code = self.defensive_code

        if target_code == self.current_holding:
            return

        if self.current_holding and self.current_holding in self.datafeeds:
            self.log(f"卖出 {self.etf_names_dict.get(self.current_holding, self.current_holding)}")
            self.close(data=self.datafeeds[self.current_holding])

        if target_code in self.datafeeds:
            target_value = self.broker.getvalue() * 0.95
            current_price = self.datafeeds[target_code].close[0]
            if current_price > 0:
                size = int(target_value / current_price / 100) * 100
                if size > 0:
                    self.log(f"买入 {self.etf_names_dict.get(target_code, target_code)} 数量:{size}")
                    self.buy(data=self.datafeeds[target_code], size=size)
                    self.current_holding = target_code
                    return
        self.current_holding = None

    def _check_stop_loss(self):
        if not self.pcfg.use_fixed_stop_loss:
            return
        if not self.current_holding or self.current_holding not in self.datafeeds:
            return
        pos = self.getposition(self.datafeeds[self.current_holding])
        if pos.size == 0:
            return
        current_price = self.datafeeds[self.current_holding].close[0]
        cost_price = pos.price
        if cost_price > 0 and current_price <= cost_price * self.pcfg.fixed_stop_loss_threshold:
            loss_percent = (current_price / cost_price - 1) * 100
            self.log(f"🚨 【止损】{self.etf_names_dict.get(self.current_holding, self.current_holding)} "
                     f"亏损 {loss_percent:.2f}% 触发清仓")
            self.close(data=self.datafeeds[self.current_holding])
            self.current_holding = None
            self.stop_loss_triggered_today = True

    # ========== 修复点3：next 中调用 _rank_etfs 时传入 current_date ==========
    def next(self):
        current_date = self.datas[0].datetime.date(0)

        if self.risk_benchmark_data is not None:
            idx = self.risk_benchmark_data.index.get_indexer([current_date], method='ffill')
            if idx[0] >= 0:
                self.risk_benchmark_data = self.risk_benchmark_data.iloc[:idx[0] + 1]

        self._check_range_bound_enter(current_date)
        self._check_range_bound_exit(current_date)
        self._rank_etfs(current_date)   # 传入 current_date
        self._check_stop_loss()
        self._execute_trades()

        current_value = self.broker.getvalue()
        if current_value > self.max_portfolio_value:
            self.max_portfolio_value = current_value
        if self.max_portfolio_value > 0:
            current_drawdown = (self.max_portfolio_value - current_value) / self.max_portfolio_value
            if current_drawdown >= 0.03:
                self.drawdown_records.append({
                    'date': current_date,
                    'drawdown': current_drawdown,
                    'portfolio_value': current_value,
                    'max_value': self.max_portfolio_value,
                })

        self.value_history.append(self.broker.getvalue())


# ==================== 主程序 ====================
def load_etf_data_list(fetcher, etf_codes, start_date, end_date):
    result = {}
    for code in etf_codes:
        df = fetcher.get_etf_daily(code, start_date, end_date)
        if df is not None and len(df) > 100:
            result[code] = df
            print(f"成功加载 {code} ({len(df)} 行)")
        else:
            print(f"跳过 {code}，数据不足")
    return result


def load_index_data(fetcher: TushareDataFetcher, index_code: str,
                    start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    return fetcher.get_index_daily(index_code, start_date, end_date)


def run_backtest():
    params = StrategyParams()
    params.enable_premium_filter = False
    TOKEN = "79b8a4a1af21b461dd2a5ab594d12aa7eb38c0defa28c79ccff3b5fb"  # 替换为您的Tushare token
    fetcher = TushareDataFetcher(TOKEN)

    fixed_etf_pool = [
        '511880', '518880', '161226', '159980', '501018', '159985',
        '513100', '159509', '513290', '513500', '159518', '159502', '159529',
        '513400', '520830', '513520', '513030',
        '513090', '513180', '513120', '513330', '513750', '159892', '159605',
        '513190', '510900', '513630', '513920', '159323', '513970',
        '510500', '512100', '563300', '510300', '512050', '510760', '159915',
        '159949', '159967', '588080', '588220', '511380',
        '513310', '588200', '159852', '512880', '512400', '512980', '159516',
        '512480', '515880', '562500', '159869', '159870', '159851', '512170',
        '512800', '159819', '512710', '159638', '517520', '515980', '159995',
        '512660', '512690', '516150', '512890', '159992', '512070', '562800',
        '512010', '515790', '510880', '159928', '159883', '159998', '515220',
        '561980', '515400', '515120', '515050', '516510', '159766', '512200',
        '159583', '159732', '516160', '516520', '515030', '512670', '159840',
        '159611', '159981', '159865', '515170', '159825', '515210',
    ]

    print("开始加载ETF日线数据...")
    # ========== 修复点4：使用 load_etf_data_list 函数 ==========
    etf_data_dict = load_etf_data_list(fetcher, fixed_etf_pool, params.backtest_start, params.backtest_end)
    print(f"成功加载 {len(etf_data_dict)} 只ETF数据")

    if not etf_data_dict:
        raise ValueError("没有加载到任何有效的ETF数据，请检查网络或Tushare token")

    print("加载风险基准指数数据...")
    benchmark_data = load_index_data(fetcher, params.risk_benchmark, params.backtest_start, params.backtest_end)
    if benchmark_data is None:
        print("警告：无法加载风险基准指数数据，震荡期判断将禁用")
        params.enable_range_bound_mode = False

    cerebro = bt.Cerebro()
    initial_cash = 1000000
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.0001, mult=1.0, percabs=True)

    # ========== 修复点5：添加主数据源（沪深300）并重新添加所有ETF数据源 ==========
    # 添加主数据源：沪深300指数（驱动时间轴）
    main_data = PandasDataWithMulti(dataname=benchmark_data)
    main_data._name = "benchmark"
    cerebro.adddata(main_data)

    # 添加所有ETF数据源（用于交易）
    for code, df in etf_data_dict.items():
        data = PandasDataWithMulti(dataname=df)
        data._name = code
        cerebro.adddata(data)

    etf_names = {code: f"ETF-{code}" for code in etf_data_dict.keys()}

    cerebro.addstrategy(FiveBlessStrategy,
                        params=params,
                        etf_data_dict=etf_data_dict,
                        etf_names_dict=etf_names,
                        defensive_code=params.defensive_etf,
                        risk_benchmark_data=benchmark_data,
                        fetcher=None)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual_return')

    print(f"开始回测，初始资金: {initial_cash:,.2f}")
    print(f"回测时间范围: {params.backtest_start} 至 {params.backtest_end}")

    results = cerebro.run()
    strat = results[0]

    final_value = cerebro.broker.getvalue()
    total_return = (final_value - initial_cash) / initial_cash

    values = strat.value_history
    strategy_returns = [(v / initial_cash - 1) * 100 for v in values]

    start_date = strat.datas[0].datetime.date(0)
    end_date = strat.datas[0].datetime.date(-1)
    bench_slice = benchmark_data.loc[pd.Timestamp(start_date):pd.Timestamp(end_date)] if benchmark_data is not None else None
    if bench_slice is not None and len(bench_slice) > 0:
        bench_prices = bench_slice['close'].values
        bench_returns = [(p / bench_prices[0] - 1) * 100 for p in bench_prices]
    else:
        bench_returns = []

    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(12, 6))
    plt.plot(strategy_returns, label='策略累计收益率', color='blue', linewidth=1.5)
    if bench_returns:
        plt.plot(bench_returns, label='沪深300累计收益率', color='red', linewidth=1.5, linestyle='--')
    plt.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    plt.xlabel('交易日')
    plt.ylabel('累计收益率 (%)')
    plt.title('策略累计收益率曲线 vs 沪深300')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()

    print("\n" + "=" * 60)
    print("回测结果")
    print("=" * 60)
    print(f"初始资金: {initial_cash:,.2f}")
    print(f"最终资金: {final_value:,.2f}")
    print(f"总收益率: {total_return:.2%}")
    print(f"年化收益率: {strat.analyzers.annual_return.get_analysis().get('rnorm100', 0):.2f}%")
    print(f"夏普比率: {strat.analyzers.sharpe.get_analysis().get('sharperatio', 0):.4f}")
    print(f"最大回撤: {strat.analyzers.drawdown.get_analysis().get('max', {}).get('drawdown', 0):.2f}%")

    if strat.drawdown_records:
        print(f"\n回撤预警记录数: {len(strat.drawdown_records)}")


if __name__ == '__main__':
    run_backtest()