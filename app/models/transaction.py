# app/models/transaction.py - обновленный с внешними ключами
from app.extensions import db
from datetime import datetime

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.BigInteger, primary_key=True)
    portfolio_id = db.Column(db.BigInteger, db.ForeignKey('portfolios.id'), nullable=False, index=True)
    asset_id = db.Column(db.BigInteger, db.ForeignKey('assets.id'), nullable=True)
    broker_id = db.Column(db.BigInteger, db.ForeignKey('brokers.id'), nullable=True)
    exchange_id = db.Column(db.BigInteger, db.ForeignKey('exchanges.id'), nullable=True)
    tx_type = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Numeric(20, 8), nullable=False)
    price = db.Column(db.Numeric(20, 8), nullable=False)
    fee = db.Column(db.Numeric(20, 8), default=0)
    tx_currency = db.Column(db.String(3), nullable=False)
    tx_date = db.Column(db.DateTime, nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_transactions_portfolio_date', 'portfolio_id', 'tx_date'),
        db.Index('idx_transactions_buy_sell', 'portfolio_id', 'asset_id', 
                 postgresql_where="tx_type IN ('buy', 'sell')"),
        db.Index('idx_transactions_broker', 'broker_id'),
        db.Index('idx_transactions_exchange', 'exchange_id'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'portfolio_id': self.portfolio_id,
            'asset_id': self.asset_id,
            'asset_ticker': self.asset.ticker if self.asset else None,
            'asset_isin': self.asset.isin if self.asset else None,
            'broker': self.broker_ref.name if self.broker_ref else None,
            'exchange': self.exchange_ref.name if self.exchange_ref else None,
            'tx_type': self.tx_type,
            'quantity': float(self.quantity),
            'price': float(self.price),
            'fee': float(self.fee),
            'tx_currency': self.tx_currency,
            'tx_date': self.tx_date.isoformat() if self.tx_date else None,
            'notes': self.notes
        }