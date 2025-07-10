import time
import schedule
import threading
from datetime import datetime
from flask import Flask, request

import config
import broker
import model
import telegram_bot
import trade_logger
from utils import is_market_open

app = Flask(__name__)
SCHEDULER_LOG_FILE = "scheduler_log.txt"

def keep_alive():
    @app.route('/')
    def home():
        return "Bot is running."

    @app.route(f'/webhook/{config.TELEGRAM_TOKEN}', methods=['POST'])
    def webhook():
        telegram_bot.handle_webhook(request.get_json(force=True))
        return "Webhook received", 200

    app.run(host='0.0.0.0', port=config.PORT)

def predict_and_trade():
    if config.TRADING_PAUSED:
        print("[BOT] Trading is paused.")
        trade_logger.log_skipped_trade({
            "timestamp": datetime.utcnow().isoformat(),
            "direction": None,
            "confidence": None,
            "reason_skipped": "Bot paused",
            "indicators": {}
        })
        return

    if not is_market_open():
        print("[BOT] Market is closed. Skipping trade.")
        trade_logger.log_skipped_trade({
            "timestamp": datetime.utcnow().isoformat(),
            "direction": None,
            "confidence": None,
            "reason_skipped": "Market closed",
            "indicators": {}
        })
        return

    print("[BOT] Running prediction and trade logic.")
    try:
        direction, confidence, indicators = model.predict_from_latest_candles()
        telegram_bot.last_prediction.update({
            "direction": direction,
            "confidence": confidence,
            "indicators": indicators
        })

        if confidence < 0.55:
            print(f"[BOT] Low confidence ({confidence:.2f}) — skipping trade.")
            trade_logger.log_skipped_trade({
                "timestamp": datetime.utcnow().isoformat(),
                "direction": direction,
                "confidence": confidence,
                "reason_skipped": "Low confidence",
                "indicators": indicators
            })
            return

        current_positions = broker.get_open_trades()
        has_open_trade = any(pos["instrument"] == config.TRADING_INSTRUMENT for pos in current_positions)

        if has_open_trade:
            print("[BOT] Existing open trade detected — closing.")
            broker.close_position(config.TRADING_INSTRUMENT)

        print(f"[BOT] Placing new trade: {'Buy' if direction == 1 else 'Sell'}")
        broker.open_trade(config.TRADING_INSTRUMENT, direction * config.TRADING_UNITS)

        trade_logger.log_trade({
            "timestamp": datetime.utcnow().isoformat(),
            "direction": direction,
            "confidence": confidence,
            "indicators": indicators
        })

        telegram_bot.send_trade_alert(direction, confidence, "buy" if direction == 1 else "sell", config.TRADING_UNITS)

    except Exception as e:
        print(f"[ERROR] Prediction or trade error: {e}")
        telegram_bot.send_text(f"❌ Trade error: {e}")

def retrain_daily():
    try:
        print("[BOT] Running daily retrain...")
        model.retrain_model()
        telegram_bot.last_retrain_time = datetime.utcnow()
        telegram_bot.send_text("🧠 Retrain finished.")
    except Exception as e:
        telegram_bot.send_text(f"❌ Retrain failed: {e}")

def reset_scheduler_log():
    with open(SCHEDULER_LOG_FILE, "w") as f:
        f.write("")
    print("[SCHEDULER] Scheduler log reset.")

def log_scheduler_activity():
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{timestamp} - [SCHEDULER] Checked tasks\n"
    with open(SCHEDULER_LOG_FILE, "a") as f:
        f.write(log_line)
    print(log_line.strip())

# Schedule jobs
schedule.every(15).minutes.do(predict_and_trade)
schedule.every().day.at("23:00").do(retrain_daily)
schedule.every().minute.do(log_scheduler_activity)
schedule.every().day.at("00:00").do(reset_scheduler_log)

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    print("✅ Bot is live: 15-min prediction + daily retrain at 23:00 UTC")

    if config.TELEGRAM_USE_WEBHOOK:
        telegram_bot.setup_webhook()
        threading.Thread(target=keep_alive).start()
        threading.Thread(target=run_schedule).start()
    else:
        threading.Thread(target=keep_alive).start()
        threading.Thread(target=run_schedule).start()
        telegram_bot.start_polling()