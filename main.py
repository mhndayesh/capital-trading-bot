from fastapi import FastAPI, Request, HTTPException
import os
import requests

app = FastAPI()

# === ENV VARIABLES ===
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")

# === HARDCODED EPICS ===
TICKER_TO_EPIC = {
    "GOLD": "CC.D.XAUUSD.CFD.IP",
    "SILVER": "CC.D.XAGUSD.CFD.IP",
    "USDJPY": "CS.D.USDJPY.CFD.IP",
    "EURUSD": "CS.D.EURUSD.CFD.IP",
    "NATURALGAS": "CC.D.NATGAS.CFD.IP",
    "OIL": "CC.D.BRENT.CFD.IP",  # or "CC.D.WTI.CFD.IP"
}

# === AUTH ===
def get_auth_token():
    url = "https://api-capital.backend-capital.com/api/v1/session"
    payload = {
        "identifier": CAPITAL_EMAIL,
        "password": CAPITAL_PASS
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    data = response.json()
    return {
        "Authorization": f"Bearer {data['oauthToken']['access_token']}",
        "CST": data['accountInfo']['clientId'],
        "X-SECURITY-TOKEN": data['oauthToken']['access_token'],
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

# === TRADE EXECUTION ===
def place_trade(symbol: str, action: str, size: int):
    epic = TICKER_TO_EPIC.get(symbol.upper())
    if not epic:
        return {"error": f"Could not find epic for: {symbol}"}

    headers = get_auth_token()
    payload = {
        "epic": epic,
        "direction": action.upper(),
        "size": size,
        "orderType": "MARKET",
        "timeInForce": "FILL_OR_KILL",
        "guaranteedStop": False,
        "forceOpen": True,
        "currencyCode": "USD"
    }

    url = "https://api-capital.backend-capital.com/api/v1/positions"
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return {"status": "ok", "response": response.json()}

# === API ENDPOINT ===
@app.post("/trade")
async def receive_alert(req: Request):
    data = await req.json()
    symbol = data.get("symbol")
    action = data.get("action")
    size = data.get("size")

    if not all([symbol, action, size]):
        raise HTTPException(status_code=400, detail="Missing parameters.")

    try:
        result = place_trade(symbol, action, int(size))
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def root():
    return {"status": "Capital bot is live ✅"}
