import os
import pandas as pd

DATA_DIR = "data"


def load_from_csv(pairs):
    data = {}
    for pair in pairs:
        h1_path  = os.path.join(DATA_DIR, f"{pair}_H1.csv")
        m15_path = os.path.join(DATA_DIR, f"{pair}_M15.csv")
        d1_path  = os.path.join(DATA_DIR, f"{pair}_D1.csv")
        if not os.path.exists(h1_path) or not os.path.exists(m15_path):
            print(f"Skipped {pair} - CSV not found")
            continue
        h1  = pd.read_csv(h1_path,  index_col=0, parse_dates=True)
        m15 = pd.read_csv(m15_path, index_col=0, parse_dates=True)
        if os.path.exists(d1_path):
            d1 = pd.read_csv(d1_path, index_col=0, parse_dates=True)
        else:
            d1 = h1.resample("D").agg({"open": "first", "high": "max",
                                        "low": "min", "close": "last"}).dropna()
        data[pair] = {"H1": h1, "M15": m15, "D1": d1}
        print(f"Loaded {pair}  H1:{len(h1)}  M15:{len(m15)}  D1:{len(d1)}")
    return data


def load_from_mt5(pairs):
    import MetaTrader5 as mt5
    from datetime import datetime
    from config import BACKTEST_START, BACKTEST_END, MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

    if not mt5.initialize():
        raise RuntimeError("MT5 initialize failed — make sure MT5 is open")
    if MT5_LOGIN and MT5_PASSWORD and MT5_SERVER:
        if not mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
            raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")

    def get_ohlc(symbol, timeframe):
        tf_map = {"H1": mt5.TIMEFRAME_H1, "M15": mt5.TIMEFRAME_M15, "D1": mt5.TIMEFRAME_D1}
        start = datetime.strptime(BACKTEST_START, "%Y-%m-%d")
        end   = datetime.strptime(BACKTEST_END,   "%Y-%m-%d")
        rates = mt5.copy_rates_range(symbol, tf_map[timeframe], start, end)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        return df[["open", "high", "low", "close"]]

    data = {}
    for pair in pairs:
        h1  = get_ohlc(pair, "H1")
        m15 = get_ohlc(pair, "M15")
        d1  = get_ohlc(pair, "D1")
        if h1 is not None and m15 is not None:
            data[pair] = {"H1": h1, "M15": m15, "D1": d1}
            print(f"Loaded {pair}")
        else:
            print(f"Skipped {pair} - no data")
    mt5.shutdown()
    return data


def load_all_pairs(pairs):
    if os.path.isdir(DATA_DIR) and any(f.endswith("_H1.csv") for f in os.listdir(DATA_DIR)):
        print("Loading from CSV files...")
        return load_from_csv(pairs)
    else:
        print("Loading data from MT5...")
        return load_from_mt5(pairs)
