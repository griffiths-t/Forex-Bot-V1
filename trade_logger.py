# trade_logger.py
import csv
import os
import broker
from utils import format_gbp

TRADE_LOG_FILE = "trade_log.csv"
SKIPPED_TRADE_LOG_FILE = "skipped_trades.csv"

def log_trade(trade_data):
    file_exists = os.path.isfile(TRADE_LOG_FILE)
    with open(TRADE_LOG_FILE, mode="a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=trade_data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(trade_data)

def log_skipped_trade(skipped_data):
    file_exists = os.path.isfile(SKIPPED_TRADE_LOG_FILE)
    with open(SKIPPED_TRADE_LOG_FILE, mode="a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=skipped_data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(skipped_data)

def get_trade_summary():
    trades = broker.get_closed_trades()

    total_trades = len(trades)
    total_pl = 0.0
    wins = 0
    losses = 0

    for trade in trades:
        pl = float(trade.get("realizedPL", 0))
        total_pl += pl
        if pl > 0:
            wins += 1
        elif pl < 0:
            losses += 1

    win_rate = (wins / total_trades) * 100 if total_trades else 0

    return {
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pl": total_pl
    }