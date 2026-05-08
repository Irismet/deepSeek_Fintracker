# app/__init__.py
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from config import config
import logging

# Импортируем расширения из отдельного модуля
from app.extensions import db, migrate, jwt

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Import models (after db is initialized)
    from app.models.user import User
    from app.models.asset import Asset
    from app.models.portfolio import Portfolio
    from app.models.transaction import Transaction
    from app.models.position import Position
    from app.models.historical_price import HistoricalPrice
    from app.models.broker import Broker
    from app.models.exchange import Exchange
    from app.models.asset_class import AssetClass
    from app.models.sector import Sector
    from app.models.currency_rate import CurrencyRate
    from app.models.cash_flow import CashFlow
    
    # Register API blueprints
    from app.api.portfolios import portfolios_bp
    from app.api.transactions import transactions_bp
    from app.api.auth import auth_bp
    from app.api.analytics import analytics_bp
    
    app.register_blueprint(portfolios_bp, url_prefix='/api')
    app.register_blueprint(transactions_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(analytics_bp, url_prefix='/api')
    
    # Register error handlers
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'Bad request', 'message': str(error)}), 400
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500
    
    return app

    @app.template_filter('format_date')
    def format_date_filter(date, format='%Y-%m-%d'):
        """Форматирует дату в строку"""
        if not date:
            return 'Недавно'
        if isinstance(date, str):
            return date[:10]
        return date.strftime(format)
        
    return app

# Регистрируем фильтр для Decimal
    @app.template_filter('decimal')
    def decimal_filter(value):
        """Безопасно конвертирует Decimal в float для шаблонов"""
        if value is None:
            return 0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0
    
    @app.template_filter('multiply')
    def multiply_filter(a, b):
        """Безопасное умножение для Decimal"""
        try:
            return float(a) * float(b)
        except (TypeError, ValueError):
            return 0
    
    return app