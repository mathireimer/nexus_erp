from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate  # Add Flask-Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy and Migrate
db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Initialize Flask-Migrate


# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='Pending')


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Auto-assigned ID
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    tax_id = db.Column(db.String(50))
    payment_terms = db.Column(db.String(50))

    # Relationship to Invoice
    invoices = db.relationship('Invoice', backref='client', lazy=True)


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)  # Foreign key to Client
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='PYG')  # Add currency field with a default value
    status = db.Column(db.String(20), default='Unpaid')  # Unpaid, Paid, Partially Paid


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'INCOME' or 'EXPENSE'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'INCOME', 'EXPENSE', 'TRANSFER'
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    source_module = db.Column(db.String(50))  # e.g., 'invoice', 'manual', etc.
    source_id = db.Column(db.String(100))  # External ID (e.g., invoice ID)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='PYG')  # ISO 4217 code
    exchange_rate = db.Column(db.Float, nullable=True)  # Optional
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='CONFIRMED')  # 'PENDING', 'CONFIRMED', 'CANCELLED'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category = db.relationship('Category', backref='transactions')


# Routes
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/clients')
def clients():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    clients = Client.query.all()
    return render_template('clients.html', clients=clients)


@app.route('/create_client', methods=['POST'])
def create_client():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    name = request.form['name']
    email = request.form['email']
    tax_id = request.form['tax_id']
    payment_terms = request.form['payment_terms']

    # Validate email uniqueness
    existing_client = Client.query.filter_by(email=email).first()
    if existing_client:
        flash('A client with this email already exists.', 'danger')
        return redirect(url_for('clients'))

    # Create the new client
    new_client = Client(
        name=name,
        email=email,
        tax_id=tax_id,
        payment_terms=payment_terms
    )
    db.session.add(new_client)
    db.session.commit()
    flash('Client created successfully!', 'success')
    return redirect(url_for('clients'))


@app.route('/products')
def products():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    products = Product.query.all()
    return render_template('products.html', products=products)


@app.route('/add_product', methods=['POST'])
def add_product():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    name = request.form['name']
    quantity = int(request.form['quantity'])
    price = float(request.form['price'])
    new_product = Product(name=name, quantity=quantity, price=price)
    db.session.add(new_product)
    db.session.commit()
    flash('Product added successfully!', 'success')
    return redirect(url_for('products'))


@app.route('/invoices')
def invoices():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Separate invoices into active and historic
    active_invoices = Invoice.query.filter_by(status='Unpaid').all()
    historic_invoices = Invoice.query.filter_by(status='Paid').all()
    return render_template('invoices.html', active_invoices=active_invoices, historic_invoices=historic_invoices)


@app.route('/create_invoice', methods=['POST'])
def create_invoice():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    client_id = int(request.form['client_id'])
    issue_date = datetime.strptime(request.form['issue_date'], '%Y-%m-%d')
    due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d')
    total_amount = float(request.form['total_amount'])
    currency = request.form.get('currency', 'PYG')  # Optional: Add currency input to the form

    # Validate client_id
    client = Client.query.get(client_id)
    if not client:
        flash('Invalid client ID. Please select a valid client.', 'danger')
        return redirect(url_for('invoices'))

    # Auto-generate invoice number
    last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
    invoice_number = f"INV-{last_invoice.id + 1 if last_invoice else 1}"

    new_invoice = Invoice(
        client_id=client_id,
        invoice_number=invoice_number,
        issue_date=issue_date,
        due_date=due_date,
        total_amount=total_amount,
        currency=currency  # Save the currency
    )
    db.session.add(new_invoice)
    db.session.commit()
    flash('Invoice created successfully!', 'success')
    return redirect(url_for('invoices'))


@app.route('/mark_paid/<int:invoice_id>', methods=['POST'])
def mark_paid(invoice_id):
    # Fetch the invoice by ID
    invoice = Invoice.query.get_or_404(invoice_id)

    # Get the payment amount from the form (default to total_amount if not provided)
    payment_amount = float(request.form.get('payment_amount', invoice.total_amount))

    # Ensure the payment amount does not exceed the invoice total
    if payment_amount > invoice.total_amount:
        flash('Payment amount cannot exceed the invoice total.', 'danger')
        return redirect(url_for('invoices'))

    # Update the invoice status based on the payment amount
    if payment_amount == invoice.total_amount:
        invoice.status = 'Paid'
    else:
        invoice.status = 'Partially Paid'

    # Create an income transaction for the payment
    new_transaction = Transaction(
        user_id=session['user_id'],
        type='INCOME',
        amount=payment_amount,
        currency=invoice.currency,  # Use the invoice's currency
        date=datetime.utcnow().date(),
        description=f'Payment for Invoice #{invoice.invoice_number}',
        source_module='invoice',
        source_id=invoice.id
    )

    # Add the transaction to the database
    db.session.add(new_transaction)

    # Commit changes to the database
    db.session.commit()

    # Flash a success message
    if payment_amount == invoice.total_amount:
        flash(f'Invoice #{invoice.invoice_number} marked as paid. Payment recorded in cash flow.', 'success')
    else:
        flash(f'Partial payment of {payment_amount} recorded for Invoice #{invoice.invoice_number}.', 'info')

    # Redirect back to the invoices page
    return redirect(url_for('invoices'))


@app.route('/cash-flow')
def cash_flow():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('cash_flow.html')


@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    if 'user_id' not in session:
        return {'error': 'Unauthorized'}, 401

    data = request.get_json()
    required_fields = ['type', 'amount', 'currency', 'date']
    if not all(field in data for field in required_fields):
        return {'error': 'Missing required fields'}, 400

    # Validate transaction type
    if data['type'] not in ['INCOME', 'EXPENSE', 'TRANSFER']:
        return {'error': 'Invalid transaction type'}, 400

    # Create the transaction
    new_transaction = Transaction(
        user_id=session['user_id'],
        type=data['type'],
        category_id=data.get('category_id'),
        source_module=data.get('source_module'),
        source_id=data.get('source_id'),
        amount=float(data['amount']),
        currency=data['currency'],
        exchange_rate=float(data.get('exchange_rate')) if data.get('exchange_rate') else None,
        date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
        description=data.get('description'),
        status=data.get('status', 'CONFIRMED')
    )
    db.session.add(new_transaction)
    db.session.commit()

    return {'message': 'Transaction added successfully', 'transaction_id': new_transaction.id}, 201


@app.route('/api/transactions', methods=['GET'])
def list_transactions():
    if 'user_id' not in session:
        return {'error': 'Unauthorized'}, 401

    start_date = request.args.get('start')
    end_date = request.args.get('end')
    transaction_type = request.args.get('type', 'ALL')

    query = Transaction.query.filter_by(user_id=session['user_id'])

    if start_date and end_date:
        query = query.filter(Transaction.date.between(start_date, end_date))

    if transaction_type != 'ALL':
        query = query.filter_by(type=transaction_type)

    transactions = query.order_by(Transaction.date.asc()).all()

    result = []
    for transaction in transactions:
        result.append({
            'id': transaction.id,
            'type': transaction.type,
            'category': transaction.category.name if transaction.category else None,
            'amount': transaction.amount,
            'currency': transaction.currency,
            'date': transaction.date.strftime('%Y-%m-%d'),
            'description': transaction.description,
            'status': transaction.status
        })

    return {'transactions': result}


@app.route('/api/transactions/summary', methods=['GET'])
def transaction_summary():
    period = request.args.get('period', 'monthly')
    start_date, end_date = calculate_period_range(period)  # Helper function to calculate date range

    income_total = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.user_id == session['user_id'],
        Transaction.type == 'INCOME',
        Transaction.date.between(start_date, end_date)
    ).scalar() or 0

    expense_total = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.user_id == session['user_id'],
        Transaction.type == 'EXPENSE',
        Transaction.date.between(start_date, end_date)
    ).scalar() or 0

    return {
        'income_total': income_total,
        'expense_total': expense_total,
        'net_cash': income_total - expense_total
    }


def calculate_period_range(period):
    today = datetime.today()
    if period == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == 'monthly':
        start_date = today.replace(day=1)
        end_date = (start_date.replace(month=start_date.month % 12 + 1) - timedelta(days=1))
    elif period == 'yearly':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    else:
        start_date = today - timedelta(days=30)
        end_date = today
    return start_date.date(), end_date.date()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(debug=True)