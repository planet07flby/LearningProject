# engine/core.py
"""
回测引擎核心类
模拟聚宽的回测环境，提供context、portfolio、订单执行等功能
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional, Any, Tuple
import jqdatasdk as jq
from collections import defaultdict
import warnings

warnings.filterwarnings('ignore')


class Position:
    """持仓对象，模拟聚宽的position"""

    def __init__(self, security: str, amount: int = 0, avg_cost: float = 0.0):
        self.security = security
        self.total_amount = amount  # 总持仓数量
        self.closeable_amount = amount  # 可卖数量
        self.avg_cost = avg_cost  # 平均成本
        self.price = 0.0  # 当前价格
        self.value = 0.0  # 当前市值
        self.pnl = 0.0  # 盈亏

    def update_price(self, price: float):
        """更新当前价格"""
        self.price = price
        self.value = self.total_amount * price
        self.pnl = self.value - self.total_amount * self.avg_cost


class Portfolio:
    """投资组合对象，模拟聚宽的portfolio"""

    def __init__(self, initial_cash: float):
        self.positions: Dict[str, Position] = {}  # 持仓字典
        self.cash = initial_cash  # 可用现金
        self.total_value = initial_cash  # 总资产
        self.initial_cash = initial_cash  # 初始资金
        self.start_date = None
        self.current_date = None

    def update_prices(self, price_dict: Dict[str, float]):
        """更新所有持仓价格"""
        self.total_value = self.cash
        for security, position in self.positions.items():
            if security in price_dict:
                position.update_price(price_dict[security])
                self.total_value += position.value

    def get_position(self, security: str) -> Optional[Position]:
        """获取某个股票的持仓"""
        return self.positions.get(security)

    def __getitem__(self, security: str) -> Position:
        """支持 portfolio[stock] 语法"""
        if security not in self.positions:
            self.positions[security] = Position(security)
        return self.positions[security]


class Context:
    """回测上下文，模拟聚宽的context"""

    def __init__(self, engine):
        self.engine = engine
        self.portfolio = engine.portfolio
        self.current_dt = None
        self.previous_date = None
        self.g = None  # 策略全局变量
        self.data_api = engine  # 数据API接口
        self.current_data = {}  # 当前快照数据

    def log(self, msg: str, level: str = 'info'):
        """日志输出"""
        timestamp = self.current_dt.strftime('%Y-%m-%d %H:%M:%S') if self.current_dt else 'N/A'
        print(f"[{timestamp}] {msg}")

    def order_target_value(self, security: str, value: float) -> Optional[Dict]:
        """调仓到目标市值（聚宽兼容接口）"""
        return self.engine.order_target_value(security, value, self)

    def get_open_orders(self):
        """获取未完成订单"""
        return []


class BacktestEngine:
    """回测引擎主类"""

    def __init__(self,
                 start_date: str,
                 end_date: str,
                 initial_cash: float = 1000000,
                 benchmark: str = '399101.XSHE',
                 data_config: Dict = None):
        """
        初始化回测引擎

        Args:
            start_date: 开始日期 'YYYY-MM-DD'
            end_date: 结束日期 'YYYY-MM-DD'
            initial_cash: 初始资金
            benchmark: 基准指数代码
            data_config: 数据配置 {'jq_username': '', 'jq_password': ''}
        """
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.initial_cash = initial_cash
        self.benchmark = benchmark

        # 登录JQData
        if data_config:
            jq.auth(data_config.get('jq_username'), data_config.get('jq_password'))

        # 回测状态
        self.current_date = None
        self.portfolio = Portfolio(initial_cash)
        self.trading_days = []  # 交易日列表

        # 策略函数注册
        self.initialize_func = None
        self.daily_funcs = defaultdict(list)  # {时间: [函数列表]}
        self.weekly_funcs = []  # [(weekday, time, func)]

        # 数据缓存
        self._price_cache = {}  # 价格缓存
        self._fundamentals_cache = {}  # 财务数据缓存
        self._industry_cache = {}  # 行业缓存
        self._security_info_cache = {}  # 证券信息缓存

        # 成交记录
        self.trades = []
        self.daily_values = []

        # 日志级别
        self.log_level = 'info'

    def initialize(self, func: Callable):
        """注册initialize函数"""
        self.initialize_func = func

    def run_daily(self, func: Callable, time: str):
        """注册每日运行函数"""
        self.daily_funcs[time].append(func)

    def run_weekly(self, func: Callable, weekday: int, time: str):
        """注册每周运行函数"""
        self.weekly_funcs.append((weekday, time, func))

    def run(self) -> Dict:
        """
        运行回测
        Returns:
            回测结果字典
        """
        # 获取交易日序列
        self.trading_days = jq.get_trade_days(self.start_date, self.end_date)
        if not len(self.trading_days):
            raise ValueError("没有交易日数据")

        print(f"回测周期: {self.start_date.date()} 至 {self.end_date.date()}")
        print(f"交易日数量: {len(self.trading_days)}")

        # 创建上下文
        context = Context(self)

        # 调用initialize
        if self.initialize_func:
            self.initialize_func(context)
            context.g = getattr(context, 'g', None)

        # 逐日回测
        for i, day in enumerate(self.trading_days):
            self.current_date = day
            context.current_dt = datetime.combine(day, datetime.min.time())
            context.previous_date = self._get_previous_trading_day(day) if i > 0 else day

            # 更新市场快照数据
            self._update_current_data(context, day)

            # 执行所有定时函数
            self._execute_scheduled_functions(context, day, i)

            # 记录每日净值
            self._record_daily_value(day)

            # 进度提示
            if (i + 1) % 100 == 0:
                print(f"已回测 {i + 1}/{len(self.trading_days)} 天...")

        # 计算回测指标
        results = self._calculate_results()

        return results

    def _get_previous_trading_day(self, date) -> pd.Timestamp:
        """获取上一个交易日（修复bug版本）"""
        try:
            # 确保date是pd.Timestamp
            if not isinstance(date, pd.Timestamp):
                date = pd.to_datetime(date)

            # 将trading_days转换为列表或使用不同的方法
            trading_days_list = list(self.trading_days)

            # 找到当前日期的索引
            for i, d in enumerate(trading_days_list):
                if d == date:
                    if i > 0:
                        return trading_days_list[i - 1]
                    else:
                        return date
            return date
        except Exception as e:
            print(f"获取上一个交易日出错: {e}")
            return date

    def _update_current_data(self, context: Context, date: pd.Timestamp):
        """更新当前快照数据"""
        # 获取所有持仓股票和可能需要的股票
        all_stocks = list(self.portfolio.positions.keys())

        # 获取这些股票的当日数据
        if all_stocks:
            try:
                df = self.get_price(
                    all_stocks,
                    end_date=date,
                    frequency='daily',
                    fields=['close', 'high', 'low', 'open',
                            'high_limit', 'low_limit', 'volume', 'money'],
                    count=1
                )

                current_data = {}
                if not df.empty:
                    for _, row in df.iterrows():
                        stock = row['code']
                        current_data[stock] = {
                            'last_price': row['close'],
                            'open': row['open'],
                            'high': row['high'],
                            'low': row['low'],
                            'high_limit': row['high_limit'],
                            'low_limit': row['low_limit'],
                            'volume': row['volume'],
                            'money': row['money'],
                            'paused': False,  # 需要从停牌数据获取
                            'is_st': False,  # 需要从ST数据获取
                            'name': self.get_security_info(stock).get('display_name', '')
                        }
                context.current_data = current_data

                # 更新持仓价格
                price_dict = {s: d['last_price'] for s, d in current_data.items()}
                self.portfolio.update_prices(price_dict)

            except Exception as e:
                print(f"更新快照数据出错 {date}: {e}")

    def _execute_scheduled_functions(self, context: Context, date: pd.Timestamp, day_idx: int):
        """执行定时函数"""
        weekday = date.weekday() + 1  # 转换为1-7，周一=1

        # 执行每日函数
        for time_str, funcs in self.daily_funcs.items():
            for func in funcs:
                try:
                    func(context)
                except Exception as e:
                    print(f"执行每日函数 {func.__name__} 出错: {e}")

        # 执行每周函数
        for weekday_target, time_str, func in self.weekly_funcs:
            if weekday == weekday_target:
                try:
                    func(context)
                except Exception as e:
                    print(f"执行每周函数 {func.__name__} 出错: {e}")

    def _record_daily_value(self, date: pd.Timestamp):
        """记录每日资产总值"""
        self.daily_values.append({
            'date': date,
            'total_value': self.portfolio.total_value,
            'cash': self.portfolio.cash,
            'positions': len(self.portfolio.positions)
        })

    def _calculate_results(self) -> Dict:
        """计算回测结果指标"""
        df = pd.DataFrame(self.daily_values)
        df.set_index('date', inplace=True)

        # 计算收益率
        df['return'] = df['total_value'].pct_change()
        df['cum_return'] = df['total_value'] / self.initial_cash - 1

        # 获取基准数据
        benchmark_data = self.get_price(
            self.benchmark,
            start_date=self.start_date,
            end_date=self.end_date,
            frequency='daily',
            fields=['close']
        )

        if not benchmark_data.empty:
            benchmark_data['return'] = benchmark_data['close'].pct_change()
            benchmark_data['cum_return'] = benchmark_data['close'] / benchmark_data['close'].iloc[0] - 1
            # 对齐日期
            df = df.join(benchmark_data[['cum_return']], rsuffix='_benchmark')
        else:
            df['cum_return_benchmark'] = 0

        # 计算指标
        total_return = df['cum_return'].iloc[-1]

        # 年化收益
        years = len(df) / 245  # 约245个交易日/年
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # 最大回撤
        cumulative = (1 + df['return']).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        # 夏普比率
        risk_free_rate = 0.03  # 假设3%无风险利率
        excess_return = df['return'] - risk_free_rate / 245
        sharpe_ratio = np.sqrt(245) * excess_return.mean() / excess_return.std() if excess_return.std() > 0 else 0

        # 胜率
        win_rate = (df['return'] > 0).sum() / len(df) if len(df) > 0 else 0

        return {
            'df': df,
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'final_value': self.portfolio.total_value,
            'final_cash': self.portfolio.cash,
            'positions_count': len(self.portfolio.positions)
        }

    # ========== 订单执行函数 ==========
    def order_target_value(self, security: str, value: float, context: Context) -> Optional[Dict]:
        """
        调仓到目标市值

        Args:
            security: 股票代码
            value: 目标市值
            context: 上下文

        Returns:
            订单信息
        """
        if value < 0:
            return None

        # 获取当前持仓
        position = self.portfolio.get_position(security)
        current_value = position.value if position else 0

        # 获取当前价格
        current_data = context.current_data.get(security, {})
        price = current_data.get('last_price', 0)

        if price <= 0:
            print(f"无法获取 {security} 的有效价格")
            return None

        # 计算需要调整的金额
        delta_value = value - current_value

        if abs(delta_value) < 0.01:  # 变化太小，忽略
            return None

        if delta_value > 0:  # 买入
            amount_to_buy = int(delta_value / price / 100) * 100  # 整手
            if amount_to_buy <= 0:
                return None

            cost = amount_to_buy * price

            # 检查现金是否足够
            if cost > self.portfolio.cash:
                # 按可用现金调整
                amount_to_buy = int(self.portfolio.cash / price / 100) * 100
                if amount_to_buy <= 0:
                    return None
                cost = amount_to_buy * price

            # 执行买入
            if security not in self.portfolio.positions:
                self.portfolio.positions[security] = Position(security)

            position = self.portfolio.positions[security]

            # 更新持仓
            new_amount = position.total_amount + amount_to_buy
            new_cost = position.avg_cost * position.total_amount + cost
            position.total_amount = new_amount
            position.closeable_amount = new_amount
            position.avg_cost = new_cost / new_amount if new_amount > 0 else 0
            position.update_price(price)

            # 扣减现金
            self.portfolio.cash -= cost

            trade_record = {
                'date': context.current_dt,
                'security': security,
                'direction': 'buy',
                'amount': amount_to_buy,
                'price': price,
                'value': cost
            }
            self.trades.append(trade_record)

            print(f"{context.current_dt.date()} 买入 {security} {amount_to_buy}股 @ {price:.2f}, 金额: {cost:.2f}")

        else:  # 卖出
            if not position or position.total_amount <= 0:
                return None

            amount_to_sell = int(-delta_value / price / 100) * 100
            amount_to_sell = min(amount_to_sell, position.total_amount)

            if amount_to_sell <= 0:
                return None

            proceeds = amount_to_sell * price

            # 更新持仓
            position.total_amount -= amount_to_sell
            position.closeable_amount = position.total_amount

            # 如果清仓，移除持仓
            if position.total_amount == 0:
                del self.portfolio.positions[security]
            else:
                position.update_price(price)

            # 增加现金
            self.portfolio.cash += proceeds

            trade_record = {
                'date': context.current_dt,
                'security': security,
                'direction': 'sell',
                'amount': amount_to_sell,
                'price': price,
                'value': proceeds
            }
            self.trades.append(trade_record)

            print(f"{context.current_dt.date()} 卖出 {security} {amount_to_sell}股 @ {price:.2f}, 金额: {proceeds:.2f}")

        # 更新总资产
        self.portfolio.total_value = self.portfolio.cash
        for s, p in self.portfolio.positions.items():
            if s in context.current_data:
                p.update_price(context.current_data[s].get('last_price', 0))
            self.portfolio.total_value += p.value

        return {'security': security, 'value': value, 'filled': True}

    # ========== 数据获取函数（模拟聚宽API） ==========
    def get_price(self,
                  security: str or List[str],
                  start_date: str or datetime = None,
                  end_date: str or datetime = None,
                  frequency: str = 'daily',
                  fields: List[str] = None,
                  count: int = None,
                  skip_paused: bool = False,
                  fq: str = 'pre',
                  panel: bool = False) -> pd.DataFrame:

        """
        获取价格数据，兼容聚宽API

        Args:
            security: 股票代码或列表
            start_date: 开始日期
            end_date: 结束日期
            frequency: 频率 'daily'/'1m'/'5m'等
            fields: 字段列表 ['open','close','high','low','volume','money','high_limit','low_limit']
            count: 获取多少条数据（与start_date互斥）
            skip_paused: 是否跳过停牌
            fq: 复权 'pre'(前复权) / 'post'(后复权) / None
            panel: 是否返回panel格式

        Returns:
            DataFrame
        """
        # 处理参数
        if fields is None:
            fields = ['open', 'close', 'high', 'low', 'volume', 'money']

        if isinstance(security, str):
            security = [security]

        # 处理日期
        if count is not None and start_date is None:
            # 按count获取数据
            end = pd.to_datetime(end_date) if end_date else pd.Timestamp.now()
            trading_days = jq.get_trade_days(end - timedelta(days=count * 2), end)
            start_date = trading_days[-count] if len(trading_days) >= count else trading_days[0]
        else:
            start_date = pd.to_datetime(start_date) if start_date else None
            end_date = pd.to_datetime(end_date) if end_date else pd.Timestamp.now()

        # 生成缓存key
        cache_key = f"{','.join(sorted(security))}_{start_date}_{end_date}_{frequency}"

        # 检查缓存
        if cache_key in self._price_cache:
            return self._price_cache[cache_key].copy()

        # 从JQData获取数据
        try:
            df_list = []
            for code in security:
                df = jq.get_price(
                    code,
                    start_date=start_date,
                    end_date=end_date,
                    frequency=frequency,
                    fields=fields,
                    skip_paused=skip_paused,
                    fq=fq,
                    panel=False
                )
                if df is not None and not df.empty:
                    df['code'] = code
                    df_list.append(df)

            if df_list:
                result = pd.concat(df_list, ignore_index=True)
                # 缓存结果
                self._price_cache[cache_key] = result.copy()
                return result
            else:
                return pd.DataFrame()

        except Exception as e:
            print(f"获取价格数据出错: {e}")
            return pd.DataFrame()

    def get_fundamentals(self, query: Dict, date=None) -> pd.DataFrame:
        """
        获取财务数据

        Args:
            query: 查询字典 {
                'table': 'valuation',  # 表名
                'fields': ['code', 'market_cap'],  # 字段
                'filters': [('code', 'in', ['000001.XSHE'])],  # 过滤条件
                'order_by': ('market_cap', 'asc'),  # 排序
                'limit': 1000  # 限制数量
            }
            date: 查询日期

        Returns:
            DataFrame
        """
        if date is None:
            date = self.current_date or pd.Timestamp.now()

        # 处理表名映射
        table_map = {
            'valuation': 'valuation',
            'indicator': 'indicator',
            'income': 'income',
            'balance': 'balance',
            'cash_flow': 'cash_flow'
        }

        jq_table = table_map.get(query.get('table', ''))
        if not jq_table:
            return pd.DataFrame()

        try:
            # 构建JQData查询
            q = jq.query(
                getattr(jq, jq_table)
            )

            # 应用过滤条件
            for field, op, value in query.get('filters', []):
                if op == 'in':
                    q = q.filter(getattr(jq_table, field).in_(value))

            # 应用排序
            if 'order_by' in query:
                field, direction = query['order_by']
                if direction == 'asc':
                    q = q.order_by(getattr(jq_table, field).asc())
                else:
                    q = q.order_by(getattr(jq_table, field).desc())

            # 获取数据
            df = jq.get_fundamentals(q, date=date)

            # 限制数量
            if 'limit' in query and len(df) > query['limit']:
                df = df.iloc[:query['limit']]

            return df

        except Exception as e:
            print(f"获取财务数据出错: {e}")
            return pd.DataFrame()

    def get_all_securities(self, types: List[str], date=None) -> List[str]:
        """获取所有股票列表"""
        if date is None:
            date = self.current_date or pd.Timestamp.now()

        try:
            df = jq.get_all_securities(types, date)
            return df.index.tolist()
        except Exception as e:
            print(f"获取证券列表出错: {e}")
            return []

    def get_security_info(self, code: str) -> Dict:
        """获取证券信息"""
        if code in self._security_info_cache:
            return self._security_info_cache[code]

        try:
            info = jq.get_security_info(code)
            self._security_info_cache[code] = {
                'code': info.code,
                'name': info.name,
                'display_name': info.display_name,
                'start_date': info.start_date,
                'end_date': info.end_date,
                'type': info.type
            }
            return self._security_info_cache[code]
        except:
            return {}

    def get_industry(self, security: str or List[str]) -> Dict:
        """获取行业信息"""
        if isinstance(security, list):
            result = {}
            for code in security:
                ind = self.get_industry(code)
                if ind:
                    result.update(ind)
            return result

        cache_key = f"industry_{security}"
        if cache_key in self._industry_cache:
            return self._industry_cache[cache_key]

        try:
            result = jq.get_industry(security)
            self._industry_cache[cache_key] = result
            return result
        except:
            return {}

    def get_index_stocks(self, index_code: str, date=None) -> List[str]:
        """获取指数成分股"""
        if date is None:
            date = self.current_date or pd.Timestamp.now()

        try:
            return jq.get_index_stocks(index_code, date)
        except:
            return []

    def plot_results(self):
        """绘制回测结果"""
        import matplotlib.pyplot as plt

        if not self.daily_values:
            return

        df = pd.DataFrame(self.daily_values)
        df.set_index('date', inplace=True)

        # 计算累计收益
        df['cum_return'] = df['total_value'] / self.initial_cash - 1

        # 获取基准数据
        benchmark = self.get_price(
            self.benchmark,
            start_date=self.start_date,
            end_date=self.end_date,
            frequency='daily',
            fields=['close']
        )

        if not benchmark.empty:
            benchmark['cum_return'] = benchmark['close'] / benchmark['close'].iloc[0] - 1

        # 绘图
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # 收益曲线
        ax1 = axes[0, 0]
        ax1.plot(df.index, df['cum_return'] * 100, label='策略收益', linewidth=2)
        if not benchmark.empty:
            ax1.plot(benchmark.index, benchmark['cum_return'] * 100, label='基准收益', linewidth=2, alpha=0.7)
        ax1.set_xlabel('日期')
        ax1.set_ylabel('累计收益率 (%)')
        ax1.set_title('收益曲线')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 持仓数量
        ax2 = axes[0, 1]
        ax2.plot(df.index, df['positions'], color='green')
        ax2.set_xlabel('日期')
        ax2.set_ylabel('持仓数量')
        ax2.set_title('每日持仓数量')
        ax2.grid(True, alpha=0.3)

        # 现金 vs 市值
        ax3 = axes[1, 0]
        ax3.fill_between(df.index, 0, df['cash'] / 10000, label='现金', alpha=0.5)
        ax3.fill_between(df.index, df['cash'] / 10000, df['total_value'] / 10000, label='股票市值', alpha=0.5)
        ax3.set_xlabel('日期')
        ax3.set_ylabel('金额 (万元)')
        ax3.set_title('资产构成')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # 月度收益热力图
        ax4 = axes[1, 1]
        df['year'] = df.index.year
        df['month'] = df.index.month
        monthly_ret = df.groupby(['year', 'month'])['total_value'].last().pct_change()
        monthly_ret = monthly_ret.dropna()

        if len(monthly_ret) > 0:
            pivot = monthly_ret.unstack(level=0)
            im = ax4.imshow(pivot.values, cmap='RdYlGn', aspect='auto')
            ax4.set_xticks(range(len(pivot.columns)))
            ax4.set_xticklabels(pivot.columns)
            ax4.set_yticks(range(len(pivot.index)))
            ax4.set_yticklabels(pivot.index)
            ax4.set_xlabel('年份')
            ax4.set_ylabel('月份')
            ax4.set_title('月度收益率 (%)')
            plt.colorbar(im, ax=ax4)

        plt.tight_layout()
        plt.show()