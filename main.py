from fastapi import FastAPI, Request
import os
import requests

app = FastAPI()

# ✅ Load credentials from environment variables (Render)
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")
CAPITAL_ACCOUNT_ID = "33244876"

# ✅ Capital.com API base setup
BASE_URL = "https://api-capital.backend-capital.com"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# ✅ Get authentication token using email + password
def get_auth_token():
    auth_data = {
        "identifier": CAPITAL_EMAIL,
        "password": CAPITAL_PASS
    }
    response = requests.post(f"{BASE_URL}/api/v1/session", json=auth_data, headers=HEADERS)
    print("🔐 Auth response:", response.status_code, response.text)

    if response.status_code == 200:
        return response.json().get("token")
    return None

# ✅ Return trade size based on symbol
def get_trade_size(symbol: str) -> float:
    symbol = symbol.upper()
    if symbol == "XAUUSD":
        return 2
    elif symbol == "XAGUSD":
        return 150
    elif symbol == "EURUSD":
        return 8000
    elif symbol == "XNGUSD":
        return 2000
    return 1  # default

# ✅ Place order to Capital.com
def place_order(direction: str, symbol: str = "XAUUSD"):
    token = get_auth_token()
    if not token:
        return {"error": "❌ Failed to authenticate — token is null."}

    size = get_trade_size(symbol)
    headers_with_auth = HEADERS.copy()
    headers_with_auth["Authorization"] = f"Bearer {token}"

    order_data = {
        "market": symbol,
        "side": direction.lower(),  # "buy" or "sell"
        "type": "market",
        "quantity": size,
        "accountId": CAPITAL_ACCOUNT_ID
    }

    print("📤 Sending order to Capital.com:", order_data)
    response = requests.post(f"{BASE_URL}/api/v1/orders", headers=headers_with_auth, json=order_data)
    print("🧾 Order response:", response.status_code, response.text)

    return response.json()

# ✅ FastAPI webhook endpoint (TradingView will post here)
@app.post("/trade")
async def trade_alert(request: Request):
    data = await request.json()
    print("🚨 Alert received:", data)

    side = data.get("side")
    symbol = data.get("symbol", "XAUUSD")

    if side not in ["buy", "sell"]:
        return {"error": "Invalid order side"}

    return place_order(side, symbol)
