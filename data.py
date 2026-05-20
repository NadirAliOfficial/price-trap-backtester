import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from config import BACKTEST_START, BACKTEST_END


def yf_symbol(pair):
    return f"{pair}=X"


def fetch(symbol, interval, start=None, end=None, period=None):
    kwargs = dict(interval=interval, auto_adjust=True, progress=False)
    if period:
        kwargs["period"] = period
    else:
        kwargs["start"] = start
        kwargs["end"] = end
    df = yf.download(yf_symbol(symbol), **kwargs)
    if df.empty:
        return None

    # flatten multi-level columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0].lower() for col in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]

    df = df[["open", "high", "low", "close"]].dropna()
    df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
    return df


def load_all_pairs(pairs):
    now = datetime.utcnow()

    h1_start = (now - timedelta(days=700)).strftime("%Y-%m-%d")
    h1_end   = now.strftime("%Y-%m-%d")

    data = {}
    for pair in pairs:
        h1  = fetch(pair, "1h",  start=h1_start, end=h1_end)
        m15 = fetch(pair, "15m", period="60d")

        if h1 is None or m15 is None or h1.empty or m15.empty:
            print(f"Skipped {pair} - no data")
            continue

        # restrict H1 to the period where M15 is also available
        h1 = h1[h1.index >= m15.index[0]]

        data[pair] = {"H1": h1, "M15": m15}
        print(f"Loaded {pair}  H1:{len(h1)} bars  M15:{len(m15)} bars")

    return data
