from fastapi import FastAPI, Request, HTTPException, Query
import os
import requests
import logging

app = FastAPI()

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# === Capital.com Credentials ===
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")

BASE_URL = "https://api-capital.backend-capital.com"
BASE_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === Manual EPIC Mapping (fallbacks) ===
TICKER_TO_EPIC = {
    "GOLD": "CC.D.XAUUSD.CFD.IP",
    "SILVER": "CC.D.XAGUSD.CFD.IP",
    "EURUSD": "CS.D.EURUSD.CFD.IP",
    "USDJPY": "CS.D.USDJPY.CFD.IP",
    "OIL": "CC.D.WTI.CFD.IP",
    "NATGAS": "CC.D.NATGAS.CFD.IP"
}

def login_to_capital():
    url = f"{BASE_URL}/api/v1/session"
    payload = {
        "identifier": CAPITAL_EMAIL,
        "password": CAPITAL_PASS
    }
    response = requests.post(url, json=payload, headers=BASE_HEADERS)
    response.raise_for_status()
    return response.json().get("token")

@app.get("/")
def read_root():
    return {"status": "Capital Trading Bot is running"}

@app.get("/check-epic")
def check_epic(symbol: str = Query(..., description="Search term like XAUUSD or EURUSD")):
    url = f"{BASE_URL}/api/v1/markets?searchTerm={symbol}"
    try:
        response = requests.get(url, headers=BASE_HEADERS)
        response.raise_for_status()
        markets = response.json().get("markets", [])
        return {
            "status": "ok",
            "symbol": symbol,
            "epics": [
                {
                    "name": m["instrumentName"],
                    "epic": m["epic"],
                    "type": m["instrumentType"],
                    "expiry": m.get("expiry")
                } for m in markets
            ]
        }
    except Exception as e:
        logger.error(f"EPIC lookup failed: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/trade")
def trade(payload: dict):
    symbol = payload.get("symbol")
    action = payload.get("action")
    size = payload.get("size")

    epic = TICKER_TO_EPIC.get(symbol.upper())
    if not epic:
        return {"error": f"Could not find epic for: {symbol}"}

    try:
        token = login_to_capital()
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return {"error": f"Login failed: {e}"}

    order_url = f"{BASE_URL}/api/v1/positions"
    headers = {
        **BASE_HEADERS,
        "Authorization": f"Bearer {token}"
    }

    order_payload = {
        "epic": epic,
        "direction": action,
        "size": size,
        "orderType": "MARKET",
        "timeInForce": "FILL_OR_KILL",
        "dealReference": f"auto-{symbol.lower()}"
    }

    try:
        order_response = requests.post(order_url, json=order_payload, headers=headers)
        order_response.raise_for_status()
        return {"status": "ok", "response": order_response.json()}
    except Exception as e:
        logger.error(f"Order failed: {e}")
        return {"status": "error", "message": str(e)}
