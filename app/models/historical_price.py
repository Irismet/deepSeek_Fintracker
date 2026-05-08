from app import db

class HistoricalPrice(db.Model):
    __tablename__ = 'historical_prices'
    
    id = db.Column(db.BigInteger, primary_key=True)
    asset_id = db.Column(db.BigInteger, db.ForeignKey('assets.id'), nullable=False, index=True)
    price_date = db.Column(db.Date, nullable=False)
    open = db.Column(db.Numeric(20, 6))
    high = db.Column(db.Numeric(20, 6))
    low = db.Column(db.Numeric(20, 6))
    close = db.Column(db.Numeric(20, 6), nullable=False)
    volume = db.Column(db.Numeric(20, 0))
    
    __table_args__ = (
        db.UniqueConstraint('asset_id', 'price_date', name='uix_asset_date'),
        db.Index('idx_prices_asset_date', 'asset_id', 'price_date'),
    )