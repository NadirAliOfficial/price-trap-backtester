from data import load_all_pairs
from strategy import run_backtest
from report import generate
from config import PAIRS

print("Loading data from MT5...")
data = load_all_pairs(PAIRS)

print("\nRunning backtest WITHOUT D1 trend filter...")
trades_no_filter = []
for pair, tf_data in data.items():
    trades = run_backtest(pair, tf_data["H1"], tf_data["M15"],
                          tf_data.get("D1"), use_trend_filter=False)
    trades_no_filter.extend(trades)
    if trades:
        print(f"  {pair}: {len(trades)} setups")

print("\nRunning backtest WITH D1 trend filter...")
trades_filtered = []
for pair, tf_data in data.items():
    trades = run_backtest(pair, tf_data["H1"], tf_data["M15"],
                          tf_data.get("D1"), use_trend_filter=True)
    trades_filtered.extend(trades)
    if trades:
        print(f"  {pair}: {len(trades)} setups")

generate(trades_no_filter, output="report_no_filter.csv", label="Without D1 Filter")
generate(trades_filtered,  output="report_filtered.csv",  label="With D1 Filter")
