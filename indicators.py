import pandas as pd
import numpy as np
import os

def calculate_macd(df, symbol, folder='macd_reports'):
    # Define the full path where the folder should be created
    base_dir = r'C:\Users\abhij\PycharmProjects\bot'
    folder_path = os.path.join(base_dir, folder)

    # Ensure the folder exists
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Calculate MACD and Signal Line
    df['12_EMA'] = df['close'].ewm(span=12, adjust=False).mean()
    df['26_EMA'] = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['12_EMA'] - df['26_EMA']
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # Define the file path with the folder
    macd_file = os.path.join(folder_path, f"macd_{symbol}.xlsx")
    df[['Date', 'MACD', 'Signal_Line']].to_excel(macd_file, index=False)
    print(f"✅ MACD saved for {symbol} at {macd_file}")

def calculate_bollinger(df, symbol, folder='bollinger_reports'):
    # Define the full path where the folder should be created
    base_dir = r'C:\Users\abhij\PycharmProjects\bot'
    folder_path = os.path.join(base_dir, folder)

    # Ensure the folder exists
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Calculate Bollinger Bands
    window = 20
    df['SMA'] = df['close'].rolling(window=window).mean()
    df['std_dev'] = df['close'].rolling(window=window).std()
    df['Upper_Band'] = df['SMA'] + (2 * df['std_dev'])
    df['Lower_Band'] = df['SMA'] - (2 * df['std_dev'])

    # Define the file path with the folder
    bollinger_file = os.path.join(folder_path, f"bollinger_{symbol}.xlsx")
    df[['Date', 'Upper_Band', 'Lower_Band']].to_excel(bollinger_file, index=False)
    print(f"✅ Bollinger Bands saved for {symbol} at {bollinger_file}")

def calculate_sma_ema(df, symbol, folder='sma_ema_reports'):
    # Define the full path where the folder should be created
    base_dir = r'C:\Users\abhij\PycharmProjects\bot'
    folder_path = os.path.join(base_dir, folder)

    # Ensure the folder exists
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Calculate SMA and EMA
    df['SMA_10'] = df['close'].rolling(window=10).mean()
    df['EMA_10'] = df['close'].ewm(span=10, adjust=False).mean()

    # Define the file path with the folder
    sma_ema_file = os.path.join(folder_path, f"sma_ema_{symbol}.xlsx")
    df[['Date', 'SMA_10', 'EMA_10']].to_excel(sma_ema_file, index=False)
    print(f"✅ SMA/EMA saved for {symbol} at {sma_ema_file}")

def calculate_adx(df, symbol, folder='adx_reports'):
    # Define the full path where the folder should be created
    base_dir = r'C:\Users\abhij\PycharmProjects\bot'
    folder_path = os.path.join(base_dir, folder)

    # Ensure the folder exists
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Calculate +DM, -DM, TR, +DI, -DI, and ADX
    df['+DM'] = df['HIGH'].diff()
    df['-DM'] = df['LOW'].diff()

    df['+DM'] = np.where(df['+DM'] < 0, 0, df['+DM'])
    df['-DM'] = np.where(df['-DM'] < 0, 0, df['-DM'])

    df['TR'] = np.maximum.reduce([
        df['HIGH'] - df['LOW'],
        (df['HIGH'] - df['close'].shift()).abs(),
        (df['close'].shift() - df['LOW']).abs()
    ])

    df['+DI'] = 100 * (df['+DM'].rolling(window=14).sum() / df['TR'].rolling(window=14).sum())
    df['-DI'] = 100 * (df['-DM'].rolling(window=14).sum() / df['TR'].rolling(window=14).sum())

    df['ADX'] = 100 * ((df['+DI'] - df['-DI']).abs() / (df['+DI'] + df['-DI']))

    # Define the file path with the folder
    adx_file = os.path.join(folder_path, f"adx_{symbol}.xlsx")
    df[['Date', 'ADX']].to_excel(adx_file, index=False)
    print(f"✅ ADX saved for {symbol} at {adx_file}")

def process_historical_data(file_path):
    xls = pd.ExcelFile(file_path)

    for symbol in xls.sheet_names:
        print(f"\n🔍 Processing {symbol}...")
        df = pd.read_excel(xls, sheet_name=symbol)

        # Strip column names
        df.columns = df.columns.str.strip()

        # Show columns for debug
        print(f"📋 Columns in {symbol}: {df.columns.tolist()}")

        # Validate required columns
        required_cols = {'Date', 'close', 'HIGH', 'LOW'}
        if not required_cols.issubset(set(df.columns)):
            print(f"❌ Skipping {symbol}: Missing columns {required_cols - set(df.columns)}")
            continue

        # Convert Date
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True)

        # Calculate indicators
        calculate_macd(df, symbol)
        calculate_bollinger(df, symbol)
        calculate_sma_ema(df, symbol)
        calculate_adx(df, symbol)

        print(f"✅ All indicators calculated for {symbol}.")


# Path to your HISTORICAL_DATA.xlsx
file_path = r"C:\Users\abhij\Downloads\HISTORICAL_DATA.xlsx"

# Run processing
process_historical_data(file_path)
