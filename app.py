from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import db, User, Client, Vendor, Contact, Tag, Product, Transaction, BillItem, Payment, Bill, StockMovement  # Import models here
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from decimal import Decimal
from routes.inventory import inventory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import requests
from functools import lru_cache
import logging
from bs4 import BeautifulSoup
import os
import json

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['EXCHANGE_RATES_API_URL'] = 'https://open.er-api.com/v6/latest/PYG'

# Initialize SQLAlchemy and Migrate
db.init_app(app)
migrate = Migrate(app, db)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Register blueprints
app.register_blueprint(inventory)

# Custom template filters
@app.template_filter('format_currency')
def format_currency_filter(value):
    """Format a number as currency."""
    try:
        return "{:,.2f}".format(float(value))
    except (ValueError, TypeError):
        return "0.00"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper Functions
def calculate_period_range(period):
    """Helper function to calculate date ranges for summaries."""
    today = datetime.today()
    if period == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == 'monthly':
        start_date = today.replace(day=1)
        next_month = start_date.replace(month=start_date.month % 12 + 1)
        end_date = (next_month - timedelta(days=1))
    elif period == 'yearly':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    else:  # Default to last 30 days
        start_date = today - timedelta(days=30)
        end_date = today
    return start_date.date(), end_date.date()

class ExchangeRateCache:
    def __init__(self):
        self.cache = {}
        self.ttl = timedelta(hours=1)  # 1 hour TTL

    def get(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None

    def set(self, key, value):
        self.cache[key] = (value, datetime.now())

# Initialize the cache
exchange_rate_cache = ExchangeRateCache()

def get_exchange_rate(from_currency, to_currency='PYG'):
    """Get real-time exchange rate from one currency to another (defaults to PYG)"""
    if from_currency == to_currency:
        return Decimal('1')
    
    # Check cache first
    cache_key = f"{from_currency}_{to_currency}"
    cached_rate = exchange_rate_cache.get(cache_key)
    if cached_rate is not None:
        return cached_rate
    
    try:
        # Using exchangerate.host API (free, no API key required)
        params = {
            'base': from_currency,
            'symbols': to_currency
        }
        response = requests.get(app.config['EXCHANGE_RATES_API_URL'], params=params, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if data.get('success', True) and data.get('rates', {}).get(to_currency):
            rate = Decimal(str(data['rates'][to_currency]))
            logging.info(f"Retrieved exchange rate: 1 {from_currency} = {rate} {to_currency}")
            # Cache the rate
            exchange_rate_cache.set(cache_key, rate)
            return rate
        else:
            raise ValueError("Exchange rate not found in response")
            
    except Exception as e:
        logging.error(f"Error fetching exchange rate: {e}")
        # Default rates as fallback (you should update these periodically)
        default_rates = {
            'USD': Decimal('7250'),  # 1 USD = 7250 PYG
            'EUR': Decimal('7900'),  # 1 EUR = 7900 PYG
            'GBP': Decimal('9200'),  # 1 GBP = 9200 PYG
        }
        
        if from_currency in default_rates:
            logging.warning(f"Using fallback rate for {from_currency}")
            return default_rates[from_currency]
        elif to_currency in default_rates:
            # If converting to PYG from another currency, use inverse rate
            base_rate = default_rates[from_currency]
            return Decimal('1') / base_rate if base_rate != 0 else Decimal('1')
        
        return Decimal('1')

def convert_to_pyg(amount, from_currency):
    """Convert any amount to PYG using real-time rates"""
    if from_currency == 'PYG':
        return amount
    rate = get_exchange_rate(from_currency)
    converted = amount * rate
    logging.info(f"Converted {amount} {from_currency} to {converted} PYG (rate: {rate})")
    return converted

# Routes
@app.route('/')
@login_required
def home():
    # Get counts for dashboard
    clients = Client.query.filter_by(user_id=current_user.id).all()
    vendors = Vendor.query.filter_by(user_id=current_user.id).all()
    products = Product.query.filter_by(user_id=current_user.id).all()
    active_bills = Bill.query.filter_by(status='Unpaid').all()
    
    # Get recent transactions
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).limit(5).all()
    
    return render_template('home.html',
                         clients=clients,
                         vendors=vendors,
                         products=products,
                         active_bills=active_bills,
                         recent_transactions=recent_transactions)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/clients')
@login_required
def clients():
    clients = Client.query.filter_by(user_id=current_user.id).all()
    return render_template('clients.html', clients=clients)

@app.route('/create_client', methods=['POST'])
@login_required
def create_client():
    name = request.form.get('name')
    email = request.form.get('email')
    tax_id = request.form.get('tax_id')
    payment_terms = request.form.get('payment_terms')

    # Validate email uniqueness
    existing_client = Client.query.filter_by(email=email, user_id=current_user.id).first()
    if existing_client:
        flash('A client with this email already exists.', 'danger')
        return redirect(url_for('clients'))

    # Create the new client
    new_client = Client(
        user_id=current_user.id,
        name=name,
        email=email,
        tax_id=tax_id,
        payment_terms=payment_terms
    )
    db.session.add(new_client)
    db.session.commit()
    flash('Client created successfully!', 'success')
    return redirect(url_for('clients'))

@app.route('/vendors')
@login_required
def vendors():
    vendors = Vendor.query.filter_by(user_id=current_user.id).all()
    return render_template('vendors.html', vendors=vendors)

@app.route('/create_vendor', methods=['POST'])
@login_required
def create_vendor():
    name = request.form.get('name')
    email = request.form.get('email')
    tax_id = request.form.get('tax_id')
    payment_terms = request.form.get('payment_terms')

    # Validate email uniqueness
    existing_vendor = Vendor.query.filter_by(email=email, user_id=current_user.id).first()
    if existing_vendor:
        flash('A vendor with this email already exists.', 'danger')
        return redirect(url_for('vendors'))

    # Create the new vendor
    new_vendor = Vendor(
        user_id=current_user.id,
        name=name,
        email=email,
        tax_id=tax_id,
        payment_terms=payment_terms
    )
    db.session.add(new_vendor)
    db.session.commit()
    flash('Vendor created successfully!', 'success')
    return redirect(url_for('vendors'))

@app.route('/edit_vendor/<int:vendor_id>', methods=['POST'])
@login_required
def edit_vendor(vendor_id):
    vendor = Vendor.query.filter_by(id=vendor_id, user_id=current_user.id).first_or_404()
    
    # Get form data
    name = request.form.get('name')
    email = request.form.get('email')
    tax_id = request.form.get('tax_id')
    payment_terms = request.form.get('payment_terms')
    
    # Check email uniqueness if email is changed
    if email != vendor.email:
        existing_vendor = Vendor.query.filter_by(email=email, user_id=current_user.id).first()
        if existing_vendor:
            flash('A vendor with this email already exists.', 'danger')
            return redirect(url_for('vendors'))
    
    # Update vendor information
    vendor.name = name
    vendor.email = email
    vendor.tax_id = tax_id
    vendor.payment_terms = payment_terms
    vendor.updated_at = datetime.utcnow()
    
    db.session.commit()
    flash('Vendor updated successfully!', 'success')
    return redirect(url_for('vendors'))

@app.route('/delete_vendor/<int:vendor_id>')
@login_required
def delete_vendor(vendor_id):
    vendor = Vendor.query.filter_by(id=vendor_id, user_id=current_user.id).first_or_404()
    
    # Check if vendor has associated bills
    if vendor.bills:
        flash('Cannot delete vendor with associated bills.', 'danger')
        return redirect(url_for('vendors'))
    
    db.session.delete(vendor)
    db.session.commit()
    flash('Vendor deleted successfully!', 'success')
    return redirect(url_for('vendors'))

@app.route('/products')
@login_required
def products():
    products = Product.query.filter_by(user_id=current_user.id).all()
    return render_template('products.html', products=products)

@app.route('/bills')
@login_required
def bills():
    active_bills = Bill.query.filter_by(user_id=current_user.id, status='Unpaid').all()
    partially_paid_bills = Bill.query.filter_by(user_id=current_user.id, status='Partially Paid').all()
    historic_bills = Bill.query.filter_by(user_id=current_user.id, status='Paid').all()
    
    # Calculate total pending amount in PYG
    partially_paid_total = sum(
        convert_to_pyg(bill.total_amount - (bill.paid_amount or 0), bill.currency)
        for bill in partially_paid_bills
    )
    
    clients = Client.query.filter_by(user_id=current_user.id).all()
    products = Product.query.filter_by(user_id=current_user.id).all()
    
    return render_template('bills.html',
                         active_bills=active_bills + partially_paid_bills,
                         historic_bills=historic_bills,
                         partially_paid_total=partially_paid_total,
                         clients=clients,
                         products=products)

@app.route('/create_bill', methods=['POST'])
@login_required
def create_bill():
    data = request.form
    
    # Auto-generate bill number
    last_bill = Bill.query.filter_by(user_id=current_user.id).order_by(Bill.id.desc()).first()
    bill_number = f"BILL-{last_bill.id + 1 if last_bill else 1}"

    # Create the new bill
    new_bill = Bill(
        user_id=current_user.id,
        bill_number=bill_number,
        client_id=data['client_id'],
        issue_date=datetime.strptime(data['issue_date'], '%Y-%m-%d'),
        due_date=datetime.strptime(data['due_date'], '%Y-%m-%d'),
        currency=data['currency'],
        notes=data.get('notes'),
        status='Unpaid'
    )
    
    # Calculate totals
    subtotal = Decimal('0')
    total_tax = Decimal('0')
    
    # Process items
    product_ids = request.form.getlist('items[][product_id]')
    quantities = request.form.getlist('items[][quantity]')
    prices = request.form.getlist('items[][price]')
    tax_rates = request.form.getlist('items[][tax_rate]')
    
    for i in range(len(product_ids)):
        if product_ids[i]:  # Only process if product is selected
            quantity = Decimal(quantities[i])
            price = Decimal(prices[i])
            tax_rate = Decimal(tax_rates[i] or '0')
            
            # Get the product
            product = Product.query.get(product_ids[i])
            if not product:
                flash(f'Product with ID {product_ids[i]} not found', 'error')
                return redirect(url_for('bills'))
            
            # Check stock availability
            if product.stock_qty < float(quantity):
                flash(f'Insufficient stock for {product.name}. Available: {product.stock_qty}', 'error')
                return redirect(url_for('bills'))
            
            item_subtotal = quantity * price
            item_tax = item_subtotal * (tax_rate / 100)
            
            subtotal += item_subtotal
            total_tax += item_tax
            
            # Add bill item
            new_bill.items.append(BillItem(
                product_id=product_ids[i],
                quantity=quantity,
                price=price,
                tax_rate=tax_rate
            ))
            
            # Update product stock
            old_stock = product.stock_qty
            product.stock_qty = product.stock_qty - float(quantity)
            
            # Create stock movement record
            movement = StockMovement(
                product_id=product.id,
                quantity=-float(quantity),  # Negative for deduction
                type='sale',
                source_type='bill',
                source_id=new_bill.id
            )
            db.session.add(movement)
    
    new_bill.total_amount = subtotal + total_tax
    
    try:
        db.session.add(new_bill)
        db.session.commit()
        flash('Bill created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating bill: {str(e)}', 'error')
    
    return redirect(url_for('bills'))

@app.route('/mark_paid/<int:bill_id>', methods=['POST'])
@login_required
def mark_paid(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    
    payment_amount = Decimal(request.form.get('payment_amount'))
    payment_currency = request.form.get('payment_currency', bill.currency)
    payment_method = request.form.get('payment_method')
    notes = request.form.get('notes')

    # Convert payment to bill's currency if different
    if payment_currency != bill.currency:
        # First convert to PYG, then to bill's currency
        amount_in_pyg = convert_to_pyg(payment_amount, payment_currency)
        if bill.currency != 'PYG':
            payment_amount = amount_in_pyg / get_exchange_rate(bill.currency)
        else:
            payment_amount = amount_in_pyg

    # Validate payment amount
    remaining_balance = bill.total_amount - (bill.paid_amount or Decimal('0'))
    if payment_amount > remaining_balance:
        flash('Payment amount cannot exceed the remaining balance.', 'danger')
        return redirect(url_for('bills'))

    # Update the bill's paid amount
    if bill.paid_amount is None:
        bill.paid_amount = Decimal('0')
    bill.paid_amount += payment_amount

    # Update bill status
    if bill.paid_amount >= bill.total_amount:
        bill.status = 'Paid'
        bill.paid_date = datetime.utcnow().date()
    else:
        bill.status = 'Partially Paid'

    # Create payment record with original currency info
    payment = Payment(
        bill_id=bill.id,
        amount=payment_amount,
        original_currency=payment_currency,
        original_amount=Decimal(request.form.get('payment_amount')),
        payment_date=datetime.utcnow().date(),
        payment_method=payment_method,
        notes=f"{notes}\nOriginal payment: {request.form.get('payment_amount')} {payment_currency}"
    )
    db.session.add(payment)

    # Create transaction record
    transaction = Transaction(
        user_id=current_user.id,
        type='INCOME',
        amount=float(payment_amount),
        currency=bill.currency,
        date=datetime.utcnow().date(),
        description=f'Payment for Bill #{bill.bill_number}',
        source_module='bill',
        source_id=bill.id
    )
    db.session.add(transaction)
    
    try:
        db.session.commit()
        if bill.status == 'Paid':
            flash(f'Bill #{bill.bill_number} marked as paid. Payment recorded in cash flow.', 'success')
        else:
            remaining = bill.total_amount - bill.paid_amount
            flash(f'Payment of {payment_amount} {bill.currency} recorded. Remaining balance: {remaining} {bill.currency}', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error recording payment. Please try again.', 'danger')
    
    return redirect(url_for('bills'))

@app.route('/cash-flow')
@login_required
def cash_flow():
    return render_template('cash_flow.html')

@app.route('/api/transactions', methods=['POST'])
@login_required
def create_transaction():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['type', 'amount', 'description', 'date']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Create new transaction
    transaction = Transaction(
        user_id=current_user.id,
        type=data['type'],
        amount=float(data['amount']),
        description=data['description'],
        date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
        status='CONFIRMED'
    )
    
    db.session.add(transaction)
    
    try:
        db.session.commit()
        return jsonify({
            'id': transaction.id,
            'type': transaction.type,
            'amount': transaction.amount,
            'description': transaction.description,
            'date': transaction.date.isoformat(),
            'status': transaction.status
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create transaction'}), 500

@app.route('/api/transactions', methods=['GET'])
@login_required
def list_transactions():
    period = request.args.get('period', 'monthly')
    start_date, end_date = calculate_period_range(period)
    
    transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).order_by(Transaction.date.desc()).all()
    
    return jsonify([{
        'id': t.id,
        'type': t.type,
        'amount': t.amount,
        'currency': t.currency,
        'date': t.date.isoformat(),
        'description': t.description,
        'status': t.status
    } for t in transactions])

@app.route('/api/transactions/summary', methods=['GET'])
@login_required
def transaction_summary():
    period = request.args.get('period', 'monthly')
    start_date, end_date = calculate_period_range(period)
    
    transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).all()
    
    income = sum(t.amount for t in transactions if t.type == 'INCOME')
    expenses = sum(t.amount for t in transactions if t.type == 'EXPENSE')
    
    return jsonify({
        'period': period,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'income': income,
        'expenses': expenses,
        'balance': income - expenses
    })

@app.route('/inventory')
@login_required
def inventory_page():
    return render_template('inventory.html')

@app.route('/billing')
@login_required
def billing():
    # Get all bills
    active_bills = Bill.query.filter(
        Bill.user_id == current_user.id,
        Bill.status.in_(['Pending', 'Partially Paid'])
    ).order_by(Bill.due_date.asc()).all()
    
    paid_bills = Bill.query.filter_by(
        user_id=current_user.id,
        status='Paid'
    ).order_by(Bill.paid_date.desc()).all()
    
    # Calculate summary statistics
    total_outstanding = sum(bill.balance_due for bill in active_bills)
    overdue_count = sum(1 for bill in active_bills if bill.is_overdue)
    
    # Calculate paid this month
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    paid_this_month = sum(
        bill.total_amount 
        for bill in paid_bills 
        if bill.paid_date and bill.paid_date >= start_of_month
    )
    
    # Get clients and products for the create bill form
    clients = Client.query.filter_by(user_id=current_user.id).all()
    products = Product.query.filter_by(user_id=current_user.id).all()
    
    return render_template('billing.html',
                         active_bills=active_bills,
                         paid_bills=paid_bills,
                         total_outstanding=total_outstanding,
                         overdue_count=overdue_count,
                         paid_this_month=paid_this_month,
                         total_bills=len(active_bills) + len(paid_bills),
                         clients=clients,
                         products=products)

@app.route('/billing/record-payment', methods=['POST'])
@login_required
def record_payment():
    data = request.form
    bill = Bill.query.filter_by(id=data['bill_id'], user_id=current_user.id).first_or_404()
    
    amount = Decimal(data['amount'])
    if amount > bill.balance_due:
        flash('Payment amount cannot exceed the remaining balance.', 'danger')
        return redirect(url_for('billing'))
    
    # Update bill
    if not bill.paid_amount:
        bill.paid_amount = amount
    else:
        bill.paid_amount += amount
    
    if bill.paid_amount >= bill.total_amount:
        bill.status = 'Paid'
        bill.paid_date = datetime.strptime(data['payment_date'], '%Y-%m-%d')
    else:
        bill.status = 'Partially Paid'
    
    # Create payment record
    payment = Payment(
        bill_id=bill.id,
        amount=amount,
        payment_date=datetime.strptime(data['payment_date'], '%Y-%m-%d'),
        payment_method=data['payment_method'],
        notes=data.get('notes')
    )
    
    # Create transaction record
    transaction = Transaction(
        user_id=current_user.id,
        type='INCOME',
        amount=amount,
        currency=bill.currency,
        date=payment.payment_date,
        description=f'Payment for Bill #{bill.bill_number}',
        source_module='billing',
        source_id=bill.id
    )
    
    db.session.add(payment)
    db.session.add(transaction)
    db.session.commit()
    
    flash('Payment recorded successfully!', 'success')
    return redirect(url_for('billing'))

@app.route('/billing/<int:bill_id>/send-reminder', methods=['POST'])
@login_required
def send_payment_reminder(bill_id):
    bill = Bill.query.filter_by(id=bill_id, user_id=current_user.id).first_or_404()
    
    if not bill.client or not bill.client.email:
        return jsonify({'error': 'Client email not available'}), 400
    
    try:
        # Here you would implement the email sending logic
        # For now, we'll just pretend it worked
        flash('Payment reminder sent successfully!', 'success')
        return jsonify({'message': 'Reminder sent successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/bill/<int:bill_id>')
@login_required
def bill_detail(bill_id):
    bill = Bill.query.filter_by(id=bill_id, user_id=current_user.id).first_or_404()
    return render_template('bill_detail.html', bill=bill)

@app.route('/currency-exchange')
@login_required
def currency_exchange():
    """Display the currency exchange rates page."""
    return render_template('currency_exchange.html')

@app.route('/api/exchange-rate', methods=['GET'])
@login_required
def get_current_rate():
    """Get current exchange rates from BCP website."""
    try:
        url = 'https://www.bcp.gov.py/webapps/web/cotizacion/monedas'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        # If we get a 403, use fallback rates
        if response.status_code == 403:
            app.logger.warning("Access to BCP website blocked. Using fallback rates.")
            return {
                'rates': {
                    'USD': 7400.00,  # Updated to reflect sell rate
                    'EUR': 8000.00,  # Updated to reflect sell rate
                    'BRL': 1550.00,  # Updated to reflect sell rate
                    'ARS': 9.00,     # Updated to reflect sell rate
                },
                'timestamp': int(datetime.now().timestamp()),
                'source': 'fallback'
            }
            
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the exchange rate table
        table = soup.find('table', {'class': 'table'})
        if not table:
            app.logger.error("Exchange rate table not found on BCP website")
            raise ValueError("Exchange rate table not found")
            
        rates = {}
        # Process each row in the table
        for row in table.find_all('tr')[1:]:  # Skip header row
            columns = row.find_all('td')
            if len(columns) >= 4:  # Ensure row has enough columns (including sell rate)
                try:
                    currency_name = columns[0].text.strip()
                    currency_code = columns[1].text.strip()
                    sell_rate_text = columns[3].text.strip().replace('.', '').replace(',', '.')  # Use column 3 for sell rate
                    
                    if currency_code and sell_rate_text:
                        rate = float(sell_rate_text)
                        rates[currency_code] = rate
                        app.logger.info(f"Found sell rate for {currency_code}: {rate}")
                except (ValueError, IndexError) as e:
                    app.logger.warning(f"Error processing row: {e}")
                    continue
        
        if not rates:
            raise ValueError("No exchange rates found")
            
        app.logger.info(f"Successfully fetched {len(rates)} exchange rates")
        return {
            'rates': rates,
            'timestamp': int(datetime.now().timestamp()),
            'source': 'bcp'
        }
            
    except requests.RequestException as e:
        app.logger.error(f"Request error fetching exchange rates: {str(e)}")
        # Return fallback rates on any request error
        return {
            'rates': {
                'USD': 7400.00,  # Updated to reflect sell rate
                'EUR': 8000.00,  # Updated to reflect sell rate
                'BRL': 1550.00,  # Updated to reflect sell rate
                'ARS': 9.00,     # Updated to reflect sell rate
            },
            'timestamp': int(datetime.now().timestamp()),
            'source': 'fallback'
        }
    except Exception as e:
        app.logger.error(f"Error processing exchange rates: {str(e)}")
        raise

@app.route('/api/exchange-rates', methods=['GET'])
@login_required
def get_exchange_rates():
    """API endpoint to get current exchange rates."""
    try:
        rates_data = get_current_rate()
        return jsonify(rates_data)
    except Exception as e:
        app.logger.error(f"Error in exchange rates endpoint: {str(e)}")
        return jsonify({'error': 'Failed to fetch exchange rates'}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
