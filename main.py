import os
import requests
from fastapi import FastAPI, HTTPException

app = FastAPI()

# === CONFIG ===
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")

BASE_URL = "https://api-capital.backend-capital.com"
SESSION_URL = f"{BASE_URL}/api/v1/session"
POSITIONS_URL = f"{BASE_URL}/api/v1/positions"

HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === EPIC Mapping (must be exact!) ===
TICKER_TO_EPIC = {
    "GOLD": "CC.D.XAUUSD.CFD.IP",
    "SILVER": "CC.D.XAGUSD.CFD.IP",
    "EURUSD": "CS.D.EURUSD.CFD.IP",
    "USDJPY": "CS.D.USDJPY.CFD.IP",
    "NATGAS": "CC.D.NATGAS.CFD.IP",
}

@app.post("/trade")
def place_trade(data: dict):
    symbol = data.get("symbol", "").upper()
    action = data.get("action", "").lower()
    size = data.get("size")

    epic = TICKER_TO_EPIC.get(symbol)
    if not epic:
        raise HTTPException(status_code=404, detail=f"EPIC not found for symbol: {symbol}")

    # Step 1: Create session
    session_payload = {
        "identifier": CAPITAL_EMAIL,
        "password": CAPITAL_PASS,
        "encryptedPassword": False
    }

    try:
        response = requests.post(SESSION_URL, headers=HEADERS, json=session_payload)
        response.raise_for_status()
        cst = response.headers["CST"]
        x_security_token = response.headers["X-SECURITY-TOKEN"]
    except Exception as e:
        return {"status": "error", "message": f"Login failed: {e}"}

    # Step 2: Place trade
    trade_headers = {
        **HEADERS,
        "CST": cst,
        "X-SECURITY-TOKEN": x_security_token
    }

    trade_payload = {
        "epic": epic,
        "direction": action.upper(),  # BUY or SELL
        "size": size,
        "orderType": "MARKET",
        "guaranteedStop": False,
        "forceOpen": True,
        "currencyCode": "USD",
        "dealReference": "bot-trade"
    }

    try:
        trade_response = requests.post(POSITIONS_URL, headers=trade_headers, json=trade_payload)
        trade_response.raise_for_status()
        return {"status": "ok", "response": trade_response.json()}
    except Exception as e:
        return {"status": "error", "message": str(e), "details": trade_response.text}
