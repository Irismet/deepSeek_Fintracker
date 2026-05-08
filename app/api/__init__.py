# app/api/__init__.py
from app.api.auth import auth_bp
from app.api.portfolios import portfolios_bp
from app.api.transactions import transactions_bp
from app.api.analytics import analytics_bp

__all__ = ['auth_bp', 'portfolios_bp', 'transactions_bp', 'analytics_bp']