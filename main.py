from fastapi import FastAPI, Request
import os
import requests

app = FastAPI()

CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")
CAPITAL_ACCOUNT_ID = os.getenv("CAPITAL_ACCOUNT_ID")

BASE_URL = "https://api-capital.backend-capital.com"
HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def place_order(direction: str, symbol: str = "XAUUSD", size: float = 1):
    order_data = {
        "market": symbol,
        "side": direction.lower(),  # "buy" or "sell"
        "type": "market",
        "quantity": size,
        "accountId": CAPITAL_ACCOUNT_ID
    }

    response = requests.post(
        f"{BASE_URL}/order/new",
        headers=HEADERS,
        json=order_data
    )

    return response.status_code, response.json()

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    action = data.get("action", "").upper()

    if action in ["BUY", "SELL"]:
        status_code, response = place_order(action)
        return {"status": "ok", "details": response, "code": status_code}
    else:
        return {"status": "ignored", "message": "Invalid action"}
