import backtrader as bt
import matplotlib.pyplot as plt

def main():
    cerebro = bt.Cerebro()


    data = bt.feeds.GenericCSVData(
        dataname="./000711.csv", dtformat="%Y%m%d",
    )
    cerebro.adddata(data)

    cerebro.run()
    cerebro.plot()


if __name__ == "__main__":
    main()