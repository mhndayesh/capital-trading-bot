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
    # sys.exit(f"Exiting: Missing environment variables: {', '.join(missing_vars)}") # Optional exit


# === Capital.com API Setup ===
BASE_URL = "https://api-capital.backend-capital.com" # Production API endpoint
# Demo endpoint (if needed for testing): "https://demo-api-capital.backend-capital.com"

# Base headers (API key is usually needed for most/all requests)
# Ensure CAPITAL_API_KEY is loaded before this dictionary is defined
BASE_HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY if CAPITAL_API_KEY else "MISSING_API_KEY", # Use loaded key or placeholder
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === Authentication Function === ### MODIFIED to extract Account ID ###
def get_session_tokens():
    """
    Logs into Capital.com using Email/Password to get session tokens AND accountId.
    Returns a dictionary with tokens and accountId or None if failed.
    """
    if not CAPITAL_EMAIL or not CAPITAL_PASS or not CAPITAL_API_KEY: # Check all needed
        logger.error("Cannot get session tokens: Email, Password, or API Key not configured in environment.")
        return None

    auth_data = {
        "identifier": CAPITAL_EMAIL,
        "password": CAPITAL_PASS
    }
    session_url = f"{BASE_URL}/api/v1/session"
    logger.info(f"Attempting session login to {session_url} with user {CAPITAL_EMAIL}")

    try:
        # Use BASE_HEADERS (containing API Key) for the session request itself
        response = requests.post(session_url, json=auth_data, headers=BASE_HEADERS, timeout=10)

        logger.info(f"Session Response Status Code: {response.status_code}")
        logger.debug(f"Session Response Headers: {response.headers}") # DEBUG level recommended

        response_json = {} # Define outside the try block
        try:
            response_json = response.json() # Try parsing JSON body
            # Log body at INFO level now to see account ID
            logger.info(f"Session Response Body: {response_json}")
        except requests.exceptions.JSONDecodeError:
            logger.info(f"Session Response Body (Non-JSON): {response.text}")
        except Exception as json_e:
             logger.error(f"Error decoding session response JSON: {json_e}")

        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx) AFTER logging

        # Successful login - Extract tokens from RESPONSE HEADERS
        cst_token = response.headers.get('CST')
        x_sec_token = response.headers.get('X-SECURITY-TOKEN')
        # --- ### ADDED: Extract accountId from RESPONSE BODY ### ---
        account_id = response_json.get('accountId') # Extract from parsed JSON
        # --- ### END ADDED ### ---


        logger.info(f"Extracted CST from Headers: {'FOUND' if cst_token else 'MISSING'}")
        logger.info(f"Extracted X-SECURITY-TOKEN from Headers: {'FOUND' if x_sec_token else 'MISSING'}")
        logger.info(f"Extracted accountId from Body: {account_id if account_id else 'MISSING'}") # Log extracted ID

        # Check if ALL required pieces were found
        if cst_token and x_sec_token and account_id:
            logger.info("🔐 Successfully obtained session tokens (CST & X-SECURITY-TOKEN) and Account ID.")
            # ### MODIFIED RETURN: Include account_id ###
            return {"cst": cst_token, "x_sec_token": x_sec_token, "account_id": str(account_id)} # Ensure account_id is string
        else:
            missing_items = []
            if not cst_token: missing_items.append("CST Header")
            if not x_sec_token: missing_items.append("X-SECURITY-TOKEN Header")
            if not account_id: missing_items.append("accountId in Body")
            logger.error(f"Failed to extract required items from session response: {', '.join(missing_items)}")
            return None

    except requests.exceptions.HTTPError as http_err:
        # Logged status/body/headers above before raise_for_status
        logger.error(f"HTTP error getting session token: {http_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request failed getting session token: {req_err}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting session token: {e}", exc_info=True)
        return None

# === Helper Function (Optional but good practice) ===
def get_trade_size(symbol: str) -> float:
    """ Returns a default trade size based on the symbol. Customize as needed. """
    symbol_upper = symbol.upper() if symbol else ""
    # Example sizing (adjust these values based on your strategy/risk management)
    if "XAUUSD" in symbol_upper: return 0.02
    if "EURUSD" in symbol_upper: return 10000
    if "BTCUSD" in symbol_upper: return 0.001
    # Add more specific sizes for other symbols you trade
    return 1.0 # Default size if symbol not matched


# === Place Order Function === ### MODIFIED to use dynamic accountId ###
def place_order(direction: str, symbol: str, size: float):
    """Authenticates, prepares headers/payload, and sends a market order."""

    # --- 1. Get dynamic session tokens AND accountId ---
    session_data = get_session_tokens()
    if not session_data:
        return {"error": "Authentication Failed", "details": "Could not obtain session tokens/accountId. Check email/password/API Key env vars and API connectivity."}

    # --- 2. Extract dynamic data ---
    dynamic_account_id = session_data.get('account_id') # ### ADDED ### Extract dynamic ID
    cst_token = session_data.get('cst')
    x_sec_token = session_data.get('x_sec_token')

    # --- 3. Prepare Order Data ---
    # Basic input validation
    if not all([direction, symbol, size]): return {"error": "Missing order parameters"}
    if direction.lower() not in ["buy", "sell"]: return {"error": f"Invalid direction: {direction}"}
    if size <= 0: return {"error": f"Invalid size: {size}"}
    # Use the dynamic account ID obtained from the session
    if not dynamic_account_id: return {"error": "Could not determine Account ID from session."}

    order_data = {
        "market": symbol.upper(),
        "side": direction.lower(),
        "type": "market",
        "quantity": size,
        "accountId": dynamic_account_id # ### MODIFIED: Use dynamic ID ###
    }

    # --- 4. Prepare Headers with ALL required tokens ---
    headers_for_order = BASE_HEADERS.copy() # Start with base headers (includes API Key)
    headers_for_order['CST'] = cst_token
    headers_for_order['X-SECURITY-TOKEN'] = x_sec_token

    # --- 5. Send Order Request ---
    endpoint = f"{BASE_URL}/api/v1/orders" # <--- Still using this endpoint
    logger.info(f"📤 Sending order to {endpoint}: {order_data}")
    logger.debug(f"  Using Headers: {headers_for_order}")

    try:
        response = requests.post(endpoint, headers=headers_for_order, json=order_data, timeout=15)
        response.raise_for_status()
        logger.info(f"🧾 Order response: {response.status_code} {response.text}")
        return response.json()

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error placing order: {http_err} - Response: {response.text}")
        try: error_details = response.json()
        except: error_details = response.text
        return {"error": f"HTTP {response.status_code}", "details": error_details}
    except requests.exceptions.Timeout:
        logger.error("Timeout error placing order.")
        return {"error": "Request Timeout"}
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request failed placing order: {req_err}")
        return {"error": "Request failed", "details": str(req_err)}
    except Exception as e:
        logger.error(f"Unexpected error during order placement or response processing: {e}", exc_info=True)
        err_details = str(e)
        if 'response' in locals() and hasattr(response, 'text'): err_details = response.text
        return {"error": "Unknown order processing error", "details": err_details}


# === FastAPI Webhook Endpoint ===
@app.post("/trade")
async def receive_alert(request: Request):
    """Receives trade alerts (webhooks) from TradingView."""
    try:
        data = await request.json()
        logger.info(f"🚨 Alert received: {data}")
    except Exception as e:
         logger.error(f"Failed to parse incoming request JSON: {e}")
         raise HTTPException(status_code=400, detail="Invalid JSON received")

    # --- Extract required fields (CASE-INSENSITIVE check for robustness) ---
    data_lower = {k.lower(): v for k, v in data.items()}
    direction = data_lower.get("action") # Expects "action" key
    symbol = data_lower.get("symbol")
    size_str = data_lower.get("size", "1") # Default size to "1" as a string

    # --- Validate extracted data ---
    if not symbol:
        logger.error("Webhook Error: 'symbol' not found in payload.")
        raise HTTPException(status_code=400, detail="'symbol' missing from webhook data")

    if not direction or direction.lower() not in ["buy", "sell"]:
        logger.error(f"Webhook Error: Invalid 'action' received: '{direction}'")
        raise HTTPException(status_code=400, detail=f"Invalid action: {direction}. Expected 'buy' or 'sell'.")

    try:
        size = float(size_str)
        if size <= 0:
             raise ValueError("Size must be positive")
    except (ValueError, TypeError):
         logger.warning(f"Invalid or missing 'size' in webhook: '{size_str}'. Using default size logic.")
         size = get_trade_size(symbol) # Use the helper function
         logger.info(f"Using default size for {symbol}: {size}")


    # --- Place the order ---
    result = place_order(direction, symbol, size)

    # --- Return response ---
    if "error" in result:
        # Determine appropriate status code based on error type returned by place_order
        error_detail = result.get("details", str(result.get("error", "Unknown Error")))
        status_code = 500 # Default to server error
        if result.get("error") == "Authentication Failed" : status_code = 503 # Service Unavailable (auth failed)
        # Check if details contain the 404 error specifically
        elif result.get("error", "").startswith("HTTP 404") or '"status":404' in str(error_detail): status_code = 404
        elif result.get("error", "").startswith("HTTP 4"): status_code = 400 # Other 4xx errors
        elif result.get("error") == "Request Timeout": status_code = 504 # Gateway Timeout
        elif result.get("error") == "Request failed": status_code = 502 # Bad Gateway

        # Raise HTTPException to return proper status code to TradingView/client
        raise HTTPException(status_code=status_code, detail=error_detail)
    else:
        # Return success status and Capital.com's response
        return {"status": "ok", "capital_response": result}

# Optional: Add a root endpoint for health checks
@app.get("/")
def read_root():
    return {"Status": "Capital.com Trading Bot is running"}

# Note: To run this locally for testing (outside Render), you might use:
# import uvicorn
# if __name__ == "__main__":
#     # Ensure environment variables are set locally if testing this way
#     uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
