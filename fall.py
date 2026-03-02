import requests
import pandas as pd

# 🔹 API URL (Change stock name if needed)
url = "https://groww.in/v1/api/charting_service/v2/chart/delayed/exchange/NSE/segment/CASH/ADANIGREEN/daily?intervalInMinutes=1&minimal=true"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

# 🔹 Fetch data
response = requests.get(url, headers=headers)

if response.status_code != 200:
    print("❌ Failed to fetch data:", response.status_code)
    exit()

data = response.json()
candles = data.get("candles", [])

if not candles:
    print("❌ No candle data found")
    exit()

# 🔹 Convert to DataFrame
df = pd.DataFrame(candles, columns=["timestamp", "price"])

# 🔹 Convert timestamp UTC → IST
df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
df["datetime"] = df["datetime"].dt.tz_convert("Asia/Kolkata")

# 🔹 Calculate changes
df["price_change"] = df["price"].diff()
df["pct_change"] = df["price"].pct_change() * 100

# 🔹 Remove first NaN row
df = df.dropna()

# 🔻 Biggest Absolute Price Fall (₹)
max_abs_fall = df.loc[df["price_change"].idxmin()]

# 🔻 Biggest Percentage Fall
max_pct_fall = df.loc[df["pct_change"].idxmin()]

# 📉 Top 5 Worst Falling Minutes (by %)
top5_falls = df.sort_values("pct_change").head(5)

# ================= OUTPUT =================

print("\n🔻 BIGGEST 1-MINUTE PRICE FALL (₹)")
print("Time (IST):", max_abs_fall["datetime"])
print("From:", round(max_abs_fall["price"] - max_abs_fall["price_change"], 2))
print("To:", round(max_abs_fall["price"], 2))
print("Drop:", round(max_abs_fall["price_change"], 2), "₹")
print("Percent:", round(max_abs_fall["pct_change"], 3), "%")

print("\n🔻 BIGGEST 1-MINUTE % FALL")
print("Time (IST):", max_pct_fall["datetime"])
print("From:", round(max_pct_fall["price"] - max_pct_fall["price_change"], 2))
print("To:", round(max_pct_fall["price"], 2))
print("Drop:", round(max_pct_fall["price_change"], 2), "₹")
print("Percent:", round(max_pct_fall["pct_change"], 3), "%")

print("\n📉 TOP 5 WORST FALLING MINUTES (IST)")
print(top5_falls[["datetime", "price_change", "pct_change"]])
