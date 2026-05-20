# Price Trap Backtester

Backtests the Price Trap forex strategy across up to 20 pairs using live MT5 data.

**Strategy logic:**
- H1: detect 20 to 30 pip consolidation range
- Wait for H1 candle body close fully outside the range
- M15: find engulfing candle at the breakout level
- Draw Fibonacci on engulfing candle body only
- Entry at 78.6% golden zone
- Trade 1: TP at 1:2 RR
- Trade 2: TP at 1:4 RR, moves to breakeven after Trade 1 closes
- SL at 100% fib level

## Setup

1. Open MetaTrader 5 on your Windows machine and make sure it is logged in
2. Install dependencies:
```
pip install -r requirements.txt
```
3. Optionally edit `config.py` to change pairs, date range, or pip settings
4. Run:
```
python main.py
```

## Output

- Console summary: win rate, total RR, per pair breakdown
- `report.csv`: full trade log with entry time, pair, direction, result
