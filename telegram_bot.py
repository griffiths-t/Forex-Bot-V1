import telegram
from telegram.ext import Updater, CommandHandler, Dispatcher
from datetime import datetime
import config
import model
import broker
import trade_logger
from utils import is_market_open

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

def summary(update, context):
    try:
        summary_msg = f"📊 Bot Status:\n"
        summary_msg += f"• Status: {'⏸️ Paused' if config.TRADING_PAUSED else '▶️ Active'}\n"
        summary_msg += f"• Market Open: {'✅ Yes' if is_market_open() else '❌ No'}\n"
        summary_msg += f"• Open Trades: {len(broker.get_open_trades())}\n"
        summary_msg += f"• Trade Value: {config.TRADING_UNITS:.2f} units\n"
        summary_msg += f"• Last Retrain: {last_retrain_time if last_retrain_time else 'Never'}\n"
        summary_msg += f"\n🧠 Last Prediction:\n{last_prediction}"
        context.bot.send_message(chat_id=update.effective_chat.id, text=summary_msg)
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
dispatcher.add_handler(CommandHandler("summary", summary))
dispatcher.add_handler(CommandHandler("retrain", retrain_command))