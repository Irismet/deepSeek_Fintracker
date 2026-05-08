# app/api/analytics.py
from flask import Blueprint, jsonify, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.portfolio import Portfolio
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.services.pricing_service import PricingService

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')

@analytics_bp.route('/portfolio/<int:portfolio_id>/xirr', methods=['GET'])
@jwt_required()
def get_xirr(portfolio_id):
    user_id = get_jwt_identity()
    portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=user_id).first_or_404()
    
    # Получаем текущую стоимость
    positions = portfolio.positions.all()
    tickers = [p.asset.ticker for p in positions if p.asset]
    current_prices = PricingService.get_current_prices(tickers)
    summary = AnalyticsService.get_portfolio_summary(portfolio_id, current_prices)
    
    xirr = AnalyticsService.get_portfolio_xirr(portfolio_id, summary['total_value'])
    
    return jsonify({'xirr': xirr}), 200

@analytics_bp.route('/html/dashboard', methods=['GET'])
@jwt_required()
def dashboard_html():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    portfolios = Portfolio.query.filter_by(user_id=user_id).all()
    
    # Собираем данные для всех портфелей
    portfolio_summaries = []
    total_value_all = 0
    
    for portfolio in portfolios:
        positions = portfolio.positions.all()
        tickers = [p.asset.ticker for p in positions if p.asset]
        current_prices = PricingService.get_current_prices(tickers)
        summary = AnalyticsService.get_portfolio_summary(portfolio.id, current_prices)
        
        portfolio_summaries.append({
            'id': portfolio.id,
            'name': portfolio.name,
            'value': summary['total_value'],
            'pnl': summary['total_unrealized_pnl'],
            'pnl_pct': summary['total_return_pct']
        })
        total_value_all += summary['total_value']
    
    return render_template('analytics/dashboard.html',
                         portfolios=portfolio_summaries,
                         total_value=total_value_all,
                         current_user=user)