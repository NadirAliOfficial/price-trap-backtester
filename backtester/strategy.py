import pandas as pd
from backtester.config import (RANGE_MIN_PIPS, RANGE_MAX_PIPS, FIBO_ENTRY, FIBO_SL_EXT,
                               TP1_RR, TP2_RR, MAX_ACTIVE_SETUPS, SESSION_START_UTC, SESSION_END_UTC)

LIMIT_EXPIRY_CANDLES = 16
MIN_ENGULF_PIPS      = 3
MIN_RANGE_CANDLES    = 4
RANGE_BODY_THRESHOLD = 0.6


def pip_size(symbol):
    return 0.01 if "JPY" in symbol else 0.0001


def in_session(ts):
    return SESSION_START_UTC <= ts.hour < SESSION_END_UTC


def detect_range(h1, i, pip):
    lookback = 12
    start    = max(0, i - lookback)
    window   = h1.iloc[start:i]
    if len(window) < MIN_RANGE_CANDLES:
        return None, None
    high   = window["high"].max()
    low    = window["low"].min()
    spread = high - low
    if not (RANGE_MIN_PIPS * pip <= spread <= RANGE_MAX_PIPS * pip):
        return None, None
    inside = sum(1 for _, c in window.iterrows()
                 if min(c["open"], c["close"]) >= low and max(c["open"], c["close"]) <= high)
    if inside / len(window) < RANGE_BODY_THRESHOLD:
        return None, None
    near_high = sum(1 for _, c in window.iterrows() if c["high"] >= high - 3 * pip)
    near_low  = sum(1 for _, c in window.iterrows() if c["low"]  <= low  + 3 * pip)
    if near_high < 1 or near_low < 1:
        return None, None
    return high, low


def is_breakout(candle, range_high, range_low):
    body_high = max(candle["open"], candle["close"])
    body_low  = min(candle["open"], candle["close"])
    if body_high == body_low:
        return None
    if body_low  > range_high:
        return "up"
    if body_high < range_low:
        return "down"
    return None


def find_engulfing(m15, breakout_time, direction, pip):
    future   = m15[m15.index > breakout_time].head(12)
    min_body = MIN_ENGULF_PIPS * pip
    for i in range(1, len(future)):
        prev = future.iloc[i - 1]
        curr = future.iloc[i]
        curr_body_h = max(curr["open"], curr["close"])
        curr_body_l = min(curr["open"], curr["close"])
        prev_body_h = max(prev["open"], prev["close"])
        prev_body_l = min(prev["open"], prev["close"])
        curr_body   = curr_body_h - curr_body_l
        if curr_body < min_body:
            continue
        if direction == "down":
            if (curr["close"] < curr["open"] and
                    curr["close"] < prev_body_l and
                    curr_body > (prev_body_h - prev_body_l)):
                return curr, future.index[i]
        else:
            if (curr["close"] > curr["open"] and
                    curr["close"] > prev_body_h and
                    curr_body > (prev_body_h - prev_body_l)):
                return curr, future.index[i]
    return None, None


def calc_fibo(candle, direction):
    body_high = max(candle["open"], candle["close"])
    body_low  = min(candle["open"], candle["close"])
    body_size = body_high - body_low
    if body_size == 0:
        return None, None
    if direction == "down":
        entry = body_high - FIBO_ENTRY * body_size
        sl    = body_high + FIBO_SL_EXT * body_size
    else:
        entry = body_low + FIBO_ENTRY * body_size
        sl    = body_low - FIBO_SL_EXT * body_size
    return entry, sl


def simulate_trade(m15, engulf_time, entry, sl, direction):
    risk = abs(entry - sl)
    if risk == 0:
        return None
    tp1 = entry - risk * TP1_RR if direction == "down" else entry + risk * TP1_RR
    tp2 = entry - risk * TP2_RR if direction == "down" else entry + risk * TP2_RR

    future = m15[m15.index > engulf_time]
    filled = False
    fill_idx = 0
    for idx, (_, candle) in enumerate(future.iterrows()):
        if idx >= LIMIT_EXPIRY_CANDLES:
            return None
        h, l = candle["high"], candle["low"]
        if direction == "down" and h >= entry:
            filled = True; fill_idx = idx; break
        if direction == "up"   and l <= entry:
            filled = True; fill_idx = idx; break
    if not filled:
        return None

    trade1_closed = False
    trade2_result = None
    for _, candle in future.iloc[fill_idx:].iterrows():
        h, l = candle["high"], candle["low"]
        if not trade1_closed:
            if direction == "down":
                if h >= sl:    return {"t1": "loss", "t2": "loss", "rr": -2.0}
                if l <= tp1:   trade1_closed = True
            else:
                if l <= sl:    return {"t1": "loss", "t2": "loss", "rr": -2.0}
                if h >= tp1:   trade1_closed = True
        if trade1_closed:
            if direction == "down":
                if h >= entry: trade2_result = "be";  break
                if l <= tp2:   trade2_result = "win"; break
            else:
                if l <= entry: trade2_result = "be";  break
                if h >= tp2:   trade2_result = "win"; break

    if trade2_result is None:
        trade2_result = "open"
    rr = TP1_RR + (TP2_RR if trade2_result == "win" else 0)
    return {"t1": "win", "t2": trade2_result, "rr": rr}


def d1_trend(d1, ts):
    if d1 is None:
        return None
    past = d1[d1.index < ts]
    if len(past) < 50:
        return None
    close = past["close"].iloc[-1]
    ema50 = past["close"].ewm(span=50, adjust=False).mean().iloc[-1]
    return "up" if close > ema50 else "down"


def run_backtest(pair, h1, m15, d1=None, use_trend_filter=True):
    pip    = pip_size(pair)
    trades = []
    active = 0

    for i in range(12, len(h1)):
        if active >= MAX_ACTIVE_SETUPS:
            active = max(0, active - 1)
            continue
        ts = h1.index[i]
        if not in_session(ts):
            continue
        candle = h1.iloc[i]
        range_high, range_low = detect_range(h1, i, pip)
        if range_high is None:
            continue
        direction = is_breakout(candle, range_high, range_low)
        if not direction:
            continue
        if use_trend_filter:
            trend = d1_trend(d1, ts)
            if trend is not None and trend != direction:
                continue
        engulf, engulf_time = find_engulfing(m15, ts, direction, pip)
        if engulf is None:
            continue
        entry, sl = calc_fibo(engulf, direction)
        if entry is None:
            continue
        result = simulate_trade(m15, engulf_time, entry, sl, direction)
        if result is None:
            continue
        result["pair"]      = pair
        result["time"]      = engulf_time
        result["direction"] = direction
        trades.append(result)
        active += 1

    return trades
