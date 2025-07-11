# telegram_bot.py
import config
import logging
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext
from datetime import datetime
from utils import is_market_open, format_gbp, get_equity
from broker import get_open_trades, get_current_price, calculate_dynamic_units
from trade_logger import get_trade_summary
from model import retrain_model, backtest_model

# === State Tracking ===
TRADING_PAUSED = False
last_prediction = {
    "direction": None,
    "confidence": None,
    "indicators": {},
    "timestamp": None
}
last_retrain_time = None

# Logging & Bot Init
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
bot = Bot(token=config.TELEGRAM_TOKEN)

# === Command Handlers ===

def start(update: Update, context: CallbackContext):
    update.message.reply_text("👋 Bot is online and ready.")

def status(update: Update, context: CallbackContext):
    global last_prediction, last_retrain_time
    direction = last_prediction.get("direction")
    confidence = last_prediction.get("confidence")
    timestamp = last_prediction.get("timestamp")
    retrain_str = last_retrain_time.strftime('%Y-%m-%d %H:%M:%S UTC') if last_retrain_time else "Never"

    if direction == 1:
        dir_str = "🟢 Buy"
    elif direction == 0:
        dir_str = "🔴 Sell"
    elif direction is None:
        dir_str = "⚪ Hold"
    else:
        dir_str = "❓ Unknown"

    if confidence is not None:
        conf_str = f"{confidence:.2f}"
        conf_status = "✅ trade triggered" if confidence >= 0.6 else "🔻 below threshold"
    else:
        conf_str = "N/A"
        conf_status = "N/A"

    pred_time = timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') if timestamp else "Never"
    paused_str = "⏸️ Paused" if TRADING_PAUSED else "▶️ Active"
    market_str = "🟢 Yes" if is_market_open() else "🔴 No"

    open_trades = get_open_trades()
    trade_count = len(open_trades)
    total_value = sum(abs(float(t["currentUnits"])) for t in open_trades)
    total_gbp = format_gbp(total_value)

    try:
        price = get_current_price(config.TRADING_INSTRUMENT)
        equity = get_equity()
        units = calculate_dynamic_units(price, equity)
        units_str = f"{units:,} units"
    except Exception as e:
        units_str = f"Error: {e}"

    msg = (
        f"📊 *Bot Status*\n\n"
        f"🔄 *Bot:* {paused_str}\n"
        f"🕒 *Market Open:* {market_str}\n"
        f"📈 *Open Trades:* {trade_count}\n"
        f"💷 *Total Position:* {total_gbp}\n"
        f"📐 *Next Trade Size:* {units_str}\n"
        f"🧠 *Last Retrain:* {retrain_str}\n\n"
        f"🤖 *Last Prediction:* {dir_str}\n"
        f"📊 *Confidence:* {conf_str} ({conf_status})\n"
        f"⏱️ *At:* {pred_time}"
    )
    update.message.reply_text(msg, parse_mode="Markdown")

def stats(update: Update, context: CallbackContext):
    try:
        summary = get_trade_summary()
        msg = (
            f"📈 *Trading Stats*\n\n"
            f"📊 *Total Trades:* {summary['total_trades']}\n"
            f"✅ *Wins:* {summary['wins']}\n"
            f"❌ *Losses:* {summary['losses']}\n"
            f"🔥 *Win Rate:* {summary['win_rate']:.1f}%\n"
            f"💰 *Net P/L:* {format_gbp(summary['total_pl'])}"
        )
        update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"❌ Stats error: {e}")

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

def backtest(update: Update, context: CallbackContext):
    try:
        result = backtest_model()
        msg = (
            f"🔁 *Backtest Results*\n\n"
            f"📦 *Samples:* {result['samples']}\n"
            f"🎯 *Train Accuracy:* {result['train_accuracy']}%\n"
            f"✅ *Test Accuracy:* {result['test_accuracy']}%\n"
            f"📈 *Confident Accuracy:* {result['confident_accuracy']}%\n"
            f"📊 *Confidence Coverage:* {result['confidence_coverage']}%"
        )
        update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"❌ Backtest failed: {e}")

# === Util Sending ===

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

def send_prediction_alert(direction, confidence):
    emoji = "🟢 Buy" if direction == 1 else "🔴 Sell" if direction == 0 else "⚪ Hold"
    msg = (
        f"🤖 *Prediction Alert*\n"
        f"{emoji} Signal\n"
        f"*Confidence:* `{confidence:.2f}`"
    )
    send_text(msg)

# === Polling Setup ===

def start_polling():
    updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("trades", trades))
    dp.add_handler(CommandHandler("pause", pause))
    dp.add_handler(CommandHandler("resume", resume))
    dp.add_handler(CommandHandler("retrain", retrain))
    dp.add_handler(CommandHandler("backtest", backtest))

    updater.start_polling()
    updater.idle()

# === Webhook Setup ===

def setup_webhook():
    from telegram.ext import Dispatcher
    from flask import Flask, request

    app = Flask(__name__)
    updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("status", status))
    dispatcher.add_handler(CommandHandler("stats", stats))
    dispatcher.add_handler(CommandHandler("trades", trades))
    dispatcher.add_handler(CommandHandler("pause", pause))
    dispatcher.add_handler(CommandHandler("resume", resume))
    dispatcher.add_handler(CommandHandler("retrain", retrain))
    dispatcher.add_handler(CommandHandler("backtest", backtest))

    @app.route(f"/webhook/{config.TELEGRAM_TOKEN}", methods=["POST"])
    def webhook():
        dispatcher.process_update(Update.de_json(request.get_json(force=True), bot))
        return "ok"

    app.run(host="0.0.0.0", port=config.PORT)