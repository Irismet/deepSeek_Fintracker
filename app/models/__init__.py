# app/models/__init__.py
"""
Модели базы данных для приложения Investment Tracker
"""

from app.models.user import User
from app.models.asset import Asset
from app.models.portfolio import Portfolio
from app.models.transaction import Transaction
from app.models.position import Position
from app.models.historical_price import HistoricalPrice

# Экспортируем все модели для удобного импорта
__all__ = [
    'User',
    'Asset', 
    'Portfolio',
    'Transaction',
    'Position',
    'HistoricalPrice'
]