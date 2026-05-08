# app/models/price_cache.py
from app.extensions import db
from datetime import datetime

class PriceCache(db.Model):
    """Таблица для кэширования текущих цен активов"""
    __tablename__ = 'price_cache'
    
    id = db.Column(db.BigInteger, primary_key=True)
    asset_id = db.Column(db.BigInteger, db.ForeignKey('assets.id'), nullable=False, unique=True, index=True)
    ticker = db.Column(db.String(50), nullable=False, index=True)
    price = db.Column(db.Numeric(20, 8), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='USD')
    last_update = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    source = db.Column(db.String(50), default='yfinance')
    
    # Relationship
    asset = db.relationship('Asset', backref=db.backref('price_cache', uselist=False))
    
    __table_args__ = (
        db.Index('idx_price_cache_ticker', 'ticker'),
        db.Index('idx_price_cache_last_update', 'last_update'),
    )
    
    def to_dict(self):
        return {
            'asset_id': self.asset_id,
            'ticker': self.ticker,
            'price': float(self.price),
            'currency': self.currency,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'source': self.source
        }
    
    def __repr__(self):
        return f'<PriceCache {self.ticker}: {self.price}>'