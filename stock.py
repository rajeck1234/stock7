import asyncio
import aiohttp
import pandas as pd
import time


BASE_URL = "https://groww.in/v1/api/stocks_data/v1/accord_points/exchange/NSE/segment/CASH/latest_prices_ohlc/{}"

CSV_INPUT = "ind_copy.csv"
CSV_OUTPUT = "start_price.csv"

MAX_CONCURRENT_REQUESTS = 100     # Adjust (50–120 safe range)
REQUEST_TIMEOUT = 5               # Seconds
LOOP_DELAY = 1                    # Delay between loops (seconds)
SAVE_EVERY_N_LOOPS = 1            # Save CSV every N loops


# ==============================
# LOAD SYMBOLS
# ==============================

df = pd.read_csv(CSV_INPUT)
symbols = df["Symbol"].dropna().unique().tolist()

SEM = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


# ==============================
# FETCH FUNCTION
# ==============================

async def fetch_price(session, symbol):
    async with SEM:
        url = BASE_URL.format(symbol)

        try:
            async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                if response.status != 200:
                    return {"Symbol": symbol, "Price": None}

                data = await response.json()
                ltp_price = data.get("ltp")

                if not ltp_price or ltp_price == 0:
                    return {"Symbol": symbol, "Price": None}

                return {"Symbol": symbol, "Price": ltp_price}

        except Exception:
            return {"Symbol": symbol, "Price": None}


# ==============================
# MAIN LOOP
# ==============================

async def main():

    connector = aiohttp.TCPConnector(
        limit=MAX_CONCURRENT_REQUESTS,
        ttl_dns_cache=300,
        ssl=False
    )

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout
    ) as session:

        loop_counter = 0

        while True:
            start_time = time.time()
            loop_counter += 1

            tasks = [fetch_price(session, symbol) for symbol in symbols]

            results = await asyncio.gather(
                *tasks,
                return_exceptions=False
            )

            # Remove None values
            clean_results = [r for r in results if r]

            output_df = pd.DataFrame(clean_results)

            # Save periodically (reduce disk load)
            if loop_counter % SAVE_EVERY_N_LOOPS == 0:
                output_df.to_csv(CSV_OUTPUT, index=False)
                print(f"✅ Prices saved ({len(clean_results)} stocks)")

            end_time = time.time()
            print(f"⏱ Loop execution time: {round(end_time - start_time, 2)} sec")

            await asyncio.sleep(LOOP_DELAY)


# ==============================
# RUN
# ==============================

if __name__ == "__main__":
    asyncio.run(main())
