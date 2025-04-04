from fastapi import FastAPI, Request
import os
import requests

app = FastAPI()

# Capital.com credentials from environment variables
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")
CAPITAL_ACCOUNT_ID = "33244876"

BASE_URL = "https://api-capital.backend-capital.com"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === Trade size logic ===
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
    return 1  # default fallback

# === Get Bearer Token ===
def get_auth_token():
    login_data = {
        "identifier": CAPITAL_EMAIL,
        "password": CAPITAL_PASS
    }
    response = requests.post(f"{BASE_URL}/api/v1/session", json=login_data, headers=HEADERS)
    token = response.json().get("token")
    return token

# === Place Order ===
def place_order(direction: str, symbol: str):
    quantity = get_trade_size(symbol)
    token = get_auth_token()
    if not token:
        return {"error": "❌ Failed to authenticate — token is null."}

    order_data = {
        "market": symbol,
        "side": direction.lower(),
        "type": "market",
        "quantity": quantity,
        "accountId": CAPITAL_ACCOUNT_ID
    }

    print("📤 Sending order to Capital.com:", order_data)
    headers_with_auth = HEADERS.copy()
    headers_with_auth["Authorization"] = f"Bearer {token}"
    response = requests.post(f"{BASE_URL}/api/v1/orders", headers=headers_with_auth, json=order_data)
    print("🧾 Response:", response.status_code, response.text)
    return response.json()

# === Webhook endpoint ===
@app.post("/trade")
async def receive_alert(request: Request):
    try:
        data = await request.json()
        print("🚨 Alert received:", data)

        side = data.get("side")
        symbol = data.get("symbol")

        if not side or not symbol:
            return {"error": "Missing required 'side' or 'symbol' field."}

        return place_order(side, symbol)

    except Exception as e:
        return {"error": str(e)}
