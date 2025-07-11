# model.py
import numpy as np
import pandas as pd
import joblib
from ta.momentum import RSIIndicator, StochasticOscillator, ROCIndicator
from ta.trend import SMAIndicator, MACD
from ta.volatility import AverageTrueRange
from sklearn.ensemble import RandomForestClassifier

import broker
import config

def preprocess_candles(candles):
    df = pd.DataFrame([{
        "time": c["time"],
        "open": float(c["mid"]["o"]),
        "high": float(c["mid"]["h"]),
        "low": float(c["mid"]["l"]),
        "close": float(c["mid"]["c"]),
        "volume": float(c["volume"])
    } for c in candles if c.get("complete", False)])

    df.set_index("time", inplace=True)

    # Technical indicators
    df["rsi"] = RSIIndicator(close=df["close"]).rsi()
    df["sma5"] = SMAIndicator(close=df["close"], window=5).sma_indicator()
    df["sma15"] = SMAIndicator(close=df["close"], window=15).sma_indicator()
    df["macd"] = MACD(close=df["close"]).macd()
    df["stoch"] = StochasticOscillator(high=df["high"], low=df["low"], close=df["close"]).stoch()
    df["roc"] = ROCIndicator(close=df["close"]).roc()
    df["atr"] = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"]).average_true_range()
    df["hour"] = pd.to_datetime(df.index).hour

    df.dropna(inplace=True)
    return df

def create_features_labels(df):
    df["return"] = df["close"].pct_change().shift(-1)
    df["direction"] = np.where(df["return"] > 0, 1, 0)
    df.dropna(inplace=True)

    features = ["rsi", "macd", "sma5", "sma15", "stoch", "roc", "atr", "hour"]
    X = df[features]
    y = df["direction"]
    return X, y

def retrain_model():
    candles = broker.get_candles(
        instrument=config.TRADING_INSTRUMENT,
        count=config.CANDLE_COUNT,
        granularity=config.TIMEFRAME
    )
    df = preprocess_candles(candles)
    X, y = create_features_labels(df)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    joblib.dump(model, config.MODEL_PATH)

def predict_from_latest_candles():
    candles = broker.get_candles(
        instrument=config.TRADING_INSTRUMENT,
        count=50,
        granularity=config.TIMEFRAME
    )
    df = preprocess_candles(candles)
    if df.empty:
        raise Exception("No valid candle data for prediction")

    model = joblib.load(config.MODEL_PATH)
    X = df.iloc[-1:][["rsi", "macd", "sma5", "sma15", "stoch", "roc", "atr", "hour"]]
    proba = model.predict_proba(X)[0]
    prediction = model.predict(X)[0]

    return int(prediction), float(max(proba)), X.to_dict("records")[0]

def run_backtest():
    candles = broker.get_candles(
        instrument=config.TRADING_INSTRUMENT,
        count=config.CANDLE_COUNT,
        granularity=config.TIMEFRAME
    )
    df = preprocess_candles(candles)
    X, y = create_features_labels(df)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)

    y_pred = model.predict(X)
    accuracy = np.mean(y_pred == y)
    correct = int((y_pred == y).sum())
    total = len(y)
    win_rate = accuracy * 100

    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "win_rate": win_rate
    }