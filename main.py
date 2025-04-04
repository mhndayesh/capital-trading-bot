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
CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY")
CAPITAL_SECURITY_TOKEN = os.getenv("CAPITAL_SECURITY_TOKEN") # The API Password/Token
CAPITAL_ACCOUNT_ID = os.getenv("CAPITAL_ACCOUNT_ID")

# --- Validate Credentials ---
if not CAPITAL_API_KEY:
    logger.critical("CRITICAL ERROR: Environment variable CAPITAL_API_KEY is not set!")
    # Optionally exit if running in production, or handle gracefully
    # sys.exit("Exiting: Missing CAPITAL_API_KEY")
if not CAPITAL_SECURITY_TOKEN:
    logger.critical("CRITICAL ERROR: Environment variable CAPITAL_SECURITY_TOKEN is not set!")
    # sys.exit("Exiting: Missing CAPITAL_SECURITY_TOKEN")
if not CAPITAL_ACCOUNT_ID:
    logger.critical("CRITICAL ERROR: Environment variable CAPITAL_ACCOUNT_ID is not set!")
    # sys.exit("Exiting: Missing CAPITAL_ACCOUNT_ID")

# === Capital.com API Setup ===
BASE_URL = "https://api-capital.backend-capital.com" # Production API endpoint
# Demo endpoint (if needed for testing): "https://demo-api-capital.backend-capital.com"

# --- Headers for API Requests (Includes Authentication) ---
HEADERS = {
    "X-CAP-API-KEY": CAPITAL_API_KEY,
    "X-SECURITY-TOKEN": CAPITAL_SECURITY_TOKEN, # Added the security token header
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === Helper Function (Optional but good practice) ===
def get_trade_size(symbol: str) -> float:
    """ Returns a default trade size based on the symbol. Customize as needed. """
    symbol_upper = symbol.upper() if symbol else ""
    # Example sizing (adjust these values based on your strategy/risk management)
    if "XAUUSD" in symbol_upper: return 0.02 # Example: Smaller size for Gold
    if "EURUSD" in symbol_upper: return 10000 # Example: Forex standard lot size base
    if "BTCUSD" in symbol_upper: return 0.001 # Example: Crypto size
    # Add more specific sizes for other symbols you trade
    return 1.0 # Default size if symbol not matched


# === Place Order Function ===
def place_order(direction: str, symbol: str, size: float):
    """Sends a market order to the Capital.com API."""

    # Validate inputs before sending
    if not all([direction, symbol, size]):
         logger.error(f"Order placement failed: Missing direction, symbol, or size.")
         return {"error": "Missing order parameters"}
    if direction.lower() not in ["buy", "sell"]:
         logger.error(f"Order placement failed: Invalid direction '{direction}'.")
         return {"error": f"Invalid direction: {direction}"}
    if size <= 0:
         logger.error(f"Order placement failed: Invalid size '{size}'.")
         return {"error": f"Invalid size: {size}"}
    if not CAPITAL_API_KEY or not CAPITAL_SECURITY_TOKEN or not CAPITAL_ACCOUNT_ID:
         logger.error("Order placement failed: API credentials not configured.")
         return {"error": "Server configuration error: Missing API credentials."}


    order_data = {
        "market": symbol.upper(), # Ensure symbol is uppercase for API
        "side": direction.lower(), # Ensure side is lowercase
        "type": "market", # Market order
        "quantity": size,
        "accountId": CAPITAL_ACCOUNT_ID
    }

    endpoint = f"{BASE_URL}/api/v1/orders"
    logger.info(f"📤 Sending order to {endpoint}: {order_data}")

    try:
        response = requests.post(endpoint, headers=HEADERS, json=order_data, timeout=15) # Increased timeout slightly
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        logger.info(f"🧾 Order response: {response.status_code} {response.text}")
        return response.json() # Return the JSON response from Capital.com

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error placing order: {http_err} - Response: {response.text}")
        return {"error": f"HTTP {response.status_code}", "details": response.text}
    except requests.exceptions.Timeout:
        logger.error("Timeout error placing order.")
        return {"error": "Request Timeout"}
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request failed placing order: {req_err}")
        return {"error": "Request failed", "details": str(req_err)}
    except Exception as e:
        # Catch other potential errors like JSON decoding errors
        logger.error(f"Unexpected error during order placement or processing response: {e}", exc_info=True)
        # Try to get text if possible, even on JSON decode error
        try:
             err_details = response.text if 'response' in locals() else str(e)
        except:
             err_details = str(e)
        return {"error": "Unknown order processing error", "details": err_details}


# === FastAPI Webhook Endpoint ===
@app.post("/trade")
async def receive_alert(request: Request):
    """Receives trade alerts (webhooks) from TradingView."""
    try:
        # Ensure content type is application/json if needed, FastAPI usually handles this
        data = await request.json()
        logger.info(f"🚨 Alert received: {data}")
    except Exception as e:
         logger.error(f"Failed to parse incoming request JSON: {e}")
         # Return a FastAPI specific error response if needed, e.g., raise HTTPException
         raise HTTPException(status_code=400, detail="Invalid JSON received")

    # --- Extract required fields (CASE-INSENSITIVE check for robustness) ---
    # Use .lower() on keys if TradingView might send mixed case
    data_lower = {k.lower(): v for k, v in data.items()}

    direction = data_lower.get("action") # Expects "action" key
    symbol = data_lower.get("symbol")
    size_str = data_lower.get("size", "1") # Default size to "1" as a string

    # --- Validate extracted data ---
    if not symbol:
        logger.error("Webhook Error: 'symbol' not found in payload.")
        raise HTTPException(status_code=400, detail="'symbol' missing from webhook data")

    if direction not in ["buy", "sell"]:
        logger.error(f"Webhook Error: Invalid 'action' received: '{direction}'")
        raise HTTPException(status_code=400, detail=f"Invalid action: {direction}. Expected 'buy' or 'sell'.")

    try:
        size = float(size_str)
        if size <= 0:
             raise ValueError("Size must be positive")
    except (ValueError, TypeError):
         logger.warning(f"Invalid or missing 'size' in webhook: '{size_str}'. Using default size logic.")
         # Use the helper function to get a default size based on symbol
         size = get_trade_size(symbol)
         logger.info(f"Using default size for {symbol}: {size}")


    # --- Place the order ---
    result = place_order(direction, symbol, size)

    # --- Return response ---
    if "error" in result:
        # Forward the error, potentially with a 500 status if it was an internal error
        status_code = 500 if "Server configuration error" in result.get("error","") or "Request failed" in result.get("error","") else 400
        raise HTTPException(status_code=status_code, detail=result)
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
#     # For example, using a .env file and python-dotenv
#     # from dotenv import load_dotenv
#     # load_dotenv()
#     # Check credentials again after loading .env
#     # CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY") ... etc ... check if None
#     uvicorn.run(app, host="0.0.0.0", port=8000) # Or Render's expected port (e.g., 10000)
