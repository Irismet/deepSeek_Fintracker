# app/models/exchange.py
from app import db
from datetime import datetime

class Exchange(db.Model):
    __tablename__ = 'exchanges'
    
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    country = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    timezone = db.Column(db.String(50), nullable=True)
    currency = db.Column(db.String(3), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='exchange_ref', lazy='dynamic',
                                   foreign_keys='Transaction.exchange_id')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'country': self.country,
            'city': self.city,
            'timezone': self.timezone,
            'currency': self.currency,
            'website': self.website,
            'is_active': self.is_active
        }
    
    def __repr__(self):
        return f'<Exchange {self.name}>'