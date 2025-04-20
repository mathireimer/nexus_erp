from flask import Blueprint, jsonify, request, current_app
from models import db, Product, StockMovement, InventoryAdjustment, Category
from datetime import datetime
from flask_login import login_required, current_user

inventory = Blueprint('inventory', __name__)

@inventory.route('/api/products', methods=['GET'])
@login_required
def get_products():
    products = Product.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': p.id,
        'sku': p.sku,
        'name': p.name,
        'description': p.description,
        'category_id': p.category_id,
        'unit': p.unit,
        'purchase_price': p.purchase_price,
        'sell_price': p.sell_price,
        'stock_qty': p.stock_qty,
        'min_stock': p.min_stock,
        'tax_rate': p.tax_rate,
        'created_at': p.created_at.isoformat(),
        'updated_at': p.updated_at.isoformat()
    } for p in products])

@inventory.route('/api/products', methods=['POST'])
@login_required
def create_product():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['sku', 'name', 'unit', 'purchase_price', 'sell_price']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Check if SKU already exists
    if Product.query.filter_by(sku=data['sku']).first():
        return jsonify({'error': 'SKU already exists'}), 400
    
    product = Product(
        user_id=current_user.id,
        sku=data['sku'],
        name=data['name'],
        description=data.get('description'),
        category_id=data.get('category_id'),
        unit=data['unit'],
        purchase_price=data['purchase_price'],
        sell_price=data['sell_price'],
        stock_qty=data.get('stock_qty', 0),
        min_stock=data.get('min_stock', 0),
        tax_rate=data.get('tax_rate', 0.0)
    )
    
    db.session.add(product)
    db.session.commit()
    
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
    for field in ['name', 'description', 'category_id', 'unit', 'purchase_price', 
                 'sell_price', 'min_stock', 'tax_rate']:
        if field in data:
            setattr(product, field, data[field])
    
    db.session.commit()
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