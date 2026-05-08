from app import db
from app.models.position import Position
from app.models.transaction import Transaction
from decimal import Decimal

class PositionService:
    
    @staticmethod
    def update_position_after_trade(portfolio_id, asset_id, tx_type, quantity, price, fee):
        """Обновление позиции после buy/sell"""
        position = Position.query.filter_by(
            portfolio_id=portfolio_id, 
            asset_id=asset_id
        ).first()
        
        if not position:
            position = Position(
                portfolio_id=portfolio_id,
                asset_id=asset_id,
                quantity=Decimal('0'),
                avg_price=Decimal('0')
            )
            db.session.add(position)
        
        q = Decimal(str(quantity))
        p = Decimal(str(price))
        
        if tx_type == 'buy':
            # Новая средняя цена = (старая сумма + новая сумма) / (старое кол-во + новое кол-во)
            old_total = position.quantity * position.avg_price
            new_total = q * p
            position.quantity += q
            if position.quantity > 0:
                position.avg_price = (old_total + new_total) / position.quantity
        elif tx_type == 'sell':
            position.quantity -= q
            # avg_price остается прежним (FIFO/LIFO не нужен для простого учета)
            if position.quantity < 0:
                raise ValueError(f"Недостаточно активов для продажи. В наличии: {position.quantity}")
        
        if position.quantity == 0:
            db.session.delete(position)
        
        return position
    
    @staticmethod
    def recalc_portfolio_positions(portfolio_id):
        """Полный пересчет всех позиций портфеля (для отказоустойчивости)"""
        # Удаляем существующие позиции
        Position.query.filter_by(portfolio_id=portfolio_id).delete()
        
        # Получаем все buy/sell транзакции
        transactions = Transaction.query.filter_by(portfolio_id=portfolio_id)\
            .filter(Transaction.tx_type.in_(['buy', 'sell']))\
            .order_by(Transaction.tx_date).all()
        
        positions = {}
        for tx in transactions:
            key = tx.asset_id
            if key not in positions:
                positions[key] = {'quantity': Decimal('0'), 'avg_price': Decimal('0')}
            
            q = Decimal(str(tx.quantity))
            p = Decimal(str(tx.price))
            
            if tx.tx_type == 'buy':
                old_total = positions[key]['quantity'] * positions[key]['avg_price']
                new_total = q * p
                positions[key]['quantity'] += q
                if positions[key]['quantity'] > 0:
                    positions[key]['avg_price'] = (old_total + new_total) / positions[key]['quantity']
            else:  # sell
                positions[key]['quantity'] -= q
        
        # Сохраняем новые позиции
        for asset_id, data in positions.items():
            if data['quantity'] > 0:
                position = Position(
                    portfolio_id=portfolio_id,
                    asset_id=asset_id,
                    quantity=data['quantity'],
                    avg_price=data['avg_price']
                )
                db.session.add(position)
        
        db.session.commit()