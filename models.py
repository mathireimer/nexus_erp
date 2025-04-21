from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

# Initialize SQLAlchemy
db = SQLAlchemy()

# Association Tables
client_tag = db.Table(
    'client_tag',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('client_id', db.Integer, db.ForeignKey('client.id'), nullable=False),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), nullable=False)
)

vendor_tags = db.Table(
    'vendor_tags',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('vendor_id', db.Integer, db.ForeignKey('vendors.id'), nullable=False),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), nullable=False)
)

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100), nullable=False)
    buying_date = db.Column(db.Date, nullable=False)
    unit = db.Column(db.String(20), nullable=False, default='piece')
    purchase_price = db.Column(db.Float, nullable=False)
    sell_price = db.Column(db.Float, nullable=False)
    stock_qty = db.Column(db.Float, nullable=False, default=0)
    min_stock = db.Column(db.Float, nullable=False, default=0)
    max_stock = db.Column(db.Float, nullable=False, default=0)
    tax_rate = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    stock_movements = db.relationship('StockMovement', backref='product', lazy=True, cascade='all, delete-orphan')
    inventory_adjustments = db.relationship('InventoryAdjustment', backref='product', lazy=True, cascade='all, delete-orphan')
    bill_items = db.relationship('BillItem', backref='product', lazy=True)

    def __repr__(self):
        return f'<Product {self.name}>'

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='Pending')

class Client(db.Model):
    __tablename__ = 'client'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    tax_id = db.Column(db.String(50))
    payment_terms = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tags = db.relationship('Tag', secondary=client_tag, backref='clients', lazy=True)
    contacts = db.relationship('Contact', backref='client', lazy=True)

class Vendor(db.Model):
    __tablename__ = 'vendors'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    tax_id = db.Column(db.String(50))
    payment_terms = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tags = db.relationship('Tag', secondary='vendor_tags', backref='vendors', lazy=True)
    contacts = db.relationship('Contact', backref='vendor', lazy=True)

class Contact(db.Model):
    __tablename__ = 'contacts'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    type = db.Column(db.String(20), nullable=False)  # "billing", "general", "legal", "technical"
    notes = db.Column(db.Text, nullable=True)

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)

class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    bill_number = db.Column(db.String(50), unique=True)
    issue_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid_amount = db.Column(db.Numeric(10, 2))
    currency = db.Column(db.String(3), default='PYG')
    status = db.Column(db.String(20), default='Pending')  # Pending, Partially Paid, Paid
    notes = db.Column(db.Text)
    paid_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client = db.relationship('Client', backref='client_bills')
    vendor = db.relationship('Vendor', backref='vendor_bills')
    items = db.relationship('BillItem', backref='parent_bill', cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='bill', cascade='all, delete-orphan')

    @property
    def is_overdue(self):
        return self.status != 'Paid' and self.due_date < datetime.now().date()

    @property
    def balance_due(self):
        return self.total_amount - (self.paid_amount or 0)

class BillItem(db.Model):
    __tablename__ = 'bill_items'
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    bill = db.relationship('Bill', backref='bill_items')

    @property
    def subtotal(self):
        return self.quantity * self.price

    @property
    def tax_amount(self):
        return self.subtotal * (self.tax_rate / 100)

    @property
    def total(self):
        return self.subtotal + self.tax_amount

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    original_amount = db.Column(db.Numeric(10, 2), nullable=True)
    original_currency = db.Column(db.String(3), nullable=True)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'INCOME' or 'EXPENSE'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Transaction(db.Model):
    __tablename__ = 'transaction'
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

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # purchase, sale, adjustment, return
    quantity = db.Column(db.Float, nullable=False)
    source_id = db.Column(db.Integer, nullable=True)  # Bill ID, Adjustment ID, etc.
    source_type = db.Column(db.String(50), nullable=True)  # "bill", "adjustment", etc.
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<StockMovement {self.type} {self.quantity} units>'

class InventoryAdjustment(db.Model):
    __tablename__ = 'inventory_adjustments'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)