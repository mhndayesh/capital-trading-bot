from fastapi import FastAPI, Request
import requests

app = FastAPI()

# ✅ Your Capital.com credentials
CAPITAL_API_KEY = "hPazUxfmhcehPjtd"
CAPITAL_ACCOUNT_ID = "33244876"

# ✅ Capital.com API setup
BASE_URL = "https://api-capital.backend-capital.com"
HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# ✅ Trade size logic based on symbol
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
    else:
        return 1  # default fallback

# ✅ Send live market order
def place_order(direction: str, symbol: str):
    size = get_trade_size(symbol)
    order_data = {
        "market": symbol,
        "side": direction.lower(),  # must be "buy" or "sell"
        "type": "market",           # instant execution
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

# ✅ Webhook route for TradingView alerts
@app.post("/trade")
async def trade_alert(request: Request):
    try:
        data = await request.json()
        print("🚨 Alert received:", data)

        side = data.get("side")
        symbol = data.get("symbol", "XAUUSD")  # default to gold
        if side not in ["buy", "sell"]:
            return {"error": "Invalid order side. Use 'buy' or 'sell'."}

        return place_order(side, symbol)

    except Exception as e:
        return {"error": str(e)}
