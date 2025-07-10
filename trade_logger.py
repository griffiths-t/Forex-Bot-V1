# trade_logger.py
import csv
import os

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