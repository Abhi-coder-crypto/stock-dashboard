import os
import time
import asyncio
import pandas as pd
import talib
import telegram
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ✅ TELEGRAM CONFIGURATION
TELEGRAM_TOKEN = "7893645378:AAH7HsxurCyJC47xICx_nx-8xov9uDx9Elk"  # Use your real bot token
TELEGRAM_CHAT_ID = "-1002511712658"  # Use your actual group chat ID
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# ✅ FILE PATHS
LIVE_PRICE_FILE = r"C:\Users\abhij\PycharmProjects\bot\LIVE_PRICE_SYMBOLS.xlsx"
HISTORICAL_DATA_FILE = r"C:\Users\abhij\Downloads\HISTORICAL_DATA.xlsx"
RESULT_FILE = r"C:\Users\abhij\PycharmProjects\bot\nifty100_results.xlsx"

# ✅ SETUP SELENIUM DRIVER
def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    )
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("✅ WebDriver initialized successfully.")
        return driver
    except Exception as e:
        print(f"❌ Error setting up WebDriver: {e}")
        return None

# ✅ FETCH TOP 20 STOCK SYMBOLS
def get_top_20_symbols():
    try:
        df = pd.read_excel(LIVE_PRICE_FILE)
        df.columns = df.columns.str.strip().str.upper()
        symbols = df["SYMBOL"].astype(str).str.strip().head(20).tolist()
        print(f"✅ Fetched top 20 symbols: {symbols}")
        return symbols
    except Exception as e:
        print(f"⚠️ Error reading top 20 symbols: {e}")
        return []

# ✅ FETCH LIVE PRICE
def fetch_live_price(driver, stock_symbol):
    url = f"https://www.nseindia.com/get-quotes/equity?symbol={stock_symbol}"
    try:
        driver.get(url)
        time.sleep(3)
        price_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='quoteLtp']"))
        )
        price_text = price_element.text.replace(",", "").strip()
        if price_text:
            price = float(price_text)
            print(f"✅ Live price fetched for {stock_symbol}: {price}")
            return price
        else:
            print(f"⚠️ No valid price found for {stock_symbol}")
            return None
    except Exception as e:
        print(f"⚠️ Failed to fetch price for {stock_symbol}: {e}")
        return None

# ✅ FETCH HISTORICAL DATA
def get_historical_data(stock_symbol):
    try:
        df = pd.read_excel(HISTORICAL_DATA_FILE, sheet_name=stock_symbol)
        if "CLOSE" not in df.columns:
            print(f"⚠️ No CLOSE column found for {stock_symbol}")
            return None
        df["CLOSE"] = pd.to_numeric(df["CLOSE"], errors="coerce")
        df.dropna(subset=["CLOSE"], inplace=True)
        print(f"✅ Historical data fetched for {stock_symbol}")
        return df
    except Exception as e:
        print(f"⚠️ Error reading historical data for {stock_symbol}: {e}")
        return None

# ✅ CALCULATE RSI & RSI-MA
def calculate_rsi(df):
    try:
        df["RSI"] = talib.RSI(df["CLOSE"], timeperiod=14)
        df["RSI-MA"] = df["RSI"].rolling(window=5).mean()
        df.dropna(inplace=True)
        return df[["CLOSE", "RSI", "RSI-MA"]]
    except Exception as e:
        print(f"⚠️ Error calculating RSI: {e}")
        return None

# ✅ SEND TELEGRAM ALERT
async def send_telegram_alert(message):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        print(f"✅ Telegram alert sent: {message}")
    except Exception as e:
        print(f"⚠️ Error sending Telegram alert: {e}")

# ✅ PROCESS & SAVE RESULTS
async def process_and_save_data():
    driver = setup_driver()
    if not driver:
        return

    symbols = get_top_20_symbols()
    results = []

    for symbol in symbols:
        live_price = fetch_live_price(driver, symbol)
        if live_price is None:
            continue

        historical_data = get_historical_data(symbol)
        if historical_data is None:
            continue

        rsi_df = calculate_rsi(historical_data)
        if rsi_df is None or rsi_df.empty:
            continue

        latest_rsi = rsi_df.iloc[-1]["RSI"]
        latest_rsi_ma = rsi_df.iloc[-1]["RSI-MA"]
        if latest_rsi < 30:
            signal = "BUY (Oversold)"
        elif latest_rsi > 70:
            signal = "SELL (Overbought)"
        elif latest_rsi > latest_rsi_ma:
            signal = "BUY (RSI Crossover)"
        elif latest_rsi < latest_rsi_ma:
            signal = "SELL (RSI Crossover)"
        else:
            signal = "HOLD"

        results.append({
            "Stock": symbol,
            "Live Price": live_price,
            "RSI": latest_rsi,
            "RSI-MA": latest_rsi_ma,
            "Signal": signal
        })

        message = (
            f"\n📊 {symbol} Market Data"
            f"\n🔹 Live Price: {live_price}"
            f"\n🔹 RSI: {latest_rsi:.2f}"
            f"\n🔹 RSI-MA: {latest_rsi_ma:.2f}"
            f"\n🔹 Signal: {signal}"
        )

        await send_telegram_alert(message)

    df_results = pd.DataFrame(results)
    df_results.to_excel(RESULT_FILE, index=False)
    print(f"💾 Data saved to {RESULT_FILE}")
    driver.quit()

# ✅ RUN SCRIPT
if __name__ == "__main__":
    asyncio.run(process_and_save_data())
