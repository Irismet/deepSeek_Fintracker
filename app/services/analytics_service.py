# app/services/analytics_service.py
from app.extensions import db
from app.models.transaction import Transaction
from app.models.position import Position
from app.models.historical_price import HistoricalPrice
from app.services.currency_service import CurrencyService
from app.services.price_cache_service import price_cache_service
from datetime import datetime, date
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class AnalyticsService:
    
    # app/services/analytics_service.py - обновленный метод get_portfolio_summary
    # app/services/analytics_service.py - обновите get_portfolio_summary

    @classmethod
    def get_portfolio_summary(cls, portfolio_id, portfolio_currency='USD', use_cache=True):
        """Получение сводки по портфелю с учетом номинала облигаций"""
        
        positions = Position.query.filter_by(portfolio_id=portfolio_id).all()
        
        if not positions:
            return {
                'total_value': 0,
                'total_cost': 0,
                'total_dividends': 0,
                'total_unrealized_pnl': 0,
                'total_realized_pnl': 0,
                'total_return_pct': 0,
                'positions': []
            }
        
        # Получаем все дивиденды и купоны
        dividends = Transaction.query.filter_by(
            portfolio_id=portfolio_id,
            tx_type='dividend'
        ).all()
        
        total_dividends = Decimal('0')
        for div in dividends:
            div_amount = div.quantity * div.price - div.fee
            total_dividends += CurrencyService.convert(
                div_amount, 
                div.tx_currency, 
                portfolio_currency, 
                div.tx_date.date()
            )
        
        # Получаем тикеры для запроса цен (только не облигации)
        tickers = []
        positions_info = []
        
        for pos in positions:
            if pos.asset:
                if pos.asset.asset_type == 'bond' and pos.asset.face_value:
                    # Для облигаций используем номинал
                    current_price = Decimal(str(pos.asset.face_value))
                    positions_info.append({
                        'position': pos,
                        'asset_currency': pos.asset.currency,
                        'current_price': current_price,
                        'is_bond': True
                    })
                else:
                    tickers.append(pos.asset.ticker)
                    positions_info.append({
                        'position': pos,
                        'asset_currency': pos.asset.currency,
                        'is_bond': False
                    })
        
        # Получаем текущие цены для обычных активов
        if use_cache:
            current_prices = price_cache_service.get_current_prices(tickers)
        else:
            current_prices = price_cache_service.get_current_prices(tickers, force_update=True)
        
        total_value = Decimal('0')
        total_cost = Decimal('0')
        total_realized_pnl = Decimal('0')
        
        summary = []
        
        for item in positions_info:
            pos = item['position']
            asset_currency = item['asset_currency']
            ticker = pos.asset.ticker
            
            # Получаем текущую цену
            if item['is_bond']:
                current_price = item['current_price']
            else:
                current_price = Decimal(str(current_prices.get(ticker, 0)))
            
            # Стоимость в валюте актива
            current_value_asset = pos.quantity * current_price
            cost_asset = pos.quantity * pos.avg_price
            
            # Получаем дивиденды по этому активу
            asset_dividends = [d for d in dividends if d.asset_id == pos.asset_id]
            total_asset_dividends = Decimal('0')
            for div in asset_dividends:
                div_amount = div.quantity * div.price - div.fee
                total_asset_dividends += CurrencyService.convert(
                    div_amount, 
                    div.tx_currency, 
                    portfolio_currency, 
                    div.tx_date.date()
                )
            
            # Конвертируем в валюту портфеля
            current_value = CurrencyService.convert(current_value_asset, asset_currency, portfolio_currency)
            cost = CurrencyService.convert(cost_asset, asset_currency, portfolio_currency)
            
            # Реализованная прибыль по активу
            from app.models.closed_positions import ClosedPosition
            closed = ClosedPosition.query.filter_by(
                portfolio_id=portfolio_id,
                asset_id=pos.asset_id
            ).first()
            
            realized_pnl_asset = Decimal('0')
            if closed:
                realized_pnl_asset = CurrencyService.convert(
                    closed.realized_pnl, 
                    asset_currency, 
                    portfolio_currency
                )
                total_realized_pnl += realized_pnl_asset
            
            # Расчет P&L
            unrealized_pnl = current_value - cost
            total_pnl_with_dividends = unrealized_pnl + realized_pnl_asset + total_asset_dividends
            total_cost_with_dividends = cost + realized_pnl_asset
            
            if total_cost_with_dividends > 0:
                total_return_with_dividends = (total_pnl_with_dividends / total_cost_with_dividends) * 100
            else:
                total_return_with_dividends = 0
            
            summary.append({
                'asset_id': pos.asset_id,
                'ticker': ticker,
                'name': pos.asset.name,
                'asset_type': pos.asset.asset_type,
                'face_value': float(pos.asset.face_value) if pos.asset.face_value else None,
                'quantity': float(pos.quantity),
                'avg_price': float(pos.avg_price),
                'avg_price_currency': asset_currency,
                'current_price': float(current_price),
                'current_price_currency': asset_currency,
                'current_value_asset': float(current_value_asset),
                'current_value': float(current_value),
                'cost_asset': float(cost_asset),
                'cost': float(cost),
                'unrealized_pnl': float(unrealized_pnl),
                'realized_pnl': float(realized_pnl_asset),
                'dividends': float(total_asset_dividends),
                'total_pnl': float(total_pnl_with_dividends),
                'total_return_pct': float(total_return_with_dividends),
                'unrealized_pnl_pct': float((unrealized_pnl / cost * 100) if cost > 0 else 0)
            })
            
            total_value += current_value
            total_cost += cost
        
        total_unrealized_pnl = total_value - total_cost
        total_pnl_with_dividends = total_unrealized_pnl + total_realized_pnl + total_dividends
        total_return_pct = (total_pnl_with_dividends / total_cost * 100) if total_cost > 0 else 0
        
        return {
            'total_value': float(total_value),
            'total_cost': float(total_cost),
            'total_dividends': float(total_dividends),
            'total_realized_pnl': float(total_realized_pnl),
            'total_unrealized_pnl': float(total_unrealized_pnl),
            'total_pnl': float(total_pnl_with_dividends),
            'total_return_pct': float(total_return_pct),
            'positions': summary,
            'portfolio_currency': portfolio_currency
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
    
    @classmethod
    def get_transactions_in_portfolio_currency(cls, portfolio_id, portfolio_currency):
        """Получение всех транзакций портфеля в валюте портфеля"""
        
        transactions = Transaction.query.filter_by(portfolio_id=portfolio_id).all()
        
        result = []
        for tx in transactions:
            tx_currency = tx.tx_currency
            amount = tx.quantity * tx.price
            
            # Конвертируем в валюту портфеля
            amount_converted = CurrencyService.convert(amount, tx_currency, portfolio_currency, tx.tx_date.date())
            fee_converted = CurrencyService.convert(tx.fee, tx_currency, portfolio_currency, tx.tx_date.date())
            
            result.append({
                'id': tx.id,
                'tx_type': tx.tx_type,
                'quantity': float(tx.quantity),
                'price': float(tx.price),
                'price_currency': tx_currency,
                'amount_converted': float(amount_converted),
                'fee_converted': float(fee_converted),
                'tx_date': tx.tx_date,
                'asset_ticker': tx.asset.ticker if tx.asset else None
            })
        
        return result