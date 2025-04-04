from fastapi import FastAPI, Request, HTTPException
import os
import requests
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")

BASE_URL = "https://api-capital.backend-capital.com"
BASE_HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
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

def get_session():
    try:
        res = requests.post(f"{BASE_URL}/api/v1/session", headers=BASE_HEADERS, json={
            "identifier": CAPITAL_EMAIL,
            "password": CAPITAL_PASS
        })
        res.raise_for_status()
        return {
            "CST": res.headers.get("CST"),
            "X-SECURITY-TOKEN": res.headers.get("X-SECURITY-TOKEN")
        }
    except Exception as e:
        logger.error(f"Session login failed: {e}")
        return None

def place_order(direction: str, epic: str, size: float):
    session = get_session()
    if not session:
        return {"error": "Authentication failed"}

    headers = BASE_HEADERS.copy()
    headers.update(session)

    payload = {
        "epic": epic,
        "direction": direction.upper(),
        "size": size
    }

    try:
        res = requests.post(f"{BASE_URL}/api/v1/positions", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logger.error(f"Trade failed: {e}")
        return {"error": str(e)}

@app.post("/trade")
async def receive_alert(request: Request):
    try:
        data = await request.json()
        direction = data.get("action")
        symbol = data.get("symbol", "XAUUSD")
        size = float(data.get("size", 1))

        if direction not in ["buy", "sell"]:
            raise ValueError("Invalid action")

        epic = TICKER_TO_EPIC.get(symbol.upper())
        if not epic:
            return {"error": f"Unknown symbol: {symbol}"}

        result = place_order(direction, epic, size)
        return {"status": "ok", "response": result}

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
def read_root():
    return {"status": "Capital Trading Bot is running"}


from fastapi import Query  # make sure this is at the top if not already

from fastapi import Query

@app.get("/check-epic")
def check_epic(symbol: str = Query(..., description="Search symbol like XAUUSD")):
    # Step 1: Login and get session tokens
    login_url = f"{BASE_URL}/api/v1/session"
    login_payload = {
        "identifier": CAPITAL_EMAIL,
        "password": CAPITAL_PASS
    }

    try:
        login_response = requests.post(login_url, json=login_payload, headers=BASE_HEADERS)
        login_response.raise_for_status()
        cst = login_response.headers.get("CST")
        x_sec = login_response.headers.get("X-SECURITY-TOKEN")
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return {"status": "error", "message": f"Login failed: {str(e)}"}

    # Step 2: Use session tokens to call /markets
    search_url = f"{BASE_URL}/api/v1/markets?searchTerm={symbol}"
    headers = {
        "X-CAP-API-KEY": CAPITAL_API_KEY,
        "CST": cst,
        "X-SECURITY-TOKEN": x_sec,
        "Accept": "application/json"
    }

    try:
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        data = response.json().get("markets", [])
        if not data:
            return {"status": "not_found", "symbol": symbol, "epics": []}

        return {
            "status": "ok",
            "symbol": symbol,
            "epics": [
                {
                    "name": m.get("instrumentName"),
                    "epic": m.get("epic"),
                    "type": m.get("instrumentType"),
                    "expiry": m.get("expiry")
                } for m in data
            ]
        }
    except Exception as e:
        logger.error(f"EPIC lookup failed: {e}")
        return {"status": "error", "message": str(e)}
