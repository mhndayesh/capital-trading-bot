from fastapi import FastAPI, Request, HTTPException
import os
import requests
import logging

app = FastAPI()

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# === Capital.com API Key ===
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")

BASE_URL = "https://api-capital.backend-capital.com"
BASE_HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === Manual Ticker to EPIC Mapping ===
TICKER_TO_EPIC = {
    "GOLD": "CC.D.XAUUSD.CFD.IP",
    "SILVER": "CC.D.XAGUSD.CFD.IP",
    "EURUSD": "CS.D.EURUSD.CFD.IP",
    "NATGAS": "CC.D.NATGAS.CFD.IP",
    "USDJPY": "CS.D.USDJPY.CFD.IP"
}

@app.get("/")
def root():
    return {"status": "Capital.com bot using API key is live"}

@app.post("/trade")
def trade(payload: dict):
    symbol = payload.get("symbol")
    action = payload.get("action")
    size = payload.get("size")

    if not all([symbol, action, size]):
        raise HTTPException(status_code=400, detail="Missing symbol, action, or size")

    epic = TICKER_TO_EPIC.get(symbol.upper())
    if not epic:
        return {"error": f"Unsupported symbol or EPIC not mapped: {symbol}"}

    # Define direction (BUY or SELL)
    direction = "BUY" if action.lower() == "buy" else "SELL"

    # Create market order payload
    order = {
        "epic": epic,
        "direction": direction,
        "size": size,
        "orderType": "MARKET",
        "guaranteedStop": False,
        "currencyCode": "USD",
        "forceOpen": True
    }

    try:
        response = requests.post(f"{BASE_URL}/api/v1/positions", headers=BASE_HEADERS, json=order)
        response.raise_for_status()
        return {"status": "ok", "response": response.json()}
    except Exception as e:
        logger.error(f"Trade error: {e}")
        return {"status": "error", "message": str(e)}
