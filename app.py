from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import db, User, Client, Vendor, Contact, Tag, Product, Invoice, Transaction  # Import models here
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy and Migrate
db.init_app(app)
migrate = Migrate(app, db)

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

# Routes
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get counts for dashboard
    clients = Client.query.all()
    vendors = Vendor.query.all()
    products = Product.query.all()
    active_invoices = Invoice.query.filter_by(status='Unpaid').all()
    
    # Get recent transactions
    recent_transactions = Transaction.query.order_by(Transaction.date.desc()).limit(5).all()
    
    return render_template('home.html',
                         clients=clients,
                         vendors=vendors,
                         products=products,
                         active_invoices=active_invoices,
                         recent_transactions=recent_transactions)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
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
def clients():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    clients = Client.query.all()
    return render_template('clients.html', clients=clients)

@app.route('/create_client', methods=['POST'])
def create_client():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    name = request.form.get('name')
    email = request.form.get('email')
    tax_id = request.form.get('tax_id')
    payment_terms = request.form.get('payment_terms')

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

@app.route('/vendors')
def vendors():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    vendors = Vendor.query.all()
    return render_template('vendors.html', vendors=vendors)

@app.route('/create_vendor', methods=['POST'])
def create_vendor():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    name = request.form.get('name')
    email = request.form.get('email')
    tax_id = request.form.get('tax_id')
    payment_terms = request.form.get('payment_terms')

    # Validate email uniqueness
    existing_vendor = Vendor.query.filter_by(email=email).first()
    if existing_vendor:
        flash('A vendor with this email already exists.', 'danger')
        return redirect(url_for('vendors'))

    # Create the new vendor
    new_vendor = Vendor(
        user_id=session['user_id'],
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
def edit_vendor(vendor_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    vendor = Vendor.query.get_or_404(vendor_id)
    
    # Check if the vendor belongs to the current user
    if vendor.user_id != session['user_id']:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('vendors'))
    
    # Get form data
    name = request.form.get('name')
    email = request.form.get('email')
    tax_id = request.form.get('tax_id')
    payment_terms = request.form.get('payment_terms')
    
    # Check email uniqueness if email is changed
    if email != vendor.email:
        existing_vendor = Vendor.query.filter_by(email=email).first()
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
def delete_vendor(vendor_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    vendor = Vendor.query.get_or_404(vendor_id)
    
    # Check if the vendor belongs to the current user
    if vendor.user_id != session['user_id']:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('vendors'))
    
    # Check if vendor has associated invoices
    if vendor.invoices:
        flash('Cannot delete vendor with associated invoices.', 'danger')
        return redirect(url_for('vendors'))
    
    db.session.delete(vendor)
    db.session.commit()
    flash('Vendor deleted successfully!', 'success')
    return redirect(url_for('vendors'))

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
    name = request.form.get('name')
    quantity = int(request.form.get('quantity'))
    price = float(request.form.get('price'))

    # Create the new product
    new_product = Product(name=name, quantity=quantity, price=price)
    db.session.add(new_product)
    db.session.commit()
    flash('Product added successfully!', 'success')
    return redirect(url_for('products'))

@app.route('/invoices')
def invoices():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    active_invoices = Invoice.query.filter_by(status='Unpaid').all()
    historic_invoices = Invoice.query.filter_by(status='Paid').all()
    return render_template('invoices.html', active_invoices=active_invoices, historic_invoices=historic_invoices)

@app.route('/create_invoice', methods=['POST'])
def create_invoice():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    client_id = int(request.form.get('client_id'))
    issue_date = datetime.strptime(request.form.get('issue_date'), '%Y-%m-%d')
    due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d')
    total_amount = float(request.form.get('total_amount'))
    currency = request.form.get('currency', 'PYG')  # Default to PYG

    # Validate client ID
    client = Client.query.get(client_id)
    if not client:
        flash('Invalid client ID. Please select a valid client.', 'danger')
        return redirect(url_for('invoices'))

    # Auto-generate invoice number
    last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
    invoice_number = f"INV-{last_invoice.id + 1 if last_invoice else 1}"

    # Create the new invoice
    new_invoice = Invoice(
        client_id=client_id,
        invoice_number=invoice_number,
        issue_date=issue_date,
        due_date=due_date,
        total_amount=total_amount,
        currency=currency
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
        currency=invoice.currency,
        date=datetime.utcnow().date(),
        description=f'Payment for Invoice #{invoice.invoice_number}',
        source_module='invoice',
        source_id=invoice.id
    )
    db.session.add(new_transaction)
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
    start_date, end_date = calculate_period_range(period)

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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(debug=True)