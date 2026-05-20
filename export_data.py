import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import os
from config import PAIRS, BACKTEST_START, BACKTEST_END, MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

DATA_DIR = "data"


def connect():
    if not mt5.initialize():
        raise RuntimeError("MT5 initialize failed — make sure MT5 is open")
    if MT5_LOGIN and MT5_PASSWORD and MT5_SERVER:
        if not mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
            raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")


def get_ohlc(symbol, timeframe):
    tf_map = {"H1": mt5.TIMEFRAME_H1, "M15": mt5.TIMEFRAME_M15}
    start = datetime.strptime(BACKTEST_START, "%Y-%m-%d")
    end   = datetime.strptime(BACKTEST_END,   "%Y-%m-%d")
    rates = mt5.copy_rates_range(symbol, tf_map[timeframe], start, end)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    return df[["open", "high", "low", "close"]]


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    connect()
    for pair in PAIRS:
        for tf in ["H1", "M15"]:
            df = get_ohlc(pair, tf)
            if df is not None:
                path = os.path.join(DATA_DIR, f"{pair}_{tf}.csv")
                df.to_csv(path)
                print(f"Exported {pair} {tf} — {len(df)} bars")
            else:
                print(f"No data: {pair} {tf}")
    mt5.shutdown()
    print("\nDone. Push the data/ folder to git.")


if __name__ == "__main__":
    main()
