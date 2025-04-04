from fastapi import FastAPI, Request, HTTPException
import os
import requests
import logging
import sys # For sys.exit on critical error

# --- Setup basic logging ---
# Logs will appear in Render's log stream
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

app = FastAPI()

# === Load Credentials from Environment Variables ===
# These MUST be set in your Render Environment Variables settings
CAPITAL_EMAIL = os.getenv("CAPITAL_EMAIL")
CAPITAL_PASS = os.getenv("CAPITAL_PASS")
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")
# Note: ACCOUNT_ID is now fetched dynamically from session
# Note: CAPITAL_SECURITY_TOKEN env var is NO LONGER needed, we get it from the session

# --- Validate Credentials Needed for Session Login ---
missing_vars = []
if not CAPITAL_EMAIL: missing_vars.append("CAPITAL_EMAIL")
if not CAPITAL_PASS: missing_vars.append("CAPITAL_PASS")
if not CAPITAL_API_KEY: missing_vars.append("CAPITAL_API_KEY") # Still needed for headers

if missing_vars:
    error_message = f"CRITICAL ERROR: Required environment variables are not set: {', '.join(missing_vars)}"
    logger.critical(error_message)
    # Consider exiting if critical variables are missing in production
    # sys.exit(f"Exiting: Missing environment variables: {', '.join(missing_vars)}")


# === Capital.com API Setup ===
# <<<!!! Double-Check This BASE URL in Capital.com API Docs if errors persist !!!>>>
BASE_URL = "https://api-capital.backend-capital.com" # Production API endpoint
# Demo endpoint (if needed for testing): "https://demo-api-capital.backend-capital.com"

# Base headers (API key is usually needed for most/all requests)
# Ensure CAPITAL_API_KEY is loaded before this dictionary is defined
BASE_HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY if CAPITAL_API_KEY else "MISSING_API_KEY", # Use loaded key or placeholder
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === !!! IMPORTANT: EPIC MAPPING DICTIONARY !!! ===
# You MUST find the correct Capital.com 'epic' for each TradingView 'ticker'
# Use Capital.com docs or GET /markets?searchTerm=... API call to find these.
TICKER_TO_EPIC = {
    "XAUUSD": "GOLD",           # Confirmed
    "XAGUSD": "SILVER",         # Confirmed
    "EURUSD": "EURUSD",         # Confirmed
    "NATURALGAS": "PLACEHOLDER_FIND_NATGAS_EPIC", # <<<=== FIND AND REPLACE THIS
    "XNGUSD": "PLACEHOLDER_FIND_NATGAS_EPIC",     # <<<=== FIND AND REPLACE THIS (if needed)
    # Add mappings for ALL symbols you intend to trade
}
# ==================================================

# === Authentication Function (Gets Session Tokens & Account ID) ===
def get_session_data(): # Renamed for clarity
    """Logs in, returns dict with tokens and accountId, or None if failed."""
    if not CAPITAL_EMAIL or not CAPITAL_PASS or not CAPITAL_API_KEY: # Check all needed
        logger.error("Cannot get session data: Email, Password, or API Key not configured.")
        return None
    auth_data = {"identifier": CAPITAL_EMAIL,"password": CAPITAL_PASS}
    session_url = f"{BASE_URL}/api/v1/session"
    logger.info(f"Attempting session login to {session_url} with user {CAPITAL_EMAIL}")
    try:
        # Use BASE_HEADERS (containing API Key) for the session request itself
        response = requests.post(session_url, json=auth_data, headers=BASE_HEADERS, timeout=10)
        logger.info(f"Session Response Status Code: {response.status_code}")
        logger.debug(f"Session Response Headers: {response.headers}") # DEBUG level recommended
        response_json = {}
        try:
            response_json = response.json(); logger.info(f"Session Response Body: {response_json}") # Log body
        except requests.exceptions.JSONDecodeError: logger.info(f"Session Response Body (Non-JSON): {response.text}")
        except Exception as json_e: logger.error(f"Error decoding session response JSON: {json_e}")
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx) AFTER logging
        cst_token = response.headers.get('CST'); x_sec_token = response.headers.get('X-SECURITY-TOKEN')
        account_id = response_json.get('currentAccountId') # Extract from parsed JSON using correct key
        logger.info(f"Extracted CST: {'FOUND' if cst_token else 'MISSING'} | X-SEC-TOKEN: {'FOUND' if x_sec_token else 'MISSING'} | AccountID: {account_id if account_id else 'MISSING'}")
        if cst_token and x_sec_token and account_id:
            logger.info("🔐 Successfully obtained session tokens and Account ID.")
            return {"cst": cst_token, "x_sec_token": x_sec_token, "account_id": str(account_id)} # Ensure account_id is string
        else:
            missing = [item for item, val in [("CST Header", cst_token), ("X-SECURITY-TOKEN Header", x_sec_token), ("currentAccountId in Body", account_id)] if not val]
            logger.error(f"Failed to extract required items from session response: {', '.join(missing)}")
            return None
    except requests.exceptions.HTTPError as http_err: logger.error(f"HTTP error getting session token: {http_err}"); return None
    except requests.exceptions.RequestException as req_err: logger.error(f"Request failed getting session token: {req_err}"); return None
    except Exception as e: logger.error(f"Unexpected error getting session token: {e}", exc_info=True); return None

# === Helper Function for Trade Size ===
def get_trade_size(symbol: str) -> float:
    """ Returns a default trade size based on the symbol. Customize as needed. """
    symbol_upper = symbol.upper() if symbol else ""
    # Example sizing (adjust these values based on your strategy/risk management)
    if "XAUUSD" in symbol_upper: return 0.02
    if "XAGUSD" in symbol_upper: return 10 # Example for Silver
    if "EURUSD" in symbol_upper: return 10000
    if "BTCUSD" in symbol_upper: return 0.001
    if "NATURALGAS" in symbol_upper or "XNGUSD" in symbol_upper: return 100 # Example for Nat Gas
    return 1.0 # Default size if symbol not matched


# === Place Order Function (Uses /positions endpoint & dynamic accountId) ===
def place_order(direction: str, epic: str, size: float): # Accepts EPIC now
    """Authenticates, prepares headers/payload, and sends request to open position."""

    # --- 1. Get dynamic session tokens AND accountId ---
    session_data = get_session_data() # Use renamed function
    if not session_data:
        return {"error": "Authentication Failed", "details": "Could not obtain session tokens/accountId. Check email/password/API Key env vars and API connectivity."}

    # --- 2. Extract dynamic data ---
    # Note: accountId is NOT typically needed in the /positions payload for placing order
    # dynamic_account_id = session_data.get('account_id')
    cst_token = session_data.get('cst')
    x_sec_token = session_data.get('x_sec_token')

    # --- 3. Prepare Position Data (Payload) ---
    # Basic input validation
    if not all([direction, epic, size]): return {"error": "Missing order parameters"}
    if direction.lower() not in ["buy", "sell"]: return {"error": f"Invalid direction: {direction}"}
    if size <= 0: return {"error": f"Invalid size: {size}"}
    # We extracted account ID earlier, but it seems it's not used in this specific payload

    # Use keys expected by /api/v1/positions endpoint
    position_data = {
        "epic": epic.upper(),           # Use "epic" from mapping
        "direction": direction.upper(), # API usually expects uppercase BUY/SELL
        "size": size                    # Use "size" key
    }

    # --- 4. Prepare Headers with ALL required tokens ---
    headers_for_order = BASE_HEADERS.copy() # Start with base headers (includes API Key)
    headers_for_order['CST'] = cst_token
    headers_for_order['X-SECURITY-TOKEN'] = x_sec_token

    # --- 5. Send Order Request to Correct Endpoint ---
    # <<<!!! VERIFY THIS PATH ('/api/v1/positions') in Capital.com API Docs if 404/other errors persist !!!>>>
    endpoint = f"{BASE_URL}/api/v1/positions" # Using /positions endpoint
    logger.info(f"📤 Sending position request to {endpoint}: {position_data}")
    logger.debug(f"  Using Headers: {headers_for_order}") # Log headers for debugging

    try:
        response = requests.post(endpoint, headers=headers_for_order, json=position_data, timeout=15)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        logger.info(f"🧾 Position response: {response.status_code} {response.text}")
        return response.json() # Return the JSON response from Capital.com

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error opening position: {http_err} - Response: {response.text}")
        try: error_details = response.json()
        except: error_details = response.text
        return {"error": f"HTTP {response.status_code}", "details": error_details} # Return dictionary indicating HTTP error
    except requests.exceptions.Timeout:
        logger.error("Timeout error opening position.")
        return {"error": "Request Timeout"}
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request failed opening position: {req_err}")
        return {"error": "Request failed", "details": str(req_err)}
    except Exception as e:
        logger.error(f"Unexpected error during position placement or response processing: {e}", exc_info=True)
        err_details = str(e)
        if 'response' in locals() and hasattr(response, 'text'): err_details = response.text
        return {"error": "Unknown position processing error", "details": err_details}


# === FastAPI Webhook Endpoint (Uses TICKER_TO_EPIC map) ===
@app.post("/trade")
async def receive_alert(request: Request):
    """Receives trade alerts (webhooks) from TradingView."""
    try:
        data = await request.json()
        logger.info(f"🚨 Alert received: {data}")
    except Exception as e:
         logger.error(f"Failed to parse incoming request JSON: {e}")
         raise HTTPException(status_code=400, detail="Invalid JSON received")

    # --- Extract required fields ---
    data_lower = {k.lower(): v for k, v in data.items()}
    direction = data_lower.get("action")
    symbol = data_lower.get("symbol") # This is the TradingView ticker
    size_str = data_lower.get("size", "1") # Default size to "1" as a string

    # --- Validate extracted data ---
    if not symbol:
        logger.error("Webhook Error: 'symbol' not found in payload.")
        raise HTTPException(status_code=400, detail="'symbol' missing from webhook data")
    if not direction or direction.lower() not in ["buy", "sell"]:
        logger.error(f"Webhook Error: Invalid 'action' received: '{direction}'")
        raise HTTPException(status_code=400, detail=f"Invalid action: {direction}. Expected 'buy' or 'sell'.")

    # --- Map ticker to epic ---
    epic = TICKER_TO_EPIC.get(symbol.upper()) # Look up the epic using the TradingView symbol
    if not epic or "PLACEHOLDER" in epic.upper(): # Check for placeholder too
        logger.error(f"Webhook Error: Epic not found or is placeholder for symbol '{symbol}'. Check TICKER_TO_EPIC map.")
        raise HTTPException(status_code=400, detail=f"Epic mapping not found/configured for symbol: {symbol}")

    try:
        size = float(size_str)
        if size <= 0: raise ValueError("Size must be positive")
    except (ValueError, TypeError):
         logger.warning(f"Invalid or missing 'size' in webhook: '{size_str}'. Using default size logic.")
         size = get_trade_size(symbol) # Use the helper function (uses symbol)
         logger.info(f"Using default size for {symbol}: {size}")


    # --- Place the order using the EPIC ---
    result = place_order(direction, epic, size) # Pass EPIC instead of symbol

    # --- Return response ---
    if "error" in result:
        error_detail = result.get("details", str(result.get("error", "Unknown Error")))
        status_code = 500 # Default server error
        # Set specific status codes based on returned error details
        if result.get("error") == "Authentication Failed" : status_code = 503
        # Check common Capital.com error codes if available in details
        elif '"errorCode":"error.market.market-closed"' in str(error_detail): status_code = 400 # Market closed is a valid rejection, return 400 maybe?
        elif '"errorCode":"error.insufficient-funds"' in str(error_detail): status_code = 400 # Insufficient funds is like a bad request
        elif '"errorCode":"error.not-found.epic"' in str(error_detail): status_code = 400 # Epic issue (shouldn't happen if map is good)
        elif result.get("error", "").startswith("HTTP 404"): status_code = 404 # Explicit 404 check (if URL is still wrong)
        elif result.get("error", "").startswith("HTTP 4"): status_code = 400 # Other 4xx
        elif result.get("error") == "Request Timeout": status_code = 504
        elif result.get("error") == "Request failed": status_code = 502

        raise HTTPException(status_code=status_code, detail=error_detail)
    else:
        # Success
        return {"status": "ok", "capital_response": result}

# Optional: Add a root endpoint for health checks
@app.get("/")
def read_root():
    return {"Status": "Capital.com Trading Bot is running"}

# Note: Local run command would be: uvicorn main:app --host 0.0.0.0 --port 10000
# if __name__ == "__main__":
#      # Make sure env vars are set if running locally
#      # uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
#      pass # Typically run via Render's start command
