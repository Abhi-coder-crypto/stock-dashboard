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
from indicators import calculate_macd, calculate_bollinger, calculate_sma_ema, calculate_adx


# ✅ TELEGRAM CONFIGURATION
TELEGRAM_TOKEN = "7893645378:AAH7HsxurCyJC47xICx_nx-8xov9uDx9Elk"  # Use your real bot token
TELEGRAM_CHAT_ID = "-1002511712658"  # Use your actual group chat ID
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# ✅ FILE PATHS
LIVE_PRICE_FILE = r"C:\Users\abhij\PycharmProjects\bot\LIVE_PRICE_SYMBOLS.xlsx"
HISTORICAL_DATA_FILE = r"C:\Users\abhij\Downloads\HISTORICAL_DATA.xlsx"
RESULT_FOLDER = r"C:\Users\abhij\PycharmProjects\bot\nifty100_results"


# Ensure result folder exists
os.makedirs(RESULT_FOLDER, exist_ok=True)

# ✅ SETUP SELENIUM DRIVER
def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
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

def fetch_live_price(driver, stock_symbol):
    url = f"https://www.nseindia.com/get-quotes/equity?symbol={stock_symbol}"
    try:
        driver.get(url)
        time.sleep(3)
        price_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='quoteLtp']"))
        )
        price_text = price_element.text.replace(",", "").strip()
        price = float(price_text) if price_text else None
        print(f"✅ Live price fetched for {stock_symbol}: {price}")
        return price
    except Exception as e:
        print(f"⚠️ Failed to fetch price for {stock_symbol}: {e}")
        return None


def get_historical_data(stock_symbol):
    try:
        df = pd.read_excel(HISTORICAL_DATA_FILE, sheet_name=stock_symbol)
        df.rename(columns=lambda x: x.strip(), inplace=True)  # Remove spaces
        df.columns = df.columns.str.upper()  # Ensure uppercase column names

        if "CLOSE" not in df.columns or "DATE" not in df.columns:
            print(f"⚠️ Missing required columns in {stock_symbol} data. Available: {df.columns.tolist()}")
            return None

        df["DATE"] = pd.to_datetime(df["DATE"], format="%d-%b-%y")  # Convert DATE column
        df.sort_values(by="DATE", ascending=True, inplace=True)  # Sort by date

        return df
    except Exception as e:
        print(f"⚠️ Error reading historical data for {stock_symbol}: {e}")
        return None


def calculate_rsi(df):
    if df is None or df.empty:
        return None
    df["RSI"] = talib.RSI(df["CLOSE"], timeperiod=14)
    df["RSI-MA"] = df["RSI"].rolling(window=5).mean()
    df.dropna(inplace=True)  # Remove NaN values
    return df

# ✅ SEND TELEGRAM ALERT
async def send_telegram_alert(symbol, live_price, latest_rsi, latest_rsi_ma, signal):
    try:
        message = (
            f"📢 *Stock Alert: {symbol}*\n"
            f"-----------------------------------\n"
            f"💰 *Live Price:* {live_price:.2f} INR\n"
            f"📉 *RSI:* {latest_rsi:.2f}\n"
            f"📊 *RSI-MA:* {latest_rsi_ma:.2f}\n"
            f"🔹 *Signal:* {signal}\n"
            f"-----------------------------------"
        )
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")
        print(f"✅ Telegram alert sent for {symbol}")
    except Exception as e:
        print(f"⚠️ Error sending Telegram alert: {e}")

async def process_and_save_data():
    global result_file
    driver = setup_driver()
    if not driver:
        return

    symbols = get_top_20_symbols()
    live_prices_dict = {}

    for symbol in symbols:
        print(f"🚀 Processing {symbol}")

        # ✅ Fetch only historical data (without adding live price)
        historical_data = get_historical_data(symbol)
        if historical_data is None:
            continue

        # ✅ Calculate the indicators using functions from indicators.py
            print(f"Calculating indicators for {symbol}...")
            calculate_macd(historical_data, symbol)
            calculate_bollinger(historical_data, symbol)
            calculate_sma_ema(historical_data, symbol)
            calculate_adx(historical_data, symbol)

        # ✅ Calculate RSI on historical data
        rsi_df = calculate_rsi(historical_data)
        if rsi_df is None or rsi_df.empty:
            print(f"⚠️ RSI data empty for {symbol}, skipping alert.")
            continue



        # ✅ Fetch live price separately
        live_price = fetch_live_price(driver, symbol)

        if live_price is None:
            continue
        live_prices_dict[symbol] = live_price

        # ✅ Get latest RSI values
        latest_rsi = rsi_df.iloc[-1]["RSI"]
        latest_rsi_ma = rsi_df.iloc[-1]["RSI-MA"]
        prev_rsi = rsi_df.iloc[-2]["RSI"] if len(rsi_df) > 1 else None
        prev_rsi_ma = rsi_df.iloc[-2]["RSI-MA"] if len(rsi_df) > 1 else None

        # ✅ Generate Trading Signal
        if latest_rsi < 30:
            signal = "BUY (Oversold)"
        elif latest_rsi > 70:
            signal = "SELL (Overbought)"
        elif prev_rsi is not None and prev_rsi_ma is not None:
            if prev_rsi < prev_rsi_ma and latest_rsi > latest_rsi_ma:
                signal = "BUY (RSI Crossover)"  # Crossed ABOVE RSI-MA
            elif prev_rsi > prev_rsi_ma and latest_rsi < latest_rsi_ma:
                signal = "SELL (RSI Crossover)"  # Crossed BELOW RSI-MA
            else:
                signal = "HOLD"
        else:
            signal = "HOLD"

        # ✅ Send Alert
        await send_telegram_alert(symbol, live_price, latest_rsi, latest_rsi_ma, signal)

        # ✅ Save historical RSI data (No live price added)
        if rsi_df is not None and not rsi_df.empty:
            result_file = os.path.join(RESULT_FOLDER, f"{symbol}.xlsx")
            rsi_df.to_excel(result_file, index=False)
            print(f"💾 Data saved for {symbol} at {result_file}")
        else:
            print(f"⚠️ RSI data invalid for {symbol}, skipping file save.")

        print(f"💾 Data saved for {symbol} at {result_file}")

    driver.quit()
    print("✅ Execution completed successfully.")

# ✅ Create summary Excel from all saved RSI files
    summary_rows = []

    for symbol in symbols:
        result_file = os.path.join(RESULT_FOLDER, f"{symbol}.xlsx")
        if not os.path.exists(result_file):
            continue

        try:
            df = pd.read_excel(result_file)
            df.columns = df.columns.str.upper()

            if df.empty or "RSI" not in df.columns or "RSI-MA" not in df.columns:
                continue

            latest = df.iloc[-1]

            rsi = latest["RSI"]
            signal = (
                "BUY (Oversold)" if rsi < 30 else
                "SELL (Overbought)" if rsi > 70 else
                "HOLD"
            )

            summary_rows.append({
                "SYMBOL": symbol,
                "LIVE_PRICE": round(live_prices_dict.get(symbol, 0), 2),  # ✅ Actual live price
                "RSI": round(rsi, 2),
                "RSI_MA": round(latest["RSI-MA"], 2),
                "SIGNAL": signal
            })

        except Exception as e:
            print(f"⚠️ Error summarizing {symbol}: {e}")
            continue

    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_file_path = os.path.join(RESULT_FOLDER, "summary_prices.xlsx")
        summary_df.to_excel(summary_file_path, index=False)
        print(f"✅ Summary saved at {summary_file_path}")

# ✅ RUN SCRIPT
if __name__ == "__main__":
    asyncio.run(process_and_save_data())
