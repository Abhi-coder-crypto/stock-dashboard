import os
import time
import asyncio
import requests
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
TELEGRAM_TOKEN = "8126579938:AAHG-BLo99VDR-qbWKVKHC7fRGY5GfJ3I6U"
TELEGRAM_CHAT_ID = "-1002461680012"
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# ✅ FILE PATHS
LIVE_EXCEL_FILE = r"C:\Users\abhij\PycharmProjects\bot\nifty100_data.xlsx"
HISTORICAL_CSV_FILE = r"C:\Users\abhij\Downloads\HISTORICAL_DATA.xlsx"
NSE_CSV_PATH = r"C:\Users\abhij\PycharmProjects\bot\ind_nifty100list.csv"


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


# ✅ FETCH LIVE STOCK PRICE
def fetch_live_price(driver, stock_symbol):
    url = f"https://www.nseindia.com/get-quotes/equity?symbol={stock_symbol}"
    print(f"🌍 Fetching live price for {stock_symbol}...")

    try:
        driver.get(url)
        time.sleep(3)
        price_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='quoteLtp']"))
        )
        price_text = price_element.text.replace(",", "").strip()
        if not price_text:
            raise ValueError("Empty price data")

        price = float(price_text)
        print(f"✅ Live price for {stock_symbol}: {price}")
        return price
    except Exception as e:
        print(f"⚠️ Failed to fetch live price for {stock_symbol}: {e}")
        return None


# ✅ GET STOCK SYMBOLS FROM NSE CSV FILE
def get_nifty100_tickers():
    if not os.path.exists(NSE_CSV_PATH):
        print(f"⚠️ NSE CSV file not found at {NSE_CSV_PATH}")
        return []

    try:
        df = pd.read_csv(NSE_CSV_PATH, encoding="ISO-8859-1")
        df.columns = df.columns.str.strip()
        if "Symbol" not in df:
            print("❌ 'Symbol' column not found in CSV.")
            return []

        nse_tickers = df["Symbol"].dropna().astype(str).tolist()
        print(f"✅ Loaded {len(nse_tickers)} tickers: {nse_tickers[:5]}...")
        return nse_tickers
    except Exception as e:
        print(f"⚠️ Error reading NIFTY 100 CSV: {e}")
        return []


# ✅ LOAD HISTORICAL DATA
# ✅ LOAD HISTORICAL DATA FROM EXCEL
def load_historical_data(stock_symbol):
    file_path = r"C:\Users\abhij\Downloads\HISTORICAL_DATA.xlsx"  # Correct Excel file path

    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path} - Creating an empty DataFrame.")
        return pd.DataFrame(columns=["Date", "CLOSE"])  # Return an empty DataFrame

    try:
        xls = pd.ExcelFile(file_path)

        if stock_symbol not in xls.sheet_names:
            print(f"❌ Sheet for {stock_symbol} not found in Excel file.")
            return pd.DataFrame(columns=["Date", "CLOSE"])  # Return an empty DataFrame

        df = pd.read_excel(file_path, sheet_name=stock_symbol)
        df.columns = df.columns.str.strip()

        expected_columns = {"Date", "CLOSE"}
        if not expected_columns.issubset(df.columns):
            print(f"❌ Missing expected columns in {stock_symbol} sheet. Found: {df.columns}")
            return pd.DataFrame(columns=["Date", "CLOSE"])  # Return an empty DataFrame

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["CLOSE"] = pd.to_numeric(df["CLOSE"], errors="coerce")
        df = df.dropna(subset=["Date", "CLOSE"])
        df.sort_values("Date", ascending=True, inplace=True)

        print(f"✅ Loaded {len(df)} historical records for {stock_symbol}.")
        return df[["Date", "CLOSE"]]  # Keep only necessary columns
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")
        return pd.DataFrame(columns=["Date", "CLOSE"])  # Return an empty DataFrame


# ✅ MERGE LIVE PRICE WITH HISTORICAL DATA
def merge_live_data(historical_df, live_price):
    new_data = pd.DataFrame({"Date": [datetime.now()], "Close": [live_price]})
    historical_df = pd.concat([historical_df, new_data]).drop_duplicates(subset="Date")

    # Keep only the last 100 rows to prevent old data from distorting RSI
    historical_df = historical_df.tail(100).reset_index(drop=True)

    return historical_df


# ✅ CALCULATE RSI & RSI-MA
def calculate_rsi(stock_df):
    if stock_df.empty or len(stock_df) < 20:  # Ensure enough data for RSI & RSI-MA
        print("⚠️ Not enough data for RSI calculation. Skipping...")
        return pd.DataFrame()  # Return an empty DataFrame to prevent errors

    stock_df["RSI"] = talib.RSI(stock_df["Close"], timeperiod=14)
    stock_df["RSI-MA"] = stock_df["RSI"].rolling(window=5).mean()
    stock_df.dropna(subset=["RSI", "RSI-MA"], inplace=True)

    print("📊 Latest RSI Values:")
    print(stock_df.tail(5)[["Date", "RSI", "RSI-MA"]])

    return stock_df


# ✅ SEND TELEGRAM ALERT
async def send_telegram_alert(df, stock):
    if df.empty or len(df) < 2:  # Ensure at least 2 RSI values exist
        print(f"⚠️ Not enough RSI data for {stock}. Skipping alert.")
        return

    try:
        latest_rsi = df.iloc[-1]["RSI"]
        latest_rsi_ma = df.iloc[-1]["RSI-MA"]
        prev_rsi = df.iloc[-2]["RSI"]
        prev_rsi_ma = df.iloc[-2]["RSI-MA"]

        print(f"🔍 Checking RSI for {stock}: RSI={latest_rsi:.2f}, RSI-MA={latest_rsi_ma:.2f}")

        message = None

        if prev_rsi < prev_rsi_ma and latest_rsi > latest_rsi_ma:
            message = f"📈 *RSI Alert* - {stock} is turning *BULLISH*! 🚀\n🔹 RSI: {latest_rsi:.2f}\n🔹 RSI-MA: {latest_rsi_ma:.2f}"
        elif prev_rsi > prev_rsi_ma and latest_rsi < latest_rsi_ma:
            message = f"📉 *RSI Alert* - {stock} is turning *BEARISH*! 📉\n🔹 RSI: {latest_rsi:.2f}\n🔹 RSI-MA: {latest_rsi_ma:.2f}"

        if latest_rsi < 30:
            message += f"\n⚠️ *OVERSOLD* - Possible buying opportunity!"
        elif latest_rsi > 70:
            message += f"\n⚠️ *OVERBOUGHT* - Possible selling opportunity!"

        if message:
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")
            print(f"✅ Alert sent: {message}")

    except Exception as e:
        print(f"⚠️ Error sending Telegram alert: {e}")


# ✅ MAIN FUNCTION
async def update_market_data():
    driver = setup_driver()
    stocks = get_nifty100_tickers()

    for stock in stocks:
        live_price = fetch_live_price(driver, stock)
        if live_price:
            historical_df = load_historical_data(stock)  # FIXED: Pass stock symbol
            merged_df = merge_live_data(historical_df, live_price)
            rsi_df = calculate_rsi(merged_df)
            await send_telegram_alert(rsi_df, stock)

    driver.quit()


async def main():
    while True:
        await update_market_data()
        await asyncio.sleep(900)


if __name__ == "__main__":
    asyncio.run(main())
