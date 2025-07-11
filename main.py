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

        telegram_bot.last_prediction.update({
            "direction": direction,
            "confidence": confidence,
            "indicators": indicators
        })

        if confidence < 0.55:
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
        same_direction_held = False

        for pos in current_positions:
            if pos["instrument"] == config.TRADING_INSTRUMENT:
                units = float(pos.get("currentUnits", "0"))
                if (units > 0 and direction == 1) or (units < 0 and direction == 0):
                    same_direction_held = True
                    break

        if same_direction_held:
            emoji = "🟢 Buy" if direction == 1 else "🔴 Sell"
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

        print(f"[BOT] Placing new trade: {'Buy' if direction == 1 else 'Sell'}")