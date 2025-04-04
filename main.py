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
CAPITAL_PASS = os.getenv("CAPITAL_PASS")

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

# === Trade Endpoint ===
@app.post("/trade")
async def place_trade(request: Request):
    data = await request.json()
    symbol = data.get("symbol")
    action = data.get("action")
    size = data.get("size")

    epic = TICKER_TO_EPIC.get(symbol.upper())
    if not epic:
        return {"error": f"Could not find epic for: {symbol}"}

    # Step 1: Login using API key + password
    try:
        login_res = requests.post(
            f"{BASE_URL}/api/v1/session",
            headers=BASE_HEADERS,
            json={
                "identifier": CAPITAL_API_KEY,
                "password": CAPITAL_PASS
            }
        )
        login_res.raise_for_status()
        auth_data = login_res.json()
        cst = auth_data["cst"]
        x_security_token = auth_data["securityToken"]
    except Exception as e:
        return {"status": "error", "message": str(e)}

    # Step 2: Place trade
    trade_headers = {
        **BASE_HEADERS,
        "CST": cst,
        "X-SECURITY-TOKEN": x_security_token
    }

    trade_payload = {
        "epic": epic,
        "direction": action.upper(),
        "size": size,
        "orderType": "MARKET",
        "guaranteedStop": False,
        "currencyCode": "USD",
        "forceOpen": True
    }

    try:
        trade_res = requests.post(
            f"{BASE_URL}/api/v1/positions",
            headers=trade_headers,
            json=trade_payload
        )
        trade_res.raise_for_status()
        return {"status": "ok", "response": trade_res.json()}
    except Exception as e:
        return {"status": "error", "message": str(e)}
