# Price Trap Backtester

## Setup

1. Install dependencies:
```
pip install -r requirements.txt
```

2. Open `config.py` and fill in your MT5 login credentials:
```python
MT5_LOGIN = 123456
MT5_PASSWORD = "yourpassword"
MT5_SERVER = "YourBroker-Server"
```

3. Run:
```
python main.py
```

## Output

- Console summary: win rate, total RR, per pair breakdown
- `report.csv`: full trade log with entry time, pair, direction, result
