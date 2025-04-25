from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from models import db, PurchaseInvoice, PurchaseInvoiceItem, Product, StockMovement, Transaction, Category
from flask_login import login_required, current_user
from decimal import Decimal

bp = Blueprint('purchase_invoices', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'xml'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/purchase-invoices', methods=['POST'])
@login_required
def create_purchase_invoice():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['invoice_number', 'date', 'vendor_id', 'items']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Create the purchase invoice
        invoice = PurchaseInvoice(
            user_id=current_user.id,
            invoice_number=data['invoice_number'],
            date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
            due_date=datetime.strptime(data['due_date'], '%Y-%m-%d').date() if data.get('due_date') else None,
            vendor_id=data['vendor_id'],
            total=data.get('total', 0),
            status=data.get('status', 'unpaid'),
            notes=data.get('notes')
        )

        # Calculate total from items
        total = 0
        for item_data in data['items']:
            item = PurchaseInvoiceItem(
                description=item_data['description'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                tax_rate=item_data.get('tax_rate', 0),
                total=item_data['quantity'] * item_data['unit_price'] * (1 + item_data.get('tax_rate', 0) / 100)
            )
            if 'product_id' in item_data:
                item.product_id = item_data['product_id']
                # Update product stock
                product = Product.query.get(item_data['product_id'])
                if product:
                    product.stock_qty += item_data['quantity']
                    # Create stock movement
                    movement = StockMovement(
                        product_id=product.id,
                        type='purchase',
                        quantity=item_data['quantity'],
                        source_id=invoice.id,
                        source_type='purchase_invoice'
                    )
                    db.session.add(movement)
            total += item.total
            invoice.items.append(item)

        invoice.total = total

        # Handle file upload if present
        if 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Save file to uploads directory
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'purchase_invoices', filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                file.save(file_path)
                invoice.attached_file = file_path

        db.session.add(invoice)
        db.session.commit()

        # Create transaction if invoice is paid
        if invoice.status == 'paid':
            expense_category = Category.query.filter_by(
                user_id=current_user.id,
                type='EXPENSE',
                name='Purchases'
            ).first()
            
            if not expense_category:
                expense_category = Category(
                    user_id=current_user.id,
                    name='Purchases',
                    type='EXPENSE'
                )
                db.session.add(expense_category)
                db.session.commit()

            transaction = Transaction(
                user_id=current_user.id,
                type='EXPENSE',
                category_id=expense_category.id,
                source_module='purchase_invoice',
                source_id=str(invoice.id),
                amount=invoice.total,
                date=invoice.date,
                description=f'Purchase Invoice #{invoice.invoice_number}',
                status='CONFIRMED'
            )
            db.session.add(transaction)
            db.session.commit()

        return jsonify({
            'message': 'Purchase invoice created successfully',
            'invoice_id': invoice.id
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/purchase-invoices/<int:invoice_id>', methods=['GET'])
@login_required
def get_purchase_invoice(invoice_id):
    invoice = PurchaseInvoice.query.filter_by(
        id=invoice_id,
        user_id=current_user.id
    ).first_or_404()

    # Calculate paid amount from payments
    paid_amount = sum(payment.amount for payment in invoice.invoice_payments)

    return jsonify({
        'id': invoice.id,
        'invoice_number': invoice.invoice_number,
        'date': invoice.date.isoformat(),
        'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
        'vendor_id': invoice.vendor_id,
        'vendor_name': invoice.vendor.name,
        'total': float(invoice.total),
        'paid_amount': float(paid_amount),
        'status': invoice.status,
        'notes': invoice.notes,
        'attached_file': invoice.attached_file,
        'items': [{
            'id': item.id,
            'product_id': item.product_id,
            'description': item.description,
            'quantity': float(item.quantity),
            'unit_price': float(item.unit_price),
            'tax_rate': float(item.tax_rate),
            'total': float(item.total)
        } for item in invoice.items]
    })

@bp.route('/purchase-invoices/<int:invoice_id>', methods=['PATCH'])
@login_required
def update_purchase_invoice(invoice_id):
    try:
        invoice = PurchaseInvoice.query.filter_by(
            id=invoice_id,
            user_id=current_user.id
        ).first_or_404()

        data = request.get_json()
        
        # Update basic fields
        if 'invoice_number' in data:
            invoice.invoice_number = data['invoice_number']
        if 'date' in data:
            invoice.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        if 'due_date' in data:
            invoice.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date() if data['due_date'] else None
        if 'status' in data:
            invoice.status = data['status']
        if 'notes' in data:
            invoice.notes = data['notes']

        # Update items if provided
        if 'items' in data:
            # Remove existing items and revert stock changes
            for item in invoice.items:
                if item.product_id:
                    product = Product.query.get(item.product_id)
                    if product:
                        # Convert Decimal to float for stock update
                        product.stock_qty = float(product.stock_qty) - float(item.quantity)
                db.session.delete(item)

            # Add new items
            total = Decimal('0')
            for item_data in data['items']:
                quantity = Decimal(str(item_data['quantity']))
                unit_price = Decimal(str(item_data['unit_price']))
                tax_rate = Decimal(str(item_data.get('tax_rate', '0')))
                
                item = PurchaseInvoiceItem(
                    description=item_data['description'],
                    quantity=quantity,
                    unit_price=unit_price,
                    tax_rate=tax_rate,
                    total=quantity * unit_price * (1 + tax_rate / 100)
                )
                
                if 'product_id' in item_data and item_data['product_id']:
                    item.product_id = item_data['product_id']
                    # Update product stock
                    product = Product.query.get(item_data['product_id'])
                    if product:
                        # Convert Decimal to float for stock update
                        product.stock_qty = float(product.stock_qty) + float(quantity)
                        # Create stock movement
                        movement = StockMovement(
                            product_id=product.id,
                            type='purchase',
                            quantity=float(quantity),
                            source_id=invoice.id,
                            source_type='purchase_invoice'
                        )
                        db.session.add(movement)
                
                total += item.total
                invoice.items.append(item)

            invoice.total = total

        db.session.commit()

        return jsonify({
            'message': 'Purchase invoice updated successfully',
            'invoice_id': invoice.id
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/purchase-invoices', methods=['GET'])
@login_required
def list_purchase_invoices():
    try:
        # Get filter parameters
        vendor_id = request.args.get('vendor_id')
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Start with base query
        query = PurchaseInvoice.query.filter_by(user_id=current_user.id)

        # Apply filters
        if vendor_id:
            query = query.filter_by(vendor_id=vendor_id)
        if status:
            query = query.filter_by(status=status)
        if start_date:
            query = query.filter(PurchaseInvoice.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(PurchaseInvoice.date <= datetime.strptime(end_date, '%Y-%m-%d').date())

        # Execute query
        invoices = query.order_by(PurchaseInvoice.date.desc()).all()

        # Format response
        return jsonify([{
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'date': invoice.date.isoformat(),
            'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
            'vendor_id': invoice.vendor_id,
            'vendor_name': invoice.vendor.name,
            'total': float(invoice.total),
            'status': invoice.status,
            'notes': invoice.notes,
            'last_payment': max([p.payment_date.isoformat() for p in invoice.invoice_payments]) if invoice.invoice_payments else None,
            'paid_amount': float(sum(payment.amount for payment in invoice.invoice_payments))
        } for invoice in invoices])

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/purchase-invoices/<int:invoice_id>', methods=['DELETE'])
@login_required
def delete_purchase_invoice(invoice_id):
    try:
        from decimal import Decimal
        
        invoice = PurchaseInvoice.query.filter_by(
            id=invoice_id,
            user_id=current_user.id
        ).first_or_404()

        # Check if invoice has payments
        if invoice.invoice_payments:
            return jsonify({
                'error': 'Cannot delete invoice with existing payments. Please remove payments first.'
            }), 400

        # Revert stock changes
        for item in invoice.items:
            if item.product_id:
                product = Product.query.get(item.product_id)
                if product:
                    try:
                        # Convert quantities to float for calculation
                        current_stock = float(product.stock_qty)
                        item_quantity = float(item.quantity)
                        # Subtract the quantity since we're deleting a purchase
                        product.stock_qty = current_stock - item_quantity
                        
                        # Create stock movement record
                        movement = StockMovement(
                            product_id=product.id,
                            type='adjustment',
                            quantity=-item_quantity,  # Negative for deduction
                            source_type='purchase_invoice_deletion',
                            source_id=invoice.id
                        )
                        db.session.add(movement)
                    except Exception as e:
                        db.session.rollback()
                        return jsonify({
                            'error': f'Error updating stock for product {product.name}: {str(e)}'
                        }), 500

        try:
            # Delete the invoice (cascade will handle items)
            db.session.delete(invoice)
            db.session.commit()

            return jsonify({
                'message': 'Purchase invoice deleted successfully'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'error': f'Error deleting invoice: {str(e)}'
            }), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Error processing delete request: {str(e)}'
        }), 500 