from app import db
from datetime import datetime

class Portfolio(db.Model):
    __tablename__ = 'portfolios'
    
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='USD')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='portfolio', lazy='dynamic', cascade='all, delete-orphan')
    positions = db.relationship('Position', backref='portfolio', lazy='dynamic', cascade='all, delete-orphan')
    cash_flows = db.relationship('CashFlow', backref='portfolio', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self, include_positions=False):
        data = {
            'id': self.id,
            'name': self.name,
            'currency': self.currency,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_positions:
            data['positions'] = [p.to_dict() for p in self.positions]
        return data