from fastapi import FastAPI, Request, HTTPException
import os
import requests
import logging
import sys

# --- Setup basic logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

app = FastAPI()

# === Load Credentials from Environment Variables ===
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")
# ACCOUNT_ID is fetched dynamically

# --- Validate Credentials Needed ---
missing_vars = []
if not CAPITAL_EMAIL: missing_vars.append("CAPITAL_EMAIL")
if not CAPITAL_PASS: missing_vars.append("CAPITAL_PASS")
if not CAPITAL_API_KEY: missing_vars.append("CAPITAL_API_KEY")

if missing_vars:
    error_message = f"CRITICAL ERROR: Required environment variables are not set: {', '.join(missing_vars)}"
    logger.critical(error_message)
    # sys.exit(...) # Optional exit

# === Capital.com API Setup ===
BASE_URL = "https://api-capital.backend-capital.com"
BASE_HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY if CAPITAL_API_KEY else "MISSING_API_KEY",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === !!! IMPORTANT: Placeholder EPIC MAPPING DICTIONARY !!! ===
# You will fill this in the *final* version of the code *after* finding epics
TICKER_TO_EPIC = {
    "XAUUSD": "PLACEHOLDER_XAUUSD",
    "EURUSD": "PLACEHOLDER_EURUSD",
    # Add placeholders for others
}
# ==================================================

# === Authentication Function (Modified to return full session data) ===
def get_session_data(): # Renamed for clarity
    """Logs in, returns dict with tokens and accountId, or None."""
    # ... (Keep the get_session_tokens function code from the previous full code example) ...
    # ... (Ensure it returns {'cst': ..., 'x_sec_token': ..., 'account_id': ...} or None) ...
    # --- [Code from previous example for get_session_tokens goes here] ---
    if not CAPITAL_EMAIL or not CAPITAL_PASS or not CAPITAL_API_KEY: # Check all needed
        logger.error("Cannot get session data: Email, Password, or API Key not configured.")
        return None
    auth_data = {"identifier": CAPITAL_EMAIL,"password": CAPITAL_PASS}
    session_url = f"{BASE_URL}/api/v1/session"
    logger.info(f"Attempting session login to {session_url} with user {CAPITAL_EMAIL}")
    try:
        response = requests.post(session_url, json=auth_data, headers=BASE_HEADERS, timeout=10)
        logger.info(f"Session Response Status Code: {response.status_code}")
        logger.debug(f"Session Response Headers: {response.headers}")
        response_json = {}
        try:
            response_json = response.json()
            logger.info(f"Session Response Body: {response_json}")
        except requests.exceptions.JSONDecodeError: logger.info(f"Session Response Body (Non-JSON): {response.text}")
        except Exception as json_e: logger.error(f"Error decoding session response JSON: {json_e}")
        response.raise_for_status()
        cst_token = response.headers.get('CST')
        x_sec_token = response.headers.get('X-SECURITY-TOKEN')
        account_id = response_json.get('currentAccountId')
        logger.info(f"Extracted CST from Headers: {'FOUND' if cst_token else 'MISSING'}")
        logger.info(f"Extracted X-SECURITY-TOKEN from Headers: {'FOUND' if x_sec_token else 'MISSING'}")
        logger.info(f"Extracted accountId from Body: {account_id if account_id else 'MISSING'}")
        if cst_token and x_sec_token and account_id:
            logger.info("🔐 Successfully obtained session tokens and Account ID.")
            return {"cst": cst_token, "x_sec_token": x_sec_token, "account_id": str(account_id)}
        else:
            missing = [item for item, val in [("CST Header", cst_token), ("X-SECURITY-TOKEN Header", x_sec_token), ("currentAccountId in Body", account_id)] if not val]
            logger.error(f"Failed to extract required items from session response: {', '.join(missing)}")
            return None
    except requests.exceptions.HTTPError as http_err: logger.error(f"HTTP error getting session token: {http_err}"); return None
    except requests.exceptions.RequestException as req_err: logger.error(f"Request failed getting session token: {req_err}"); return None
    except Exception as e: logger.error(f"Unexpected error getting session token: {e}", exc_info=True); return None
    # --- [End of get_session_tokens code] ---


# === Place Order Function (Keep the corrected version using /positions) ===
def place_order(direction: str, epic: str, size: float):
    """Authenticates, prepares headers/payload, and sends request to open position."""
    session_data = get_session_data() # Use renamed function
    if not session_data:
        return {"error": "Authentication Failed", "details": "Could not obtain session tokens/accountId."}
    dynamic_account_id = session_data.get('account_id')
    cst_token = session_data.get('cst')
    x_sec_token = session_data.get('x_sec_token')
    if not all([direction, epic, size]): return {"error": "Missing order parameters"}
    if direction.lower() not in ["buy", "sell"]: return {"error": f"Invalid direction: {direction}"}
    if size <= 0: return {"error": f"Invalid size: {size}"}
    if not dynamic_account_id: return {"error": "Could not determine Account ID from session."}
    position_data = { "epic": epic.upper(), "direction": direction.upper(), "size": size }
    headers_for_order = BASE_HEADERS.copy()
    headers_for_order['CST'] = cst_token
    headers_for_order['X-SECURITY-TOKEN'] = x_sec_token
    endpoint = f"{BASE_URL}/api/v1/positions" # Using /positions endpoint
    logger.info(f"📤 Sending position request to {endpoint}: {position_data}")
    logger.debug(f"  Using Headers: {headers_for_order}")
    try:
        response = requests.post(endpoint, headers=headers_for_order, json=position_data, timeout=15)
        response.raise_for_status()
        logger.info(f"🧾 Position response: {response.status_code} {response.text}")
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error opening position: {http_err} - Response: {response.text}")
        try: error_details = response.json()
        except: error_details = response.text
        return {"error": f"HTTP {response.status_code}", "details": error_details}
    # ... (keep other exception handling) ...
    except Exception as e:
        logger.error(f"Unexpected error during position placement: {e}", exc_info=True); return {"error": "Unknown position error"}


# === FastAPI Webhook Endpoint (Modified to use TICKER_TO_EPIC map) ===
@app.post("/trade")
async def receive_alert(request: Request):
    """Receives trade alerts (webhooks) from TradingView."""
    try: data = await request.json(); logger.info(f"🚨 Alert received: {data}")
    except Exception as e: logger.error(f"Failed to parse request JSON: {e}"); raise HTTPException(status_code=400, detail="Invalid JSON")
    data_lower = {k.lower(): v for k, v in data.items()}
    direction = data_lower.get("action"); symbol = data_lower.get("symbol"); size_str = data_lower.get("size", "1")
    if not symbol: logger.error("Webhook Error: 'symbol' missing."); raise HTTPException(status_code=400, detail="'symbol' missing")
    if not direction or direction.lower() not in ["buy", "sell"]: logger.error(f"Webhook Error: Invalid 'action': '{direction}'."); raise HTTPException(status_code=400, detail=f"Invalid action: {direction}")
    epic = TICKER_TO_EPIC.get(symbol.upper()) # Look up epic
    if not epic or "PLACEHOLDER" in epic: logger.error(f"Webhook Error: Epic not found or is placeholder for symbol '{symbol}'."); raise HTTPException(status_code=400, detail=f"Epic mapping not found/configured for symbol: {symbol}")
    try: size = float(size_str); assert size > 0
    except: logger.warning(f"Invalid 'size': '{size_str}'. Using default."); size = 1.0 # Default or use get_trade_size(symbol)
    result = place_order(direction, epic, size) # Use epic
    if "error" in result:
        detail = result.get("details", str(result.get("error", "Unknown Error")))
        status = 500 # Default
        if result.get("error") == "Authentication Failed" : status = 503
        elif '"status":404' in str(detail): status = 404
        elif result.get("error", "").startswith("HTTP 4"): status = 400
        elif result.get("error") == "Request Timeout": status = 504
        raise HTTPException(status_code=status, detail=detail)
    else: return {"status": "ok", "capital_response": result}

# === ### ADDED: Endpoint to Fetch Market Details ### ===
@app.get("/find_epics")
async def find_market_epics(searchTerm: str = None): # Optional searchTerm
    """
    Fetches market details from Capital.com API.
    Use query parameter ?searchTerm=SYMBOL (e.g., /find_epics?searchTerm=XAUUSD)
    or leave blank to get all markets (might be slow/large).
    AUTHENTICATION REQUIRED. Result logged to Render logs.
    """
    logger.info(f"Received request to find epics. SearchTerm: {searchTerm}")
    session_data = get_session_data()
    if not session_data:
        raise HTTPException(status_code=503, detail="Could not authenticate session to fetch markets.")

    # Prepare headers for market request
    market_headers = BASE_HEADERS.copy()
    market_headers['CST'] = session_data['cst']
    market_headers['X-SECURITY-TOKEN'] = session_data['x_sec_token']

    # Prepare URL with optional searchTerm
    market_url = f"{BASE_URL}/api/v1/markets"
    params = {}
    if searchTerm:
        params['searchTerm'] = searchTerm.upper()

    logger.info(f"Fetching market details from {market_url} with params {params}")

    try:
        response = requests.get(market_url, headers=market_headers, params=params, timeout=20) # Longer timeout for potentially large response
        response.raise_for_status()
        market_data = response.json()
        # Log the crucial info - might be large!
        logger.info(f"Market data received (showing first 500 chars): {str(market_data)[:500]}...")
        # Log specifically if searching and found markets
        if searchTerm and market_data.get("markets"):
            logger.info(f"Found {len(market_data['markets'])} market(s) matching '{searchTerm}'. Check details below or full log.")
            for market in market_data.get("markets", []):
                 logger.info(f"  -> Market: {market.get('instrumentName')}, EPIC: {market.get('epic')}")

        return {"status": "ok", "message": "Market data logged. Check Render logs.", "data_preview": market_data} # Return data as well

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error fetching markets: {http_err} - Response: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=response.text)
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request failed fetching markets: {req_err}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to Capital.com API: {req_err}")
    except Exception as e:
        logger.error(f"Unexpected error fetching markets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected server error fetching markets: {e}")
# === ### END ADDED Endpoint ### ===


# Optional: Add a root endpoint for health checks
@app.get("/")
def read_root():
    return {"Status": "Capital.com Trading Bot is running"}

# Note: Local run command would be: uvicorn main:app --host 0.0.0.0 --port 10000
