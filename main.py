import time
import schedule
import threading
from datetime import datetime
from flask import Flask, request
import os

import config
import broker
import model
import telegram_bot
import trade_logger
from utils import is_market_open, get_equity

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
    print(f"[{datetime.utcnow()}] ✅ predict_and_trade() called")

    try:
        if config.TRADING_PAUSED:
            reason = "⏸️ Bot paused"
            print(f"[BOT] {reason}")
            telegram_bot.send_text(f"📭 Trade skipped: {reason}")
            trade_logger.log_skipped_trade({
                "timestamp": datetime.utcnow().isoformat(),
                "direction": None,
                "confidence": None,
                "reason_skipped": reason,
                "indicators": {}
            })
            return

        if not is_market_open():
            reason = "❌ Market closed"
            print(f"[BOT] {reason}")
            telegram_bot.send_text(f"📭 Trade skipped: {reason}")
            trade_logger.log_skipped_trade({
                "timestamp": datetime.utcnow().isoformat(),
                "direction": None,
                "confidence": None,
                "reason_skipped": reason,
                "indicators": {}
            })
            return

        print("[BOT] Running prediction and trade logic.")
        result = model.predict_from_latest_candles()
        print(f"[MODEL] Prediction result: {result}")

        if result is None or len(result) != 3:
            raise ValueError("Model returned invalid prediction result")

        direction, confidence, indicators = result

        # ✅ Update last prediction and send alert regardless of trade
        telegram_bot.last_prediction.update({
            "direction": direction,
            "confidence": confidence,
            "indicators": indicators,
            "timestamp": datetime.utcnow()
        })
        telegram_bot.send_prediction_alert(direction, confidence)

        emoji = "🟢 Buy" if direction == 1 else "🔴 Sell" if direction == 0 else "⚪ Hold"
        print(f"[PREDICT] {emoji}, confidence: {confidence:.2f}")

        if confidence < 0.6:
            reason = f"⚠️ Low confidence ({confidence:.2f})"
            print(f"[BOT] {reason}")
            telegram_bot.send_text(f"📭 Trade skipped: {reason}")
            trade_logger.log_skipped_trade({
                "timestamp": datetime.utcnow().isoformat(),
                "direction": direction,
                "confidence": confidence,
                "reason_skipped": reason,
                "indicators": indicators
            })
            return

        current_positions = broker.get_open_trades()
        same_direction_held = any(
            pos["instrument"] == config.TRADING_INSTRUMENT and
            ((float(pos.get("currentUnits", "0")) > 0 and direction == 1) or
             (float(pos.get("currentUnits", "0")) < 0 and direction == 0))
            for pos in current_positions
        )

        if same_direction_held:
            reason = f"Already holding a {emoji} position"
            print(f"[BOT] {reason}")
            telegram_bot.send_text(f"📭 Trade skipped: {reason}")
            trade_logger.log_skipped_trade({
                "timestamp": datetime.utcnow().isoformat(),
                "direction": direction,
                "confidence": confidence,
                "reason_skipped": reason,
                "indicators": indicators
            })
            return

        has_open_trade = any(pos["instrument"] == config.TRADING_INSTRUMENT for pos in current_positions)
        if has_open_trade:
            print("[BOT] Existing open trade detected — closing.")
            broker.close_position(config.TRADING_INSTRUMENT)

        print(f"[BOT] Calculating dynamic trade size and placing new trade...")
        price = broker.get_current_price(config.TRADING_INSTRUMENT)
        equity = get_equity()
        units = broker.calculate_dynamic_units(price, equity)
        signed_units = units if direction == 1 else -units

        broker.open_trade(config.TRADING_INSTRUMENT, signed_units)

        trade_logger.log_trade({
            "timestamp": datetime.utcnow().isoformat(),
            "direction": direction,
            "confidence": confidence,
            "indicators": indicators
        })

        telegram_bot.send_trade_alert(direction, confidence, "buy" if direction == 1 else "sell", signed_units)

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

def heartbeat():
    print(f"[HEARTBEAT] Bot alive at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

# ⏰ Schedule jobs
schedule.every(15).minutes.do(predict_and_trade)
schedule.every().day.at("23:00").do(retrain_daily)
schedule.every().minute.do(log_scheduler_activity)
schedule.every().minute.do(heartbeat)
schedule.every().day.at("00:00").do(reset_scheduler_log)

def run_schedule():
    while True:
        try:
            schedule.run_pending()
            print(f"[SCHEDULER] Tick: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"[SCHEDULER ERROR] {e}")
        time.sleep(1)

if __name__ == "__main__":
    print("✅ Bot is live: 15-min prediction + daily retrain at 23:00 UTC")

    if not os.path.exists(config.MODEL_PATH):
        print("[INIT] No model.pkl found — training now...")
        model.retrain_model()
        telegram_bot.last_retrain_time = datetime.utcnow()

    predict_and_trade()

    if config.TELEGRAM_USE_WEBHOOK:
        telegram_bot.setup_webhook()
        threading.Thread(target=keep_alive, daemon=True).start()
        threading.Thread(target=run_schedule, daemon=True).start()
    else:
        threading.Thread(target=keep_alive, daemon=True).start()
        threading.Thread(target=run_schedule, daemon=True).start()
        telegram_bot.start_polling()