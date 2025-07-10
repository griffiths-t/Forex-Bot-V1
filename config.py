import os

# === OANDA API credentials ===
OANDA_API_KEY = os.getenv("OANDA_API_KEY")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")
OANDA_URL = "https://api-fxpractice.oanda.com/v3"  # Change if using live account

# === Telegram Bot settings ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Use webhook (True) or polling (False) for Telegram updates
TELEGRAM_USE_WEBHOOK = True

# Webhook settings (used only if TELEGRAM_USE_WEBHOOK = True)
WEBHOOK_HOST = "https://forex-bot-m0qs.onrender.com"  # Replace with your Render URL
WEBHOOK_PATH = f"/webhook/{TELEGRAM_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = 8080  # Must match Flask app port

# === Trading Configuration ===
TRADING_INSTRUMENT = os.getenv("OANDA_INSTRUMENT", "GBP_USD")
TRADING_UNITS = int(os.getenv("TRADE_UNITS", 1000))
TRADING_PAUSED = False  # Can be toggled via Telegram /pause

# === Model & Training Settings ===
MODEL_PATH = "model.pkl"
CANDLE_COUNT = 1500
TIMEFRAME = "M15"

# === Compatibility Aliases ===
INSTRUMENT = TRADING_INSTRUMENT
TRADE_UNITS = TRADING_UNITS