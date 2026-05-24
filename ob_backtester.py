import pandas as pd
import numpy as np

OB_DATA_DIR  = "ob_data"
PAIRS        = ["XAUUSD", "EURUSD", "US30"]

DOJI_BODY_PCT    = 0.20   # body/range < this = doji (stricter)
MIN_IMPULSE_BODY = 0.70   # body/range > this = impulsive (stricter)
MIN_IMPULSE_PCT  = 0.0003 # impulse body must be >= 0.03% of price
MIN_OB_SIZE_PCT  = 0.0001 # OB zone must be >= 0.01% of price
EMA_PERIOD       = 200
BB_PERIOD        = 20
BB_STD           = 2.0
TP1_RR           = 1.0
TP2_RR           = 2.0
OB_EXPIRY_M1     = 30


def load_pair(pair):
    m1 = pd.read_csv(f"{OB_DATA_DIR}/{pair}_M1.csv", index_col=0, parse_dates=True)
    m3 = pd.read_csv(f"{OB_DATA_DIR}/{pair}_M3.csv", index_col=0, parse_dates=True)
    return m1, m3


def add_indicators(df):
    df = df.copy()
    df["ema200"]   = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    df["bb_mid"]   = df["close"].rolling(BB_PERIOD).mean()
    df["bb_std"]   = df["close"].rolling(BB_PERIOD).std()
    df["bb_upper"] = df["bb_mid"] + BB_STD * df["bb_std"]
    df["bb_lower"] = df["bb_mid"] - BB_STD * df["bb_std"]
    return df


def detect_obs(m3):
    obs = []
    for i in range(2, len(m3) - 1):
        doji = m3.iloc[i]
        nxt  = m3.iloc[i + 1]
        prev = m3.iloc[i - 1]

        d_range = doji["high"] - doji["low"]
        if d_range == 0:
            continue
        d_body = abs(doji["close"] - doji["open"])
        if d_body / d_range > DOJI_BODY_PCT:
            continue

        n_range = nxt["high"] - nxt["low"]
        if n_range == 0:
            continue
        n_body = abs(nxt["close"] - nxt["open"])
        if n_body / n_range < MIN_IMPULSE_BODY:
            continue

        direction = -1 if nxt["close"] < nxt["open"] else 1

        ema = doji["ema200"]
        if pd.isna(ema):
            continue
        if direction == -1 and doji["close"] > ema:
            continue
        if direction ==  1 and doji["close"] < ema:
            continue

        # imbalance: impulse close breaks beyond previous candle's extreme
        if direction == -1 and nxt["close"] >= prev["low"]:
            continue
        if direction ==  1 and nxt["close"] <= prev["high"]:
            continue

        # minimum impulse size
        n_body_size = abs(nxt["close"] - nxt["open"])
        if n_body_size < nxt["close"] * MIN_IMPULSE_PCT:
            continue

        ob_high = max(doji["open"], doji["close"])
        ob_low  = min(doji["open"], doji["close"])
        if ob_high == ob_low:
            ob_high = doji["high"]
            ob_low  = doji["low"]

        # minimum OB zone size
        if (ob_high - ob_low) < ob_high * MIN_OB_SIZE_PCT:
            continue

        obs.append({
            "time":      m3.index[i + 1],
            "direction": direction,
            "ob_high":   ob_high,
            "ob_low":    ob_low,
            "sl_ref":    doji["high"] if direction == -1 else doji["low"],
        })
    return obs


def simulate_trade(m1, ob, fill_idx):
    direction = ob["direction"]
    entry = ob["ob_high"] if direction == -1 else ob["ob_low"]
    sl    = ob["sl_ref"] + (ob["ob_high"] - ob["ob_low"]) * 0.1
    sl    = ob["sl_ref"] if direction == -1 else ob["sl_ref"]
    # give SL a buffer beyond doji extreme
    sl = (ob["sl_ref"] + (ob["ob_high"] - ob["ob_low"]) * 0.5) if direction == -1 \
         else (ob["sl_ref"] - (ob["ob_high"] - ob["ob_low"]) * 0.5)

    risk = abs(entry - sl)
    if risk == 0:
        return None

    tp1 = entry - risk * TP1_RR if direction == -1 else entry + risk * TP1_RR
    tp2 = entry - risk * TP2_RR if direction == -1 else entry + risk * TP2_RR

    t1_done = False
    for _, c in m1.iloc[fill_idx:].iterrows():
        h, l = c["high"], c["low"]
        if not t1_done:
            if direction == -1:
                if h >= sl:  return {"t1": "loss", "t2": "loss", "rr": -2.0}
                if l <= tp1: t1_done = True
            else:
                if l <= sl:  return {"t1": "loss", "t2": "loss", "rr": -2.0}
                if h >= tp1: t1_done = True
        if t1_done:
            if direction == -1:
                if h >= entry: return {"t1": "win", "t2": "be",  "rr": TP1_RR}
                if l <= tp2:   return {"t1": "win", "t2": "win", "rr": TP1_RR + TP2_RR}
            else:
                if l <= entry: return {"t1": "win", "t2": "be",  "rr": TP1_RR}
                if h >= tp2:   return {"t1": "win", "t2": "win", "rr": TP1_RR + TP2_RR}

    return {"t1": "win" if t1_done else "open", "t2": "open",
            "rr": TP1_RR if t1_done else 0}


def backtest_pair(pair):
    m1, m3 = load_pair(pair)
    m3 = add_indicators(m3)
    m1 = add_indicators(m1)
    obs = detect_obs(m3)
    trades = []

    for ob in obs:
        candidates = m1[m1.index > ob["time"]].iloc[:OB_EXPIRY_M1]
        for ts, candle in candidates.iterrows():
            h, l = candle["high"], candle["low"]
            bb_u = candle["bb_upper"]
            bb_l = candle["bb_lower"]
            if pd.isna(bb_u) or pd.isna(bb_l):
                continue

            if ob["direction"] == -1:
                if h < ob["ob_high"]: continue
                # BB upper must be inside OB zone (price at upper BB = at OB resistance)
                if not (ob["ob_low"] <= bb_u <= ob["ob_high"] * 1.005): continue
            else:
                if l > ob["ob_low"]: continue
                # BB lower must be inside OB zone (price at lower BB = at OB support)
                if not (ob["ob_low"] * 0.995 <= bb_l <= ob["ob_high"]): continue

            fill_idx = m1.index.get_loc(ts)
            result = simulate_trade(m1, ob, fill_idx)
            if result:
                result.update({"pair": pair, "time": ts, "dir": ob["direction"]})
                trades.append(result)
            break

    return trades


def report(all_trades):
    if not all_trades:
        print("No trades found — parameters may be too strict.")
        return
    df = pd.DataFrame(all_trades)
    total = len(df)
    wins  = len(df[df["t1"] == "win"])
    loss  = len(df[df["t1"] == "loss"])
    wr    = wins / total * 100
    print(f"\n{'='*50}")
    print(f"OB Strategy Backtest  ({df['time'].min().date()} to {df['time'].max().date()})")
    print(f"{'='*50}")
    print(f"Total trades : {total}")
    print(f"Win rate     : {wr:.1f}%  ({wins}W / {loss}L)")
    print(f"Avg RR       : {df['rr'].mean():.2f}R")
    print(f"Total RR     : {df['rr'].sum():.2f}R")
    print(f"\nBy pair:")
    for p in df["pair"].unique():
        sub = df[df["pair"] == p]
        w   = len(sub[sub["t1"] == "win"])
        print(f"  {p}: {len(sub)} trades  {w}/{len(sub)} wins  "
              f"({w/len(sub)*100:.0f}%)  {sub['rr'].sum():.1f}R")
    df.to_csv("ob_report.csv", index=False)
    print(f"\nSaved to ob_report.csv")


if __name__ == "__main__":
    all_trades = []
    for pair in PAIRS:
        print(f"Scanning {pair}...")
        t = backtest_pair(pair)
        print(f"  {len(t)} trades")
        all_trades.extend(t)
    report(all_trades)
