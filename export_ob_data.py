import MetaTrader5 as mt5
import pandas as pd
import time
import os

DATA_DIR = "ob_data"
PAIRS = ["XAUUSD", "EURUSD", "US30"]


def connect():
    if not mt5.initialize():
        raise RuntimeError("MT5 initialize failed — make sure MT5 is open")


def get_m1(symbol):
    mt5.symbol_select(symbol, True)
    time.sleep(1)
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 150000)
    if rates is None or len(rates) == 0:
        print(f"  {symbol} M1 error: {mt5.last_error()}")
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    return df[["open", "high", "low", "close"]]


def get_d1(symbol):
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 500)
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


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    connect()

    available = {s.name for s in mt5.symbols_get()}

    print("ALL available symbols:")
    with open("symbols.txt", "w") as f:
        for s in mt5.symbols_get():
            print(" ", s.name)
            f.write(s.name + "\n")
    print("Saved to symbols.txt")

    print("\nExporting data...")
    for pair in PAIRS:
        if pair not in available:
            print(f"  {pair} not found in broker — update PAIRS list")
            continue

        m1 = get_m1(pair)
        if m1 is None:
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
    main()
