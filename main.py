from data import load_all_pairs
from strategy import run_backtest
from report import generate
from config import PAIRS

all_trades = []

print("Loading data from MT5...")
data = load_all_pairs(PAIRS)

print("\nRunning backtest...")
for pair, tf_data in data.items():
    print(f"  Backtesting {pair}...")
    trades = run_backtest(pair, tf_data["H1"], tf_data["M15"])
    all_trades.extend(trades)
    print(f"  {pair}: {len(trades)} setups found")

generate(all_trades)
