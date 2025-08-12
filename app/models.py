from app import db
from flask_login import UserMixin
from datetime import datetime
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    pin_code = db.Column(db.String(20), nullable=True)
    phone_number = db.Column(db.String(15), nullable=True)
    vehicle_number = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(20), nullable=False)
    reservations = db.relationship('Reservation', back_populates='user')

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(200))
    pin_code = db.Column(db.String(20))
    max_spots = db.Column(db.Integer, nullable=False)

    spots = db.relationship('ParkingSpot', back_populates='lot')

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    status = db.Column(db.String(1), default='A')
    spot_number = db.Column(db.Integer, nullable = False)

    lot = db.relationship('ParkingLot', back_populates='spots')  
    reservations = db.relationship('Reservation', back_populates='spot')

    __table_args__ = (
        db.UniqueConstraint('lot_id', 'spot_number', name='unique_spot_per_lot'),
    )
class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'))
    parking_time = db.Column(db.DateTime, default=datetime.utcnow)
    leaving_time = db.Column(db.DateTime, nullable=True)
    cost_per_hour = db.Column(db.Float)
    
    user = db.relationship('User', back_populates='reservations')
    spot = db.relationship('ParkingSpot', back_populates='reservations')