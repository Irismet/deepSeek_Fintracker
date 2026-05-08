# recalc_all_portfolios.py
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.portfolio import Portfolio
from app.models.position import Position
from app.models.closed_positions import ClosedPosition
from app.services.position_service import PositionService

def full_recalc():
    app = create_app('development')
    
    with app.app_context():
        print("\n" + "="*60)
        print("🔄 ПОЛНЫЙ ПЕРЕСЧЕТ ВСЕХ ПОРТФЕЛЕЙ")
        print("="*60)
        
        portfolios = Portfolio.query.all()
        
        for portfolio in portfolios:
            print(f"\n📁 Портфель: {portfolio.name} (ID: {portfolio.id})")
            
            # Сохраняем статистику до пересчета
            old_positions = Position.query.filter_by(portfolio_id=portfolio.id).count()
            old_closed = ClosedPosition.query.filter_by(portfolio_id=portfolio.id).count()
            print(f"  До пересчета: {old_positions} позиций, {old_closed} закрытых")
            
            try:
                PositionService.recalc_portfolio_positions(portfolio.id)
                
                # Проверяем результат
                new_positions = Position.query.filter_by(portfolio_id=portfolio.id).count()
                new_closed = ClosedPosition.query.filter_by(portfolio_id=portfolio.id).count()
                print(f"  ✅ После пересчета: {new_positions} позиций, {new_closed} закрытых")
                
            except Exception as e:
                print(f"  ❌ Ошибка: {e}")
                db.session.rollback()
        
        print("\n" + "="*60)
        print("✅ ПЕРЕСЧЕТ ЗАВЕРШЕН")
        print("="*60)

if __name__ == '__main__':
    full_recalc()