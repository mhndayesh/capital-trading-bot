from fastapi import FastAPI, Request
import os
import requests

app = FastAPI()

# Capital.com credentials (loaded from environment)
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")
CAPITAL_ACCOUNT_ID = "33244876"

# Capital.com base URL
BASE_URL = "https://api-capital.backend-capital.com"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Step 1: Authenticate and get bearer token
def get_auth_token():
    auth_data = {
        "identifier": CAPITAL_EMAIL,
        "password": CAPITAL_PASS
    }
    response = requests.post(f"{BASE_URL}/api/v1/session", json=auth_data, headers=HEADERS)
    data = response.json()
    token = data.get("token")
    return token

# Step 2: Determine quantity based on symbol
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
    return 1  # fallback

# Step 3: Send market order to Capital.com
def place_order(direction: str, symbol: str):
    token = get_auth_token()
    if not token:
        return {"error": "❌ Failed to authenticate — token is null."}

    quantity = get_trade_size(symbol)
    order_data = {
        "market": symbol,
        "side": direction.lower(),
        "type": "market",
        "quantity": quantity,
        "accountId": CAPITAL_ACCOUNT_ID
    }

    headers_with_auth = HEADERS.copy()
    headers_with_auth["Authorization"] = f"Bearer {token}"

    print("📤 Sending order to Capital.com:", order_data)
    response = requests.post(f"{BASE_URL}/api/v1/orders", headers=headers_with_auth, json=order_data)
    print("🧾 Response:", response.status_code, response.text)
    return response.json()

# Step 4: Webhook to receive TradingView alerts
@app.post("/trade")
async def trade_alert(request: Request):
    data = await request.json()
    print("🚨 Alert received:", data)

    side = data.get("side")
    symbol = data.get("symbol")

    if not side or not symbol:
        return {"error": "Missing 'side' or 'symbol'"}

    return place_order(side, symbol)
