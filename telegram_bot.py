import config
import telegram
import pandas as pd
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)

BOT_TOKEN = config.TELEGRAM_TOKEN
CHAT_ID = config.TELEGRAM_CHAT_ID

# Store latest prediction for status report
last_prediction = {
    "direction": None,
    "confidence": None,
    "indicators": {}
}
last_retrain_time = None

def format_prediction():
    direction = last_prediction.get("direction")
    confidence = last_prediction.get("confidence")
    if direction is None:
        return "No prediction made yet."
    emoji = "🟢 Buy" if direction == 1 else "🔴 Sell"
    return f"{emoji} ({confidence:.2f})"

def format_market_status():
    from utils import is_market_open
    return "✅ Yes" if is_market_open() else "❌ No"

def send_text(message):
    bot = telegram.Bot(token=BOT_TOKEN)
    bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")

def send_trade_alert(direction, confidence, label, units):
    emoji = "🟢 Buy" if direction == 1 else "🔴 Sell"
    msg = (
        f"*ForexBot*\n"
        f"{emoji} *{label.upper()}* signal\n"
        f"Confidence: *{confidence:.2f}*\n"
        f"Units: *{units}*"
    )
    send_text(msg)

def setup_webhook():
    from telegram.ext import Application
    application = Application.builder().token(BOT_TOKEN).build()
    url = f"{config.PUBLIC_URL}/webhook/{BOT_TOKEN}"
    application.bot.set_webhook(url=url)

def handle_webhook(update_json):
    update = Update.de_json(update_json, telegram.Bot(BOT_TOKEN))
    context = None
    command = update.message.text

    if command == "/start":
        send_text("👋 Welcome! I am your Forex trading bot.")
    elif command == "/status":
        prediction = format_prediction()
        market_status = format_market_status()
        paused = "⏸️ Paused" if config.TRADING_PAUSED else "▶️ Active"
        retrain_time = last_retrain_time or "Not yet"
        send_text(
            "*📊 Bot Status*\n"
            f"• 🔄 Status: {paused}\n"
            f"• 🕒 Market Open: {market_status}\n"
            f"• 🧠 Last Retrain: `{retrain_time}`\n\n"
            "*🤖 Last Prediction*\n"
            f"• Direction: {prediction}"
        )
    elif command == "/retrain":
        from model import retrain_model
        try:
            retrain_model()
            global last_retrain_time
            last_retrain_time = datetime.utcnow()
            send_text("🧠 Retrain complete.")
        except Exception as e:
            send_text(f"❌ Retrain failed: {e}")
    elif command == "/pause":
        config.TRADING_PAUSED = True
        send_text("⏸️ Trading paused by user.")
    elif command == "/resume":
        config.TRADING_PAUSED = False
        send_text("▶️ Trading resumed by user.")
    elif command == "/trades":
        try:
            df = pd.read_csv("trade_log.csv")
            if df.empty:
                send_text("📭 No trades have been logged yet.")
                return
            last_5 = df.tail(5)
            lines = []
            for _, row in last_5.iterrows():
                time = row["timestamp"][:16].replace("T", " ")
                side = "🟢 Buy" if int(row["direction"]) == 1 else "🔴 Sell"
                conf = f"{row['confidence']:.2f}"
                lines.append(f"{time} | {side} | {conf}")
            msg = "*📄 Last 5 Trades:*\n" + "\n".join(lines)
            send_text(msg)
        except Exception as e:
            send_text(f"❌ Could not load trades: {e}")