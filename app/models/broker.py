# app/models/broker.py
from app import db
from datetime import datetime

class Broker(db.Model):
    __tablename__ = 'brokers'
    
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    country = db.Column(db.String(100), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    commission_fee = db.Column(db.Numeric(10, 2), nullable=True)  # Стандартная комиссия в %
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='broker_ref', lazy='dynamic', 
                                   foreign_keys='Transaction.broker_id')
    cash_flows = db.relationship('CashFlow', backref='broker_ref', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'country': self.country,
            'website': self.website,
            'commission_fee': float(self.commission_fee) if self.commission_fee else None,
            'is_active': self.is_active
        }
    
    def __repr__(self):
        return f'<Broker {self.name}>'