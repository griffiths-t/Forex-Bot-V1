# model.py
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from ta.momentum import RSIIndicator, StochasticOscillator, ROCIndicator
from ta.trend import SMAIndicator, MACD
from ta.volatility import AverageTrueRange

import broker
import config

# === Data Preprocessing ===

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

    # Indicators
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

# === Retrain ===

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

# === Predict Live ===

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

# === Backtest ===

def backtest_model(conf_threshold=0.55, test_size=0.2):
    candles = broker.get_candles(
        instrument=config.TRADING_INSTRUMENT,
        count=config.CANDLE_COUNT,
        granularity=config.TIMEFRAME
    )
    df = preprocess_candles(candles)
    X, y = create_features_labels(df)

    # Train/Test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, shuffle=False
    )

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    joblib.dump(model, config.MODEL_PATH)

    # Accuracy metrics
    train_acc = model.score(X_train, y_train)
    test_acc = model.score(X_test, y_test)

    proba = model.predict_proba(X_test)
    preds = model.predict(X_test)

    confident_mask = np.max(proba, axis=1) >= conf_threshold
    confident_preds = preds[confident_mask]
    confident_truth = y_test.iloc[confident_mask]

    if len(confident_preds) > 0:
        confident_acc = np.mean(confident_preds == confident_truth)
        confidence_coverage = len(confident_preds) / len(y_test)
    else:
        confident_acc = 0.0
        confidence_coverage = 0.0

    return {
        "samples": len(y),
        "train_accuracy": round(train_acc * 100, 2),
        "test_accuracy": round(test_acc * 100, 2),
        "confident_accuracy": round(confident_acc * 100, 2),
        "confidence_coverage": round(confidence_coverage * 100, 2)
    }