import pandas as pd


def generate(trades, output="report.csv"):
    df = pd.DataFrame(trades)
    df.to_csv(output, index=False)

    total = len(df)
    wins = len(df[df["t1"] == "win"])
    losses = len(df[df["t1"] == "loss"])
    win_rate = (wins / total * 100) if total > 0 else 0
    total_rr = df["rr"].sum()

    print("\n===== BACKTEST REPORT =====")
    print(f"Total trades   : {total}")
    print(f"Wins           : {wins}")
    print(f"Losses         : {losses}")
    print(f"Win rate       : {win_rate:.1f}%")
    print(f"Total RR       : {total_rr:.2f}")
    print(f"Avg RR/trade   : {total_rr / total:.2f}" if total > 0 else "")
    print(f"\nFull log saved : {output}")

    by_pair = df.groupby("pair")["rr"].sum().sort_values(ascending=False)
    print("\nPerformance by pair:")
    for pair, rr in by_pair.items():
        print(f"  {pair:<10} {rr:+.1f}")
