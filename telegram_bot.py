import config
import broker
import trade_logger
from utils import format_gbp
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext

TRADING_PAUSED = False
last_prediction = {}
last_retrain_time = None

def send_text(text):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[TELEGRAM] Failed to send message: {e}")

def send_trade_alert(direction, confidence, side, units):
    emoji = "🟢" if direction == 1 else "🔴"
    msg = (
        f"{emoji} *{side.upper()}* {side.capitalize()} signal\n"
        f"Confidence: *{confidence:.2f}*\n"
        f"Units: *{units}*"
    )
    send_text(msg)

def status(update: Update, context: CallbackContext):
    try:
        open_trades = broker.get_open_trades()
        trade_value = sum(abs(float(t['currentUnits'])) for t in open_trades if t['instrument'] == config.TRADING_INSTRUMENT)
        trade_count = len(open_trades)

        msg = "📊 *Bot Status*\n"
        msg += f"• 🔄 Status: {'⏸️ Paused' if TRADING_PAUSED else '▶️ Active'}\n"
        msg += f"• 📈 Open Trades: *{trade_count}*\n"
        msg += f"• 💷 Trade Value: *{format_gbp(trade_value)}*\n"
        if last_retrain_time:
            msg += f"• 🧠 Last Retrain: `{last_retrain_time}`\n"
        if last_prediction:
            dir_emoji = "🟢 Buy" if last_prediction.get("direction") == 1 else "🔴 Sell"
            msg += "\n🤖 *Last Prediction*\n"
            msg += f"• Direction: *{dir_emoji}*\n"
            msg += f"• Confidence: *{last_prediction.get('confidence'):.2f}*\n"

        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        update.message.reply_text(f"❌ Error in /status: {e}")

def start(update: Update, context: CallbackContext):
    update.message.reply_text("✅ Forex bot is running!")

def pause(update: Update, context: CallbackContext):
    global TRADING_PAUSED
    TRADING_PAUSED = True
    update.message.reply_text("⏸️ Trading paused.")

def resume(update: Update, context: CallbackContext):
    global TRADING_PAUSED
    TRADING_PAUSED = False
    update.message.reply_text("▶️ Trading resumed.")

def trades(update: Update, context: CallbackContext):
    try:
        trades = broker.get_open_trades()
        if not trades:
            update.message.reply_text("💤 No open trades.")
            return

        msg = "📄 *Open Trades:*\n"
        for trade in trades:
            side = "🟢 Buy" if int(trade["currentUnits"]) > 0 else "🔴 Sell"
            pl = float(trade["unrealizedPL"])
            msg += (
                f"• {side} *{trade['instrument']}* | Units: *{trade['currentUnits']}* | "
                f"P/L: *{format_gbp(pl)}*\n"
            )
        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        update.message.reply_text(f"❌ Error in /trades: {e}")

def retrain(update: Update, context: CallbackContext):
    try:
        import model
        model.retrain_model()
        global last_retrain_time
        from datetime import datetime
        last_retrain_time = datetime.utcnow()
        update.message.reply_text("🧠 Model retrained successfully.")
    except Exception as e:
        update.message.reply_text(f"❌ Retrain failed: {e}")

def stats(update: Update, context: CallbackContext):
    try:
        trades = trade_logger.get_trade_summary()
        msg = (
            "📊 *Trade Performance Stats*\n"
            f"• 📈 Total Trades: *{trades['total']}*\n"
            f"• ✅ Wins: *{trades['wins']}*\n"
            f"• ❌ Losses: *{trades['losses']}*\n"
            f"• 🔥 Win Rate: *{trades['win_rate']}%*\n"
            f"• 💰 Net P/L: *{format_gbp(trades['net_pl'])}*"
        )
        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        update.message.reply_text(f"❌ Error in /stats: {e}")

def setup_bot():
    updater = Updater(config.TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("pause", pause))
    dp.add_handler(CommandHandler("resume", resume))
    dp.add_handler(CommandHandler("trades", trades))
    dp.add_handler(CommandHandler("retrain", retrain))
    dp.add_handler(CommandHandler("stats", stats))

    return updater

def start_polling():
    updater = setup_bot()
    print("🤖 Telegram bot polling started.")
    updater.start_polling()
    updater.idle()

def handle_webhook(data):
    from telegram import Bot, Update
    bot = Bot(token=config.TELEGRAM_TOKEN)
    update = Update.de_json(data, bot)
    dispatcher = setup_bot().dispatcher
    dispatcher.process_update(update)