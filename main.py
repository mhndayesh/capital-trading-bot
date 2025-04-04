from fastapi import FastAPI, Request
import requests

app = FastAPI()

# === Capital.com account credentials ===
CAPITAL_API_KEY = "hPazUxfmhcehPjtd"
CAPITAL_ACCOUNT_ID = "33244876"

# === Capital.com API config ===
BASE_URL = "https://api-capital.backend-capital.com"
HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
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

# === Send order to Capital.com ===
def place_order(direction: str, symbol: str):
    size = get_trade_size(symbol)

    order_data = {
        "market": symbol,
        "side": direction.lower(),  # "buy" or "sell"
        "type": "market",           # market execution
        "quantity": size,
        "accountId": CAPITAL_ACCOUNT_ID
    }

    print("📤 Sending order to Capital.com:", order_data)

    try:
        response = requests.post(f"{BASE_URL}/api/v1/orders", headers=HEADERS, json=order_data)
        print("🧾 Response:", response.status_code, response.text)
        return response.json()
    except Exception as e:
        print("❌ Request failed:", str(e))
        return {"error": str(e)}

# === Webhook to receive alerts from TradingView ===
@app.post("/trade")
async def receive_alert(request: Request):
    data = await request.json()
    print("🚨 Alert received:", data)

    side = data.get("side")
    symbol = data.get("symbol")

    if not side or not symbol:
        return {"error": "Missing 'side' or 'symbol' in alert."}
    
    if side.lower() not in ["buy", "sell"]:
        return {"error": "Invalid side. Must be 'buy' or 'sell'."}

    return place_order(side, symbol)
