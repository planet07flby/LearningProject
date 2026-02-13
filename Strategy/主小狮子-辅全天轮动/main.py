# main.py
"""
主程序入口 - 负责创建回测引擎并注册策略函数
"""
from engine.core import BacktestEngine
import strategy
import config


def main():
    # 创建回测引擎
    engine = BacktestEngine(
        start_date=config.START_DATE,
        end_date=config.END_DATE,
        initial_cash=config.INITIAL_CASH,
        benchmark=config.BENCHMARK,
        data_config={
            'jq_username': config.JQ_USERNAME,
            'jq_password': config.JQ_PASSWORD
        }
    )

    # 注册initialize函数
    engine.initialize(strategy.initialize)

    # ===== 注册定时函数（对应原代码的run_daily/run_weekly）=====
    # 注意：时间格式为 'HH:MM'
    engine.run_daily(strategy.prepare_stock_list, '09:05')
    engine.run_weekly(strategy.weekly_adjustment, weekday=2, time='10:30')  # 周二
    engine.run_daily(strategy.sell_stocks, '10:00')
    engine.run_daily(strategy.check_extreme_market, '09:30')
    engine.run_daily(strategy.trade_afternoon, '14:20')
    engine.run_daily(strategy.trade_afternoon, '14:55')
    engine.run_daily(strategy.close_account, '14:50')

    # 运行回测
    results = engine.run()

    # 输出结果
    print(f"\n=== 回测结果 ===")
    print(f"初始资金: {config.INITIAL_CASH:,.2f}")
    print(f"最终资金: {results['final_value']:,.2f}")
    print(f"总收益率: {results['total_return'] * 100:.2f}%")
    print(f"年化收益: {results['annual_return'] * 100:.2f}%")
    print(f"最大回撤: {results['max_drawdown'] * 100:.2f}%")
    print(f"夏普比率: {results['sharpe_ratio']:.2f}")

    # 绘制收益曲线
    if config.PLOT_RESULTS:
        engine.plot_results()


if __name__ == '__main__':
    main()