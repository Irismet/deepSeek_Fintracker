# app/models/cash_flow.py
from app import db
from datetime import datetime

class CashFlow(db.Model):
    __tablename__ = 'cash_flows'
    
    id = db.Column(db.BigInteger, primary_key=True)
    portfolio_id = db.Column(db.BigInteger, db.ForeignKey('portfolios.id'), nullable=False, index=True)
    broker_id = db.Column(db.BigInteger, db.ForeignKey('brokers.id'), nullable=True)
    flow_type = db.Column(db.String(20), nullable=False)  # deposit, withdrawal
    amount = db.Column(db.Numeric(20, 8), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    flow_date = db.Column(db.DateTime, nullable=False)
    fee = db.Column(db.Numeric(20, 8), default=0)  # Комиссия за перевод
    reference = db.Column(db.String(100), nullable=True)  # Номер транзакции, чек
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_cash_flows_portfolio_date', 'portfolio_id', 'flow_date'),
        db.Index('idx_cash_flows_broker', 'broker_id'),
        db.Index('idx_cash_flows_type', 'flow_type'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'portfolio_id': self.portfolio_id,
            'portfolio_name': self.portfolio.name if self.portfolio else None,
            'broker_id': self.broker_id,
            'broker_name': self.broker_ref.name if self.broker_ref else None,
            'flow_type': self.flow_type,
            'amount': float(self.amount),
            'currency': self.currency,
            'flow_date': self.flow_date.isoformat() if self.flow_date else None,
            'fee': float(self.fee),
            'reference': self.reference,
            'notes': self.notes
        }
    
    def __repr__(self):
        return f'<CashFlow {self.flow_type} {self.amount} {self.currency}>'