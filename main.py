import requests

url = "https://capital-bot-api.onrender.com/trade"
payload = {
    "symbol": "USDJPY",
    "action": "buy",
    "size": 8000
}
headers = {
    "Content-Type": "application/json"
}

res = requests.post(url, json=payload, headers=headers)
print(res.status_code)
print(res.json())
