from fastapi import FastAPI, Request, HTTPException, Query
import os
import requests
import logging

# === FastAPI setup ===
app = FastAPI()

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# === Environment variables ===
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")

BASE_URL = "https://api-capital.backend-capital.com"
BASE_HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === Manual fallback EPICs ===
TICKER_TO_EPIC = {
    "XAUUSD": "CC.D.XAUUSD.CFD.IP",
    "XAGUSD": "CC.D.XAGUSD.CFD.IP",
    "EURUSD": "CS.D.EURUSD.MINI.IP",
    "USDJPY": "CS.D.USDJPY.MINI.IP",      # ✅ fallback
    "OIL": "CC.D.BRENT.CFD.IP",           # ✅ fallback
    "WTI": "CC.D.WTI.CFD.IP",             # optional alias
    "XNGUSD": "CC.D.NATGAS.CFD.IP",
    "NATURALGAS": "CC.D.NATGAS.CFD.IP"
}

# === Session token fetch ===
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

# === Fetch EPIC dynamically from API ===
def fetch_epic(symbol: str):
    try:
        url = f"{BASE_URL}/api/v1/markets?searchTerm={symbol}"
        response = requests.get(url, headers={
            "X-CAP-API-KEY": CAPITAL_API_KEY,
            "Accept": "application/json"
        })
        response.raise_for_status()
        data = response.json()
        markets = data.get("markets", [])
        if markets:
            return markets[0]["epic"]
    except Exception as e:
        logger.error(f"EPIC fetch failed: {e}")
    return None

# === Place live order ===
def place_order(direction: str, epic: str, size: float):
    session = get_session()
    if not session:
        return {"error": "Authentication failed"}

    headers = BASE_HEADERS.copy()
    headers.update(session)

    payload = {
        "epic": epic,
        "direction": direction.upper(),  # BUY or SELL
        "size": size
    }

    try:
        res = requests.post(f"{BASE_URL}/api/v1/positions", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logger.error(f"Trade failed: {e}")
        return {"error": str(e)}

# === Webhook /trade ===
@app.post("/trade")
async def receive_alert(request: Request):
    try:
        data = await request.json()
        direction = data.get("action")
        symbol = data.get("symbol", "").upper()
        size = float(data.get("size", 1))

        if direction not in ["buy", "sell"]:
            raise ValueError("Invalid action")

        # Check static or fetch epic
        epic = TICKER_TO_EPIC.get(symbol)
        if not epic:
            epic = fetch_epic(symbol)
        if not epic:
            return {"error": f"Could not find epic for: {symbol}"}

        result = place_order(direction, epic, size)
        return {"status": "ok", "response": result}

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# === Epic Lookup ===
@app.get("/check-epic")
def check_epic(symbol: str = Query(..., description="Search term like XAUUSD or USD/JPY")):
    try:
        url = f"{BASE_URL}/api/v1/markets?searchTerm={symbol}"
        response = requests.get(url, headers={
            "X-CAP-API-KEY": CAPITAL_API_KEY,
            "Accept": "application/json"
        })
        response.raise_for_status()
        markets = response.json().get("markets", [])
        if not markets:
            return {"status": "not_found", "symbol": symbol, "epics": []}
        return {
            "status": "ok",
            "symbol": symbol,
            "epics": [
                {
                    "name": m.get("instrumentName"),
                    "epic": m.get("epic"),
                    "type": m.get("instrumentType"),
                    "expiry": m.get("expiry", "-")
                } for m in markets
            ]
        }
    except Exception as e:
        logger.error(f"EPIC lookup failed: {e}")
        return {"status": "error", "message": str(e)}

# === Health check ===
@app.get("/")
def read_root():
    return {"status": "Capital Trading Bot is running"}
