from fastapi import FastAPI, Request
import requests

app = FastAPI()

# ✅ Your Capital.com credentials (DO NOT SHARE THIS)
CAPITAL_API_KEY = "hPazUxfmhcehPjtd"
CAPITAL_ACCOUNT_ID = "33244876"

# Capital.com API details
BASE_URL = "https://api-capital.backend-capital.com"
HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# ✅ Send order to Capital.com
def place_order(direction: str, symbol: str = "XAUUSD", size: float = 1):
    order_data = {
        "market": symbol,
        "side": direction.lower(),  # buy or sell
        "type": "market",
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

# ✅ Webhook endpoint from TradingView alerts
@app.post("/trade")
async def trade_alert(request: Request):
    try:
        data = await request.json()
        print("🚨 Alert received:", data)

        side = data.get("side")
        symbol = data.get("symbol", "XAUUSD")
        size = data.get("size", 1)

        if side not in ["buy", "sell"]:
            return {"error": "Invalid side. Use 'buy' or 'sell'."}

        return place_order(side, symbol, size)

    except Exception as e:
        return {"error": str(e)}
