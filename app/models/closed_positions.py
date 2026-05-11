# app/models/closed_position.py - добавьте поле dividends
from app.extensions import db
from datetime import datetime

class ClosedPosition(db.Model):
    """Таблица для хранения закрытых позиций (история продаж)"""
    __tablename__ = 'closed_positions'
    
    id = db.Column(db.BigInteger, primary_key=True)
    portfolio_id = db.Column(db.BigInteger, db.ForeignKey('portfolios.id'), nullable=False, index=True)
    asset_id = db.Column(db.BigInteger, db.ForeignKey('assets.id'), nullable=False, index=True)
    
    # Информация о позиции
    total_quantity = db.Column(db.Numeric(20, 8), nullable=False)  # Всего куплено
    total_buy_cost = db.Column(db.Numeric(20, 8), nullable=False)  # Общая стоимость покупки
    total_sold_quantity = db.Column(db.Numeric(20, 8), nullable=False)  # Всего продано
    total_sell_revenue = db.Column(db.Numeric(20, 8), nullable=False)  # Общая выручка от продажи
    total_fees = db.Column(db.Numeric(20, 8), default=0)  # Общие комиссии
    total_dividends = db.Column(db.Numeric(20, 8), default=0)  # Дивиденды и купоны по этому активу
    
    # Результаты
    realized_pnl = db.Column(db.Numeric(20, 8), nullable=False)  # Реализованная прибыль/убыток от продажи
    return_percentage = db.Column(db.Numeric(10, 4), nullable=False)  # Доходность в % (без учета дивидендов)
    total_return_percentage = db.Column(db.Numeric(10, 4), default=0)  # Доходность с учетом дивидендов
    
    # Даты
    first_buy_date = db.Column(db.DateTime, nullable=False)
    last_sell_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    portfolio = db.relationship('Portfolio', backref=db.backref('closed_positions', lazy='dynamic'))
    asset = db.relationship('Asset', backref=db.backref('closed_positions', lazy='dynamic'))
    
    __table_args__ = (
        db.Index('idx_closed_portfolio_asset', 'portfolio_id', 'asset_id'),
        db.Index('idx_closed_sell_date', 'last_sell_date'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'portfolio_id': self.portfolio_id,
            'asset_id': self.asset_id,
            'ticker': self.asset.ticker if self.asset else None,
            'name': self.asset.name if self.asset else None,
            'total_quantity': float(self.total_quantity),
            'avg_buy_price': float(self.total_buy_cost / self.total_quantity) if self.total_quantity > 0 else 0,
            'total_sold_quantity': float(self.total_sold_quantity),
            'avg_sell_price': float(self.total_sell_revenue / self.total_sold_quantity) if self.total_sold_quantity > 0 else 0,
            'realized_pnl': float(self.realized_pnl),
            'total_dividends': float(self.total_dividends),
            'total_pnl': float(self.realized_pnl + self.total_dividends),
            'return_percentage': float(self.return_percentage),
            'total_return_percentage': float(self.total_return_percentage),
            'first_buy_date': self.first_buy_date.isoformat() if self.first_buy_date else None,
            'last_sell_date': self.last_sell_date.isoformat() if self.last_sell_date else None
        }
    
    def __repr__(self):
        ticker = self.asset.ticker if self.asset else 'Unknown'
        return f'<ClosedPosition {ticker}: {self.realized_pnl}>'