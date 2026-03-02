from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import yfinance as yf
import os
import json
import threading
import time
import requests
app = Flask(__name__, static_folder="public")
CORS(app)
import time
PORT = int(os.environ.get("PORT", 3000))

print("CURRENT WORKING DIR:", os.getcwd())
import asyncio
import aiohttp
BASE_URL = "https://groww.in/v1/api/stocks_data/v1/accord_points/exchange/NSE/segment/CASH/latest_prices_ohlc/{}"
CANDLE_URL = "https://groww.in/v1/api/charting_service/v2/chart/delayed/exchange/NSE/segment/CASH/{}/daily?intervalInMinutes=1&minimal=true"

# BASE_URL = "https://groww.in/v1/api/stocks_data/v1/tr_live_book/exchange/NSE/segment/CASH/{}/latest"

MAX_CONCURRENT_REQUESTS = 30
SEM = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
# -----------------------------
# JSON Helpers
# -----------------------------
def load_json(file, default):
    try:
        with open(file) as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):

    with open(file, "w") as f:

        json.dump(data, f, indent=2)

# -----------------------------
# Load Files
# -----------------------------
stocks = load_json("stocks.json", [])
portfolio = load_json("portfolio.json", [])
prices_cache = load_json("prices.json", {})
# -----------------------------
# Load CSV Momentum Stocks
# -----------------------------
import pandas as pd
import logging

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

df = pd.read_csv("ind_copy.csv")

# -----------------------------
# Load Start Price CSV
# -----------------------------
start_price_df = pd.read_csv("start_price.csv")

start_price_map = {}

for _, row in start_price_df.iterrows():
    symbol = str(row["Symbol"]).strip() + ".NS"
    start_price_map[symbol] = float(row["Price"])
    
if "Symbol" not in df.columns:
    raise Exception("CSV must contain 'Symbol' column")

def clean_symbol(symbol):
    symbol = str(symbol).strip()
    symbol = symbol.replace("$", "")
    symbol = symbol.replace("-", "")
    return symbol + ".NS"

stocks1 = [clean_symbol(s) for s in df["Symbol"].tolist()]

print("Momentum stock list loaded:", len(stocks1))


# -----------------------------
# ⭐ BEST PRICE FETCH FUNCTION
# -----------------------------
# -----------------------------
# ⭐ Groww API Price Fetch Function (SYNC VERSION)
# -----------------------------
def fetch_price(symbol):

    try:
        grow_symbol = symbol.replace(".NS", "")

        url = BASE_URL.format(grow_symbol)

        response = requests.get(url, timeout=3)
        data = response.json()

        ltp_price = data.get("ltp")

        if ltp_price:
            return float(ltp_price)

        return None

    except Exception as e:
        print("Groww Fetch error:", symbol, e)
        return None


def update_prices():
    global prices_cache

    # print("Updating prices...")

    for symbol in stocks:

        price = fetch_price(symbol)

        if price:
            prices_cache[symbol] = float(price)
            
    save_json("prices.json", prices_cache)


# -----------------------------
# Background Scheduler
# -----------------------------
def scheduler():
    while True:
        update_prices()
        time.sleep(1)

momentum_30_cache = []
momentum_3min_cache = []
momentum_30_price_cache = []
momentum_3min_price_cache = []
max_loss_1_min = []
stable_growth_cache = []
latest_prices_cache = {}


last_10_cycles = load_json("last_10_cycles.json", [])


async def fetch_price_async(session, symbol):

    grow_symbol = symbol.replace(".NS", "")

    url = BASE_URL.format(grow_symbol)

    try:
        async with SEM:
            async with session.get(url) as response:
                data = await response.json()
                # print(data)
                # best_sell = data.get("sellBook", {}).get("1", {}).get("price")
                ltp_price = data.get("ltp")
                # print(symbol)
                # print(ltp_price)
                if ltp_price:
                    return symbol, float(ltp_price)

                return symbol, 0


    except:
        return symbol, 0


async def fetch_last1min_change(session, symbol):

    grow_symbol = symbol.replace(".NS", "")
    url = CANDLE_URL.format(grow_symbol)

    try:
        async with SEM:
            async with session.get(url) as response:
                data = await response.json()

                candles = data.get("candles", [])

                if not candles or len(candles) < 2:
                    return None

                prev_price = candles[-2][1]
                last_price = candles[-1][1]

                if prev_price == 0:
                    return None

                percent_change = ((last_price - prev_price) / prev_price) * 100

                return {
                    "name": symbol,
                    "price": last_price,
                    "change": round(percent_change, 3),
                    "candles": candles
                }

    except:
        return None


async def calculate_top5_last1min():

    import statistics
    # print("hii")
    connector = aiohttp.TCPConnector(
        limit=MAX_CONCURRENT_REQUESTS,
        ttl_dns_cache=300,
        ssl=False
    )

    timeout = aiohttp.ClientTimeout(total=5)

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout
    ) as session:

        tasks = [
            fetch_last1min_change(session, symbol)
            for symbol in stocks1
        ]

        responses = await asyncio.gather(*tasks)

        gainers = []
        losers = []
        stable_list = []

        for item in responses:

            if not item:
                continue

            # =============================
            # 1️⃣ GAINERS / LOSERS
            # =============================
            if item["change"] > 0:
                gainers.append(item)
            elif item["change"] < 0:
                losers.append(item)

            # =============================
            # 2️⃣ SMOOTH STABLE GROWTH
            # =============================
            candles = item.get("candles")

            if not candles or len(candles) < 20:
                continue

            percent_changes = []
            green_count = 0
            red_count = 0

            for i in range(len(candles) - 1):

                prev_price = candles[i][1]
                curr_price = candles[i+1][1]

                if prev_price == 0:
                    break

                change = ((curr_price - prev_price) / prev_price) * 100
                percent_changes.append(change)

                if change > 0:
                    green_count += 1
                elif change < 0:
                    red_count += 1

            if len(percent_changes) < 2:
                continue

            # Must have more green than red
            if green_count <= red_count:
                continue

            overall_change = ((candles[-1][1] - candles[0][1]) / candles[0][1]) * 100

            # Avoid flat stocks
            if overall_change < 0.5:
                continue

            fluctuation = statistics.stdev(percent_changes)
            # Reject highly volatile stocks
            if fluctuation > 0.5:
                continue

            stable_list.append({
                "name": item["name"],
                "price": candles[-1][1],
                "overall_change": round(overall_change, 3),
                "fluctuation": round(fluctuation, 5)
            })

        # =============================
        # SORTING
        # =============================

        gainers.sort(key=lambda x: x["change"], reverse=True)
        losers.sort(key=lambda x: x["change"])

        # Best smooth growth = highest growth + lowest fluctuation
        stable_list.sort(
            key=lambda x: (-x["overall_change"], x["fluctuation"])
        )

        top5_gainers = {
            stock["name"]: {
                "price": stock["price"],
                "change": stock["change"]
            }
            for stock in gainers[:20]
        }

        top5_losers = {
            stock["name"]: {
                "price": stock["price"],
                "change": stock["change"]
            }
            for stock in losers[:20]
        }
        # print(stable_list)
        top5_stable = stable_list[:20]
        # print(top5_stable)
        return top5_gainers, top5_losers, top5_stable


async def fetch_all_prices_async():

    prices = {}

    connector = aiohttp.TCPConnector(
        limit=MAX_CONCURRENT_REQUESTS,
        ttl_dns_cache=300,
        ssl=False
    )

    timeout = aiohttp.ClientTimeout(total=5)

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout
    ) as session:

        tasks = [fetch_price_async(session, symbol) for symbol in stocks1]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=False
        )

        for symbol, price in results:
            prices[symbol] = price

    return prices


def calculate_momentum(start, end):

    results = []
    # print("0")
    for stock in start:
        if stock in end and start[stock] != 0:
            change = ((end[stock] - start[stock]) / start[stock]) * 100
            results.append({
                "name": stock,
                "price": end[stock],
                "change": round(change,3)
            })

    results.sort(key=lambda x: x["change"], reverse=True)
    return results

def calculate_continuous_price_raise(cycles):
    
    results = []

    if len(cycles) < 5:
        return []

    stocks = cycles[0].keys()

    for stock in stocks:

        increases = []
        valid = True

        for i in range(len(cycles) - 1):

            start_price = cycles[i].get(stock)
            end_price = cycles[i + 1].get(stock)

            if not start_price or not end_price:
                valid = False
                break

            diff = (end_price - start_price)/start_price*100

            if diff < 0:   # ❌ if price falls, remove stock
                valid = False
                break
            
            increases.append(diff)

        if valid and len(increases) > 0:
            avg_increase = sum(increases) / len(increases)

            results.append({
                "name": stock,
                "price": cycles[-1][stock],
                "diff": round(avg_increase, 3)
            })

    results.sort(key=lambda x: x["diff"], reverse=True)

    return results[:20]


def calculate_static_momentum(cycles):
    
    results = []
   
    if len(cycles) < 2:
        return []

    start_cycle = cycles[0]
    end_cycle = cycles[-1]

    for stock in start_cycle:

        if stock in end_cycle and start_cycle[stock] != 0:

            start_price = start_cycle[stock]
            end_price = end_cycle[stock]

            change = ((end_price - start_price) / start_price) * 100

            results.append({
                "name": stock,
                "price": end_price,
                "change": round(change, 3)
            })

    results.sort(key=lambda x: x["change"], reverse=True)

    return results[:20]

def calculate_static_price_raise(cycles):
    
    results = []

    if len(cycles) < 5:
        return []

    stocks = cycles[0].keys()

    for stock in stocks:

        valid = True
        increases = []

        for i in range(len(cycles) - 1):

            start_price = cycles[i].get(stock)
            end_price = cycles[i + 1].get(stock)
            if not start_price or not end_price or start_price == 0:
                valid = False
                break

            # % growth per cycle
            percent_change = ((end_price - start_price) / start_price) * 100
            # print(percent_change)
            if percent_change < 0:   # ❌ minimum growth condition
                valid = False
                break

            increases.append(percent_change)
            # print("hii")
        if valid and len(increases) > 0:
            # print("hii")
            avg_increase = sum(increases) / len(increases)

            results.append({
                "name": stock,
                "price": cycles[-1][stock],
                "diff": round(avg_increase, 3)
            })

    results.sort(key=lambda x: x["diff"], reverse=True)
    # print(results)
    return results[:20]

def calculate_start_price_movement(direction="up"):
    
    results = []

    for symbol, start_price in start_price_map.items():

        current_price = latest_prices_cache.get(symbol)

        if not current_price or start_price == 0:
            continue

        change = ((current_price - start_price) / start_price) * 100

        results.append({
            "name": symbol,
            "start_price": start_price,
            "current_price": current_price,
            "change": round(change, 3)
        })

    if direction == "up":
        results = [r for r in results if r["change"] >= 0]
        results.sort(key=lambda x: x["change"], reverse=True)
        

    elif direction == "down":
        results = [r for r in results if r["change"] <= 0]
        results.sort(key=lambda x: x["change"])

    elif direction == "both":
        results.sort(key=lambda x: abs(x["change"]), reverse=True)
    
    return results[:20]


def calculate_15sec_loss(cycles):
    
    if len(cycles) < 2:
        return []

    start = cycles[0]
    end = cycles[-1]

    results = []

    for stock in start:
        if stock in end and start[stock] != 0:

            change = ((end[stock] - start[stock]) / start[stock]) * 100

            results.append({
                "name": stock,
                "price": end[stock],
                "change": round(change, 3)
            })

    # Sort lowest first (biggest loss)
    results.sort(key=lambda x: x["change"])

    return results[:20]

def momentum_scheduler():
    
    global momentum_30_cache
    global momentum_3min_cache
    global momentum_30_price_cache
    global momentum_3min_price_cache
    global last_10_cycles
    global max_loss_1_min
    global stable_growth_cache

    # ✅ Create ONE event loop only once
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    previous_prices = loop.run_until_complete(fetch_all_prices_async())

    if not previous_prices:
        previous_prices = {}
    # coun = 0
    last_candle_scan_time = 0

    while True:
        # print("hii")
        current_time = time.time()
        current_prices = loop.run_until_complete(fetch_all_prices_async())

        global latest_prices_cache
        latest_prices_cache = current_prices
        
        if not current_prices:
            time.sleep(2)
            continue

        # Store cycles
        last_10_cycles.append(current_prices)

        if len(last_10_cycles) > 15:
            last_10_cycles.pop(0)

        save_json("last_10_cycles.json", last_10_cycles)

        # ===============================
        # SECTION 2 → 5 SEC
        # ===============================
        if len(last_10_cycles) >= 5:
            last_5 = last_10_cycles[-5:]
            momentum_30_cache = calculate_static_momentum(last_5)

        # ===============================
        # SECTION 3 → 10 SEC
        # ===============================
        if len(last_10_cycles) >= 10:
            last_10 = last_10_cycles[-10:]
            momentum_3min_cache = calculate_static_momentum(last_10)

        # ===============================
        # SECTION 4 → 15 SEC
        # ===============================
        if len(last_10_cycles) >= 15:
            last_15 = last_10_cycles[-15:]
            momentum_30_price_cache = calculate_static_momentum(last_15)
            max_loss_1_min = calculate_15sec_loss(last_15)

        

         
        # if current_time - last_candle_scan_time >= 1:
        momentum_3min_price_cache,max_loss_1_min2,stable_growth_cache = loop.run_until_complete(
                calculate_top5_last1min()
            )
        # print("jiii")
        # print(stable_growth_cache)
        # print(current_time - last_candle_scan_time)
        # last_candle_scan_time = current_time
        

        # time.sleep(1)


@app.route("/momentum1loss")
def momentum1loss():
    # print(momentum_30_cache)
    return jsonify(max_loss_1_min)

@app.route("/momentum30")
def momentum30():
    # print(momentum_30_cache)
    return jsonify(momentum_30_cache)

@app.route("/momentum3min")
def momentum3min():
    return jsonify(momentum_3min_cache)

@app.route("/momentum30price")
def momentum30price():
    return jsonify(momentum_30_price_cache)

@app.route("/momentum3minprice")
def momentum3minprice():
    return jsonify(momentum_3min_price_cache)

@app.route("/stablegrowth")
def stable_growth():
    return jsonify(stable_growth_cache)

@app.route("/start-movement/<direction>")
def start_movement(direction):
    data = calculate_start_price_movement(direction)
    return jsonify(data)
# -----------------------------
# Serve Frontend
# -----------------------------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)


# -----------------------------
# Get Stocks
# -----------------------------
@app.route("/stocks")
def get_stocks():

    result = []
    # print("jss")
    for symbol in stocks:
        result.append({
            "name": symbol,
            "price": prices_cache.get(symbol)
        })
        # print(result)
        # print(symbol)
    # print("stockpr")    
    # print(result)    
    return jsonify(result)


# -----------------------------
# Add Stock
# -----------------------------
@app.route("/add-stock", methods=["POST"])
def add_stock():
    
    data = request.get_json()
    symbol = data["symbol"].upper() 
    if not symbol.endswith(".NS"):
        symbol += ".NS"

    if symbol not in stocks:
        stocks.append(symbol)
        save_json("stocks.json", stocks)

    return jsonify(stocks)


@app.route("/removeStock/<name>", methods=["DELETE"])
def remove_stock(name):

    if name in stocks:
        stocks.remove(name)
        save_json("stocks.json", stocks)
        return jsonify({"status":"removed"})

    return jsonify({"status":"not found"})

# -----------------------------
# Portfolio
# -----------------------------
@app.route("/portfolio")
def get_portfolio():
    return jsonify(portfolio)


# -----------------------------
# Buy Stock
# -----------------------------
@app.route("/buy", methods=["POST"])
def buy_stock():

    data = request.get_json()
    buy_price = float(data["price"])

    stock = {
        "name": data["name"],
        "buy_price": buy_price,
        "target_price": buy_price,
        "highest_price": buy_price,
        "alert_triggered": False
    }
    portfolio.append(stock)
    save_json("portfolio.json", portfolio)

    return jsonify(portfolio)


# -----------------------------
# Sell Stock
# -----------------------------
@app.route("/sell", methods=["POST"])
def sell_stock():

    name = request.get_json()["name"]

    global portfolio
    portfolio = [s for s in portfolio if s["name"] != name]

    save_json("portfolio.json", portfolio)

    return jsonify(portfolio)


# -----------------------------
# ALERT LOGIC
# -----------------------------

@app.route("/check-alerts")
def check_alerts():

    alerts = []
    for stock in portfolio:
        
        symbol = stock["name"]
        current_price = prices_cache.get(symbol)
        # print(current_price)
        if current_price is None:
            continue

        buy_price = stock["buy_price"]
        if "highest_price" not in stock:
            stock["highest_price"] = buy_price

        # Update highest price
        
        if current_price > stock["highest_price"]:
            
            stock["highest_price"] = current_price

        highest_price = stock["highest_price"]

        # -----------------------------
        # 🔴 CONDITION 1: STOP LOSS
        # -----------------------------
        # buy_price = stock["buy_price"]
        stop_loss_price = buy_price

        # -----------------------------
        # 🔴 CONDITION 2: TRAILING STOP
        # -----------------------------
        trailing_price = highest_price

        if current_price < stop_loss_price:

            alerts.append(symbol)

        if current_price < trailing_price:

            alerts.append(symbol)

    save_json("portfolio.json", portfolio)
    return jsonify(alerts)

if __name__ == "__main__":

    threading.Thread(target=scheduler, daemon=True).start()
    threading.Thread(target=momentum_scheduler, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)