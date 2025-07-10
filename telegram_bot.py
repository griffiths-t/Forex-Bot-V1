import telegram
from telegram.ext import Updater, CommandHandler, Dispatcher
from datetime import datetime

import config
import model
import broker
import trade_logger
from utils import is_market_open, format_gbp

# Setup bot
bot = telegram.Bot(token=config.TELEGRAM_TOKEN)
updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)
dispatcher: Dispatcher = updater.dispatcher

# Shared state
last_prediction = {
    "direction": None,
    "confidence": None,
    "indicators": None
}
last_retrain_time = None

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="👋 Bot is online and ready to trade!")

def status(update, context):
    try:
        open_trades = broker.get_open_trades()
        num_trades = len(open_trades)

        # Estimate value using live price
        candles = broker.get_candles(config.TRADING_INSTRUMENT, count=1)
        current_price = float(candles[-1]["mid"]["c"])
        trade_value_gbp = config.TRADING_UNITS * current_price * num_trades
        formatted_value = format_gbp(trade_value_gbp)

        summary_msg = f"📊 *Bot Status*\n"
        summary_msg += f"• 🔄 Status: {'⏸️ Paused' if config.TRADING_PAUSED else '▶️ Active'}\n"
        summary_msg += f"• 🕒 Market Open: {'✅ Yes' if is_market_open() else '❌ No'}\n"
        summary_msg += f"• 📈 Open Trades: {num_trades}\n"
        summary_msg += f"• 💷 Trade Value: {formatted_value} GBP\n"
        summary_msg += f"• 🧠 Last Retrain: `{last_retrain_time if last_retrain_time else 'Never'}`\n\n"

        if last_prediction["direction"] is not None:
            direction = "🟢 Buy" if last_prediction["direction"] == 1 else "🔴 Sell"
            confidence = f"{last_prediction['confidence']:.2f}"
            summary_msg += f"🤖 *Last Prediction*\n"
            summary_msg += f"• Direction: {direction}\n"
            summary_msg += f"• Confidence: {confidence}\n"
        else:
            summary_msg += f"🤖 *Last Prediction*: _None yet._"

        context.bot.send_message(chat_id=update.effective_chat.id, text=summary_msg, parse_mode=telegram.ParseMode.MARKDOWN)
    except Exception as e:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Error: {e}")

def retrain_command(update, context):
    global last_retrain_time
    try:
        model.retrain_model()
        last_retrain_time = datetime.utcnow()
        context.bot.send_message(chat_id=update.effective_chat.id, text="🧠 Model retrained successfully.")
    except Exception as e:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Retrain failed: {e}")

def stats(update, context):
    try:
        stats = trade_logger.get_trade_summary()
        msg = (
            f"📊 *Trade Performance Stats*\n"
            f"• 📈 Total Trades: {stats['total_trades']}\n"
            f"• ✅ Wins: {stats['wins']}\n"
            f"• ❌ Losses: {stats['losses']}\n"
            f"• 🔥 Win Rate: {stats['win_rate']:.1f}%\n"
            f"• 💰 Net P/L: {format_gbp(stats['total_pl'])}"
        )
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=telegram.ParseMode.MARKDOWN)
    except Exception as e:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Error: {e}")

def send_text(message):
    bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=message)

def send_trade_alert(direction, confidence, label, units):
    emoji = "🟢 Buy" if direction == 1 else "🔴 Sell"
    msg = f"{emoji} {label.upper()} signal\nConfidence: {confidence:.2f}\nUnits: {units}"
    send_text(msg)

def setup_webhook():
    bot.set_webhook(url=config.WEBHOOK_URL)

def start_polling():
    updater.start_polling()

def handle_webhook(update_data):
    if update_data is None:
        print("[WEBHOOK] Empty payload.")
        return
    try:
        update = telegram.Update.de_json(update_data, bot)
        dispatcher.process_update(update)
    except Exception as e:
        print(f"[WEBHOOK] Failed to process update: {e}")

# Register commands
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("status", status))
dispatcher.add_handler(CommandHandler("retrain", retrain_command))
dispatcher.add_handler(CommandHandler("stats", stats))