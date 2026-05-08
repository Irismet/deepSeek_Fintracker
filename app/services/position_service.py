# app/services/position_service.py
from app.extensions import db
from app.models.position import Position
from app.models.closed_positions import ClosedPosition
from app.models.transaction import Transaction
from decimal import Decimal
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PositionService:
    
    @staticmethod
    def update_position_after_trade(portfolio_id, asset_id, tx_type, quantity, price, fee, tx_date=None):
        """Обновление позиции после сделки (вызывается при создании/изменении транзакции)"""
        
        if tx_date is None:
            tx_date = datetime.utcnow()
        
        position = Position.query.filter_by(
            portfolio_id=portfolio_id, 
            asset_id=asset_id
        ).first()
        
        q = Decimal(str(quantity))
        p = Decimal(str(price))
        f = Decimal(str(fee))
        
        if tx_type == 'buy':
            if not position:
                position = Position(
                    portfolio_id=portfolio_id,
                    asset_id=asset_id,
                    quantity=Decimal('0'),
                    avg_price=Decimal('0')
                )
                db.session.add(position)
            
            # Обновляем среднюю цену
            old_total = position.quantity * position.avg_price
            new_total = q * p
            position.quantity += q
            if position.quantity > 0:
                position.avg_price = (old_total + new_total) / position.quantity
            
            db.session.flush()
            
        elif tx_type == 'sell':
            if not position or position.quantity < q:
                raise ValueError(f"Недостаточно активов для продажи. Доступно: {position.quantity if position else 0}")
            
            # Обновляем текущую позицию
            position.quantity -= q
            if position.quantity == 0:
                db.session.delete(position)
            
            db.session.flush()
        
        # Пересчитываем закрытую позицию для этого актива
        PositionService._recalc_closed_position(portfolio_id, asset_id)
        
        return position
    
    @staticmethod
    def _recalc_closed_position(portfolio_id, asset_id):
        """Полный пересчет закрытой позиции для конкретного актива на основе всех транзакций"""
        
        # Получаем все buy и sell транзакции по этому активу
        buys = Transaction.query.filter_by(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            tx_type='buy'
        ).order_by(Transaction.tx_date).all()
        
        sells = Transaction.query.filter_by(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            tx_type='sell'
        ).order_by(Transaction.tx_date).all()
        
        # Если нет покупок - удаляем закрытую позицию если есть
        if not buys:
            ClosedPosition.query.filter_by(
                portfolio_id=portfolio_id,
                asset_id=asset_id
            ).delete()
            db.session.commit()
            return
        
        # Рассчитываем общие показатели
        total_quantity = sum(b.quantity for b in buys)
        total_buy_cost = sum(b.quantity * b.price + b.fee for b in buys)
        total_sold_quantity = sum(s.quantity for s in sells)
        
        # Если ничего не продано - удаляем закрытую позицию
        if total_sold_quantity == 0:
            ClosedPosition.query.filter_by(
                portfolio_id=portfolio_id,
                asset_id=asset_id
            ).delete()
            db.session.commit()
            return
        
        # Расчет realized PnL по методу FIFO
        remaining_sells = []
        for s in sells:
            remaining_sells.append({
                'quantity': s.quantity,
                'price': s.price,
                'fee': s.fee,
                'tx_date': s.tx_date
            })
        
        total_cost_basis = Decimal('0')
        total_sell_revenue = Decimal('0')
        
        # FIFO: проходим по покупкам и списываем их продажами
        for buy in buys:
            buy_quantity = buy.quantity
            buy_price = buy.price
            buy_fee = buy.fee
            buy_cost = buy_quantity * buy_price + buy_fee
            
            remaining_quantity = buy_quantity
            
            while remaining_quantity > 0 and remaining_sells:
                sell = remaining_sells[0]
                sell_quantity = sell['quantity']
                sell_price = sell['price']
                sell_fee = sell['fee']
                
                # Определяем, сколько из этой покупки продается
                sell_from_this_buy = min(remaining_quantity, sell_quantity)
                
                # Рассчитываем cost basis для этой части
                cost_basis_portion = (sell_from_this_buy / buy_quantity) * buy_cost
                sell_revenue_portion = sell_from_this_buy * sell_price - (sell_fee * (sell_from_this_buy / sell_quantity))
                
                total_cost_basis += cost_basis_portion
                total_sell_revenue += sell_revenue_portion
                
                # Обновляем остатки
                remaining_quantity -= sell_from_this_buy
                remaining_sells[0]['quantity'] -= sell_from_this_buy
                
                if remaining_sells[0]['quantity'] <= 0:
                    remaining_sells.pop(0)
        
        realized_pnl = total_sell_revenue - total_cost_basis
        
        # Расчет доходности
        return_percentage = Decimal('0')
        if total_cost_basis > 0:
            return_percentage = (realized_pnl / total_cost_basis) * 100
        
        # Получаем даты
        first_buy_date = buys[0].tx_date if buys else datetime.utcnow()
        last_sell_date = sells[-1].tx_date if sells else datetime.utcnow()
        
        # Обновляем или создаем запись в closed_positions
        closed_pos = ClosedPosition.query.filter_by(
            portfolio_id=portfolio_id,
            asset_id=asset_id
        ).first()
        
        if closed_pos:
            # Обновляем существующую
            closed_pos.total_quantity = total_quantity
            closed_pos.total_buy_cost = total_buy_cost
            closed_pos.total_sold_quantity = total_sold_quantity
            closed_pos.total_sell_revenue = total_sell_revenue
            closed_pos.realized_pnl = realized_pnl
            closed_pos.return_percentage = return_percentage
            closed_pos.first_buy_date = first_buy_date
            closed_pos.last_sell_date = last_sell_date
        else:
            # Создаем новую
            closed_pos = ClosedPosition(
                portfolio_id=portfolio_id,
                asset_id=asset_id,
                total_quantity=total_quantity,
                total_buy_cost=total_buy_cost,
                total_sold_quantity=total_sold_quantity,
                total_sell_revenue=total_sell_revenue,
                realized_pnl=realized_pnl,
                return_percentage=return_percentage,
                first_buy_date=first_buy_date,
                last_sell_date=last_sell_date
            )
            db.session.add(closed_pos)
        
        db.session.commit()
        logger.info(f"Closed position for asset {asset_id}: sold {total_sold_quantity}/{total_quantity}, PnL={realized_pnl}, Return={return_percentage}%")
    
    @staticmethod
    def recalc_portfolio_positions(portfolio_id):
        """Полный пересчет всех позиций и закрытых позиций портфеля"""
        
        # Получаем все уникальные asset_id из транзакций
        asset_ids = db.session.query(Transaction.asset_id).filter_by(
            portfolio_id=portfolio_id
        ).distinct().all()
        
        asset_ids = [a[0] for a in asset_ids if a[0] is not None]
        
        # Сохраняем старые закрытые позиции для восстановления
        old_closed_positions = {}
        for closed in ClosedPosition.query.filter_by(portfolio_id=portfolio_id).all():
            old_closed_positions[closed.asset_id] = {
                'total_quantity': closed.total_quantity,
                'total_sold_quantity': closed.total_sold_quantity,
                'realized_pnl': closed.realized_pnl
            }
        
        # Удаляем существующие позиции (НО НЕ закрытые!)
        Position.query.filter_by(portfolio_id=portfolio_id).delete()
        
        # Временно удаляем закрытые позиции, чтобы пересчитать их заново
        ClosedPosition.query.filter_by(portfolio_id=portfolio_id).delete()
        db.session.flush()
        
        for asset_id in asset_ids:
            # Получаем все транзакции для этого актива
            transactions = Transaction.query.filter_by(
                portfolio_id=portfolio_id,
                asset_id=asset_id
            ).order_by(Transaction.tx_date).all()
            
            # Рассчитываем текущую позицию
            current_quantity = Decimal('0')
            total_cost = Decimal('0')
            
            for tx in transactions:
                q = tx.quantity
                p = tx.price
                
                if tx.tx_type == 'buy':
                    old_total = current_quantity * (total_cost / current_quantity if current_quantity > 0 else 0)
                    new_total = q * p
                    current_quantity += q
                    if current_quantity > 0:
                        avg_price = (old_total + new_total) / current_quantity
                        total_cost = current_quantity * avg_price
                elif tx.tx_type == 'sell':
                    current_quantity -= q
            
            # Сохраняем текущую позицию если есть
            if current_quantity > 0:
                avg_price = total_cost / current_quantity if current_quantity > 0 else 0
                position = Position(
                    portfolio_id=portfolio_id,
                    asset_id=asset_id,
                    quantity=current_quantity,
                    avg_price=avg_price
                )
                db.session.add(position)
            
            # Пересчитываем закрытую позицию
            PositionService._recalc_closed_position(portfolio_id, asset_id)
        
        # Проверяем, не потерялись ли какие-то закрытые позиции
        # (если актив был полностью продан, но транзакций больше нет)
        for asset_id, old_data in old_closed_positions.items():
            if asset_id not in asset_ids and old_data['total_sold_quantity'] > 0:
                # Восстанавливаем закрытую позицию из старых данных, если она была
                existing = ClosedPosition.query.filter_by(
                    portfolio_id=portfolio_id,
                    asset_id=asset_id
                ).first()
                if not existing:
                    # Нужно восстановить из транзакций, но их нет - сохраняем старые данные
                    # Находим актив
                    from app.models.asset import Asset
                    asset = Asset.query.get(asset_id)
                    if asset:
                        closed_pos = ClosedPosition(
                            portfolio_id=portfolio_id,
                            asset_id=asset_id,
                            total_quantity=old_data['total_quantity'],
                            total_buy_cost=0,  # Мы не знаем точную стоимость
                            total_sold_quantity=old_data['total_sold_quantity'],
                            total_sell_revenue=0,
                            realized_pnl=old_data['realized_pnl'],
                            return_percentage=0,
                            first_buy_date=datetime.utcnow(),
                            last_sell_date=datetime.utcnow()
                        )
                        db.session.add(closed_pos)
                        logger.warning(f"Restored closed position for asset {asset_id} from old data")
        
        db.session.commit()
        logger.info(f"Recalculated portfolio {portfolio_id}: {len(asset_ids)} assets processed")