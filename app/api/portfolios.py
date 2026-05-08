# app/api/portfolios.py (только API)
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.portfolio import Portfolio
from app.services.pricing_service import PricingService
from app.services.analytics_service import AnalyticsService

portfolios_bp = Blueprint('api_portfolios', __name__)

@portfolios_bp.route('/portfolios', methods=['GET'])
@jwt_required()
def get_portfolios():
    user_id = get_jwt_identity()
    portfolios = Portfolio.query.filter_by(user_id=user_id).all()
    return jsonify([p.to_dict() for p in portfolios]), 200

@portfolios_bp.route('/portfolios', methods=['POST'])
@jwt_required()
def create_portfolio():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    portfolio = Portfolio(
        user_id=user_id,
        name=data['name'],
        currency=data.get('currency', 'USD')
    )
    
    db.session.add(portfolio)
    db.session.commit()
    
    return jsonify(portfolio.to_dict()), 201

@portfolios_bp.route('/portfolios/<int:portfolio_id>', methods=['GET'])
@jwt_required()
def get_portfolio(portfolio_id):
    user_id = get_jwt_identity()
    portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=user_id).first_or_404()
    
    positions = portfolio.positions.all()
    tickers = [p.asset.ticker for p in positions if p.asset]
    current_prices = PricingService.get_current_prices(tickers)
    summary = AnalyticsService.get_portfolio_summary(portfolio_id, current_prices)
    
    result = portfolio.to_dict()
    result.update(summary)
    
    return jsonify(result), 200

@portfolios_bp.route('/portfolios/<int:portfolio_id>', methods=['DELETE'])
@jwt_required()
def delete_portfolio(portfolio_id):
    user_id = get_jwt_identity()
    portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=user_id).first_or_404()
    
    db.session.delete(portfolio)
    db.session.commit()
    
    return jsonify({'message': 'Portfolio deleted'}), 200