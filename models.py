from database import db
from datetime import datetime


class Product(db.Model):
    __tablename__ = 'product'
    product_id = db.Column(db.String(50), primary_key=True)
    description = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<Product {self.product_id}>'


class Location(db.Model):
    __tablename__ = 'location'
    location_id = db.Column(db.String(50), primary_key=True)

    def __repr__(self):
        return f'<Location {self.location_id}>'


class ProductMovement(db.Model):
    __tablename__ = 'productmovement'
    movement_id = db.Column(db.String(50), primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    from_location = db.Column(db.String(50), db.ForeignKey('location.location_id'), nullable=True)
    to_location = db.Column(db.String(50), db.ForeignKey('location.location_id'), nullable=True)
    product_id = db.Column(db.String(50), db.ForeignKey('product.product_id'), nullable=False)
    qty = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<ProductMovement {self.movement_id}>'