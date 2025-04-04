from fastapi import FastAPI, Request, HTTPException
import os
import requests
import logging

app = FastAPI()

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# === Capital.com API Credentials ===
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")

BASE_URL = "https://api-capital.backend-capital.com"
BASE_HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === Manual EPIC Mapping ===
TICKER_TO_EPIC = {
    "GOLD": "CC.D.XAUUSD.CFD.IP",
    "SILVER": "CC.D.XAGUSD.CFD.IP",
    "EURUSD": "CS.D.EURUSD.CFD.IP",
    "USDJPY": "CS.D.USDJPY.CFD.IP",
    "OIL": "CC.D.USOIL.CFD.IP",
    "NATGAS": "CC.D.NATGAS.CFD.IP"
}

@app.get("/")
def read_root():
    return {"status": "Capital Trading Bot is live using API Key 🔐"}

@app.post("/trade")
def place_trade(request: Request):
    try:
        data = request.json()
    except Exception as e:
        logger.error(f"Invalid JSON in request: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    symbol = data.get("symbol")
    direction = data.get("action")
    size = data.get("size")

    if not symbol or not direction or not size:
        raise HTTPException(status_code=400, detail="Missing required fields")

    epic = TICKER_TO_EPIC.get(symbol.upper())
    if not epic:
        return {"error": f"Unknown symbol: {symbol}"}

    logger.info(f"Placing trade for {symbol} ({epic}): {direction} x {size}")

    try:
        url = f"{BASE_URL}/api/v1/positions"
        payload = {
            "epic": epic,
            "direction": direction.upper(),
            "size": size,
            "orderType": "MARKET",
            "currencyCode": "USD",
            "forceOpen": True,
            "guaranteedStop": False,
            "timeInForce": "FILL_OR_KILL",
            "dealReference": f"bot-{symbol.lower()}"
        }

        response = requests.post(url, headers=BASE_HEADERS, json=payload)
        response.raise_for_status()

        return {"status": "ok", "response": response.json()}

    except requests.exceptions.RequestException as e:
        logger.error(f"Trade failed: {e}")
        return {"status": "error", "message": str(e)}
