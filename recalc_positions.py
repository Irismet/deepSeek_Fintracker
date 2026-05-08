# recalc_all.py
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.portfolio import Portfolio
from app.models.position import Position
from app.models.closed_positions import ClosedPosition
from app.models.transaction import Transaction
from app.services.position_service import PositionService

def full_recalc():
    """Полный пересчет всех портфелей"""
    
    app = create_app('development')
    
    with app.app_context():
        print("\n" + "="*70)
        print("🔄 ПОЛНЫЙ ПЕРЕСЧЕТ ВСЕХ ПОРТФЕЛЕЙ")
        print("="*70)
        
        # Показываем текущие транзакции
        print("\n📊 Текущие транзакции в базе:")
        transactions = Transaction.query.all()
        print(f"  Всего транзакций: {len(transactions)}")
        
        for tx in transactions[:10]:  # Показываем первые 10
            asset_ticker = tx.asset.ticker if tx.asset else 'Cash'
            print(f"  - {tx.tx_date.strftime('%Y-%m-%d')}: {tx.tx_type} {asset_ticker} {tx.quantity} @ {tx.price}")
        
        portfolios = Portfolio.query.all()
        
        for portfolio in portfolios:
            print(f"\n{'='*50}")
            print(f"📁 Портфель: {portfolio.name} (ID: {portfolio.id})")
            
            # Получаем транзакции для этого портфеля
            portfolio_transactions = Transaction.query.filter_by(portfolio_id=portfolio.id).all()
            print(f"  Транзакций в портфеле: {len(portfolio_transactions)}")
            
            # Удаляем старые данные
            deleted_positions = Position.query.filter_by(portfolio_id=portfolio.id).delete()
            deleted_closed = ClosedPosition.query.filter_by(portfolio_id=portfolio.id).delete()
            print(f"  Удалено позиций: {deleted_positions}")
            print(f"  Удалено закрытых позиций: {deleted_closed}")
            
            # Пересчитываем
            try:
                PositionService.recalc_portfolio_positions(portfolio.id)
                
                # Проверяем результат
                new_positions = Position.query.filter_by(portfolio_id=portfolio.id).all()
                new_closed = ClosedPosition.query.filter_by(portfolio_id=portfolio.id).all()
                
                print(f"\n  ✅ Результат:")
                print(f"     Активных позиций: {len(new_positions)}")
                print(f"     Закрытых позиций: {len(new_closed)}")
                
                # Показываем детали закрытых позиций
                for closed in new_closed:
                    asset = closed.asset
                    ticker = asset.ticker if asset else 'Unknown'
                    print(f"\n     📈 {ticker}:")
                    print(f"        Куплено: {float(closed.total_quantity):.4f} @ ${float(closed.total_buy_cost / closed.total_quantity if closed.total_quantity > 0 else 0):.2f}")
                    print(f"        Продано: {float(closed.total_sold_quantity):.4f}")
                    print(f"        P&L: ${float(closed.realized_pnl):.2f}")
                    print(f"        Доходность: {float(closed.return_percentage):.2f}%")
                    print(f"        Период: {closed.first_buy_date.strftime('%Y-%m-%d')} → {closed.last_sell_date.strftime('%Y-%m-%d')}")
                
                db.session.commit()
                
            except Exception as e:
                db.session.rollback()
                print(f"  ❌ Ошибка: {e}")
                import traceback
                traceback.print_exc()
        
        print("\n" + "="*70)
        print("✅ ПЕРЕСЧЕТ ЗАВЕРШЕН")
        print("="*70)
        
        # Итоговая статистика
        total_positions = Position.query.count()
        total_closed = ClosedPosition.query.count()
        print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА:")
        print(f"  - Всего активных позиций: {total_positions}")
        print(f"  - Всего закрытых позиций: {total_closed}")

if __name__ == '__main__':
    full_recalc()