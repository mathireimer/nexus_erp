from flask import Blueprint, jsonify, request, current_app
from models import db, Product, StockMovement, InventoryAdjustment, Category
from datetime import datetime
from flask_login import login_required, current_user
import random
import string

inventory = Blueprint('inventory', __name__)

def generate_sku():
    """Generate a unique 25-character SKU."""
    while True:
        # Generate a random string of 25 characters (letters and numbers)
        chars = string.ascii_uppercase + string.digits
        sku = ''.join(random.choice(chars) for _ in range(25))
        
        # Check if SKU already exists
        if not Product.query.filter_by(sku=sku).first():
            return sku

@inventory.route('/api/products', methods=['GET'])
@login_required
def get_products():
    products = Product.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': p.id,
        'sku': p.sku,
        'name': p.name,
        'description': p.description,
        'category': p.category,
        'buying_date': p.buying_date.isoformat() if p.buying_date else None,
        'unit': p.unit,
        'purchase_price': p.purchase_price,
        'sell_price': p.sell_price,
        'stock_qty': p.stock_qty,
        'min_stock': p.min_stock,
        'max_stock': p.max_stock,
        'tax_rate': p.tax_rate,
        'created_at': p.created_at.isoformat(),
        'updated_at': p.updated_at.isoformat()
    } for p in products])

@inventory.route('/api/products', methods=['POST'])
@login_required
def create_product():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['name', 'category', 'buying_date', 'unit', 'purchase_price', 'sell_price', 'max_stock']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Generate unique SKU
    sku = generate_sku()
    
    # Parse buying_date from string to date object
    try:
        buying_date = datetime.strptime(data['buying_date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid buying_date format. Use YYYY-MM-DD'}), 400
    
    product = Product(
        user_id=current_user.id,
        sku=sku,
        name=data['name'],
        description=data.get('description'),
        category=data['category'],
        buying_date=buying_date,
        unit=data['unit'],
        purchase_price=data['purchase_price'],
        sell_price=data['sell_price'],
        stock_qty=data.get('stock_qty', 0),
        min_stock=data.get('min_stock', 0),
        max_stock=data['max_stock'],
        tax_rate=data.get('tax_rate', 0.0)
    )
    
    db.session.add(product)
    db.session.commit()
    
    return jsonify({
        'id': product.id,
        'sku': product.sku,
        'name': product.name,
        'description': product.description,
        'category': product.category,
        'buying_date': product.buying_date.isoformat(),
        'unit': product.unit,
        'purchase_price': product.purchase_price,
        'sell_price': product.sell_price,
        'stock_qty': product.stock_qty,
        'min_stock': product.min_stock,
        'max_stock': product.max_stock,
        'tax_rate': product.tax_rate,
        'created_at': product.created_at.isoformat(),
        'updated_at': product.updated_at.isoformat()
    }), 201

@inventory.route('/api/products/<int:product_id>', methods=['GET'])
@login_required
def get_product(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()
    return jsonify({
        'id': product.id,
        'sku': product.sku,
        'name': product.name,
        'description': product.description,
        'category_id': product.category_id,
        'unit': product.unit,
        'purchase_price': product.purchase_price,
        'sell_price': product.sell_price,
        'stock_qty': product.stock_qty,
        'min_stock': product.min_stock,
        'tax_rate': product.tax_rate,
        'created_at': product.created_at.isoformat(),
        'updated_at': product.updated_at.isoformat()
    })

@inventory.route('/api/products/<int:product_id>', methods=['PATCH'])
@login_required
def update_product(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    
    # Update fields if provided
    if 'name' in data:
        product.name = data['name']
    if 'description' in data:
        product.description = data['description']
    if 'category' in data:
        product.category = data['category']
    if 'unit' in data:
        product.unit = data['unit']
    if 'purchase_price' in data:
        product.purchase_price = data['purchase_price']
    if 'sell_price' in data:
        product.sell_price = data['sell_price']
    if 'min_stock' in data:
        product.min_stock = data['min_stock']
    if 'max_stock' in data:
        product.max_stock = data['max_stock']
    if 'tax_rate' in data:
        product.tax_rate = data['tax_rate']
    if 'buying_date' in data:
        try:
            product.buying_date = datetime.strptime(data['buying_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid buying_date format. Use YYYY-MM-DD'}), 400
    
    try:
        db.session.commit()
        return jsonify({
            'id': product.id,
            'sku': product.sku,
            'name': product.name,
            'description': product.description,
            'category': product.category,
            'buying_date': product.buying_date.isoformat() if product.buying_date else None,
            'unit': product.unit,
            'purchase_price': product.purchase_price,
            'sell_price': product.sell_price,
            'stock_qty': product.stock_qty,
            'min_stock': product.min_stock,
            'max_stock': product.max_stock,
            'tax_rate': product.tax_rate,
            'created_at': product.created_at.isoformat(),
            'updated_at': product.updated_at.isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@inventory.route('/api/products/<int:product_id>', methods=['DELETE'])
@login_required
def delete_product(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()
    db.session.delete(product)
    db.session.commit()
    return '', 204

@inventory.route('/api/products/<int:product_id>/adjust-stock', methods=['POST'])
@login_required
def adjust_stock(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    
    if 'quantity' not in data or 'reason' not in data:
        return jsonify({'error': 'Missing required fields: quantity and reason'}), 400
    
    quantity = float(data['quantity'])
    reason = data['reason']
    
    # Create inventory adjustment
    adjustment = InventoryAdjustment(
        product_id=product.id,
        quantity=quantity,
        reason=reason,
        user_id=current_user.id
    )
    
    # Update stock quantity
    product.stock_qty += quantity
    
    # Record stock movement
    movement = StockMovement(
        product_id=product.id,
        type='adjustment',
        quantity=quantity,
        source_id=adjustment.id,
        source_type='adjustment'
    )
    
    db.session.add(adjustment)
    db.session.add(movement)
    db.session.commit()
    
    return jsonify({
        'id': adjustment.id,
        'product_id': adjustment.product_id,
        'quantity': adjustment.quantity,
        'reason': adjustment.reason,
        'created_at': adjustment.created_at.isoformat()
    }), 201

@inventory.route('/api/products/<int:product_id>/stock-movements', methods=['GET'])
@login_required
def get_stock_movements(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()
    movements = StockMovement.query.filter_by(product_id=product.id).order_by(StockMovement.timestamp.desc()).all()
    
    return jsonify([{
        'id': m.id,
        'type': m.type,
        'quantity': m.quantity,
        'source_id': m.source_id,
        'source_type': m.source_type,
        'timestamp': m.timestamp.isoformat()
    } for m in movements])

@inventory.route('/api/products/low-stock', methods=['GET'])
@login_required
def get_low_stock_products():
    products = Product.query.filter(
        Product.user_id == current_user.id,
        Product.stock_qty <= Product.min_stock
    ).all()
    
    return jsonify([{
        'id': p.id,
        'sku': p.sku,
        'name': p.name,
        'stock_qty': p.stock_qty,
        'min_stock': p.min_stock,
        'unit': p.unit
    } for p in products]) 