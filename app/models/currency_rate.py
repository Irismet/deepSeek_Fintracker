# app/models/currency_rate.py
from app.extensions import db
from datetime import date, datetime

class CurrencyRate(db.Model):
    __tablename__ = 'currency_rates'
    
    id = db.Column(db.BigInteger, primary_key=True)
    base_currency = db.Column(db.String(3), nullable=False)
    target_currency = db.Column(db.String(3), nullable=False)
    rate = db.Column(db.Numeric(20, 8), nullable=False)
    rate_date = db.Column(db.Date, nullable=False, default=date.today)
    source = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('base_currency', 'target_currency', 'rate_date', name='uix_currency_pair_date'),
        db.Index('idx_currency_rates_date', 'rate_date'),
        db.Index('idx_currency_rates_pair', 'base_currency', 'target_currency'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'base_currency': self.base_currency,
            'target_currency': self.target_currency,
            'rate': float(self.rate),
            'rate_date': self.rate_date.isoformat(),
            'source': self.source
        }
    
    def __repr__(self):
        return f'<CurrencyRate {self.base_currency}/{self.target_currency}: {self.rate}>'