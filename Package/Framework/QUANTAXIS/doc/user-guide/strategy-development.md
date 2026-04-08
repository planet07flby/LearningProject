# 策略开发

**版本**: 2.1.0-alpha2
**作者**: @yutiansut @quantaxis
**更新日期**: 2025-10-25

本章节介绍如何使用QUANTAXIS开发量化交易策略。QUANTAXIS提供了完整的策略开发框架，支持CTA、套利、因子等多种策略类型。

---

## 📚 策略框架概览

QUANTAXIS提供了四种策略基类：

### 🔧 策略基类

```python
from QUANTAXIS.QAStrategy import (
    QAStrategyCtaBase,    # CTA策略基类（单标的）
    QAMultiBase,          # 多标的多市场基类
    QAHedgeBase,          # 对冲/套利策略基类
    QAFactorBase,         # 因子策略基类
)
```

### ✨ 核心特性

- **事件驱动**: 基于Bar/Tick事件驱动的策略执行
- **回测实盘一体化**: 同一策略代码可用于回测和实盘
- **QIFI账户系统**: 统一的多市场账户管理
- **风险控制**: 内置风险检查和仓位管理
- **实时监控**: 支持实时策略监控和调试

---

## 🎯 CTA策略开发

CTA (Commodity Trading Advisor) 策略是最常见的趋势跟踪策略。

### 1. 策略结构

一个完整的CTA策略包含以下部分：

```python
from QUANTAXIS.QAStrategy import QAStrategyCtaBase
import QUANTAXIS as QA


class MyStrategy(QAStrategyCtaBase):
    """我的CTA策略"""

    def user_init(self):
        """策略初始化 - 只在策略启动时执行一次"""
        # 设置策略参数
        self.fast_period = 5     # 快线周期
        self.slow_period = 20    # 慢线周期
        self.stop_loss = 0.02    # 止损比例

        # 初始化指标数据
        self.ma_fast = []
        self.ma_slow = []

    def on_bar(self, bar):
        """K线更新回调 - 每根K线触发一次"""
        # 1. 更新指标
        self.update_indicators(bar)

        # 2. 生成信号
        signal = self.generate_signal()

        # 3. 执行交易
        if signal == 'BUY':
            self.BuyOpen(bar.code, 1)
        elif signal == 'SELL':
            self.SellClose(bar.code, 1)

    def on_tick(self, tick):
        """Tick更新回调 - 每个tick触发一次（可选）"""
        pass

    def update_indicators(self, bar):
        """更新技术指标"""
        # 获取历史数据
        data = self.get_code_marketdata(bar.code)

        # 计算均线
        if len(data) >= self.slow_period:
            close_prices = [x['close'] for x in data]
            self.ma_fast = QA.MA(close_prices, self.fast_period)
            self.ma_slow = QA.MA(close_prices, self.slow_period)

    def generate_signal(self):
        """生成交易信号"""
        if len(self.ma_fast) < 2 or len(self.ma_slow) < 2:
            return None

        # 金叉买入
        if self.ma_fast[-2] < self.ma_slow[-2] and \
           self.ma_fast[-1] > self.ma_slow[-1]:
            return 'BUY'

        # 死叉卖出
        elif self.ma_fast[-2] > self.ma_slow[-2] and \
             self.ma_fast[-1] < self.ma_slow[-1]:
            return 'SELL'

        return None
```

### 2. 策略参数配置

```python
# 初始化策略
strategy = MyStrategy(
    code='rb2501',               # 交易标的
    frequence='5min',            # K线周期: '1min', '5min', '15min', '30min', '60min', 'day'
    strategy_id='ma_cross',      # 策略ID
    start='2024-01-01',          # 回测开始时间
    end='2024-12-31',            # 回测结束时间
    init_cash=1000000,           # 初始资金
    portfolio='my_portfolio',    # 投资组合名称
    send_wx=False,               # 是否发送微信通知
    data_host='127.0.0.1',       # 数据服务器
    trade_host='127.0.0.1',      # 交易服务器
)

# 运行回测
strategy.run_backtest()
```

### 3. 下单方法

#### 期货市场

```python
# 开多仓
self.BuyOpen(code, volume)       # 买入开仓
# 参数:
#   code: 合约代码
#   volume: 手数

# 平多仓
self.SellClose(code, volume)     # 卖出平仓

# 开空仓
self.SellOpen(code, volume)      # 卖出开仓

# 平空仓
self.BuyClose(code, volume)      # 买入平仓

# 示例
self.BuyOpen('rb2501', 1)        # 买开1手螺纹钢
self.SellClose('rb2501', 1)      # 平掉1手多单
```

#### 股票市场

```python
# 买入股票
self.Buy(code, volume)           # 买入
# 参数:
#   code: 股票代码
#   volume: 股数（最小100股）

# 卖出股票
self.Sell(code, volume)          # 卖出

# 示例
self.Buy('000001', 100)          # 买入100股平安银行
self.Sell('000001', 100)         # 卖出100股
```

### 4. 获取账户信息

```python
def on_bar(self, bar):
    # 获取当前持仓
    positions = self.acc.positions
    print(f"当前持仓: {positions}")

    # 获取可用资金
    available = self.acc.cash_available
    print(f"可用资金: {available}")

    # 获取账户权益
    balance = self.acc.balance
    print(f"账户权益: {balance}")

    # 获取持仓信息
    if bar.code in positions:
        pos = positions[bar.code]
        print(f"持仓量: {pos.volume_long}")           # 多头持仓
        print(f"持仓均价: {pos.open_price_long}")     # 开仓均价
        print(f"持仓盈亏: {pos.position_profit_long}") # 持仓盈亏

    # 获取今日订单
    orders = self.acc.orders
    print(f"今日订单数: {len(orders)}")
```

### 5. 市场数据获取

```python
def on_bar(self, bar):
    # 获取当前Bar数据
    current_price = bar.close        # 收盘价
    current_open = bar.open          # 开盘价
    current_high = bar.high          # 最高价
    current_low = bar.low            # 最低价
    current_volume = bar.volume      # 成交量

    # 获取历史数据
    market_data = self.get_code_marketdata(bar.code)
    # 返回最近的K线数据列表
    # [{'open': xx, 'high': xx, 'low': xx, 'close': xx, ...}, ...]

    # 获取最新N根K线
    recent_bars = market_data[-10:]  # 最近10根K线

    # 计算技术指标
    close_prices = [x['close'] for x in market_data]
    ma5 = QA.MA(close_prices, 5)
    ma10 = QA.MA(close_prices, 10)
```

### 6. 完整示例：双均线策略

```python
from QUANTAXIS.QAStrategy import QAStrategyCtaBase
import QUANTAXIS as QA


class DualMAStrategy(QAStrategyCtaBase):
    """双均线CTA策略

    策略逻辑:
    - 快线上穿慢线：买入开仓
    - 快线下穿慢线：卖出平仓
    - 设置固定止损止盈
    """

    def user_init(self):
        """初始化策略参数"""
        # 均线参数
        self.fast_period = 5
        self.slow_period = 20

        # 风控参数
        self.stop_loss_pct = 0.02      # 止损2%
        self.take_profit_pct = 0.05    # 止盈5%

        # 仓位管理
        self.max_position = 5          # 最大持仓手数
        self.position_size = 1         # 每次开仓手数

        # 状态变量
        self.entry_price = 0           # 入场价格
        self.is_long = False           # 是否持有多单

        print(f"策略初始化完成: 快线{self.fast_period}, 慢线{self.slow_period}")

    def on_bar(self, bar):
        """K线更新回调"""
        # 1. 获取市场数据
        market_data = self.get_code_marketdata(bar.code)
        if len(market_data) < self.slow_period:
            return  # 数据不足，跳过

        # 2. 计算技术指标
        close_prices = [x['close'] for x in market_data]
        ma_fast = QA.MA(close_prices, self.fast_period)
        ma_slow = QA.MA(close_prices, self.slow_period)

        # 3. 获取当前持仓
        positions = self.acc.positions
        current_pos = positions.get(bar.code, None)

        # 4. 生成交易信号
        if len(ma_fast) >= 2 and len(ma_slow) >= 2:
            # 金叉信号
            if ma_fast[-2] <= ma_slow[-2] and ma_fast[-1] > ma_slow[-1]:
                if current_pos is None or current_pos.volume_long == 0:
                    # 无持仓，开仓
                    self.BuyOpen(bar.code, self.position_size)
                    self.entry_price = bar.close
                    self.is_long = True
                    print(f"[{bar.datetime}] 金叉买入开仓 @ {bar.close:.2f}")

            # 死叉信号
            elif ma_fast[-2] >= ma_slow[-2] and ma_fast[-1] < ma_slow[-1]:
                if current_pos and current_pos.volume_long > 0:
                    # 有持仓，平仓
                    self.SellClose(bar.code, current_pos.volume_long)
                    self.is_long = False
                    print(f"[{bar.datetime}] 死叉卖出平仓 @ {bar.close:.2f}")

        # 5. 风险控制
        if current_pos and current_pos.volume_long > 0 and self.entry_price > 0:
            # 计算盈亏比例
            pnl_pct = (bar.close - self.entry_price) / self.entry_price

            # 止损
            if pnl_pct <= -self.stop_loss_pct:
                self.SellClose(bar.code, current_pos.volume_long)
                self.is_long = False
                print(f"[{bar.datetime}] 止损平仓 @ {bar.close:.2f}, 亏损{pnl_pct*100:.2f}%")

            # 止盈
            elif pnl_pct >= self.take_profit_pct:
                self.SellClose(bar.code, current_pos.volume_long)
                self.is_long = False
                print(f"[{bar.datetime}] 止盈平仓 @ {bar.close:.2f}, 盈利{pnl_pct*100:.2f}%")

    def on_dailyclose(self):
        """每日收盘回调"""
        # 输出每日统计信息
        print(f"[日终] 权益: {self.acc.balance:.2f}, 可用: {self.acc.cash_available:.2f}")

    def on_dailyopen(self):
        """每日开盘回调"""
        print(f"[开盘] 新的交易日开始")


# 运行策略
if __name__ == '__main__':
    strategy = DualMAStrategy(
        code='rb2501',
        frequence='5min',
        strategy_id='dual_ma_cta',
        start='2024-01-01',
        end='2024-12-31',
        init_cash=1000000,
    )

    strategy.run_backtest()
```

---

## 🔄 多标的策略开发

使用`QAMultiBase`开发多标的策略：

```python
from QUANTAXIS.QAStrategy.qamultibase import QAMultiBase


class MultiAssetStrategy(QAMultiBase):
    """多标的轮动策略"""

    def user_init(self):
        """初始化"""
        # 设置标的池
        self.codes = ['rb2501', 'hc2501', 'i2501']  # 螺纹钢、热轧卷板、铁矿石

        # 策略参数
        self.momentum_period = 20    # 动量周期
        self.top_n = 2               # 持仓数量

    def on_bar(self, bars):
        """多标的K线回调

        参数:
            bars: dict, {code: bar_data}
        """
        # 1. 计算每个标的的动量
        momentums = {}

        for code in self.codes:
            market_data = self.get_code_marketdata(code)
            if len(market_data) >= self.momentum_period:
                # 计算动量 = 当前价格 / N日前价格 - 1
                current_price = market_data[-1]['close']
                past_price = market_data[-self.momentum_period]['close']
                momentum = (current_price / past_price) - 1
                momentums[code] = momentum

        # 2. 选择动量最大的N个标的
        sorted_codes = sorted(momentums.items(),
                            key=lambda x: x[1],
                            reverse=True)
        target_codes = [code for code, _ in sorted_codes[:self.top_n]]

        # 3. 调整持仓
        positions = self.acc.positions

        # 平掉不在目标池的持仓
        for code in list(positions.keys()):
            if code not in target_codes:
                pos = positions[code]
                if pos.volume_long > 0:
                    self.SellClose(code, pos.volume_long)
                    print(f"平仓 {code}")

        # 开仓目标标的
        available_cash = self.acc.cash_available
        position_value = available_cash / len(target_codes)

        for code in target_codes:
            if code not in positions or positions[code].volume_long == 0:
                # 计算手数
                price = bars[code].close
                volume = int(position_value / (price * 10))  # 假设合约乘数10
                if volume > 0:
                    self.BuyOpen(code, volume)
                    print(f"开仓 {code}, 手数: {volume}")
```

---

## ⚖️ 套利策略开发

使用`QAHedgeBase`开发对冲套利策略：

```python
from QUANTAXIS.QAStrategy.qahedgebase import QAHedgeBase


class PairTradingStrategy(QAHedgeBase):
    """配对交易策略"""

    def user_init(self):
        """初始化"""
        # 配对标的
        self.code1 = 'rb2501'  # 螺纹钢
        self.code2 = 'hc2501'  # 热轧卷板

        # 策略参数
        self.lookback_period = 30      # 回看周期
        self.entry_threshold = 2.0     # 开仓阈值（标准差倍数）
        self.exit_threshold = 0.5      # 平仓阈值

        # 状态
        self.is_in_position = False
        self.position_type = None      # 'LONG_SPREAD' or 'SHORT_SPREAD'

    def on_bar(self, bars):
        """K线更新回调"""
        # 1. 获取两个标的的历史数据
        data1 = self.get_code_marketdata(self.code1)
        data2 = self.get_code_marketdata(self.code2)

        if len(data1) < self.lookback_period or len(data2) < self.lookback_period:
            return

        # 2. 计算价差
        prices1 = [x['close'] for x in data1[-self.lookback_period:]]
        prices2 = [x['close'] for x in data2[-self.lookback_period:]]
        spread = [p1 - p2 for p1, p2 in zip(prices1, prices2)]

        # 3. 计算价差的标准化值
        import numpy as np
        spread_mean = np.mean(spread[:-1])
        spread_std = np.std(spread[:-1])
        current_spread = spread[-1]
        z_score = (current_spread - spread_mean) / spread_std if spread_std > 0 else 0

        # 4. 生成交易信号
        if not self.is_in_position:
            # 价差过高，做空价差（买code2，卖code1）
            if z_score > self.entry_threshold:
                self.SellOpen(self.code1, 1)
                self.BuyOpen(self.code2, 1)
                self.is_in_position = True
                self.position_type = 'SHORT_SPREAD'
                print(f"开仓做空价差, Z-Score: {z_score:.2f}")

            # 价差过低，做多价差（买code1，卖code2）
            elif z_score < -self.entry_threshold:
                self.BuyOpen(self.code1, 1)
                self.SellOpen(self.code2, 1)
                self.is_in_position = True
                self.position_type = 'LONG_SPREAD'
                print(f"开仓做多价差, Z-Score: {z_score:.2f}")

        else:
            # 平仓条件：价差回归
            if abs(z_score) < self.exit_threshold:
                if self.position_type == 'SHORT_SPREAD':
                    self.BuyClose(self.code1, 1)
                    self.SellClose(self.code2, 1)
                else:  # LONG_SPREAD
                    self.SellClose(self.code1, 1)
                    self.BuyClose(self.code2, 1)

                self.is_in_position = False
                self.position_type = None
                print(f"平仓, Z-Score: {z_score:.2f}")
```

---

## 📊 因子策略开发

使用`QAFactorBase`开发因子驱动策略：

```python
from QUANTAXIS.QAStrategy.qafactorbase import QAFactorBase
import pandas as pd


class FactorStrategy(QAFactorBase):
    """多因子选股策略"""

    def user_init(self):
        """初始化"""
        # 股票池（沪深300成分股）
        self.stock_pool = QA.QA_fetch_index_constituents('000300')

        # 因子参数
        self.momentum_period = 20    # 动量周期
        self.value_metric = 'pe'     # 估值指标
        self.top_n = 30              # 选股数量

        # 调仓频率
        self.rebalance_days = 20     # 20个交易日调仓一次
        self.days_counter = 0

    def calculate_factors(self):
        """计算因子值"""
        factor_df = pd.DataFrame()

        for code in self.stock_pool:
            # 获取历史数据
            data = QA.QA_fetch_stock_day(
                code,
                start=self.start,
                end=self.end
            )

            if len(data) < self.momentum_period:
                continue

            # 动量因子
            momentum = (data['close'].iloc[-1] / data['close'].iloc[-self.momentum_period]) - 1

            # 估值因子（需要财务数据）
            pe_ratio = self.get_pe_ratio(code)  # 自定义方法获取PE

            factor_df = factor_df.append({
                'code': code,
                'momentum': momentum,
                'pe': pe_ratio
            }, ignore_index=True)

        return factor_df

    def select_stocks(self, factor_df):
        """因子打分选股"""
        # 因子标准化
        factor_df['momentum_score'] = (factor_df['momentum'] - factor_df['momentum'].mean()) / factor_df['momentum'].std()
        factor_df['value_score'] = -(factor_df['pe'] - factor_df['pe'].mean()) / factor_df['pe'].std()  # PE越低越好

        # 综合评分
        factor_df['total_score'] = factor_df['momentum_score'] * 0.6 + factor_df['value_score'] * 0.4

        # 选择得分最高的N只股票
        selected = factor_df.nlargest(self.top_n, 'total_score')
        return selected['code'].tolist()

    def on_bar(self, bars):
        """K线更新回调"""
        self.days_counter += 1

        # 到达调仓日
        if self.days_counter >= self.rebalance_days:
            # 1. 计算因子
            factor_df = self.calculate_factors()

            # 2. 选股
            target_stocks = self.select_stocks(factor_df)

            # 3. 调仓
            self.rebalance(target_stocks)

            # 重置计数器
            self.days_counter = 0

    def rebalance(self, target_stocks):
        """调仓"""
        positions = self.acc.positions

        # 卖出不在目标池的持仓
        for code in list(positions.keys()):
            if code not in target_stocks:
                self.Sell(code, positions[code].volume_long)

        # 等权买入目标股票
        available_cash = self.acc.cash_available
        position_value = available_cash / len(target_stocks)

        for code in target_stocks:
            price = bars[code].close
            volume = int(position_value / price / 100) * 100  # 取整100股
            if volume > 0:
                self.Buy(code, volume)
```

---

## 🎯 策略回调方法

### 核心回调

```python
class MyStrategy(QAStrategyCtaBase):

    def user_init(self):
        """策略初始化 - 只执行一次"""
        pass

    def on_bar(self, bar):
        """K线更新回调 - 每根K线触发一次"""
        pass

    def on_tick(self, tick):
        """Tick更新回调 - 每个tick触发一次（高频策略）"""
        pass

    def on_dailyopen(self):
        """每日开盘回调"""
        pass

    def on_dailyclose(self):
        """每日收盘回调"""
        pass

    def on_sync(self):
        """同步回调 - 定时触发"""
        pass
```

### 扩展回调

```python
def on_signal(self, signal):
    """信号触发回调"""
    pass

def on_order(self, order):
    """订单回调"""
    pass

def on_trade(self, trade):
    """成交回调"""
    pass

def risk_check(self):
    """风险检查 - 定期触发"""
    return True  # 返回False会暂停策略
```

---

## 🔐 风险管理

### 1. 仓位控制

```python
def on_bar(self, bar):
    # 方法1: 固定手数
    max_position = 5
    current_pos = self.acc.positions.get(bar.code)
    if current_pos is None or current_pos.volume_long < max_position:
        self.BuyOpen(bar.code, 1)

    # 方法2: 资金比例
    position_pct = 0.3  # 单笔不超过30%资金
    available_cash = self.acc.cash_available
    max_value = available_cash * position_pct
    volume = int(max_value / (bar.close * 10))  # 假设合约乘数10

    # 方法3: 风险比例（如凯利公式）
    win_rate = 0.6
    avg_win = 0.02
    avg_loss = 0.01
    kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
    position_pct = kelly * 0.5  # 使用半凯利
```

### 2. 止损止盈

```python
def on_bar(self, bar):
    positions = self.acc.positions
    if bar.code in positions:
        pos = positions[bar.code]

        # 固定止损止盈
        if pos.volume_long > 0:
            entry_price = pos.open_price_long
            pnl_pct = (bar.close - entry_price) / entry_price

            # 止损2%
            if pnl_pct <= -0.02:
                self.SellClose(bar.code, pos.volume_long)
                print(f"止损: {pnl_pct*100:.2f}%")

            # 止盈5%
            elif pnl_pct >= 0.05:
                self.SellClose(bar.code, pos.volume_long)
                print(f"止盈: {pnl_pct*100:.2f}%")

        # ATR止损
        import talib
        data = self.get_code_marketdata(bar.code)
        high = [x['high'] for x in data]
        low = [x['low'] for x in data]
        close = [x['close'] for x in data]
        atr = talib.ATR(high, low, close, timeperiod=14)[-1]

        stop_loss_price = entry_price - 2 * atr
        if bar.close <= stop_loss_price:
            self.SellClose(bar.code, pos.volume_long)
```

### 3. 资金管理

```python
class RiskManager:
    """资金管理器"""

    def __init__(self, init_cash, max_risk_pct=0.02):
        self.init_cash = init_cash
        self.max_risk_pct = max_risk_pct  # 单笔最大风险

    def calculate_position_size(self, entry_price, stop_loss_price):
        """计算合理仓位

        参数:
            entry_price: 入场价格
            stop_loss_price: 止损价格

        返回:
            volume: 建议手数
        """
        # 单笔风险金额
        max_risk = self.init_cash * self.max_risk_pct

        # 单手风险
        risk_per_unit = abs(entry_price - stop_loss_price) * 10  # 合约乘数

        # 计算手数
        volume = int(max_risk / risk_per_unit)

        return max(1, volume)  # 至少1手


# 使用
risk_mgr = RiskManager(init_cash=1000000, max_risk_pct=0.02)

def on_bar(self, bar):
    entry_price = bar.close
    stop_loss_price = entry_price * 0.98  # 2%止损

    volume = risk_mgr.calculate_position_size(entry_price, stop_loss_price)
    self.BuyOpen(bar.code, volume)
```

---

## 📝 策略调试

### 1. 日志输出

```python
import logging

class MyStrategy(QAStrategyCtaBase):

    def user_init(self):
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename=f'strategy_{self.strategy_id}.log'
        )
        self.logger = logging.getLogger(self.strategy_id)

    def on_bar(self, bar):
        self.logger.info(f"K线更新: {bar.datetime}, 价格: {bar.close}")

        if signal:
            self.logger.info(f"生成信号: {signal}")

        if order:
            self.logger.info(f"下单: {order}")
```

### 2. 性能监控

```python
import time

def on_bar(self, bar):
    start_time = time.time()

    # 策略逻辑
    self.update_indicators(bar)
    signal = self.generate_signal()

    # 计算耗时
    elapsed = time.time() - start_time
    if elapsed > 0.1:  # 超过100ms警告
        print(f"⚠️ 策略执行耗时: {elapsed*1000:.2f}ms")
```

### 3. 回测结果分析

```python
# 运行回测
strategy.run_backtest()

# 获取回测结果
acc = strategy.acc

# 账户信息
print(f"初始资金: {acc.init_cash}")
print(f"最终权益: {acc.balance}")
print(f"总收益: {acc.balance - acc.init_cash}")
print(f"收益率: {(acc.balance / acc.init_cash - 1) * 100:.2f}%")

# 交易统计
trades = acc.trades
print(f"总交易次数: {len(trades)}")

# 订单统计
orders = acc.orders
print(f"总订单数: {len(orders)}")

# 持仓统计
positions = acc.positions
print(f"当前持仓: {positions}")
```

---

## 🔗 实盘部署

### 1. 实盘配置

```python
# 实盘策略配置
strategy = MyStrategy(
    code='rb2501',
    frequence='5min',
    strategy_id='my_strategy_live',
    portfolio='live_portfolio',

    # 实盘模式
    model='live',  # 'sim' 模拟, 'live' 实盘

    # EventMQ配置
    data_host='192.168.1.100',
    data_port=5672,
    data_user='admin',
    data_password='admin',

    trade_host='192.168.1.100',
    trade_port=5672,
    trade_user='admin',
    trade_password='admin',

    # 通知
    send_wx=True,  # 开启微信通知
)

# 运行实盘
strategy.run()
```

### 2. 监控和日志

```python
# 实时监控
def on_bar(self, bar):
    # 输出关键信息
    positions = self.acc.positions
    balance = self.acc.balance

    print(f"[{bar.datetime}] 权益: {balance:.2f}, 持仓: {len(positions)}")

    # 发送微信通知（重要事件）
    if self.send_wx and signal:
        self.send_wx_message(f"交易信号: {signal}, 价格: {bar.close}")
```

---

## 📊 策略评估指标

### 1. 收益指标

```python
import numpy as np

# 总收益率
total_return = (final_balance / init_cash - 1) * 100

# 年化收益率
days = (end_date - start_date).days
annual_return = ((final_balance / init_cash) ** (365 / days) - 1) * 100

# 超额收益
benchmark_return = 10  # 基准收益率
alpha = total_return - benchmark_return
```

### 2. 风险指标

```python
# 最大回撤
def calculate_max_drawdown(balance_series):
    """计算最大回撤"""
    cummax = np.maximum.accumulate(balance_series)
    drawdown = (balance_series - cummax) / cummax
    max_drawdown = drawdown.min()
    return abs(max_drawdown)

# 夏普比率
def calculate_sharpe(returns, risk_free_rate=0.03):
    """计算夏普比率"""
    excess_returns = returns - risk_free_rate / 252  # 日收益率
    sharpe = np.sqrt(252) * excess_returns.mean() / excess_returns.std()
    return sharpe

# 波动率
volatility = np.std(returns) * np.sqrt(252)
```

### 3. 交易指标

```python
# 胜率
win_trades = [t for t in trades if t.profit > 0]
win_rate = len(win_trades) / len(trades) if trades else 0

# 盈亏比
avg_win = np.mean([t.profit for t in win_trades]) if win_trades else 0
lose_trades = [t for t in trades if t.profit < 0]
avg_loss = abs(np.mean([t.profit for t in lose_trades])) if lose_trades else 0
profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

# 期望收益
expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
```

---

## ⚠️ 常见问题

### Q1: 策略回测和实盘结果不一致？

**A**: 可能原因和解决方案：

```python
# 1. 数据对齐问题
# 确保回测和实盘使用相同的数据源和频率

# 2. 滑点设置
# 回测时考虑滑点
self.slippage = 0.0002  # 0.02%滑点

# 3. 手续费设置
# 设置真实的手续费
self.commission = 0.0003  # 0.03%手续费

# 4. 延迟问题
# 实盘考虑信号延迟
# 使用上一根K线的信号，当前K线开盘价执行
```

### Q2: 如何避免未来函数？

**A**: 确保只使用历史数据：

```python
def on_bar(self, bar):
    # ❌ 错误：使用了当前bar的close
    if bar.close > self.ma[-1]:
        self.BuyOpen(bar.code, 1)

    # ✅ 正确：使用上一根bar的数据
    market_data = self.get_code_marketdata(bar.code)
    if len(market_data) >= 2:
        last_close = market_data[-2]['close']
        if last_close > self.ma[-2]:
            self.BuyOpen(bar.code, 1)
```

### Q3: 策略性能优化？

**A**: 优化建议：

```python
# 1. 使用向量化计算
import numpy as np
close_prices = np.array([x['close'] for x in market_data])
ma = np.convolve(close_prices, np.ones(period)/period, mode='valid')

# 2. 缓存中间结果
@lru_cache(maxsize=128)
def calculate_indicator(self, code, period):
    # 计算指标
    pass

# 3. 减少数据库查询
# 批量获取数据，而不是每次查询

# 4. 使用高效的数据结构
from collections import deque
self.price_buffer = deque(maxlen=100)  # 固定长度队列
```

---

## 🔗 相关资源

- **API参考**: [QAStrategy API文档](../api-reference/qastrategy.md)
- **数据获取**: [QAFetch数据获取](data-fetching.md)
- **回测系统**: [QABacktest回测](backtesting.md)
- **实盘交易**: [QALive实盘](live-trading.md)

---

## 📝 总结

QUANTAXIS策略开发框架提供了：

✅ **多种策略类型**: CTA、多标的、套利、因子
✅ **事件驱动**: 灵活的回调机制
✅ **风险管理**: 内置仓位控制和风控
✅ **回测实盘一体化**: 同一代码无缝切换
✅ **QIFI账户**: 统一的多市场账户管理

**下一步**: 学习如何进行[策略回测](backtesting.md)

---

**作者**: @yutiansut @quantaxis
**最后更新**: 2025-10-25

[← 上一页：数据获取](data-fetching.md) | [下一页：回测系统 →](backtesting.md)
