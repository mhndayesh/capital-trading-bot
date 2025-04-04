from fastapi import FastAPI, Request, HTTPException, Query
import os
import requests
import logging

app = FastAPI()

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# === Capital.com Credentials ===
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")

BASE_URL = "https://api-capital.backend-capital.com"
BASE_HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === Manual EPIC Mapping (fallbacks) ===
TICKER_TO_EPIC = {
    "GOLD": "GOLD",
    "SILVER": "SILVER",
    "XAUUSD": "CC.D.XAUUSD.CFD.IP",
    "XAGUSD": "CC.D.XAGUSD.CFD.IP",
    "EURUSD": "CS.D.EURUSD.MINI.IP",
    "USDJPY": "CS.D.USDJPY.MINI.IP",
    "NATURALGAS": "CC.D.NATGAS.CFD.IP",
    "XNGUSD": "CC.D.NATGAS.CFD.IP"
}

# === Capital Session ===
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

# === Place Order ===
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

# === /trade webhook ===
@app.post("/trade")
async def receive_alert(request: Request):
    try:
        data = await request.json()
        symbol = data.get("symbol")
        direction = data.get("action")
        size = float(data.get("size", 1))

        if not symbol or not direction:
            raise HTTPException(status_code=400, detail="Missing required fields")

        # Lookup epic
        epic = TICKER_TO_EPIC.get(symbol.upper())
        if not epic:
            return {"error": f"Could not find epic for: {symbol}"}

        result = place_order(direction, epic, size)
        return {"status": "ok", "response": result}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# === /check-epic route ===
@app.get("/check-epic")
def check_epic(symbol: str = Query(..., description="Search any symbol like USDJPY or GOLD")):
    url = f"{BASE_URL}/api/v1/markets?searchTerm={symbol}"
    headers = {
        "X-CAP-API-KEY": CAPITAL_API_KEY,
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return {
            "status": "ok",
            "symbol": symbol,
            "epics": data.get("markets", [])
        }
    except Exception as e:
        logger.error(f"EPIC lookup failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

# === Health check ===
@app.get("/", include_in_schema=False)
@app.head("/", include_in_schema=False)
def root():
    return {"status": "Capital Bot is running ✅"}
