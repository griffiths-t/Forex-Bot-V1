from datetime import datetime
import os
import requests
import config

SCHEDULER_LOG_PATH = "scheduler_log.txt"

def is_market_open():
    now = datetime.utcnow()
    weekday = now.weekday()
    hour = now.hour

    if weekday == 5:  # Saturday
        return False
    if weekday == 6 and hour < 21:  # Sunday before 21:00 UTC
        return False
    if weekday == 4 and hour >= 22:  # Friday after 22:00 UTC
        return False
    return True

def log_scheduler_message(message):
    now = datetime.utcnow()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    # Reset the file at 00:00 UTC
    if now.strftime("%H:%M") == "00:00":
        with open(SCHEDULER_LOG_PATH, "w") as f:
            f.write(f"{timestamp} - {message}\n")
    else:
        with open(SCHEDULER_LOG_PATH, "a") as f:
            f.write(f"{timestamp} - {message}\n")

def format_gbp(amount):
    """Format a float as British Pound currency (e.g., £1,234.56)"""
    try:
        return f"£{float(amount):,.2f}"
    except:
        return "£0.00"

def get_equity():
    """Fetch live account equity (NAV) from OANDA API"""
    url = f"https://api-fxpractice.oanda.com/v3/accounts/{config.OANDA_ACCOUNT_ID}/summary"
    headers = {
        "Authorization": f"Bearer {config.OANDA_API_KEY}"
    }
    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        return float(data["account"]["NAV"])
    except Exception as e:
        print(f"[utils.py] Equity fetch failed: {e}")
        return 0.0