# --- app.py ---

import os
import requests # For making API calls to Capital.com
import json
import logging
from flask import Flask, request, abort, jsonify

# Basic logging setup (consider using Flask's built-in logger or a more robust library for production)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# --- Configuration ---
# Load sensitive data from environment variables - NEVER hardcode them!
# Set these in your Render environment settings
CAPITAL_API_KEY = os.environ.get('CAPITAL_API_KEY')           # Your Capital.com API Key/Identifier
CAPITAL_PASSWORD = os.environ.get('CAPITAL_PASSWORD')       # Your Capital.com Password/API Secret
CAPITAL_API_ENDPOINT = os.environ.get('CAPITAL_API_ENDPOINT') # e.g., "https://demo-api-capital.backend-capital.com/api/v1"
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET')             # Your secret phrase to verify TradingView requests (optional)

# --- Capital.com API Interaction ---
# ==============================================================================
# !! CRITICAL !! : These functions are PLACEHOLDERS.
# You MUST replace the logic below with actual calls to the Capital.com API
# according to their official documentation.
# ==============================================================================

def get_capital_session_tokens():
    """
    Handles authentication with Capital.com API.

    !! REPLACE THIS FUNCTION'S CONTENT !!
    Consult the Capital.com API documentation for the correct authentication endpoint
    (often '/session'), request method (POST), headers, and payload (identifier, password).
    It likely returns a session token (CST) and a security token (X-SECURITY-TOKEN)
    in the response headers, which are needed for subsequent requests.

    Returns:
        tuple: (cst_token, security_token) or (None, None) if authentication fails.
    """
    if not CAPITAL_API_KEY or not CAPITAL_PASSWORD or not CAPITAL_API_ENDPOINT:
        logging.error("Missing Capital.com credentials or API endpoint in environment variables.")
        return None, None

    auth_url = f"{CAPITAL_API_ENDPOINT}/session" # <-- CHECK CAPITAL.COM DOCS FOR CORRECT URL
    headers = {'Content-Type': 'application/json'}
    payload = json.dumps({
        "identifier": CAPITAL_API_KEY,
        "password": CAPITAL_PASSWORD,
        # "encryptedPassword": "false" # Check if needed
    })

    logging.info(f"Attempting authentication at {auth_url}")
    try:
        response = requests.post(auth_url, headers=headers, data=payload, timeout=10) # 10-second timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        # --- Extract tokens ---
        # !! CHECK CAPITAL.COM DOCS !! - Tokens might be in headers or response body
        cst_token = response.headers.get('CST')
        security_token = response.headers.get('X-SECURITY-TOKEN')
        # ----------------------

        if not cst_token or not security_token:
            logging.error(f"Authentication successful (Status {response.status_code}) but failed to extract tokens from response headers.")
            logging.debug(f"Response Headers: {response.headers}")
            return None, None

        logging.info("Successfully obtained Capital.com session tokens.")
        return cst_token, security_token

    except requests.exceptions.RequestException as e:
        logging.error(f"Error authenticating with Capital.com: {e}")
        if e.response is not None:
            logging.error(f"Response Status: {e.response.status_code}")
            logging.error(f"Response Text: {e.response.text}")
        return None, None
    except Exception as e:
        logging.error(f"An unexpected error occurred during authentication: {e}")
        return None, None


def place_capital_order(signal_data, cst_token, security_token):
    """
    Places an order on Capital.com based on the signal data.

    !! REPLACE THIS FUNCTION'S CONTENT !!
    Consult the Capital.com API documentation for the correct endpoints for placing
    market orders or pending orders (e.g., '/positions/otc', '/workingorders/otc').
    Determine the required request method (POST), headers (including CST and X-SECURITY-TOKEN),
    and the exact structure of the JSON payload (direction, epic/symbol, size, orderType,
    stopLoss, takeProfit, etc.).

    Args:
        signal_data (dict): Parsed data from the TradingView webhook.
        cst_token (str): Capital.com session token.
        security_token (str): Capital.com security token.

    Returns:
        tuple: (bool: success, dict: response_data or error_message)
    """
    if not cst_token or not security_token:
        logging.error("Cannot place order: Missing session tokens.")
        return False, {"error": "Missing authentication tokens"}

    # --- Determine API endpoint and payload based on Capital.com docs ---
    # Example for a MARKET order endpoint - !! CHECK DOCS !!
    order_url = f"{CAPITAL_API_ENDPOINT}/positions/otc"

    headers = {
        'Content-Type': 'application/json',
        'X-SECURITY-TOKEN': security_token,
        'CST': cst_token
    }

    # --- Translate TradingView signal to Capital.com API format ---
    # !! THIS MAPPING IS CRITICAL AND DEPENDS ENTIRELY ON CAPITAL.COM's API !!
    try:
        direction = "BUY" if signal_data.get('action', '').lower() == 'buy' else "SELL"
        # Capital.com often uses 'epic' for the instrument identifier
        epic = signal_data.get('symbol') # You might need to map TradingView ticker to Capital.com epic
        size = float(signal_data.get('quantity'))
        order_type = signal_data.get('order_type', 'MARKET') # Assuming MARKET if not specified

        payload_dict = {
            "direction": direction,
            "epic": epic,
            "orderType": order_type,
            "size": size,
            # Add other required/optional fields based on docs:
            # "level": signal_data.get('price'), # Required for LIMIT/STOP orders
            # "stopLoss": ...,
            # "takeProfit": ...,
            # "guaranteedStop": False,
            # "trailingStop": False,
        }
        payload = json.dumps(payload_dict)
    except Exception as e:
        logging.error(f"Error creating order payload from signal data {signal_data}: {e}")
        return False, {"error": f"Invalid signal data format: {e}"}
    # --------------------------------------------------------------------

    logging.info(f"Placing order via API: {order_url} with payload: {payload}")
    try:
        response = requests.post(order_url, headers=headers, data=payload, timeout=15) # 15-second timeout
        response.raise_for_status() # Check for HTTP errors

        response_data = response.json()
        logging.info(f"Order placement successful. API Response: {response_data}")
        # Add logic here to check response_data for confirmation/dealReference if needed
        return True, response_data

    except requests.exceptions.RequestException as e:
        logging.error(f"Error placing Capital.com order: {e}")
        error_details = {"error": str(e)}
        if e.response is not None:
            logging.error(f"Response Status: {e.response.status_code}")
            try:
                error_details = e.response.json() # Try to get JSON error response
                logging.error(f"Response Body: {error_details}")
            except json.JSONDecodeError:
                error_text = e.response.text
                logging.error(f"Response Text: {error_text}")
                error_details = {"error": f"API Error {e.response.status_code}", "details": error_text[:500]} # Limit length
        return False, error_details
    except Exception as e:
        logging.error(f"An unexpected error occurred during order placement: {e}")
        return False, {"error": f"Unexpected error: {str(e)}"}

# ==============================================================================
# --- Webhook Endpoint ---
# ==============================================================================

@app.route('/webhook', methods=['POST'])
def tradingview_webhook():
    """
    Listens for incoming POST requests from TradingView alerts.
    """
    logging.info("Webhook endpoint hit.")

    # --- Verify Request (Optional but recommended) ---
    if WEBHOOK_SECRET:
        try:
            # Ensure data is JSON and get it
            data = request.get_json()
            if not data:
                logging.warning("Webhook received empty request body.")
                abort(400, description="Empty request body.") # Bad request

            # Check if the secret key matches
            if data.get('secret_key') != WEBHOOK_SECRET:
                logging.warning(f"Webhook verification failed: Invalid secret key received.")
                abort(403, description="Invalid secret key.") # Forbidden
            else:
                logging.info("Webhook secret key verified successfully.")

        except Exception as e:
            # Handle cases where request body is not JSON
             logging.error(f"Error parsing webhook JSON or checking secret: {e}")
             abort(400, description=f"Invalid JSON or secret key check failed: {e}") # Bad request
    else:
        # If no secret is configured, just get the JSON data
        data = request.get_json()
        if not data:
            logging.warning("Webhook received empty request body.")
            abort(400, description="Empty request body.")

    logging.info(f"Webhook received data: {data}")

    # --- Basic Signal Validation ---
    required_fields = ['symbol', 'action', 'quantity'] # Add 'price' if using limit orders etc.
    if not all(field in data for field in required_fields):
         logging.warning(f"Webhook received incomplete data. Missing fields. Data: {data}")
         return jsonify({"status": "error", "message": "Missing required fields in signal"}), 400

    # --- Process the Trade Signal ---
    logging.info("Attempting to authenticate with Capital.com...")
    cst, sec_token = get_capital_session_tokens()

    if not cst or not sec_token:
        logging.error("Authentication failed. Cannot place order.")
        # Consider adding retry logic or specific notifications here
        return jsonify({"status": "error", "message": "Capital.com authentication failed"}), 500 # Internal Server Error

    logging.info("Authentication successful. Placing order...")
    success, result = place_capital_order(data, cst, sec_token)

    if success:
        logging.info(f"Order placed successfully. Result: {result}")
        return jsonify({"status": "success", "message": "Trade signal processed", "details": result}), 200
    else:
        logging.error(f"Failed to place order. Reason: {result}")
        # Provide more context in the response if possible, but be careful not to leak sensitive info
        return jsonify({"status": "error", "message": "Failed to place Capital.com order", "details": result}), 500 # Internal Server Error

# Health check endpoint (optional, useful for monitoring)
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"}), 200

# --- Main Execution ---
if __name__ == '__main__':
    # Get port from environment variable (Render sets this automatically)
    port = int(os.environ.get('PORT', 5000))
    # Run the app using waitress or gunicorn in production, host='0.0.0.0' makes it accessible externally
    logging.info(f"Starting Flask app on host 0.0.0.0 port {port}")
    # For local testing you might run: app.run(host='0.0.0.0', port=port, debug=True)
    # For production on Render, the start command 'gunicorn app:app' handles running the server.
    # This __main__ block might not be strictly necessary when using Gunicorn, but is good practice.
    app.run(host='0.0.0.0', port=port) # Gunicorn will manage this when deployed
