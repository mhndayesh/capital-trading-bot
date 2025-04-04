import os
import requests
from fastapi import FastAPI

app = FastAPI()

# === CONFIG ===
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY") or "YOUR_API_KEY"
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL") or "your@email.com"
CAPITAL_PASS = os.getenv("CAPITAL_PASS") or "your_api_password"

# Use demo or live API
BASE_URL = "https://api-capital.backend-capital.com"
# For demo use: BASE_URL = "https://demo-api-capital.backend-capital.com"

# === LOGIN ===
session_url = f"{BASE_URL}/api/v1/session"
session_headers = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}
session_payload = {
    "identifier": CAPITAL_EMAIL,
    "password": CAPITAL_PASS,
    "encryptedPassword": False
}

try:
    login_response = requests.post(session_url, headers=session_headers, json=session_payload)
    login_response.raise_for_status()
    cst = login_response.headers.get("CST")
    xst = login_response.headers.get("X-SECURITY-TOKEN")
    if not cst or not xst:
        raise ValueError("Login failed: Missing CST or X-SECURITY-TOKEN")
    print("✅ Logged in successfully.")
except Exception as e:
    print("❌ Login failed:", e)
    exit()

# === TRADE PAYLOAD ===
trade_url = f"{BASE_URL}/api/v1/positions"
trade_headers = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "CST": cst,
    "X-SECURITY-TOKEN": xst,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Example trade — GOLD CFD
trade_payload = {
    "epic": "CC.D.XAUUSD.CFD.IP",     # GOLD epic
    "direction": "BUY",               # or "SELL"
    "size": 2,                        # Trade size
    "orderType": "MARKET",
    "currencyCode": "USD",
    "forceOpen": True,
    "guaranteedStop": False
}

# === SEND ORDER ===
try:
    trade_response = requests.post(trade_url, headers=trade_headers, json=trade_payload)
    trade_response.raise_for_status()
    print("✅ Trade placed successfully!")
    print("Response:", trade_response.json())
except Exception as e:
    print("❌ Trade failed:", e)
    print("Response:", trade_response.text)
