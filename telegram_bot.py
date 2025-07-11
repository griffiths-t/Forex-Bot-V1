import config
import logging
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext
from datetime import datetime

# Track bot state and metrics
TRADING_PAUSED = False
last_prediction = {"direction": None, "confidence": None, "indicators": {}}
last_retrain_time = None
trade_log = []

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
bot = Bot(token=config.TELEGRAM_TOKEN)

# === Command Handlers ===

def start(update: Update, context: CallbackContext):
    update.message.reply_text("👋 Bot is online and ready.")

def status(update: Update, context: CallbackContext):
    global last_prediction, last_retrain_time

    direction = last_prediction.get("direction")
    confidence = last_prediction.get("confidence")
    indicators = last_prediction.get("indicators", {})

    dir_str = "🟢 Buy" if direction == 1 else "🔴 Sell" if direction == 0 else "❓ Unknown"
    confidence_str = f"{confidence:.2f}" if isinstance(confidence, (float, int)) else "N/A"
    retrain_str = last_retrain_time.strftime('%Y-%m-%d %H:%M:%S UTC') if last_retrain_time else "Never"

    msg = (
        f"📊 *Bot Status*\n\n"
        f"*Prediction:* {dir_str}\n"
        f"*Confidence:* `{confidence_str}`\n"
        f"*Indicators:*\n"
    )

    if indicators:
        for k, v in indicators.items():
            if isinstance(v, (float, int)):
                msg += f"`{k}`: `{v:.2f}`\n"
            else:
                msg += f"`{k}`: `{v}`\n"
    else:
        msg += "`No indicators yet.`\n"

    msg += f"\n*Retrained:* {retrain_str}"
    update.message.reply_text(msg, parse_mode="Markdown")

def pause(update: Update, context: CallbackContext):
    global TRADING_PAUSED
    TRADING_PAUSED = True
    update.message.reply_text("⏸️ Trading paused.")

def resume(update: Update, context: CallbackContext):
    global TRADING_PAUSED
    TRADING_PAUSED = False
    update.message.reply_text("▶️ Trading resumed.")

def retrain(update: Update, context: CallbackContext):
    from model import retrain_model
    global last_retrain_time

    try:
        retrain_model()
        last_retrain_time = datetime.utcnow()
        update.message.reply_text("🧠 Model retrained.")
    except Exception as e:
        update.message.reply_text(f"❌ Retrain failed: {e}")

def trades(update: Update, context: CallbackContext):
    try:
        with open("trade_log.csv", "r") as f:
            lines = f.readlines()

            if not lines:
                update.message.reply_text("No trades logged yet.")
                return

            last_lines = lines[-5:]
            msg = "*Recent Trades:*\n"
            for line in last_lines:
                msg += f"`{line.strip()}`\n"
            update.message.reply_text(msg, parse_mode="Markdown")
    except FileNotFoundError:
        update.message.reply_text("📭 Trade log not found.")
    except Exception as e:
        update.message.reply_text(f"❌ Failed to read trades: {e}")

# === Webhook Setup ===

def setup_webhook():
    from telegram.ext import Dispatcher
    from flask import Flask, request

    app = Flask(__name__)
    updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("status", status))
    dispatcher.add_handler(CommandHandler("pause", pause))
    dispatcher.add_handler(CommandHandler("resume", resume))
    dispatcher.add_handler(CommandHandler("retrain", retrain))
    dispatcher.add_handler(CommandHandler("trades", trades))

    @app.route(f"/webhook/{config.TELEGRAM_TOKEN}", methods=["POST"])
    def webhook():
        dispatcher.process_update(Update.de_json(request.get_json(force=True), bot))
        return "ok"

    app.run(host='0.0.0.0', port=config.PORT)

# === Polling Setup ===

def start_polling():
    updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("pause", pause))
    dp.add_handler(CommandHandler("resume", resume))
    dp.add_handler(CommandHandler("retrain", retrain))
    dp.add_handler(CommandHandler("trades", trades))

    updater.start_polling()
    updater.idle()

# === Text Sending ===

def send_text(msg):
    try:
        bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        print(f"[Telegram] Send failed: {e}")

def send_trade_alert(direction, confidence, signal_type, units):
    emoji = "🟢 Buy" if direction == 1 else "🔴 Sell"
    confidence_str = f"{confidence:.2f}" if isinstance(confidence, (float, int)) else "N/A"
    msg = (
        f"*Trade Executed*\n"
        f"{emoji} {signal_type.capitalize()} {abs(units)} units\n"
        f"*Confidence:* `{confidence_str}`"
    )
    send_text(msg)