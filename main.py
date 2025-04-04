from fastapi import FastAPI, Request, HTTPException, Query
import os
import requests
import logging
from typing import Optional

# --- Setup basic logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

app = FastAPI()

# === Load Credentials from Environment Variables ===
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")

missing_vars = []
if not CAPITAL_EMAIL: missing_vars.append("CAPITAL_EMAIL")
if not CAPITAL_PASS: missing_vars.append("CAPITAL_PASS")
if not CAPITAL_API_KEY: missing_vars.append("CAPITAL_API_KEY")
if missing_vars:
    logger.critical(f"CRITICAL ERROR: Required environment variables are not set: {', '.join(missing_vars)}")

BASE_URL = "https://api-capital.backend-capital.com"
BASE_HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY if CAPITAL_API_KEY else "MISSING_API_KEY",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

TICKER_TO_EPIC = {
    "XAUUSD": "CC.D.XAUUSD.CFD.IP",
    "XAGUSD": "CC.D.XAGUSD.CFD.IP",
    "EURUSD": "CS.D.EURUSD.MINI.IP",
    "NATURALGAS": "CC.D.NATGAS.CFD.IP",
    "XNGUSD": "CC.D.NATGAS.CFD.IP",
}

def get_session_data():
    if not CAPITAL_EMAIL or not CAPITAL_PASS or not CAPITAL_API_KEY:
        logger.error("Cannot get session data: Email, Password, or API Key not configured.")
        return None
    auth_data = {"identifier": CAPITAL_EMAIL, "password": CAPITAL_PASS}
    session_url = f"{BASE_URL}/api/v1/session"
    try:
        response = requests.post(session_url, json=auth_data, headers=BASE_HEADERS, timeout=10)
        response.raise_for_status()
        response_json = response.json()
        cst_token = response.headers.get('CST')
        x_sec_token = response.headers.get('X-SECURITY-TOKEN')
        account_id = response_json.get('currentAccountId')
        if cst_token and x_sec_token and account_id:
            return {"cst": cst_token, "x_sec_token": x_sec_token, "account_id": str(account_id)}
        else:
            return None
    except Exception as e:
        logger.error(f"Session login failed: {e}")
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
    session_data = get_session_data()
    if not session_data:
        return {"error": "Authentication Failed", "details": "Could not obtain session tokens/accountId."}

    cst_token = session_data.get('cst')
    x_sec_token = session_data.get('x_sec_token')

    if not all([direction, epic, size]): return {"error": "Missing order parameters"}
    if direction.lower() not in ["buy", "sell"]: return {"error": f"Invalid direction: {direction}"}
    if size <= 0: return {"error": f"Invalid size: {size}"}

    position_data = {
        "epic": epic.upper(),
        "direction": direction.upper(),
        "size": size
    }

    headers_for_order = BASE_HEADERS.copy()
    headers_for_order['CST'] = cst_token
    headers_for_order['X-SECURITY-TOKEN'] = x_sec_token

    try:
        endpoint = f"{BASE_URL}/api/v1/positions"
        response = requests.post(endpoint, headers=headers_for_order, json=position_data, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Order failed: {e}")
        return {"error": str(e)}

@app.post("/trade")
async def receive_alert(request: Request):
    try:
        data = await request.json()
        logger.info(f"🚨 Alert received: {data}")
    except Exception as e:
        logger.error(f"Invalid JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON received")

    data_lower = {k.lower(): v for k, v in data.items()}
    direction = data_lower.get("action")
    symbol = data_lower.get("symbol")
    size_str = data_lower.get("size", "1")

    if not symbol:
        raise HTTPException(status_code=400, detail="'symbol' missing")
    if direction.lower() not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    epic = TICKER_TO_EPIC.get(symbol.upper())
    if not epic:
        raise HTTPException(status_code=400, detail=f"Epic not found for symbol: {symbol}")

    try:
        size = float(size_str)
        if size <= 0: raise ValueError
    except:
        size = get_trade_size(symbol)
        logger.info(f"Default size used for {symbol}: {size}")

    result = place_order(direction, epic, size)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result)
    return {"status": "ok", "capital_response": result}

@app.get("/check-epic")
def check_epic(symbol: str = Query(..., description="Symbol like XAUUSD, XAGUSD, EURUSD, etc.")):
    url = f"{BASE_URL}/api/v1/markets?searchTerm={symbol}"
    headers = {
        "X-CAP-API-KEY": CAPITAL_API_KEY,
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        markets = data.get("markets", [])
        if not markets:
            return {"status": "not_found", "symbol": symbol, "epics": []}
        epics = [
            {
                "name": m["instrumentName"],
                "epic": m["epic"],
                "type": m["instrumentType"],
                "expiry": m.get("expiry", "-")
            } for m in markets
        ]
        return {"status": "ok", "symbol": symbol, "epics": epics}
    except Exception as e:
        logger.error(f"Error checking EPIC for {symbol}: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/")
def read_root():
    return {"Status": "Capital.com Trading Bot is running"}
