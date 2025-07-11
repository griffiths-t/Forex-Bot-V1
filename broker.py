# broker.py
import requests
import config
from utils import get_equity

OANDA_API_URL = "https://api-fxpractice.oanda.com/v3"
HEADERS = {
    "Authorization": f"Bearer {config.OANDA_API_KEY}",
    "Content-Type": "application/json"
}

def get_candles(instrument, count, granularity):
    url = f"{OANDA_API_URL}/instruments/{instrument}/candles"
    params = {
        "count": count,
        "granularity": granularity,
        "price": "M"
    }
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()["candles"]

def get_open_trades():
    url = f"{OANDA_API_URL}/accounts/{config.OANDA_ACCOUNT_ID}/openTrades"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()["trades"]

def close_position(instrument):
    url = f"{OANDA_API_URL}/accounts/{config.OANDA_ACCOUNT_ID}/positions/{instrument}/close"
    data = {
        "longUnits": "ALL",
        "shortUnits": "ALL"
    }
    response = requests.put(url, headers=HEADERS, json=data)
    response.raise_for_status()
    return response.json()

def get_current_price(instrument):
    url = f"{OANDA_API_URL}/accounts/{config.OANDA_ACCOUNT_ID}/pricing"
    params = {"instruments": instrument}
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    prices = response.json()["prices"][0]
    return (float(prices["bids"][0]["price"]) + float(prices["asks"][0]["price"])) / 2

def calculate_dynamic_units(price, equity, risk_percent=0.15, leverage=20):
    risk_amount = equity * risk_percent
    margin_per_unit = price / leverage
    units = risk_amount / margin_per_unit
    return int(units)

def place_trade(instrument, direction, tp_pips=15, sl_pips=10):
    price = get_current_price(instrument)
    equity = get_equity()
    units = calculate_dynamic_units(price, equity)

    side = "buy" if direction == 1 else "sell"
    sl_price = price - sl_pips * 0.0001 if direction == 1 else price + sl_pips * 0.0001
    tp_price = price + tp_pips * 0.0001 if direction == 1 else price - tp_pips * 0.0001

    order_data = {
        "order": {
            "instrument": instrument,
            "units": str(units if direction == 1 else -units),
            "type": "MARKET",
            "positionFill": "DEFAULT",
            "takeProfitOnFill": {"price": f"{tp_price:.5f}"},
            "stopLossOnFill": {"price": f"{sl_price:.5f}"}
        }
    }

    url = f"{OANDA_API_URL}/accounts/{config.OANDA_ACCOUNT_ID}/orders"
    response = requests.post(url, headers=HEADERS, json=order_data)
    response.raise_for_status()
    return response.json(), units