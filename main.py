import os
import requests
from fastapi import FastAPI, HTTPException, Request
from dotenv import load_dotenv

load_dotenv()  # Optional for local .env testing

app = FastAPI()

CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")
CAPITAL_API_PASS = os.getenv("CAPITAL_PASS")
CAPITAL_API_EMAIL = os.getenv("CAPITAL_EMAIL")

BASE_URL = "https://api-capital.backend-capital.com"
SESSION_URL = f"{BASE_URL}/api/v1/session"
POSITIONS_URL = f"{BASE_URL}/api/v1/positions"

HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Static mapping
TICKER_TO_EPIC = {
    "GOLD": "CC.D.XAUUSD.CFD.IP",
    "SILVER": "CC.D.XAGUSD.CFD.IP",
    "EURUSD": "CS.D.EURUSD.CFD.IP",
    "USDJPY": "CS.D.USDJPY.CFD.IP",
    "OIL": "CC.D.BRENT.CFD.IP",  # Example
}



@app.post("/trade")
def place_order(data: dict):
    symbol = data.get("symbol")
    action = data.get("action")
    size = data.get("size")

    epic = TICKER_TO_EPIC.get(symbol.upper())
    if not epic:
        raise HTTPException(status_code=404, detail="EPIC not found")

    session_payload = {
        "identifier": CAPITAL_API_EMAIL,
        "password": CAPITAL_API_PASS,
        "encryptedPassword": False
    }

    login_response = requests.post(SESSION_URL, headers=HEADERS, json=session_payload)
    if login_response.status_code != 200:
        return {"status": "error", "message": "Login failed", "details": login_response.text}

    cst = login_response.headers.get("CST")
    x_sec = login_response.headers.get("X-SECURITY-TOKEN")

    if not cst or not x_sec:
        return {"status": "error", "message": "Missing CST or Security Token"}

    order_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CAP-API-KEY": CAPITAL_API_KEY,
        "CST": cst,
        "X-SECURITY-TOKEN": x_sec
    }

    order_payload = {
        "epic": epic,
        "direction": action.upper(),
        "size": size,
        "orderType": "MARKET",
        "timeInForce": "FILL_OR_KILL",
        "guaranteedStop": False,
        "forceOpen": True,
        "currencyCode": "USD"
    }

    order_response = requests.post(POSITIONS_URL, headers=order_headers, json=order_payload)

    if order_response.status_code == 200:
        return {"status": "ok", "response": order_response.json()}
    else:
        return {"status": "error", "message": order_response.text}
