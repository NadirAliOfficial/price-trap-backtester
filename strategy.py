import pandas as pd
from config import RANGE_MIN_PIPS, RANGE_MAX_PIPS, FIBO_ENTRY, TP1_RR, TP2_RR, MAX_ACTIVE_SETUPS

LIMIT_EXPIRY_CANDLES = 16  # cancel limit order if not filled within 16 x M15 candles (4 hours)
MIN_ENGULF_PIPS = 3        # engulfing candle body must be at least 3 pips
MIN_RANGE_CANDLES = 4      # range must contain at least 4 candles
RANGE_BODY_THRESHOLD = 0.6 # 60% of candles must have bodies inside the range


def pip_size(symbol):
    return 0.01 if "JPY" in symbol else 0.0001


def detect_range(h1, i, pip):
    lookback = 12
    start = max(0, i - lookback)
    window = h1.iloc[start:i]

    if len(window) < MIN_RANGE_CANDLES:
        return None, None

    high = window["high"].max()
    low = window["low"].min()
    spread = high - low
    min_range = RANGE_MIN_PIPS * pip
    max_range = RANGE_MAX_PIPS * pip

    if not (min_range <= spread <= max_range):
        return None, None

    # most candle bodies must sit inside the range
    inside = 0
    for _, c in window.iterrows():
        body_h = max(c["open"], c["close"])
        body_l = min(c["open"], c["close"])
        if body_l >= low and body_h <= high:
            inside += 1

    if inside / len(window) < RANGE_BODY_THRESHOLD:
        return None, None

    # must have candles touching both sides (genuine two-sided range, not a trend)
    near_high = sum(1 for _, c in window.iterrows() if c["high"] >= high - 3 * pip)
    near_low = sum(1 for _, c in window.iterrows() if c["low"] <= low + 3 * pip)
    if near_high < 1 or near_low < 1:
        return None, None

    return high, low


def is_breakout(candle, range_high, range_low):
    body_high = max(candle["open"], candle["close"])
    body_low = min(candle["open"], candle["close"])
    body_size = body_high - body_low
    if body_size == 0:
        return None
    # full body must close outside the range, not just wick
    if body_low > range_high:
        return "up"
    if body_high < range_low:
        return "down"
    return None


def find_engulfing(m15, breakout_time, direction, range_high, range_low, pip):
    # only look at candles within 3 hours of the breakout
    future = m15[m15.index > breakout_time].head(12)
    min_body = MIN_ENGULF_PIPS * pip

    for i in range(1, len(future)):
        prev = future.iloc[i - 1]
        curr = future.iloc[i]

        curr_body_h = max(curr["open"], curr["close"])
        curr_body_l = min(curr["open"], curr["close"])
        prev_body_h = max(prev["open"], prev["close"])
        prev_body_l = min(prev["open"], prev["close"])
        curr_body = curr_body_h - curr_body_l
        prev_body = prev_body_h - prev_body_l

        if curr_body < min_body:
            continue

        # engulf: current body must fully contain previous body
        if curr_body <= prev_body:
            continue

        if direction == "down":
            # bearish engulfing: opens above prev body high, closes below prev body low
            if (curr["close"] < curr["open"] and
                    curr["open"] >= prev_body_h and
                    curr["close"] <= prev_body_l):
                return curr, future.index[i]
        else:
            # bullish engulfing: opens below prev body low, closes above prev body high
            if (curr["close"] > curr["open"] and
                    curr["open"] <= prev_body_l and
                    curr["close"] >= prev_body_h):
                return curr, future.index[i]

    return None, None


def calc_fibo(candle, direction, pip):
    body_high = max(candle["open"], candle["close"])
    body_low = min(candle["open"], candle["close"])
    body_size = body_high - body_low

    if direction == "down":
        # price retraces UP into the bearish engulf body — sell limit at 78.6% retracement
        entry = body_low + body_size * FIBO_ENTRY
        sl = body_high + body_size * 0.786  # -78.6% extension above body
    else:
        # price retraces DOWN into the bullish engulf body — buy limit at 78.6% retracement
        entry = body_high - body_size * FIBO_ENTRY
        sl = body_low - body_size * 0.786   # -78.6% extension below body

    return entry, sl


def simulate_trade(m15, engulf_time, entry, sl, direction, pip):
    risk = abs(entry - sl)
    if risk == 0:
        return None

    tp1 = entry - risk * TP1_RR if direction == "down" else entry + risk * TP1_RR
    tp2 = entry - risk * TP2_RR if direction == "down" else entry + risk * TP2_RR

    future = m15[m15.index > engulf_time]
    filled = False
    fill_idx = 0

    # wait for price to retrace to the limit order level
    for idx, (ts, candle) in enumerate(future.iterrows()):
        if idx >= LIMIT_EXPIRY_CANDLES:
            return None  # limit expired, no trade
        h, l = candle["high"], candle["low"]
        if direction == "down" and h >= entry:
            filled = True
            fill_idx = idx
            break
        if direction == "up" and l <= entry:
            filled = True
            fill_idx = idx
            break

    if not filled:
        return None

    # simulate from fill point
    trade1_closed = False
    trade2_result = None
    remaining = future.iloc[fill_idx:]

    for _, candle in remaining.iterrows():
        h, l = candle["high"], candle["low"]

        if not trade1_closed:
            if direction == "down":
                if h >= sl:
                    return {"t1": "loss", "t2": "loss", "rr": -2.0}
                if l <= tp1:
                    trade1_closed = True
            else:
                if l <= sl:
                    return {"t1": "loss", "t2": "loss", "rr": -2.0}
                if h >= tp1:
                    trade1_closed = True

        if trade1_closed:
            if direction == "down":
                if h >= entry:
                    trade2_result = "be"
                    break
                if l <= tp2:
                    trade2_result = "win"
                    break
            else:
                if l <= entry:
                    trade2_result = "be"
                    break
                if h >= tp2:
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

    for i in range(12, len(h1)):
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

        entry, sl = calc_fibo(engulf, direction, pip)
        result = simulate_trade(m15, engulf_time, entry, sl, direction, pip)
        if result is None:
            continue  # limit never filled or risk was zero

        result["pair"] = pair
        result["time"] = engulf_time
        result["direction"] = direction
        trades.append(result)
        active += 1

    return trades
