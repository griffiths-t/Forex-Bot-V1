# broker.py
import requests
import config

def get_headers():
    return {
        "Authorization": f"Bearer {config.OANDA_API_KEY}",
        "Content-Type": "application/json"
    }

def get_candles(instrument=None, count=1500, granularity="M15"):
    instrument = instrument or config.TRADING_INSTRUMENT
    url = f"{config.OANDA_URL}/instruments/{instrument}/candles"
    params = {
        "count": count,
        "granularity": granularity,
        "price": "M"
    }
    response = requests.get(url, headers=get_headers(), params=params)
    if response.status_code != 200:
        raise Exception(f"Error fetching candles: {response.status_code} - {response.text}")
    return response.json()["candles"]

def get_open_trades():
    url = f"{config.OANDA_URL}/accounts/{config.OANDA_ACCOUNT_ID}/openTrades"
    response = requests.get(url, headers=get_headers())
    if response.status_code != 200:
        raise Exception(f"Failed to get open trades: {response.status_code} - {response.text}")
    return response.json().get("trades", [])

def get_position(instrument):
    url = f"{config.OANDA_URL}/accounts/{config.OANDA_ACCOUNT_ID}/positions/{instrument}"
    response = requests.get(url, headers=get_headers())
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise Exception(f"Failed to fetch position: {response.status_code} - {response.text}")
    return response.json().get("position", {})

def open_trade(instrument, units, stop_loss=None, take_profit=None):
    url = f"{config.OANDA_URL}/accounts/{config.OANDA_ACCOUNT_ID}/orders"
    order = {
        "order": {
            "instrument": instrument,
            "units": str(units),
            "type": "MARKET",
            "positionFill": "DEFAULT"
        }
    }
    if stop_loss:
        order["order"]["stopLossOnFill"] = {"price": str(stop_loss)}
    if take_profit:
        order["order"]["takeProfitOnFill"] = {"price": str(take_profit)}

    response = requests.post(url, headers=get_headers(), json=order)
    if response.status_code not in (200, 201):
        raise Exception(f"Failed to open trade: {response.status_code} - {response.text}")
    return response.json()

def close_position(instrument):
    position = get_position(instrument)
    if not position:
        print("[BROKER] No open position to close.")
        return

    body = {}
    long_units = float(position.get("long", {}).get("units", "0"))
    short_units = float(position.get("short", {}).get("units", "0"))

    if long_units != 0:
        body["longUnits"] = "ALL"
    if short_units != 0:
        body["shortUnits"] = "ALL"

    if not body:
        print("[BROKER] Nothing to close.")
        return

    url = f"{config.OANDA_URL}/accounts/{config.OANDA_ACCOUNT_ID}/positions/{instrument}/close"
    response = requests.put(url, headers=get_headers(), json=body)
    if response.status_code != 200:
        raise Exception(f"Failed to close position: {response.status_code} - {response.text}")
    return response.json()

def get_transaction_history(limit=100):
    url = f"{config.OANDA_URL}/accounts/{config.OANDA_ACCOUNT_ID}/transactions"
    params = {
        "type": "ORDER_FILL",
        "count": limit
    }
    response = requests.get(url, headers=get_headers(), params=params)
    if response.status_code != 200:
        raise Exception(f"Error fetching transactions: {response.status_code} - {response.text}")
    return response.json().get("transactions", [])

def get_closed_trades():
    url = f"{config.OANDA_URL}/accounts/{config.OANDA_ACCOUNT_ID}/trades"
    params = {
        "state": "CLOSED"
    }
    response = requests.get(url, headers=get_headers(), params=params)
    if response.status_code != 200:
        raise Exception(f"Error fetching closed trades: {response.status_code} - {response.text}")
    return response.json().get("trades", [])