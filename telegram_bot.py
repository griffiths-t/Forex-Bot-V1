# telegram_bot.py

import config
import logging
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext
from datetime import datetime
from utils import is_market_open, get_equity, format_gbp
from broker import get_open_trades
from trade_logger import get_trade_summary
from model import retrain_model, backtest_model

# === Global State ===
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
    retrain_str = last_retrain_time.strftime('%Y-%m-%d %H:%M:%S UTC') if last_retrain_time else "Never"

    dir_str = "🟢 Buy" if direction == 1 else "🔴 Sell" if direction == 0 else "❓ Unknown"
    conf_str = f"{confidence:.2f}" if confidence is not None else "N/A"
    paused_str = "⏸️ Paused" if TRADING_PAUSED else "▶️ Active"
    market_str = "🟢 Yes" if is_market_open() else "🔴 No"

    open_trades = get_open_trades()
    trade_count = len(open_trades)
    total_value = sum(abs(float(t["currentUnits"])) for t in open_trades)
    total_gbp = format_gbp(total_value)

    msg = (
        f"📊 *Bot Status*\n\n"
        f"🔄 *Bot:* {paused_str}\n"
        f"🕒 *Market Open:* {market_str}\n"
        f"📈 *Open Trades:* {trade_count}\n"
        f"💷 *Total Position:* {total_gbp}\n"
        f"🧠 *Last Retrain:* {retrain_str}\n"
        f"🤖 *Last Prediction:* {dir_str} (conf: {conf_str})"
    )
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
            lines = f.readlines()[-5:]
            if not lines:
                update.message.reply_text("No trades logged yet.")
                return
            msg = "*Recent Trades:*\n"
            for line in lines:
                msg += f"`{line.strip()}`\n"
            update.message.reply_text(msg, parse_mode="Markdown")
    except FileNotFoundError:
        update.message.reply_text("Trade log not found.")

def stats(update: Update, context: CallbackContext):
    try:
        summary = get_trade_summary()
        msg = (
            f"📈 *Trading Stats*\n\n"
            f"📊 *Total Trades:* {summary['total_trades']}\n"
            f"✅ *Wins:* {summary['wins']}\n"
            f"❌ *Losses:* {summary['losses']}\n"
            f"🔥 *Win Rate:* {summary['win_rate']:.2f}%\n"
            f"💰 *Net P/L:* {format_gbp(summary['total_pl'])}"
        )
        update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"❌ Stats error: {e}")

def backtest(update: Update, context: CallbackContext):
    try:
        update.message.reply_text("🔍 Running backtest, please wait...")
        report = backtest_model()
        update.message.reply_text(f"📊 *Backtest Results:*\n\n{report}", parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"❌ Backtest failed: {e}")

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
    dispatcher.add_handler(CommandHandler("stats", stats))
    dispatcher.add_handler(CommandHandler("backtest", backtest))

    @app.route(f"/webhook/{config.TELEGRAM_TOKEN}", methods=["POST"])
    def webhook():
        dispatcher.process_update(Update.de_json(request.get_json(force=True), bot))
        return "ok"

    app.run(host="0.0.0.0", port=config.PORT)

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
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("backtest", backtest))

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
    msg = (
        f"*Trade Executed*\n"
        f"{emoji} {signal_type.capitalize()} {abs(units)} units\n"
        f"*Confidence:* `{confidence:.2f}`"
    )
    send_text(msg)