# Price Trap EA — Forex Strategy Backtester & Expert Advisor

A complete backtesting suite and live MetaTrader 5 Expert Advisor for the **Price Trap** forex strategy.

---

## Strategy Logic

1. **Range Detection** — Find a 20–30 pip consolidation zone on H1 (minimum 4 candles, 60% of bodies inside, both sides tested)
2. **Breakout** — H1 candle body closes fully outside the range
3. **Engulfing** — M15 engulfing candle forms in the breakout direction within 12 M15 bars
4. **Entry** — Fibonacci limit order at 61.8% retracement of the engulfing candle body
5. **Stop Loss** — 78.6% extension beyond the engulfing candle body
6. **Take Profit 1** — 1:2 RR (half position closes here, SL moves to breakeven on remaining)
7. **Take Profit 2** — 1:4 RR
8. **Filters** — D1 EMA50 trend filter, session filter (07:00–21:00 UTC), news filter, weekend filter

---

## Backtest Results

**Python Backtest — 2023 to 2024 — 6 pairs with D1 trend filter**

| Metric | Result |
|---|---|
| Pairs tested | EURUSD, AUDCAD, AUDUSD, CADJPY, USDCAD, AUDNZD |
| Direction | With D1 EMA50 trend filter |
| Max drawdown | ~6R at 1% risk = 6% |

**MT5 Strategy Tester — EURUSD — 2020 to 2024**

| Metric | Result |
|---|---|
| Net Profit | +8% on $100,000 |
| Win Rate | 75% |
| Profit Factor | 1453 |
| Max Drawdown | 2.94% |
| Sharpe Ratio | 2.54 |
| History Quality | 99% |

---

## Recommended Pairs

EURUSD · AUDCAD · AUDUSD · CADJPY · USDCAD · AUDNZD

---

## Repository Structure

```
price-trap-backtester/
├── ea/
│   ├── PriceTrapEA.mq5     # MetaTrader 5 Expert Advisor
│   └── PriceTrapEA.set     # Optimised preset file
├── data/                   # CSV price data (H1, M15, D1 per pair)
├── config.py               # Pairs, risk settings, date range
├── strategy.py             # Core strategy logic
├── data.py                 # Data loader (CSV or MT5)
├── main.py                 # Run backtest
├── report.py               # Console report output
├── generate_report.py      # HTML report generator
└── export_data.py          # Export data from MT5 on Windows VPS
```

---

## Python Backtester Setup

```bash
pip install -r requirements.txt
python main.py
```

Loads CSV files from `data/` if present, otherwise pulls from MT5 directly.

---

## EA Installation (MetaTrader 5)

1. Copy `ea/PriceTrapEA.mq5` into `MT5 → MQL5 → Experts`
2. Compile in MetaEditor (F7) — should show 0 errors
3. Attach to a chart for each pair
4. In the Inputs tab click **Load** and select `ea/PriceTrapEA.set`
5. Enable **Algo Trading** in the toolbar

Run one chart per pair. All settings are pre-configured in the preset file.

---

## Key EA Settings

| Parameter | Default | Description |
|---|---|---|
| RiskPercent | 1.0 | % risk per leg (2 legs = 2% total per setup) |
| MaxActiveSetups | 5 | Maximum concurrent setups |
| UseTrendFilter | true | Only trade with D1 EMA50 trend |
| UseNewsFilter | true | Block 30 min around high-impact news |
| UseWeekendFilter | true | Close all positions before weekend |
| SessionStartUTC | 7 | London open |
| SessionEndUTC | 21 | NY close |
<!-- updated: 2023-05-06-r01 -->
