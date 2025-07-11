import os
import time
import threading
from datetime import datetime
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
import pytz  # ✅ Required for APScheduler timezones

import config
import broker
import model
import telegram_bot
import trade_logger
from utils import is_market_open, get_equity

app = Flask(__name__)
SCHEDULER_LOG_FILE = "scheduler_log.txt"

# ✅ Use pytz.utc as required by APScheduler
scheduler = BackgroundScheduler(timezone=pytz.utc)

# ─────────────────────────────
# 🌐 Flask Routes
# ─────────────────────────────
@app.route('/')
def home():
    return "Bot is running."

@app.route(f'/webhook/{config.TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    telegram_bot.handle_webhook(request.get_json(force=True))
    return "Webhook received", 200

# ─────────────────────────────
# 🔐 Safe Job Wrapper
# ─────────────────────────────
def safe_job(func):
    def wrapper():
        try:
            print(f"[APScheduler] Running job: {func.__name__} at {datetime.utcnow()}")
            func()
        except Exception as e:
            print(f"[APScheduler ERROR] Job '{func.__name__}' failed: {e}")
            telegram_bot.send_text(f"❌ Job '{func.__name__}' error: {e}")
    return wrapper

# ─────────────────────────────
# 🔁 Prediction & Trading Logic
# ─────────────────────────────
def predict_and_trade():
    print(f"[{datetime.utcnow()}] ✅ predict_and_trade() called")

    if config.TRADING_PAUSED:
        reason = "⏸️ Bot paused"
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
        telegram_bot.send_text(f"📭 Trade skipped: {reason}")
        trade_logger.log_skipped_trade({
            "timestamp": datetime.utcnow().isoformat(),
            "direction": None,
            "confidence": None,
            "reason_skipped": reason,
            "indicators": {}
        })
        return

    result = model.predict_from_latest_candles()
    print(f"[MODEL] Prediction result: {result}")

    if result is None or len(result) != 3:
        raise ValueError("Model returned invalid prediction result")

    direction, confidence, indicators = result

    # Update last prediction
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

    print("[BOT] Placing new trade...")
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

# ─────────────────────────────
# 📅 Other Scheduled Jobs
# ─────────────────────────────
def retrain_daily():
    print("[BOT] Running daily retrain...")
    model.retrain_model()
    telegram_bot.last_retrain_time = datetime.utcnow()
    telegram_bot.send_text("🧠 Retrain finished.")

def log_scheduler_activity():
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{timestamp} - [SCHEDULER] Checked tasks\n"
    with open(SCHEDULER_LOG_FILE, "a") as f:
        f.write(log_line)
    print(log_line.strip())

def reset_scheduler_log():
    with open(SCHEDULER_LOG_FILE, "w") as f:
        f.write("")
    print("[SCHEDULER] Scheduler log reset.")

def heartbeat():
    print(f"[HEARTBEAT] Bot alive at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

# ─────────────────────────────
# ▶️ Start Bot
# ─────────────────────────────
if __name__ == "__main__":
    print("✅ Bot is live: 15-min prediction + daily retrain at 23:00 UTC")

    if not os.path.exists(config.MODEL_PATH):
        print("[INIT] No model.pkl found — training now...")
        model.retrain_model()
        telegram_bot.last_retrain_time = datetime.utcnow()

    # Run prediction immediately on startup
    predict_and_trade()

    # Schedule jobs via APScheduler
    scheduler.add_job(safe_job(predict_and_trade), 'interval', minutes=15)
    scheduler.add_job(safe_job(retrain_daily), 'cron', hour=23, minute=0)
    scheduler.add_job(safe_job(log_scheduler_activity), 'interval', minutes=1)
    scheduler.add_job(safe_job(heartbeat), 'interval', minutes=1)
    scheduler.add_job(safe_job(reset_scheduler_log), 'cron', hour=0, minute=0)
    scheduler.start()
    print("[SCHEDULER] APScheduler started")

    if config.TELEGRAM_USE_WEBHOOK:
        telegram_bot.setup_webhook()
        app.run(host='0.0.0.0', port=config.PORT)
    else:
        threading.Thread(target=lambda: app.run(host='0.0.0.0', port=config.PORT), daemon=True).start()
        telegram_bot.start_polling()