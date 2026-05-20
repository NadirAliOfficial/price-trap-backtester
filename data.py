import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, BACKTEST_START, BACKTEST_END


def connect():
    if not mt5.initialize():
        raise RuntimeError("MT5 initialize failed")
    if MT5_LOGIN and MT5_PASSWORD and MT5_SERVER:
        mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)


def disconnect():
    mt5.shutdown()


def get_ohlc(symbol, timeframe, start, end):
    tf_map = {"H1": mt5.TIMEFRAME_H1, "M15": mt5.TIMEFRAME_M15}
    tf = tf_map[timeframe]
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    rates = mt5.copy_rates_range(symbol, tf, start_dt, end_dt)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    return df[["open", "high", "low", "close"]]


def load_all_pairs(pairs):
    connect()
    data = {}
    for pair in pairs:
        h1 = get_ohlc(pair, "H1", BACKTEST_START, BACKTEST_END)
        m15 = get_ohlc(pair, "M15", BACKTEST_START, BACKTEST_END)
        if h1 is not None and m15 is not None:
            data[pair] = {"H1": h1, "M15": m15}
            print(f"Loaded {pair}")
        else:
            print(f"Skipped {pair} - no data")
    disconnect()
    return data
