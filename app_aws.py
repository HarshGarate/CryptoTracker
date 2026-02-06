import boto3
import requests
import io
import base64
import decimal
import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr

application = Flask(__name__)
application.secret_key = 'capstone_secret_key'

# --- AWS DynamoDB Configuration (Matches PDF Pgs 9, 11, 33) ---
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
USERS_TABLE = dynamodb.Table('Users')
WATCHLIST_TABLE = dynamodb.Table('Watchlist')
MARKET_TABLE = dynamodb.Table('MarketPrices')

login_manager = LoginManager()
login_manager.init_app(application)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    return User(username)

# --- Helper Functions ---
def create_chart(prices):
    """Generates sparkline chart (PDF Pg 26)"""
    if not prices: return ""
    plt.figure(figsize=(4, 1.5))
    plt.plot(prices, color='#ff9900', linewidth=2)
    plt.axis('off')
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    plt.close()
    return image_base64

def store_crypto_data(data):
    """Stores API data into DynamoDB MarketPrices (PDF Pg 28)"""
    with MARKET_TABLE.batch_writer() as batch:
        for coin in data:
            # Convert float to Decimal for DynamoDB
            price = decimal.Decimal(str(coin['current_price'])) if coin['current_price'] else decimal.Decimal(0)
            change = decimal.Decimal(str(coin.get('price_change_percentage_24h', 0) or 0))
            m_cap = decimal.Decimal(str(coin.get('market_cap', 0) or 0))
            
            # Extract sparkline prices (limit to avoid DB size issues if needed)
            sparkline = [str(p) for p in coin.get('sparkline_in_7d', {}).get('price', [])]

            batch.put_item(Item={
                'symbol': coin['symbol'],
                'name': coin['name'],
                'current_price': price,
                'price_change_percentage_24h': change,
                'market_cap': m_cap,
                'image': coin['image'],
                'sparkline_7d': sparkline, # Storing as list of strings
                'last_updated': str(datetime.datetime.now())
            })

# --- Routes ---
@application.route('/')
def index():
    return render_template('index.html')

@application.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        
        try:
            # Check if user exists
            if 'Item' in USERS_TABLE.get_item(Key={'username': username}):
                flash('Username already exists', 'danger')
            else:
                USERS_TABLE.put_item(Item={'username': username, 'email': email, 'password': password})
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
        except ClientError as e:
            flash(f"Error: {e.response['Error']['Message']}", 'danger')
    return render_template('register.html')

@application.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        response = USERS_TABLE.get_item(Key={'username': username})
        if 'Item' in response and check_password_hash(response['Item']['password'], password):
            login_user(User(username))
            return redirect(url_for('trading'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@application.route('/trading')
@login_required
def trading():
    # 1. Fetch from API
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1&sparkline=true"
    try:
        api_data = requests.get(url).json()
        # 2. Store in DynamoDB (PDF Requirement)
        store_crypto_data(api_data)
    except Exception as e:
        print(f"API Error: {e}")
    
    # 3. Read from DynamoDB to display (PDF Requirement)
    response = MARKET_TABLE.scan()
    db_items = response.get('Items', [])
    
    # Sort locally since Scan doesn't guarantee order
    db_items.sort(key=lambda x: x.get('market_cap', 0), reverse=True)
    
    return render_template('trading.html', cryptos=db_items)

@application.route('/crypto/<symbol>')
@login_required
def crypto_detail(symbol):
    # Fetch details from DB or API
    try:
        response = MARKET_TABLE.get_item(Key={'symbol': symbol})
        coin = response.get('Item')
        
        if coin and 'sparkline_7d' in coin:
            # Convert decimal strings back to floats for charting
            prices = [float(p) for p in coin['sparkline_7d']]
            chart_img = create_chart(prices)
            coin['chart'] = chart_img
            return render_template('crypto_detail.html', coin=coin)
    except:
        pass
    flash('Crypto details not found or API limit reached', 'warning')
    return redirect(url_for('trading'))

@application.route('/add_to_watchlist', methods=['POST'])
@login_required
def add_to_watchlist():
    data = request.get_json()
    symbol = data.get('symbol')
    WATCHLIST_TABLE.put_item(Item={'user_id': current_user.id, 'crypto_symbol': symbol})
    return jsonify({'message': f'{symbol} added to watchlist'})

@application.route('/remove_from_watchlist', methods=['POST'])
@login_required
def remove_from_watchlist():
    data = request.get_json()
    symbol = data.get('symbol')
    WATCHLIST_TABLE.delete_item(Key={'user_id': current_user.id, 'crypto_symbol': symbol})
    return jsonify({'message': f'{symbol} removed'})

@application.route('/watchlist')
@login_required
def watchlist():
    # Scan watchlist table for current user
    response = WATCHLIST_TABLE.scan(FilterExpression=Attr('user_id').eq(current_user.id))
    watchlist_items = response.get('Items', [])
    
    final_items = []
    # Join with MarketPrices to get price details
    for item in watchlist_items:
        sym = item['crypto_symbol']
        coin_resp = MARKET_TABLE.get_item(Key={'symbol': sym})
        if 'Item' in coin_resp:
            coin = coin_resp['Item']
            # Re-key for template compatibility if needed
            coin['crypto_symbol'] = sym
            final_items.append(coin)
        else:
            # Fallback if market data missing
            final_items.append({'crypto_symbol': sym, 'name': sym.upper(), 'current_price': 'N/A'})
            
    return render_template('watchlist.html', items=final_items)

@application.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=5000)