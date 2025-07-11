# model.py
import numpy as np
import pandas as pd
import joblib
from ta.momentum import RSIIndicator, StochasticOscillator, ROCIndicator
from ta.trend import SMAIndicator, MACD, ADXIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

import broker
import config

TP_PIPS = 15
SL_PIPS = 10
PIP_VALUE = 0.0001  # for GBP/USD

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

    # Standard indicators
    df["rsi"] = RSIIndicator(close=df["close"]).rsi()
    df["sma5"] = SMAIndicator(close=df["close"], window=5).sma_indicator()
    df["sma15"] = SMAIndicator(close=df["close"], window=15).sma_indicator()
    df["macd"] = MACD(close=df["close"]).macd()
    df["stoch"] = StochasticOscillator(high=df["high"], low=df["low"], close=df["close"]).stoch()
    df["roc"] = ROCIndicator(close=df["close"]).roc()
    df["atr"] = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"]).average_true_range()

    # New indicators
    df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()
    bb = BollingerBands(close=df["close"])
    df["bb_percent"] = bb.bollinger_pband()
    df["adx"] = ADXIndicator(high=df["high"], low=df["low"], close=df["close"]).adx()

    df["hour"] = pd.to_datetime(df.index).hour
    df["body_ratio"] = abs(df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-6)
    df["range"] = df["high"] - df["low"]
    df["ma_slope"] = df["sma15"].diff()

    df.dropna(inplace=True)
    return df

def label_tp_sl(df, tp_pips=TP_PIPS, sl_pips=SL_PIPS, pip_value=PIP_VALUE):
    labels = []
    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values

    tp_threshold = tp_pips * pip_value
    sl_threshold = sl_pips * pip_value

    for i in range(len(df)):
        entry = closes[i]
        future_high = highs[i+1:i+6]
        future_low = lows[i+1:i+6]

        label = np.nan
        for h, l in zip(future_high, future_low):
            if h - entry >= tp_threshold:
                label = 1
                break
            elif entry - l >= sl_threshold:
                label = 0
                break
        labels.append(label)

    labels += [np.nan] * (len(df) - len(labels))
    df["direction"] = labels
    df.dropna(subset=["direction"], inplace=True)
    df["direction"] = df["direction"].astype(int)
    return df

def create_features_labels(df):
    df = label_tp_sl(df)
    features = [
        "rsi", "macd", "sma5", "sma15", "stoch", "roc", "atr", "hour",
        "body_ratio", "range", "ma_slope",
        "vwap", "bb_percent", "adx"
    ]
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

    base_model = RandomForestClassifier(n_estimators=100, random_state=42)
    model = CalibratedClassifierCV(base_model, method='sigmoid', cv=5)
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
    X = df.iloc[-1:][[
        "rsi", "macd", "sma5", "sma15", "stoch", "roc", "atr", "hour",
        "body_ratio", "range", "ma_slope",
        "vwap", "bb_percent", "adx"
    ]]
    proba = model.predict_proba(X)[0]
    prediction = model.predict(X)[0]

    return int(prediction), float(max(proba)), X.to_dict("records")[0]

def backtest_model():
    candles = broker.get_candles(
        instrument=config.TRADING_INSTRUMENT,
        count=config.CANDLE_COUNT,
        granularity=config.TIMEFRAME
    )
    df = preprocess_candles(candles)
    X, y = create_features_labels(df)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, shuffle=False)

    base_model = RandomForestClassifier(n_estimators=100, random_state=42)
    model = CalibratedClassifierCV(base_model, method='sigmoid', cv=5)
    model.fit(X_train, y_train)

    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)

    train_acc = accuracy_score(y_train, y_train_pred) * 100
    test_acc = accuracy_score(y_test, y_test_pred) * 100

    confident_mask = (y_prob.max(axis=1) >= 0.60)
    confident_acc = accuracy_score(
        y_test[confident_mask],
        y_test_pred[confident_mask]
    ) * 100 if confident_mask.sum() > 0 else 0

    coverage = confident_mask.sum() / len(y_test) * 100

    return {
        "samples": len(X),
        "train_accuracy": round(train_acc, 2),
        "test_accuracy": round(test_acc, 2),
        "confident_accuracy": round(confident_acc, 2),
        "confidence_coverage": round(coverage, 2)
    }