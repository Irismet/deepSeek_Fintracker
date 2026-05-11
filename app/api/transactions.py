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
import traceback

transactions_bp = Blueprint('api_transactions', __name__)

@transactions_bp.route('/transactions', methods=['POST'])
@jwt_required()
def create_transaction():
    import traceback
    from flask import current_app
    
    current_app.logger.info("=== Creating transaction ===")
    try:
        user_id = get_jwt_identity()
        current_app.logger.info(f"User ID: {user_id}, type: {type(user_id)}")

        # Конвертируем user_id из строки в int если нужно
        if isinstance(user_id, str):
            user_id = int(user_id)
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Проверяем обязательные поля
        required_fields = ['portfolio_id', 'tx_type', 'quantity', 'price', 'tx_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Проверяем портфель
        portfolio = Portfolio.query.filter_by(id=data['portfolio_id'], user_id=user_id).first()
        if not portfolio:
            return jsonify({'error': 'Portfolio not found'}), 404
        
        # Обработка актива
        asset = None
        if 'asset_id' in data and data['asset_id']:
            asset = Asset.query.get(data['asset_id'])
            if not asset:
                return jsonify({'error': 'Asset not found'}), 404
        elif 'asset_ticker' in data and data['asset_ticker']:
            asset = Asset.query.filter_by(ticker=data['asset_ticker']).first()
            if not asset:
                # Создаем новый актив
                asset = Asset(
                    ticker=data['asset_ticker'],
                    name=data.get('asset_name', data['asset_ticker']),
                    asset_type=data.get('asset_type', 'stock'),
                    currency=data.get('asset_currency', 'USD')
                )
                db.session.add(asset)
                db.session.flush()
        
        # Обработка брокера
        broker_id = data.get('broker_id')
        if broker_id:
            broker = Broker.query.get(broker_id)
            if not broker:
                return jsonify({'error': 'Broker not found'}), 404
        
        # Обработка биржи
        exchange = None
        exchange_name = data.get('exchange')
        if exchange_name:
            exchange = Exchange.query.filter_by(name=exchange_name).first()
        
        # Создание транзакции
        transaction = Transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id if asset else None,
            broker_id=broker_id,
            exchange_id=exchange.id if exchange else None,
            tx_type=data['tx_type'],
            quantity=data['quantity'],
            price=data['price'],
            fee=data.get('fee', 0),
            tx_currency=data.get('tx_currency', portfolio.currency),
            tx_date=datetime.fromisoformat(data['tx_date'].replace('Z', '+00:00')),
            notes=data.get('notes')
        )
        
        db.session.add(transaction)
        
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
        
        db.session.commit()
        
        return jsonify(transaction.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating transaction: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        print(f"Error creating transaction: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@transactions_bp.route('/transactions/portfolio/<int:portfolio_id>', methods=['GET'])
@jwt_required()
def get_portfolio_transactions(portfolio_id):
    user_id = get_jwt_identity()
    portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=user_id).first_or_404()
    
    transactions = Transaction.query.filter_by(portfolio_id=portfolio_id)\
        .order_by(Transaction.tx_date.desc())\
        .limit(100)\
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