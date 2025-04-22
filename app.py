from flask import Flask, render_template, redirect, url_for, request, session, Response
import pandas as pd
import os
import sqlite3


app = Flask(__name__)
app.secret_key = 'ABHI'  # Change this for security

# ✅ Path to the result data
RESULT_FOLDER = r"C:\Users\abhij\PycharmProjects\bot\nifty100_results"


# ✅ Load instrument tokens globally after defining the function
instrument_tokens = {}

def load_instrument_tokens():
    global instrument_tokens  # Ensure it modifies the global dictionary
    try:
        df = pd.read_csv("instruments.csv")  # Ensure the file exists
        instrument_tokens = {row['tradingsymbol']: row['instrument_token'] for _, row in df.iterrows()}
        print("✅ Instrument tokens loaded successfully!")
    except Exception as e:
        print(f"⚠️ Error loading instruments.csv: {e}")

# ✅ Call the function before using `instrument_tokens`
load_instrument_tokens()

# Update stock data function
def get_stock_data():
    stock_data = {}
    files = os.listdir(RESULT_FOLDER)

    for file in files:
        if file.endswith(".xlsx"):
            symbol = file.replace(".xlsx", "")  # Extract stock symbol
            instrument_token = instrument_tokens.get(symbol, None)  # Get token

            if not instrument_token:
                print(f"⚠️ No token found for {symbol}")
                continue  # Skip stock if token not found

            file_path = os.path.join(RESULT_FOLDER, file)
            df = pd.read_excel(file_path)
            df.columns = df.columns.str.strip().str.upper()

            if not {'DATE', 'CLOSE', 'RSI', 'RSI-MA'}.issubset(df.columns):
                continue  # Skip if required columns are missing

            df['DATE'] = df['DATE'].astype(str)
            latest_data = df.iloc[-1]

            rsi = latest_data['RSI']
            signal = "BUY (Oversold)" if rsi < 30 else "SELL (Overbought)" if rsi > 70 else "HOLD"

            stock_data[symbol] = {
                'live_price': round(latest_data['CLOSE'], 2),
                'RSI': round(rsi, 2),
                'RSI_MA': round(latest_data['RSI-MA'], 2),
                'signal': signal,
                'instrument_token': instrument_token  # Add token here
            }

    return stock_data


# ✅ Home Page Route
@app.route('/')
def home():
    return render_template('signup.html')  # This should load the signup form


@app.route('/signup', methods=['GET', 'POST'])
def signup():

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Connect to database
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        # Check if user already exists
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return render_template('signup.html', error="Username already exists.")

        # Insert new user
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()

        return redirect(url_for('login'))  # Redirect to login page after successful signup

    return render_template('signup.html')  # For GET request, render the signup page

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Connect to the database
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        # Check credentials in the users table
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials. Please try again.")

    # For GET request, render the login form
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('home'))

    stock_data = get_stock_data()

    historical_data = {}

    for symbol in stock_data:
        try:
            file_path = os.path.join(RESULT_FOLDER, f"{symbol}.xlsx")
            df = pd.read_excel(file_path)
            df.columns = df.columns.str.upper()

            # Limit to last 30 rows
            df = df.tail(30)

            # Create dictionary with dates and close prices
            historical_data[symbol] = {
                'dates': df['DATE'].astype(str).tolist(),
                'close_prices': df['CLOSE'].tolist()
            }
        except Exception as e:
            print(f"Error loading historical data for {symbol}: {e}")
            continue

    return render_template("dashboard.html", stock_data=stock_data, historical_data=historical_data)

# ✅ CSV Download Route
@app.route('/download_csv')
def download_csv():
    stock_data = get_stock_data()  # Fetch stock data
    df_list = []

    for symbol, data in stock_data.items():
        df_list.append({
            "Stock Symbol": symbol,
            "Live Price": data['live_price'],
            "RSI": data['RSI'],
            "RSI-MA": data['RSI_MA'],
            "Signal": data['signal']
        })

    # Convert to DataFrame
    df = pd.DataFrame(df_list)

    # Convert DataFrame to CSV format
    csv_data = df.to_csv(index=False)

    # Send CSV as response
    response = Response(csv_data, mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=stock_data.csv"
    return response


# ✅ Logout Route
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))


# ✅ Routes for Indicators

# MACD Route
@app.route('/macd')
def macd_page():
    stock_data = get_stock_data()  # Fetching stock data
    macd_data = {}
    macd_folder = r'C:\Users\abhij\PycharmProjects\bot\macd_reports'

    for symbol in stock_data:
        try:
            file_path = os.path.join(macd_folder, f"macd_{symbol}.xlsx")
            df = pd.read_excel(file_path)
            df.columns = df.columns.str.upper()

            # Ensure required columns exist
            if 'DATE' not in df.columns or 'MACD' not in df.columns or 'SIGNAL_LINE' not in df.columns:
                raise ValueError(f"Missing required columns for {symbol}")

            # Collect the MACD data in the correct format for the template
            macd_data[symbol] = {
                'dates': df['DATE'].astype(str).tolist(),
                'macd': df['MACD'].tolist(),
                'signal_line': df['SIGNAL_LINE'].tolist(),
                'histogram': df['MACD'] - df['SIGNAL_LINE']  # Histogram = MACD - Signal Line
            }
        except FileNotFoundError:
            print(f"❌ File for {symbol} not found")
            continue
        except pd.errors.EmptyDataError:
            print(f"❌ No data in file for {symbol}")
            continue
        except Exception as e:
            print(f"❌ Error loading MACD for {symbol}: {e}")
            continue

    return render_template('macd_page.html', macd_data=macd_data)

@app.route('/bollinger')
def bollinger_page():
    stock_data = get_stock_data()  # Fetching stock data
    bollinger_data = {}
    bollinger_folder = r'C:\Users\abhij\PycharmProjects\bot\bollinger_reports'

    for symbol in stock_data:
        try:
            file_path = os.path.join(bollinger_folder, f"bollinger_{symbol}.xlsx")
            df = pd.read_excel(file_path)
            df.columns = df.columns.str.upper()

            # Ensure required columns exist
            if 'DATE' not in df.columns or 'UPPER_BAND' not in df.columns or 'LOWER_BAND' not in df.columns:
                raise ValueError(f"Missing required columns for {symbol}")

            bollinger_data[symbol] = {
                'dates': df['DATE'].astype(str).tolist(),
                'upper_band': df['UPPER_BAND'].tolist(),
                'lower_band': df['LOWER_BAND'].tolist()
            }
        except FileNotFoundError:
            print(f"❌ File for {symbol} not found")
            continue
        except pd.errors.EmptyDataError:
            print(f"❌ No data in file for {symbol}")
            continue
        except Exception as e:
            print(f"❌ Error loading Bollinger Bands for {symbol}: {e}")
            continue

    return render_template('bollinger_page.html', bollinger_data=bollinger_data)


# SMA/EMA Route
@app.route('/sma-ema')
def sma_ema_page():
    stock_data = get_stock_data()
    sma_ema_data = {}
    sma_ema_folder = r'C:\Users\abhij\PycharmProjects\bot\sma_ema_reports'

    for symbol in stock_data:
        try:
            file_path = os.path.join(sma_ema_folder, f"sma_ema_{symbol}.xlsx")
            df = pd.read_excel(file_path)
            df.columns = df.columns.str.upper()

            if 'DATE' not in df.columns or 'SMA_10' not in df.columns or 'EMA_10' not in df.columns:
                raise ValueError(f"Missing required columns for {symbol}")

            sma_ema_data[symbol] = {
                'dates': df['DATE'].astype(str).tolist(),
                'sma': df['SMA_10'].tolist(),
                'ema': df['EMA_10'].tolist()
            }
        except FileNotFoundError:
            print(f"❌ File for {symbol} not found")
            continue
        except pd.errors.EmptyDataError:
            print(f"❌ No data in file for {symbol}")
            continue
        except Exception as e:
            print(f"❌ Error loading SMA/EMA for {symbol}: {e}")
            continue

    return render_template('sma_ema_page.html', sma_ema_data=sma_ema_data)


# ADX Route
@app.route('/adx')
def adx_page():
    stock_data = get_stock_data()
    adx_data = {}
    adx_folder = r'C:\Users\abhij\PycharmProjects\bot\adx_reports'

    for symbol in stock_data:
        try:
            file_path = os.path.join(adx_folder, f"adx_{symbol}.xlsx")
            df = pd.read_excel(file_path)
            df.columns = df.columns.str.upper()

            if 'DATE' not in df.columns or 'ADX' not in df.columns:
                raise ValueError(f"Missing required columns for {symbol}")

            adx_data[symbol] = {
                'dates': df['DATE'].astype(str).tolist(),
                'adx': df['ADX'].tolist()
            }
        except FileNotFoundError:
            print(f"❌ File for {symbol} not found")
            continue
        except pd.errors.EmptyDataError:
            print(f"❌ No data in file for {symbol}")
            continue
        except Exception as e:
            print(f"❌ Error loading ADX for {symbol}: {e}")
            continue

    return render_template('adx_page.html', adx_data=adx_data)


if __name__ == '__main__':
    app.run(debug=True)
