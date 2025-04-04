from fastapi import FastAPI, Request
import os
import requests

app = FastAPI()

# Capital.com API credentials (set in Render environment or hardcoded for testing)
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY") or "hPazUxfmhcehPjtd"
CAPITAL_ACCOUNT_ID = os.getenv("CAPITAL_ACCOUNT_ID") or "33244876"

# Capital.com API URL and headers
BASE_URL = "https://api-capital.backend-capital.com"
HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Function to send real market order
def place_order(direction: str, symbol: str = "XAUUSD", size: float = 1):
    order_data = {
        "market": symbol,
        "side": direction.lower(),  # must be "buy" or "sell"
        "type": "market",           # instant market execution
        "quantity": size,
        "accountId": CAPITAL_ACCOUNT_ID
    }

    print("📤 Sending order to Capital.com:", order_data)

    try:
        response = requests.post(f"{BASE_URL}/api/v1/orders", headers=HEADERS, json=order_data)
        print("🧾 Response:", response.status_code, response.text)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# Webhook endpoint to receive TradingView alerts
@app.post("/trade")
async def trade_alert(request: Request):
    try:
        data = await request.json()
        print("🚨 Alert received:", data)

        side = data.get("side")
        symbol = data.get("symbol", "XAUUSD")
        size = data.get("size", 1)

        if side not in ["buy", "sell"]:
            return {"error": "Invalid order side. Use 'buy' or 'sell'."}

        # Place the trade
        return place_order(side, symbol, size)

    except Exception as e:
        return {"error": str(e)}
