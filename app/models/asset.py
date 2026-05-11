# app/models/asset.py - добавьте новое поле
from app.extensions import db

class Asset(db.Model):
    __tablename__ = 'assets'
    
    id = db.Column(db.BigInteger, primary_key=True)
    ticker = db.Column(db.String(50), nullable=False)
    isin = db.Column(db.String(12), unique=True, nullable=True)
    name = db.Column(db.String(255), nullable=False)
    asset_type = db.Column(db.String(20), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    
    # Новое поле для облигаций
    face_value = db.Column(db.Numeric(20, 2), nullable=True)  # Номинал облигации
    coupon_rate = db.Column(db.Numeric(10, 4), nullable=True)  # Купонная ставка (%)
    maturity_date = db.Column(db.Date, nullable=True)  # Дата погашения
    
    # Существующие поля
    asset_class_id = db.Column(db.BigInteger, db.ForeignKey('asset_classes.id'), nullable=True)
    sector_id = db.Column(db.BigInteger, db.ForeignKey('sectors.id'), nullable=True)
    exchange_id = db.Column(db.BigInteger, db.ForeignKey('exchanges.id'), nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('ticker', 'asset_type', name='uix_ticker_type'),
        db.Index('idx_asset_isin', 'isin'),
        db.Index('idx_asset_class', 'asset_class_id'),
        db.Index('idx_asset_sector', 'sector_id'),
    )
    
    # Relationships
    transactions = db.relationship('Transaction', backref='asset', lazy='dynamic')
    positions = db.relationship('Position', backref='asset', lazy='dynamic')
    historical_prices = db.relationship('HistoricalPrice', backref='asset', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'ticker': self.ticker,
            'isin': self.isin,
            'name': self.name,
            'asset_type': self.asset_type,
            'currency': self.currency,
            'face_value': float(self.face_value) if self.face_value else None,
            'coupon_rate': float(self.coupon_rate) if self.coupon_rate else None,
            'maturity_date': self.maturity_date.isoformat() if self.maturity_date else None,
            'asset_class': self.asset_class.name if self.asset_class else None,
            'sector': self.sector.name if self.sector else None,
            'exchange': self.exchange.name if self.exchange else None
        }