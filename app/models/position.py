from app import db

class Position(db.Model):
    __tablename__ = 'positions'
    
    id = db.Column(db.BigInteger, primary_key=True)
    portfolio_id = db.Column(db.BigInteger, db.ForeignKey('portfolios.id'), nullable=False, index=True)
    asset_id = db.Column(db.BigInteger, db.ForeignKey('assets.id'), nullable=False)
    quantity = db.Column(db.Numeric(20, 8), nullable=False, default=0)
    avg_price = db.Column(db.Numeric(20, 8), nullable=False, default=0)
    
    __table_args__ = (
        db.UniqueConstraint('portfolio_id', 'asset_id', name='uix_portfolio_asset'),
    )
    
    def to_dict(self):
        return {
            'asset_id': self.asset_id,
            'ticker': self.asset.ticker,
            'quantity': float(self.quantity),
            'avg_price': float(self.avg_price),
            'current_price': None,  # будет добавлено сервисом
            'current_value': None,
            'unrealized_pnl': None
        }