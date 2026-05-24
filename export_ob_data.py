import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import os

DATA_DIR = "ob_data"
PAIRS = ["XAUUSD", "EURUSD", "US30"]
START  = "2025-01-01"
END    = "2026-05-25"


def connect():
    if not mt5.initialize():
        raise RuntimeError("MT5 initialize failed — make sure MT5 is open")


def get_m1(symbol):
    start = datetime.strptime(START, "%Y-%m-%d")
    end   = datetime.strptime(END,   "%Y-%m-%d")
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, end)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    return df[["open", "high", "low", "close"]]


def resample_m3(m1):
    return m1.resample("3min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()


def get_d1(symbol):
    start = datetime.strptime("2024-01-01", "%Y-%m-%d")
    end   = datetime.strptime(END, "%Y-%m-%d")
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_D1, start, end)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    return df[["open", "high", "low", "close"]]


def list_symbols():
    connect()
    print("Available symbols matching XAU, GOLD, US30, DJ, DOW, EUR, NAS, SPX:")
    for s in mt5.symbols_get():
        if any(x in s.name.upper() for x in ["XAU","GOLD","US30","DJ","DOW","NAS","SPX"]):
            print(" ", s.name)
    mt5.shutdown()


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    connect()

    symbols = mt5.symbols_get()
    available = {s.name for s in symbols}
    print("Checking symbols...")

    for pair in PAIRS:
        if pair not in available:
            print(f"  {pair} not found — check broker symbol name")
            continue

        m1 = get_m1(pair)
        if m1 is None:
            print(f"  {pair} M1: no data")
            continue

        m3 = resample_m3(m1)
        d1 = get_d1(pair)

        m1.to_csv(os.path.join(DATA_DIR, f"{pair}_M1.csv"))
        m3.to_csv(os.path.join(DATA_DIR, f"{pair}_M3.csv"))
        if d1 is not None:
            d1.to_csv(os.path.join(DATA_DIR, f"{pair}_D1.csv"))

        print(f"  {pair}  M1:{len(m1)}  M3:{len(m3)}  D1:{len(d1) if d1 is not None else 0}")

    mt5.shutdown()
    print("\nDone.")


if __name__ == "__main__":
    list_symbols()
    main()
