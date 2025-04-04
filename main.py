from fastapi import FastAPI, Request, HTTPException, Query
import os
import requests
import logging
from typing import Optional

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-8s] %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# --- Environment Variables ---
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")

missing_vars = []
if not CAPITAL_EMAIL: missing_vars.append("CAPITAL_EMAIL")
if not CAPITAL_PASS: missing_vars.append("CAPITAL_PASS")
if not CAPITAL_API_KEY: missing_vars.append("CAPITAL_API_KEY")
if missing_vars:
    logger.critical(f"Missing environment variables: {', '.join(missing_vars)}")

BASE_URL = "https://api-capital.backend-capital.com"
BASE_HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY or "MISSING",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

TICKER_TO_EPIC = {
    "XAUUSD": "CC.D.XAUUSD.CFD.IP",
    "XAGUSD": "CC.D.XAGUSD.CFD.IP",
    "EURUSD": "CS.D.EURUSD.MINI.IP",
    "NATURALGAS": "CC.D.NATGAS.CFD.IP",
    "XNGUSD": "CC.D.NATGAS.CFD.IP"
}

def get_session_data():
    if not CAPITAL_EMAIL or not CAPITAL_PASS or not CAPITAL_API_KEY:
        logger.error("Missing credentials for session.")
        return None
    auth_data = {"identifier": CAPITAL_EMAIL, "password": CAPITAL_PASS}
    try:
        response = requests.post(f"{BASE_URL}/api/v1/session", json=auth_data, headers=BASE_HEADERS)
        response.raise_for_status()
        cst = response.headers.get("CST")
        x_sec = response.headers.get("X-SECURITY-TOKEN")
        account_id = response.json().get("currentAccountId")
        if cst and x_sec and account_id:
            return {"cst": cst, "x_sec_token": x_sec, "account_id": account_id}
    except Exception as e:
        logger.error(f"Session error: {e}")
    return None

def get_trade_size(symbol: str) -> float:
    symbol = symbol.upper()
    if "XAUUSD" in symbol: return 0.02
    if "XAGUSD" in symbol: return 10
    if "EURUSD" in symbol: return 10000
    if "BTCUSD" in symbol: return 0.001
    if "NATURALGAS" in symbol or "XNGUSD" in symbol: return 100
    return 1.0

def place_order(direction: str, epic: str, size: float):
    session = get_session_data()
    if not session:
        return {"error": "Authentication Failed"}
    headers = BASE_HEADERS.copy()
    headers.update({"CST": session["cst"], "X-SECURITY-TOKEN": session["x_sec_token"]})
    payload = {"epic": epic.upper(), "direction": direction.upper(), "size": size}
    try:
        response = requests.post(f"{BASE_URL}/api/v1/positions", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Order error: {e}")
        return {"error": str(e)}

@app.post("/trade")
async def receive_alert(request: Request):
    try:
        data = await request.json()
        logger.info(f"Received alert: {data}")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    data = {k.lower(): v for k, v in data.items()}
    direction = data.get("action")
    symbol = data.get("symbol")
    size_str = data.get("size", "1")

    if not symbol or direction not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="Missing or invalid fields")

    epic = TICKER_TO_EPIC.get(symbol.upper())
    if not epic:
        raise HTTPException(status_code=400, detail=f"EPIC not mapped for: {symbol}")

    try:
        size = float(size_str)
    except:
        size = get_trade_size(symbol)

    result = place_order(direction, epic, size)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result)
    return {"status": "ok", "capital_response": result}

@app.get("/check-epic")
def check_epic(symbol: str = Query(...)):
    url = f"{BASE_URL}/api/v1/markets?searchTerm={symbol}"
    headers = {
        "X-CAP-API-KEY": CAPITAL_API_KEY,
        "Accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        markets = response.json().get("markets", [])
        if not markets:
            return {"status": "not_found", "symbol": symbol, "epics": []}
        return {
            "status": "ok",
            "symbol": symbol,
            "epics": [
                {
                    "name": m["instrumentName"],
                    "epic": m["epic"],
                    "type": m["instrumentType"],
                    "expiry": m.get("expiry", "-")
                } for m in markets
            ]
        }
    except Exception as e:
        logger.error(f"EPIC lookup error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/")
def read_root():
    return {"status": "Capital.com Trading Bot is running"}
