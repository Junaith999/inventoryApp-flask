from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import db
from models import Product, Location, ProductMovement
from sqlalchemy import func
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize db with app
db.init_app(app)

# Create tables within app context
with app.app_context():
    db.create_all()


# Helper function to generate unique IDs
def generate_id():
    return str(uuid.uuid4())[:8]


def get_available_quantity(product_id, location_id):
    """Calculate available quantity for a product at a location"""
    # Sum of all incoming movements to this location
    incoming = db.session.query(func.coalesce(func.sum(ProductMovement.qty), 0)).filter(
        ProductMovement.product_id == product_id,
        ProductMovement.to_location == location_id
    ).scalar()

    # Sum of all outgoing movements from this location
    outgoing = db.session.query(func.coalesce(func.sum(ProductMovement.qty), 0)).filter(
        ProductMovement.product_id == product_id,
        ProductMovement.from_location == location_id
    ).scalar()

    return incoming - outgoing


def get_product_locations(product_id):
    """Get all locations where a product is available with quantities"""
    locations = Location.query.all()
    product_locations = []

    for location in locations:
        qty = get_available_quantity(product_id, location.location_id)
        if qty > 0:
            product_locations.append({
                'location_id': location.location_id,
                'quantity': qty
            })

    return product_locations


# Routes for Products
@app.route('/')
def index():
    return redirect(url_for('products'))


@app.route('/products')
def products():
    products = Product.query.all()
    locations = Location.query.all()

    # Calculate current quantities and locations for display
    product_data = {}
    for product in products:
        product_locations = get_product_locations(product.product_id)
        total_quantity = sum(loc['quantity'] for loc in product_locations)

        product_data[product.product_id] = {
            'product': product,
            'locations': product_locations,
            'total_quantity': total_quantity
        }

    return render_template('products.html', product_data=product_data, locations=locations)


@app.route('/add_product', methods=['POST'])
def add_product():
    product_id = request.form.get('product_id')
    description = request.form.get('description', '')
    location_id = request.form.get('location_id')
    quantity = int(request.form.get('quantity', 0))

    if Product.query.get(product_id):
        flash('Product ID already exists!', 'error')
        return redirect(url_for('products'))

    # Create the product
    product = Product(
        product_id=product_id,
        description=description
    )
    db.session.add(product)

    # Create initial movement if quantity > 0 and location is specified
    if quantity > 0 and location_id:
        movement = ProductMovement(
            movement_id=generate_id(),
            from_location=None,
            to_location=location_id,
            product_id=product_id,
            qty=quantity
        )
        db.session.add(movement)
        flash(f'Product "{product_id}" added with {quantity} units at {location_id}!', 'success')
    else:
        flash(f'Product "{product_id}" added! Add stock using movements.', 'success')

    db.session.commit()
    return redirect(url_for('products'))


@app.route('/edit_product/<product_id>', methods=['POST'])
def edit_product(product_id):
    product = Product.query.get(product_id)
    if not product:
        flash('Product not found!', 'error')
        return redirect(url_for('products'))

    new_product_id = request.form.get('product_id')
    description = request.form.get('description', '')

    if new_product_id != product_id and Product.query.get(new_product_id):
        flash('Product ID already exists!', 'error')
        return redirect(url_for('products'))

    product.product_id = new_product_id
    product.description = description

    db.session.commit()
    flash('Product updated successfully!', 'success')
    return redirect(url_for('products'))


@app.route('/delete_product/<product_id>')
def delete_product(product_id):
    product = Product.query.get(product_id)
    if product:
        # Check if product has movements
        movements = ProductMovement.query.filter_by(product_id=product_id).first()
        if movements:
            flash('Cannot delete product with existing movements!', 'error')
        else:
            db.session.delete(product)
            db.session.commit()
            flash('Product deleted successfully!', 'success')
    return redirect(url_for('products'))


# Routes for Locations
@app.route('/locations')
def locations():
    locations = Location.query.all()
    return render_template('locations.html', locations=locations)


@app.route('/add_location', methods=['POST'])
def add_location():
    location_id = request.form.get('location_id')
    if Location.query.get(location_id):
        flash('Location ID already exists!', 'error')
        return redirect(url_for('locations'))

    location = Location(location_id=location_id)
    db.session.add(location)
    db.session.commit()
    flash('Location added successfully!', 'success')
    return redirect(url_for('locations'))


@app.route('/edit_location/<location_id>', methods=['POST'])
def edit_location(location_id):
    location = Location.query.get(location_id)
    if not location:
        flash('Location not found!', 'error')
        return redirect(url_for('locations'))

    new_location_id = request.form.get('location_id')
    if new_location_id != location_id and Location.query.get(new_location_id):
        flash('Location ID already exists!', 'error')
        return redirect(url_for('locations'))

    location.location_id = new_location_id
    db.session.commit()
    flash('Location updated successfully!', 'success')
    return redirect(url_for('locations'))


@app.route('/delete_location/<location_id>')
def delete_location(location_id):
    location = Location.query.get(location_id)
    if location:
        # Check if location has movements
        movements_from = ProductMovement.query.filter_by(from_location=location_id).first()
        movements_to = ProductMovement.query.filter_by(to_location=location_id).first()

        if movements_from or movements_to:
            flash('Cannot delete location with existing movements!', 'error')
        else:
            db.session.delete(location)
            db.session.commit()
            flash('Location deleted successfully!', 'success')
    return redirect(url_for('locations'))


# Routes for Product Movements
@app.route('/movements')
def movements():
    movements = ProductMovement.query.order_by(ProductMovement.timestamp.desc()).all()
    products = Product.query.all()
    locations = Location.query.all()
    return render_template('movements.html', movements=movements, products=products, locations=locations)


@app.route('/add_movement', methods=['POST'])
def add_movement():
    movement_id = generate_id()
    from_location = request.form.get('from_location') or None
    to_location = request.form.get('to_location') or None
    product_id = request.form.get('product_id')
    qty = int(request.form.get('qty'))

    # Validate movement
    if not from_location and not to_location:
        flash('Either from location or to location must be specified!', 'error')
        return redirect(url_for('movements'))

    if from_location == to_location:
        flash('From and To locations cannot be the same!', 'error')
        return redirect(url_for('movements'))

    # Check if enough quantity available when moving from location
    if from_location:
        available_qty = get_available_quantity(product_id, from_location)
        if available_qty < qty:
            flash(f'Not enough quantity available! Only {available_qty} units available at {from_location}.', 'error')
            return redirect(url_for('movements'))

    movement = ProductMovement(
        movement_id=movement_id,
        from_location=from_location,
        to_location=to_location,
        product_id=product_id,
        qty=qty
    )

    db.session.add(movement)
    db.session.commit()

    if from_location and to_location:
        flash(f'Moved {qty} units of {product_id} from {from_location} to {to_location}!', 'success')
    elif from_location:
        flash(f'Removed {qty} units of {product_id} from {from_location}!', 'success')
    elif to_location:
        flash(f'Added {qty} units of {product_id} to {to_location}!', 'success')

    return redirect(url_for('movements'))


@app.route('/edit_movement/<movement_id>', methods=['POST'])
def edit_movement(movement_id):
    movement = ProductMovement.query.get(movement_id)
    if not movement:
        flash('Movement not found!', 'error')
        return redirect(url_for('movements'))

    from_location = request.form.get('from_location') or None
    to_location = request.form.get('to_location') or None
    product_id = request.form.get('product_id')
    qty = int(request.form.get('qty'))

    # Validate movement
    if not from_location and not to_location:
        flash('Either from location or to location must be specified!', 'error')
        return redirect(url_for('movements'))

    if from_location == to_location:
        flash('From and To locations cannot be the same!', 'error')
        return redirect(url_for('movements'))

    movement.from_location = from_location
    movement.to_location = to_location
    movement.product_id = product_id
    movement.qty = qty

    db.session.commit()
    flash('Movement updated successfully!', 'success')
    return redirect(url_for('movements'))


@app.route('/delete_movement/<movement_id>')
def delete_movement(movement_id):
    movement = ProductMovement.query.get(movement_id)
    if movement:
        db.session.delete(movement)
        db.session.commit()
        flash('Movement deleted successfully!', 'success')
    return redirect(url_for('movements'))


# Balance Report
@app.route('/balance')
def balance():
    """Generate balance report showing product quantities at each location"""
    balance_data = []
    products = Product.query.all()
    locations = Location.query.all()

    for product in products:
        for location in locations:
            qty = get_available_quantity(product.product_id, location.location_id)
            if qty > 0:
                balance_data.append({
                    'product': product.product_id,
                    'location': location.location_id,
                    'quantity': qty
                })

    return render_template('balance.html', balance_data=balance_data)


# API endpoint for checking available quantity
@app.route('/api/available_quantity/<product_id>/<location_id>')
def api_available_quantity(product_id, location_id):
    quantity = get_available_quantity(product_id, location_id)
    return jsonify({'available_quantity': quantity})


# Add stock to existing product
@app.route('/add_stock', methods=['POST'])
def add_stock():
    """Add stock to existing product at a location"""
    product_id = request.form.get('product_id')
    location_id = request.form.get('location_id')
    quantity = int(request.form.get('quantity', 0))

    if not product_id or not location_id or quantity <= 0:
        flash('Please provide valid product, location and quantity!', 'error')
        return redirect(url_for('products'))

    # Check if product exists
    product = Product.query.get(product_id)
    if not product:
        flash('Product does not exist!', 'error')
        return redirect(url_for('products'))

    # Check if location exists
    location = Location.query.get(location_id)
    if not location:
        flash('Location does not exist!', 'error')
        return redirect(url_for('products'))

    # Create movement
    movement = ProductMovement(
        movement_id=generate_id(),
        from_location=None,
        to_location=location_id,
        product_id=product_id,
        qty=quantity
    )
    db.session.add(movement)
    db.session.commit()

    flash(f'Added {quantity} units of {product_id} to {location_id}!', 'success')
    return redirect(url_for('products'))


if __name__ == '__main__':
    app.run(debug=True)