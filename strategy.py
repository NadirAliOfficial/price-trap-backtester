import pandas as pd
from config import RANGE_MIN_PIPS, RANGE_MAX_PIPS, FIBO_ENTRY, FIBO_SL, TP1_RR, TP2_RR, MAX_ACTIVE_SETUPS


def pip_size(symbol):
    return 0.01 if "JPY" in symbol else 0.0001


def detect_range(h1, i, pip):
    lookback = 10
    start = max(0, i - lookback)
    window = h1.iloc[start:i]
    high = window["high"].max()
    low = window["low"].min()
    spread = high - low
    min_range = RANGE_MIN_PIPS * pip
    max_range = RANGE_MAX_PIPS * pip
    if min_range <= spread <= max_range:
        return high, low
    return None, None


def is_breakout(candle, range_high, range_low):
    body_high = max(candle["open"], candle["close"])
    body_low = min(candle["open"], candle["close"])
    if body_low > range_high:
        return "up"
    if body_high < range_low:
        return "down"
    return None


def find_engulfing(m15, breakout_time, direction, range_high, range_low, pip):
    future = m15[m15.index > breakout_time].head(20)
    for i in range(1, len(future)):
        prev = future.iloc[i - 1]
        curr = future.iloc[i]
        if direction == "down":
            if (curr["close"] < curr["open"] and
                    curr["open"] > prev["open"] and
                    curr["close"] < prev["close"]):
                return curr, future.index[i]
        else:
            if (curr["close"] > curr["open"] and
                    curr["open"] < prev["open"] and
                    curr["close"] > prev["close"]):
                return curr, future.index[i]
    return None, None


def calc_fibo(candle, direction):
    body_high = max(candle["open"], candle["close"])
    body_low = min(candle["open"], candle["close"])
    body_size = body_high - body_low
    if direction == "down":
        entry = body_high - body_size * FIBO_ENTRY
        sl = body_high - body_size * FIBO_SL
        sl = body_high
    else:
        entry = body_low + body_size * FIBO_ENTRY
        sl = body_low
    return entry, sl


def simulate_trade(m15, entry_time, entry, sl, direction, pip):
    risk = abs(entry - sl)
    tp1 = entry + risk * TP1_RR if direction == "up" else entry - risk * TP1_RR
    tp2 = entry + risk * TP2_RR if direction == "up" else entry - risk * TP2_RR

    future = m15[m15.index > entry_time]
    trade1_closed = False
    trade2_result = None
    be_active = False

    for _, candle in future.iterrows():
        h = candle["high"]
        l = candle["low"]

        if not trade1_closed:
            if direction == "up":
                if l <= sl:
                    return {"t1": "loss", "t2": "loss", "rr": -1 + -1}
                if h >= tp1:
                    trade1_closed = True
                    be_active = True
            else:
                if h >= sl:
                    return {"t1": "loss", "t2": "loss", "rr": -1 + -1}
                if l <= tp1:
                    trade1_closed = True
                    be_active = True

        if trade1_closed:
            be = entry
            if direction == "up":
                if l <= be:
                    trade2_result = "be"
                    break
                if h >= tp2:
                    trade2_result = "win"
                    break
            else:
                if h >= be:
                    trade2_result = "be"
                    break
                if l <= tp2:
                    trade2_result = "win"
                    break

    if trade2_result is None:
        trade2_result = "open"

    rr = TP1_RR + (TP2_RR if trade2_result == "win" else 0)
    return {"t1": "win", "t2": trade2_result, "rr": rr}


def run_backtest(pair, h1, m15):
    pip = pip_size(pair)
    trades = []
    active = 0

    for i in range(10, len(h1)):
        if active >= MAX_ACTIVE_SETUPS:
            active = max(0, active - 1)
            continue

        candle = h1.iloc[i]
        range_high, range_low = detect_range(h1, i, pip)
        if range_high is None:
            continue

        direction = is_breakout(candle, range_high, range_low)
        if not direction:
            continue

        engulf, engulf_time = find_engulfing(m15, h1.index[i], direction, range_high, range_low, pip)
        if engulf is None:
            continue

        entry, sl = calc_fibo(engulf, direction)
        result = simulate_trade(m15, engulf_time, entry, sl, direction, pip)
        result["pair"] = pair
        result["time"] = engulf_time
        result["direction"] = direction
        trades.append(result)
        active += 1

    return trades
