from app import db
from app.models.transaction import Transaction
from app.models.position import Position
from app.models.historical_price import HistoricalPrice
from datetime import datetime, date
from decimal import Decimal
from app.utils.xirr import calculate_xirr

class AnalyticsService:
    
    @staticmethod
    def get_portfolio_summary(portfolio_id, current_prices):
        """Получение сводки по портфелю"""
        positions = Position.query.filter_by(portfolio_id=portfolio_id).all()
        
        total_value = Decimal('0')
        total_cost = Decimal('0')
        
        summary = []
        for pos in positions:
            ticker = pos.asset.ticker
            current_price = Decimal(str(current_prices.get(ticker, 0)))
            current_value = pos.quantity * current_price
            cost = pos.quantity * pos.avg_price
            unrealized_pnl = current_value - cost
            unrealized_pnl_pct = (unrealized_pnl / cost * 100) if cost > 0 else 0
            
            summary.append({
                'asset': ticker,
                'quantity': float(pos.quantity),
                'avg_price': float(pos.avg_price),
                'current_price': float(current_price),
                'current_value': float(current_value),
                'cost': float(cost),
                'unrealized_pnl': float(unrealized_pnl),
                'unrealized_pnl_pct': float(unrealized_pnl_pct)
            })
            
            total_value += current_value
            total_cost += cost
        
        total_unrealized_pnl = total_value - total_cost
        total_return_pct = (total_unrealized_pnl / total_cost * 100) if total_cost > 0 else 0
        
        return {
            'total_value': float(total_value),
            'total_cost': float(total_cost),
            'total_unrealized_pnl': float(total_unrealized_pnl),
            'total_return_pct': float(total_return_pct),
            'positions': summary
        }
    
    @staticmethod
    def get_cashflows(portfolio_id):
        """Получение денежных потоков для XIRR"""
        transactions = Transaction.query.filter_by(portfolio_id=portfolio_id).all()
        
        cashflows = []
        for tx in transactions:
            amount = Decimal('0')
            if tx.tx_type == 'deposit':
                amount = -tx.quantity * tx.price
            elif tx.tx_type == 'withdraw':
                amount = tx.quantity * tx.price
            elif tx.tx_type == 'buy':
                amount = -tx.quantity * tx.price - tx.fee
            elif tx.tx_type == 'sell':
                amount = tx.quantity * tx.price - tx.fee
            elif tx.tx_type == 'dividend':
                amount = tx.quantity * tx.price
            elif tx.tx_type == 'tax_fee':
                amount = -tx.fee
            
            if amount != 0:
                cashflows.append({
                    'date': tx.tx_date,
                    'amount': float(amount)
                })
        
        return cashflows
    
    @staticmethod
    def get_portfolio_xirr(portfolio_id, current_value):
        """Расчет XIRR портфеля"""
        cashflows = AnalyticsService.get_cashflows(portfolio_id)
        
        if not cashflows:
            return None
        
        # Добавляем текущую стоимость как финальный cashflow
        cashflows.append({
            'date': datetime.utcnow(),
            'amount': float(current_value)
        })
        
        return calculate_xirr(cashflows)
    
    @staticmethod
    def get_daily_valuation(portfolio_id, start_date, end_date):
        """Получение исторической стоимости портфеля по дням"""
        # Сложная логика с материализованным view
        # Упрощенная версия:
        result = db.session.execute("""
            SELECT day, total_market_value 
            FROM portfolio_daily_valuation 
            WHERE portfolio_id = :pid 
            AND day BETWEEN :start AND :end
            ORDER BY day
        """, {'pid': portfolio_id, 'start': start_date, 'end': end_date})
        
        return [{'date': str(row[0]), 'value': float(row[1])} for row in result]