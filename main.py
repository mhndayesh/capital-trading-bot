from fastapi import FastAPI, Request, HTTPException
import os
import requests
import logging

app = FastAPI()

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# === Capital.com credentials from environment ===
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
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
    "XNGUSD": "CC.D.NATGAS.CFD.IP"
}

# === Session login to get CST and X-SECURITY-TOKEN ===
def get_session_tokens():
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
        logger.error(f"Login failed: {e}")
        return None

# === Place a trade ===
def place_order(direction: str, epic: str, size: float):
    session = get_session_tokens()
    if not session:
        return {"error": "Authentication failed"}

    headers = BASE_HEADERS.copy()
    headers.update(session)

    order_payload = {
        "epic": epic,
        "direction": direction.upper(),  # BUY or SELL
        "size": size,
        "orderType": "MARKET"
    }

    try:
        response = requests.post(f"{BASE_URL}/api/v1/positions", headers=headers, json=order_payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Order failed: {e}")
        return {"error": str(e)}

# === Webhook endpoint ===
@app.post("/trade")
async def trade_handler(request: Request):
    try:
        data = await request.json()
        symbol = data.get("symbol", "").upper()
        direction = data.get("action", "").lower()
        size = float(data.get("size", 1))

        epic = TICKER_TO_EPIC.get(symbol)
        if not epic:
            return {"error": f"Could not find epic for: {symbol}"}

        if direction not in ["buy", "sell"]:
            return {"error": f"Invalid action: {direction}"}

        result = place_order(direction, epic, size)
        return {"status": "ok", "response": result}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# === Health check ===
@app.get("/")
def root():
    return {"status": "Bot running ✅"}
