PAIRS = [
    "AUDCAD", "AUDJPY", "AUDNZD", "AUDUSD", "CADJPY",
    "EURUSD", "EURAUD", "EURNZD", "GBPAUD", "GBPJPY",
    "GBPNZD", "GBPUSD", "USDCAD"
]

RANGE_MIN_PIPS = 20
RANGE_MAX_PIPS = 30
MAX_ACTIVE_SETUPS = 5

FIBO_ENTRY = 0.618   # entry at 61.8% from top of engulfing body (golden zone first line)
FIBO_SL_EXT = 0.786  # SL at -78.6% extension beyond the body

# London 07:00-16:00 UTC, NY 13:00-21:00 UTC — combined active window
SESSION_START_UTC = 7
SESSION_END_UTC = 21

TP1_RR = 2.0
TP2_RR = 4.0

MT5_LOGIN = 0        # your broker account number
MT5_PASSWORD = ""    # your broker password
MT5_SERVER = ""      # your broker server name e.g. "ICMarkets-Demo"
MT5_PATH = ""        # path to terminal64.exe e.g. "C:\\Program Files\\MetaTrader 5\\terminal64.exe"

BACKTEST_START = "2023-01-01"
BACKTEST_END = "2024-12-31"
