from fastapi import FastAPI, Request, HTTPException, Query
import os
import requests
import logging

app = FastAPI()

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# === Env ===
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")

BASE_URL = "https://api-capital.backend-capital.com"
BASE_HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === Auth ===
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

# === Lookup EPIC from Capital.com ===
def fetch_epic(symbol: str):
    try:
        url = f"{BASE_URL}/api/v1/markets?searchTerm={symbol}"
        res = requests.get(url, headers={
            "X-CAP-API-KEY": CAPITAL_API_KEY,
            "Accept": "application/json"
        })
        res.raise_for_status()
        markets = res.json().get("markets", [])
        for m in markets:
            if m.get("instrumentType") == "COMMODITIES" and m.get("expiry") in ["-", None]:
                return m.get("epic")
        if markets:
            return markets[0].get("epic")
    except Exception as e:
        logger.error(f"EPIC fetch failed: {e}")
    return None

# === Place order ===
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

# === POST /trade ===
@app.post("/trade")
async def receive_alert(request: Request):
    try:
        data = await request.json()
        direction = data.get("action")
        symbol = data.get("symbol", "XAUUSD")
        size = float(data.get("size", 1))

        if direction not in ["buy", "sell"]:
            raise ValueError("Invalid action")

        epic = fetch_epic(symbol)
        if not epic:
            return {"error": f"Could not find epic for: {symbol}"}

        result = place_order(direction, epic, size)
        return {"status": "ok", "epic": epic, "response": result}

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# === GET / ===
@app.get("/")
def root():
    return {"status": "Capital Bot running"}
