# Price Trap Backtester

A complete backtesting suite and MetaTrader 5 Expert Advisor for the Price Trap forex strategy — an order-block and liquidity-trap based approach targeting high-probability reversals.

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white)
![MT5](https://img.shields.io/badge/MetaTrader5-007bff?style=flat)

## Strategy Logic

The Price Trap strategy identifies setups where price:
1. Sweeps a key liquidity level (stops above/below a swing)
2. Returns into an order block (institutional demand/supply zone)
3. Confirms with a displacement candle

Entry triggers on the close of the confirmation candle. Stop is placed beyond the liquidity sweep candle. Target is the next opposing liquidity level.

## Backtester Modules

| File                          | Purpose                                         |
|-------------------------------|-------------------------------------------------|
| `main.py`                     | Run full backtest                               |
| `ob_backtester.py`            | Order block detection and backtest engine       |
| `backtester/strategy.py`      | Signal generation and trade logic               |
| `backtester/data.py`          | MT5 / CSV historical data loader               |
| `backtester/report.py`        | Performance metrics (win rate, RR, drawdown)   |
| `backtester/generate_report.py` | HTML report generation                        |
| `export_data.py`              | Export MT5 data to CSV                         |

## Setup

```bash
pip install MetaTrader5 pandas numpy matplotlib
```

Run backtest:

```bash
python main.py
```

Export results:

```bash
python backtester/generate_report.py
```

## Output Metrics

- Win rate, loss rate, breakeven rate
- Average R:R ratio
- Max drawdown
- Equity curve chart (HTML report)

## License

MIT
<!-- updated: 2026-06-13 -->
