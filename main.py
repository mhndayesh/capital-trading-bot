from fastapi import FastAPI, Request
import os
import requests
import logging

app = FastAPI()

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Capital API Credentials ===
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")

BASE_URL = "https://api-capital.backend-capital.com"
BASE_HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === Hardcoded EPICs ===
TICKER_TO_EPIC = {
    "GOLD": "CC.D.XAUUSD.CFD.IP",
    "SILVER": "CC.D.XAGUSD.CFD.IP",
    "EURUSD": "CS.D.EURUSD.MINI.IP",
    "USDJPY": "CS.D.USDJPY.MINI.IP",
    "OIL": "CC.D.BRENT.CMD/USD.IP",
    "NATGAS": "CC.D.NATGAS.CMD/USD.IP"
}

@app.post("/trade")
async def place_trade(request: Request):
    data = await request.json()
    symbol = data.get("symbol", "").upper()
    action = data.get("action", "").upper()
    size = data.get("size", 1)

    epic = TICKER_TO_EPIC.get(symbol)
    if not epic:
        return {"error": f"Unknown symbol: {symbol}"}

    trade_payload = {
        "epic": epic,
        "direction": action,
        "size": size,
        "orderType": "MARKET",
        "currencyCode": "USD",
        "forceOpen": True,
        "guaranteedStop": False
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/positions",
            headers=BASE_HEADERS,
            json=trade_payload
        )
        response.raise_for_status()
        return {"status": "ok", "response": response.json()}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": str(e), "details": response.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}
