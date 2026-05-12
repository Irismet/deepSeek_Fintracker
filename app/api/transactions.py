# app/api/transactions.py
from decimal import Decimal

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.portfolio import Portfolio
from app.models.asset import Asset
from app.models.transaction import Transaction
from app.models.broker import Broker
from app.models.exchange import Exchange
from app.services.position_service import PositionService
from datetime import datetime
from app.models.tax_event import TaxEvent
import traceback

transactions_bp = Blueprint('api_transactions', __name__)

@transactions_bp.route('/transactions', methods=['POST'])
@jwt_required()
def create_transaction():
    try:
        user_id = get_jwt_identity()
        if isinstance(user_id, str):
            user_id = int(user_id)
        
        data = request.get_json()
        print(f"Received transaction data: {data}")
        
        portfolio = Portfolio.query.filter_by(id=data['portfolio_id'], user_id=user_id).first()
        if not portfolio:
            return jsonify({'error': 'Portfolio not found'}), 404
        
        # Обработка актива
        asset = None
        if 'asset_id' in data and data['asset_id']:
            asset = Asset.query.get(data['asset_id'])
        
        # Обработка биржи
        exchange = None
        if data.get('exchange'):
            exchange = Exchange.query.filter_by(name=data['exchange']).first()
        
        # Создание транзакции
        transaction = Transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id if asset else None,
            broker_id=data.get('broker_id'),
            exchange_id=exchange.id if exchange else None,
            tx_type=data['tx_type'],
            quantity=Decimal(str(data['quantity'])),
            price=Decimal(str(data['price'])),
            fee=Decimal(str(data.get('fee', 0))),
            tx_currency=data.get('tx_currency', portfolio.currency),
            tx_date=datetime.fromisoformat(data['tx_date'].replace('Z', '+00:00')),
            notes=data.get('notes')
        )
        
        db.session.add(transaction)
        db.session.flush()  # Чтобы получить transaction.id
        
        # Если это дивиденды - создаем налоговые события
        if data['tx_type'] == 'dividend' and asset:
            gross_amount = Decimal(str(data.get('gross_amount', data['quantity'] * data['price'])))
            
            # Получаем информацию о бирже и ISIN
            exchange_name = exchange.name if exchange else (asset.exchange.name if asset.exchange else '')
            isin = asset.isin or ''
            
            # Определяем ставки налогов
            us_tax_rate = 0
            local_tax_rate = 0
            
            if exchange_name in ['KASE', 'AIX']:
                if isin.startswith('KZ'):
                    us_tax_rate = 0
                    local_tax_rate = 5
                else:
                    us_tax_rate = 15
                    local_tax_rate = 5
            else:
                if isin.startswith('US'):
                    us_tax_rate = 15
                    local_tax_rate = 10
                else:
                    us_tax_rate = 0
                    local_tax_rate = 10
            
            # Рассчитываем налоги
            us_tax = gross_amount * Decimal(str(us_tax_rate)) / 100
            local_tax = gross_amount * Decimal(str(local_tax_rate)) / 100
            
            # Создаем налоговое событие для США
            if us_tax > 0:
                tax_event_us = TaxEvent(
                    portfolio_id=portfolio.id,
                    asset_id=asset.id,
                    transaction_id=transaction.id,
                    tax_type='withholding_us',
                    tax_rate=us_tax_rate,
                    taxable_amount=gross_amount,
                    tax_amount=us_tax,
                    currency=data['tx_currency'],
                    tax_date=transaction.tx_date,
                    notes=f'Налог у источника в США ({us_tax_rate}%) на дивиденды по {asset.ticker}'
                )
                db.session.add(tax_event_us)
                print(f"Created US tax event: {us_tax} {data['tx_currency']}")
            
            # Создаем налоговое событие для местного налога
            if local_tax > 0:
                tax_event_local = TaxEvent(
                    portfolio_id=portfolio.id,
                    asset_id=asset.id,
                    transaction_id=transaction.id,
                    tax_type='local_dividend',
                    tax_rate=local_tax_rate,
                    taxable_amount=gross_amount,
                    tax_amount=local_tax,
                    currency=data['tx_currency'],
                    tax_date=transaction.tx_date,
                    notes=f'Местный налог ({local_tax_rate}%) на дивиденды по {asset.ticker}'
                )
                db.session.add(tax_event_local)
                print(f"Created local tax event: {local_tax} {data['tx_currency']}")
        
        db.session.commit()
        
        # Обновляем позиции для buy/sell
        if transaction.tx_type in ['buy', 'sell'] and asset:
            PositionService.update_position_after_trade(
                portfolio_id=portfolio.id,
                asset_id=asset.id,
                tx_type=transaction.tx_type,
                quantity=transaction.quantity,
                price=transaction.price,
                fee=transaction.fee
            )
        
        return jsonify(transaction.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating transaction: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@transactions_bp.route('/transactions/portfolio/<int:portfolio_id>', methods=['GET'])
@jwt_required()
def get_portfolio_transactions(portfolio_id):
    user_id = get_jwt_identity()
    portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=user_id).first_or_404()
    
    transactions = Transaction.query.filter_by(portfolio_id=portfolio_id)\
        .order_by(Transaction.tx_date.desc())\
        .limit(999999)\
        .all()
    
    return jsonify([t.to_dict() for t in transactions]), 200

@transactions_bp.route('/transactions/<int:transaction_id>', methods=['PUT'])
@jwt_required()
def update_transaction_api(transaction_id):
    """API обновление транзакции"""
    try:
        user_id = get_jwt_identity()
        if isinstance(user_id, str):
            user_id = int(user_id)
        
        transaction = Transaction.query.get_or_404(transaction_id)
        
        if transaction.portfolio.user_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        
        # Обновляем поля
        if 'tx_type' in data:
            transaction.tx_type = data['tx_type']
        if 'quantity' in data:
            transaction.quantity = Decimal(str(data['quantity']))
        if 'price' in data:
            transaction.price = Decimal(str(data['price']))
        if 'fee' in data:
            transaction.fee = Decimal(str(data.get('fee', 0)))
        if 'tx_currency' in data:
            transaction.tx_currency = data['tx_currency']
        if 'tx_date' in data:
            transaction.tx_date = datetime.fromisoformat(data['tx_date'].replace('Z', '+00:00'))
        if 'broker_id' in data:
            transaction.broker_id = data.get('broker_id')
        if 'exchange' in data and data['exchange']:
            exchange = Exchange.query.filter_by(name=data['exchange']).first()
            transaction.exchange_id = exchange.id if exchange else None
        else:
            transaction.exchange_id = None
        if 'notes' in data:
            transaction.notes = data.get('notes')
        if 'asset_id' in data:
            transaction.asset_id = data['asset_id'] if data['asset_id'] else None
        
        db.session.commit()
        
        # Пересчитываем позиции портфеля
        from app.services.position_service import PositionService
        PositionService.recalc_portfolio_positions(transaction.portfolio_id)
        
        return jsonify(transaction.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating transaction: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    

@transactions_bp.route('/transactions/<int:transaction_id>', methods=['DELETE'])
@jwt_required()
def delete_transaction(transaction_id):
    """Удаление транзакции"""
    try:
        user_id = get_jwt_identity()
        if isinstance(user_id, str):
            user_id = int(user_id)
        
        transaction = Transaction.query.get_or_404(transaction_id)
        
        # Проверяем права доступа
        if transaction.portfolio.user_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        portfolio_id = transaction.portfolio_id
        
        # Удаляем транзакцию
        db.session.delete(transaction)
        db.session.commit()
        
        # Пересчитываем позиции портфеля
        from app.services.position_service import PositionService
        PositionService.recalc_portfolio_positions(portfolio_id)
        
        return jsonify({'message': 'Transaction deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting transaction: {e}")
        return jsonify({'error': str(e)}), 500