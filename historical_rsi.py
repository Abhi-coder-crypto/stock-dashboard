import os
import time
import random
import requests
import pandas as pd
import yfinance as yf
import telegram
from datetime import datetime
from itertools import cycle
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from fake_useragent import UserAgent
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# ✅ Setup API Keys & Proxy Rotation
ALPHA_VANTAGE_KEYS = cycle(["ZQG4E34AQ7TC3GD8", "UMXJ71LN8JZQ5VE4"])
PROXIES = cycle(["http://proxy1.com:8080", "http://proxy2.com:8080"])

# ✅ Telegram Bot Config
TELEGRAM_TOKEN = "7893645378:AAH7HsxurCyJC47xICx_nx-8xov9uDx9Elk"
TELEGRAM_CHAT_ID = "-1002511712658"

# ✅ Load Nifty100 Symbols
NIFTY100_FILE_PATH = r"C:\Users\abhij\Downloads\ind_nifty100list.xlsx"

# ✅ Initialize Telegram Bot
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# ✅ Fake User-Agent
ua = UserAgent()


# ✅ Fetch Nifty 100 Stock Symbols
def get_nifty100_symbols():
    try:
        df = pd.read_excel(NIFTY100_FILE_PATH)
        return df['Symbol'].tolist()
    except Exception as e:
        print(f"⚠️ Error reading Nifty 100 file: {e}")
        return []


# ✅ **Selenium Web Scraper for NSE**
def get_live_price_nse(symbol):
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument(f"user-agent={ua.random}")
        options.add_argument("--disable-blink-features=AutomationControlled")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        driver.get(f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}")
        time.sleep(random.uniform(3, 6))

        price_element = driver.find_element(By.XPATH, "//*[@id='quoteLtp']")
        price = float(price_element.text.replace(",", ""))
        driver.quit()
        return price

    except Exception as e:
        print(f"⚠️ Selenium Error: {e}")
        return None


# ✅ **Get Live Price (Smart Fallbacks)**
def get_live_price(symbol):
    headers = {"User-Agent": ua.random}
    proxy = next(PROXIES)
    url = f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}"

    try:
        response = requests.get(url, headers=headers, proxies={"http": proxy, "https": proxy}, timeout=10)
        response.raise_for_status()
        price = response.json().get('data')[0].get('lastPrice')
        return round(float(price.replace(",", "")), 2)

    except requests.exceptions.RequestException:
        print(f"⚠️ NSE blocked request. Using Selenium Scraper for {symbol}...")
        price = get_live_price_nse(symbol)
        if price:
            return price

        print(f"⚠️ Selenium failed. Using Yahoo Finance for {symbol}...")
        try:
            stock = yf.Ticker(symbol + ".NS")
            return round(stock.history(period="1d")['Close'].iloc[-1], 2)
        except:
            print(f"⚠️ Yahoo blocked. Using Alpha Vantage...")
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}.BSE&apikey={next(ALPHA_VANTAGE_KEYS)}"
            response = requests.get(url).json()
            return float(response["Global Quote"]["05. price"]) if "Global Quote" in response else None


# ✅ **Exponential Backoff with Randomized Delay**
def get_historical_data(symbol, max_retries=5):
    retries = 0
    while retries < max_retries:
        try:
            stock = yf.Ticker(symbol + ".NS")
            df = stock.history(period="14d")
            if not df.empty:
                return df

            print(f"⚠️ Yahoo failed. Trying Alpha Vantage...")
            url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol={symbol}.BSE&apikey={next(ALPHA_VANTAGE_KEYS)}&outputsize=compact&datatype=json"
            response = requests.get(url).json()

            if "Time Series (Daily)" in response:
                df = pd.DataFrame(response["Time Series (Daily)"]).T
                df.index = pd.to_datetime(df.index)
                df = df.sort_index()
                df['close'] = df['4. close'].astype(float)
                return df

        except Exception as e:
            print(f"⚠️ Error fetching data for {symbol}: {e}")

        retries += 1
        wait_time = random.uniform(10, 30)
        print(f"Retrying {symbol} in {wait_time:.2f} seconds...")
        time.sleep(wait_time)

    print(f"🚨 Failed to fetch data for {symbol} after {max_retries} retries.")
    return None


# ✅ **Main Function**
def main():
    nifty100_symbols = get_nifty100_symbols()
    processed_data = []

    for i, symbol in enumerate(nifty100_symbols[:10]):
        print(f"Fetching data for {symbol} ({i + 1}/{len(nifty100_symbols)})")

        historical_df = get_historical_data(symbol)
        if historical_df is None or historical_df.empty:
            continue

        live_price = get_live_price(symbol)
        if live_price:
            processed_data.append(
                [symbol, datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%H:%M:%S'), live_price])

        time.sleep(random.uniform(10, 30))

    # ✅ **Run the Script**


if __name__ == "__main__":
    main()
