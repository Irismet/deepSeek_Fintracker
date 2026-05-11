# recalc_dividends.py
from app import create_app
from app.extensions import db
from app.models.portfolio import Portfolio
from app.services.position_service import PositionService

def recalc_all_with_dividends():
    app = create_app('development')
    
    with app.app_context():
        print("\n" + "="*60)
        print("🔄 ПЕРЕСЧЕТ ЗАКРЫТЫХ ПОЗИЦИЙ С УЧЕТОМ ДИВИДЕНДОВ")
        print("="*60)
        
        portfolios = Portfolio.query.all()
        
        for portfolio in portfolios:
            print(f"\n📁 Портфель: {portfolio.name} (ID: {portfolio.id})")
            try:
                PositionService.recalc_portfolio_positions(portfolio.id)
                print(f"  ✅ Пересчитано")
            except Exception as e:
                print(f"  ❌ Ошибка: {e}")
                db.session.rollback()
        
        print("\n" + "="*60)
        print("✅ ПЕРЕСЧЕТ ЗАВЕРШЕН")
        print("="*60)

if __name__ == '__main__':
    recalc_all_with_dividends()