from flask import request, jsonify
from flask_login import login_required
from datetime import datetime
from models import Product, Bill, BillItem, StockMovement
from app import db

@bp.route('/api/bills', methods=['POST'])
@login_required
def create_bill():
    try:
        data = request.get_json()
        print(f"Received bill data: {data}")  # Debug log
        
        # Validate required fields
        if not data.get('client_id') or not data.get('items'):
            return jsonify({'error': 'Client ID and items are required'}), 400
        
        # Validate items
        items = data.get('items', [])
        if not items:
            return jsonify({'error': 'At least one item is required'}), 400
        
        # Check stock availability and collect products
        products = []
        for item in items:
            product = Product.query.get(item.get('product_id'))
            if not product:
                return jsonify({'error': f'Product with ID {item.get("product_id")} not found'}), 404
            
            quantity = item.get('quantity', 0)
            if quantity <= 0:
                return jsonify({'error': 'Quantity must be greater than 0'}), 400
            
            print(f"Checking stock for product {product.name}: Current stock = {product.stock_qty}, Requested quantity = {quantity}")  # Debug log
            
            if product.stock_qty < quantity:
                return jsonify({
                    'error': f'Insufficient stock for {product.name}. Available: {product.stock_qty}'
                }), 400
            
            products.append((product, quantity))
        
        # Create bill
        bill = Bill(
            client_id=data.get('client_id'),
            issue_date=datetime.strptime(data.get('issue_date'), '%Y-%m-%d').date(),
            due_date=datetime.strptime(data.get('due_date'), '%Y-%m-%d').date(),
            status='draft',
            currency=data.get('currency', 'USD')
        )
        
        db.session.add(bill)
        db.session.flush()  # Get bill ID
        print(f"Created bill with ID: {bill.id}")  # Debug log
        
        # Create bill items and deduct stock
        total_amount = 0
        for product, quantity in products:
            price = float(items[products.index((product, quantity))].get('price', 0))
            tax_rate = float(items[products.index((product, quantity))].get('tax_rate', 0))
            
            # Calculate item total with tax
            item_subtotal = price * quantity
            item_tax = item_subtotal * (tax_rate / 100)
            item_total = item_subtotal + item_tax
            
            # Create bill item
            bill_item = BillItem(
                bill_id=bill.id,
                product_id=product.id,
                quantity=quantity,
                price=price,
                tax_rate=tax_rate,
                subtotal=item_subtotal,
                tax_amount=item_tax,
                total=item_total
            )
            db.session.add(bill_item)
            
            # Add to total amount
            total_amount += item_total
            
            # Update product stock
            old_stock = product.stock_qty
            product.stock_qty = product.stock_qty - quantity
            print(f"Updating stock for {product.name}: {old_stock} -> {product.stock_qty}")  # Debug log
            
            # Create stock movement record
            movement = StockMovement(
                product_id=product.id,
                quantity=-quantity,  # Negative for deduction
                type='sale',
                source_type='bill',
                source_id=bill.id,
                notes=f'Sold in bill #{bill.id}'
            )
            db.session.add(movement)
            print(f"Created stock movement: {movement.quantity} units of {product.name}")  # Debug log
        
        # Update bill total
        bill.total_amount = total_amount
        
        try:
            db.session.commit()
            print("Successfully committed all changes to database")  # Debug log
            return jsonify({
                'id': bill.id,
                'message': 'Bill created successfully'
            }), 201
        except Exception as e:
            print(f"Error committing changes: {str(e)}")  # Debug log
            db.session.rollback()
            return jsonify({'error': f'Failed to create bill: {str(e)}'}), 500
            
    except Exception as e:
        print(f"Error in create_bill: {str(e)}")  # Debug log
        db.session.rollback()
        return jsonify({'error': str(e)}), 500 