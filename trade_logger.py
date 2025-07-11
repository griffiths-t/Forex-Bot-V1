import csv
import os
import pandas as pd

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

def get_trade_summary(log_path=TRADE_LOG_FILE):
    try:
        df = pd.read_csv(log_path)
        if df.empty:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pl": 0.0
            }

        wins = df[df["pnl"] > 0].shape[0]
        losses = df[df["pnl"] <= 0].shape[0]
        total_trades = wins + losses
        win_rate = (wins / total_trades) * 100 if total_trades else 0.0
        total_pl = df["pnl"].sum()

        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
            "total_pl": round(total_pl, 2)
        }
    except FileNotFoundError:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "total_pl": 0.0
        }