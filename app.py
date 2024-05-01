from flask import Flask, jsonify, request
from flask_cors import CORS
from nse import NSE
from datetime import date, timedelta
from jugaad_data.nse import stock_df, NSELive

# Working directory
DIR = "/content"

app = Flask(__name__)
CORS(app)

@app.route("/get_symbol_lastprice", methods=["GET"])
def get_symbol_lastprice():
    nse = NSE(download_folder=DIR)
    status = nse.listFnoStocks()
    data = status["data"]

    symbol_lastprice = {}
    for item in data:
        symbol_lastprice[item["symbol"]] = item["lastPrice"]

    return jsonify(symbol_lastprice)



def get_total_close_price(stocks, num_days):
    end_date = date.today()
    start_date = end_date - timedelta(days=num_days)

    total_close_price_by_date = {}
    historical_data = {}

    # Fetch historical data for each stock once
    for symbol in stocks:
        historical_data[symbol] = stock_df(symbol=symbol, from_date=start_date, to_date=end_date + timedelta(days=1), series="EQ")

    for day_delta in range(num_days):
        current_date = start_date + timedelta(days=day_delta)
        total_close_price = 0

        for symbol, quantity in stocks.items():
            df = historical_data[symbol]

            if not df.empty:
                relevant_data = df[df['DATE'] == current_date.strftime("%Y-%m-%d")]
                if not relevant_data.empty:
                    close_price = relevant_data.iloc[0]["CLOSE"]
                    total_close_price += close_price * quantity

        total_close_price = round(total_close_price, 2)
        if total_close_price > 0:  # Only include dates with total_value > 0
            total_close_price_by_date[current_date.strftime("%Y-%m-%d")] = total_close_price

    return [{"date": date, "total_value": value} for date, value in total_close_price_by_date.items()]

@app.route("/calculate_total_value", methods=["POST"])
def calculate_total_value():
    request_data = request.get_json()

    stocks = request_data.get("stocks", {})
    num_days = request_data.get("num_days", 30)

    if not isinstance(num_days, int) or num_days <= 0:
        return jsonify({"error": "Invalid num_days, must be a positive integer"}), 400

    if not isinstance(stocks, dict) or not stocks:
        return jsonify({"error": "Invalid or empty stocks data"}), 400

    result = get_total_close_price(stocks, num_days)
    return jsonify(result)

@app.route('/calculate_sts', methods=['POST'])
def calculate_sts():
    try:
        plans_data = request.json['plans_data']
        response_data = []
        nse = NSELive()

        for plan in plans_data:
            data = plan['stocks']
            results = []
            for stock in data:
                symbol = stock['symbol']
                qty = stock['qty']
                avg_price = stock['price']

                stock_quote = nse.stock_quote(symbol)
                price_info = stock_quote['priceInfo']

                current_price = price_info['lastPrice']
                previous_close = price_info['previousClose']
                close_price = price_info['close']

                if current_price == 0 and previous_close == 0:
                    today_change_percent = 0
                    total_change_percent = ((close_price - avg_price) / avg_price) * 100
                    current_price = close_price
                else:
                    today_change_percent = ((current_price - previous_close) / previous_close) * 100
                    total_change_percent = ((current_price - avg_price) / avg_price) * 100

                results.append({
                    'symbol': symbol,
                    'today_change_percent': round(today_change_percent, 2),
                    'total_change_percent': round(total_change_percent, 2),
                    'current_value': round(qty * current_price, 2),
                    'total_current_value': round((total_current_value + plan['cash']),2),
                    'initial_value': round(plan['startVal'])
                })

            total_current_value = sum(stock['current_value'] for stock in results)

            response_data.append({
                'planName': plan['planName'],
                'individual_stocks': results,
                'total_current_gains': round(((total_current_value + plan["cash"] - plan['startVal']) / plan['startVal']) * 100, 2)
            })

        return jsonify({'plans_data': response_data}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 400
    
@app.route('/calculate', methods=['POST'])
def calculate_stocks():
    try:
        data = request.json['stocks']
        results = []
        nse = NSELive()

        for stock in data:
            symbol = stock['symbol']
            qty = stock['qty']
            avg_price = stock['avg_price']

            stock_quote = nse.stock_quote(symbol)
            price_info = stock_quote['priceInfo']
            current_price = price_info['lastPrice']
            previous_close = price_info['previousClose']
            close_price = price_info['close']


            if current_price == 0 or previous_close == 0:
                today_change_percent = 0
                total_change_percent = ((close_price - avg_price) / avg_price) * 100
                current_price = close_price
            else:
                today_change_percent = ((current_price - previous_close) / previous_close) * 100
                total_change_percent = ((current_price - avg_price) / avg_price) * 100

            results.append({
                'symbol': symbol,
                'today_change_percent': round(today_change_percent, 2),
                'total_change_percent': round(total_change_percent, 2),
                'current_value': round(qty * current_price, 2)
            })

        total_current_value = sum(stock['current_value'] for stock in results)

        return jsonify({
            'individual_stocks': results,
            'total_current_value': round(total_current_value, 2)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    
@app.route('/calculate_cagr', methods=['POST'])
def calculate_cagr():
    try:
        data = request.json['stocks']
        nse = NSELive()
        current_date = date.today()
        one_year_ago = current_date - timedelta(days=365)

        current_value = 0
        value_one_year_ago = 0

        for stock in data:
            symbol = stock['symbol']
            qty = stock['qty']
            avg_price = stock['avg_price']

            stock_quote = nse.stock_quote(symbol)
            price_info = stock_quote['priceInfo']
            # print (price_info)
            current_price = price_info['lastPrice']

            current_value += qty * current_price


            historical_data = stock_df(symbol=symbol, from_date=one_year_ago-timedelta(3), to_date=one_year_ago, series="EQ")
            print (historical_data)
            if not historical_data.empty:
                value_one_year_ago += qty * historical_data.iloc[-1]["CLOSE"]

        cagr = ((current_value / value_one_year_ago) ** (1/1) - 1) * 100  # CAGR formula assuming one year

        return jsonify({
            'current_value': round(current_value, 2),
            'value_one_year_ago': round(value_one_year_ago, 2),
            'cagr': round(cagr, 2)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == "__main__":
    app.run()

