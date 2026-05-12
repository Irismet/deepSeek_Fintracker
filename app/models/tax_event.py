# app/models/tax_event.py
from app.extensions import db
from datetime import datetime

class TaxEvent(db.Model):
    """Модель для учета налоговых событий"""
    __tablename__ = 'tax_events'
    
    id = db.Column(db.BigInteger, primary_key=True)
    portfolio_id = db.Column(db.BigInteger, db.ForeignKey('portfolios.id'), nullable=False, index=True)
    asset_id = db.Column(db.BigInteger, db.ForeignKey('assets.id'), nullable=True)
    transaction_id = db.Column(db.BigInteger, db.ForeignKey('transactions.id'), nullable=True)
    
    tax_type = db.Column(db.String(30), nullable=False)  # withholding_us, local_dividend, local_capital_gains
    tax_rate = db.Column(db.Numeric(5, 2), nullable=False)  # налоговая ставка
    taxable_amount = db.Column(db.Numeric(20, 8), nullable=False)  # налогооблагаемая сумма
    tax_amount = db.Column(db.Numeric(20, 8), nullable=False)  # сумма налога
    currency = db.Column(db.String(3), nullable=False)
    tax_date = db.Column(db.DateTime, nullable=False)
    is_paid = db.Column(db.Boolean, default=False)  # уплачен ли налог
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_tax_portfolio', 'portfolio_id'),
        db.Index('idx_tax_asset', 'asset_id'),
        db.Index('idx_tax_date', 'tax_date'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'portfolio_id': self.portfolio_id,
            'asset_id': self.asset_id,
            'tax_type': self.tax_type,
            'tax_rate': float(self.tax_rate),
            'taxable_amount': float(self.taxable_amount),
            'tax_amount': float(self.tax_amount),
            'currency': self.currency,
            'tax_date': self.tax_date.isoformat() if self.tax_date else None,
            'is_paid': self.is_paid,
            'notes': self.notes
        }