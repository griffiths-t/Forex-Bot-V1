# 💹 Forex-Bot

An AI-powered automated Forex trading bot that predicts GBP/USD movements every 15 minutes using technical indicators and machine learning. It retrains daily and executes trades via the OANDA API, with alerts and control via Telegram.

## 📦 Features

- ✅ 15-minute trading cycle using live market data (GBP/USD, M15)
- ✅ ML model (XGBoost/RandomForest) with confidence-based filtering
- ✅ Daily model retraining at 23:00 UTC
- ✅ Telegram bot with `/status`, `/pause`, `/resume`, `/retrain` commands
- ✅ Smart indicators: RSI, SMA, MACD, Stochastic, ROC, volatility, trend slope, market hours
- ✅ Trade logging (executed + skipped)
- ✅ Scheduler + Flask ping for uptime
- ✅ Fully deployable to [Render.com](https://render.com)

---

## 🚀 Live Deployment on Render

### 1. 🧱 Prerequisites

- A GitHub account
- A [Render](https://render.com) account (free tier supported)
- A valid [OANDA API Key](https://developer.oanda.com/)
- Your own Telegram bot + chat ID

---

### 2. 📁 Folder Structure