import requests
import pandas as pd
from datetime import datetime

# 🔹 API URL
url = "https://groww.in/v1/api/charting_service/v2/chart/delayed/exchange/NSE/segment/CASH/ADANIGREEN/daily?intervalInMinutes=1&minimal=true"

# 🔹 Headers (VERY IMPORTANT – Groww blocks plain requests)
headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

# 🔹 Fetch data
response = requests.get(url, headers=headers)

if response.status_code != 200:
    print("Failed to fetch data")
    print(response.status_code)
    exit()

data = response.json()

# 🔹 Extract candles
candles = data.get("candles", [])

if not candles:
    print("No candle data found")
    exit()

# 🔹 Convert to DataFrame
df = pd.DataFrame(candles, columns=["timestamp", "price"])

# 🔹 Convert timestamp
df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")

# 🔹 Calculate percentage change
df["pct_change"] = df["price"].pct_change() * 100

# 🔹 Calculate absolute price change
df["price_change"] = df["price"].diff()

# 🔥 Highest Gain
max_gain = df.loc[df["pct_change"].idxmax()]

# 🔻 Highest Loss
max_loss = df.loc[df["pct_change"].idxmin()]

print("\n🔥 Highest 1-Minute Gain:")
print("Time:", max_gain["datetime"])
print("Price Change:", round(max_gain["price_change"], 2))
print("Percent Change:", round(max_gain["pct_change"], 3), "%")

print("\n🔻 Highest 1-Minute Loss:")
print("Time:", max_loss["datetime"])
print("Price Change:", round(max_loss["price_change"], 2))
print("Percent Change:", round(max_loss["pct_change"], 3), "%")
