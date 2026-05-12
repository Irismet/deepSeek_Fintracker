# app/services/split_service.py
from app.extensions import db
from app.models.split_event import SplitEvent
from app.models.asset import Asset
from app.models.position import Position
from app.models.transaction import Transaction
from app.services.position_service import PositionService
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class SplitService:
    """Сервис для обработки сплитов и обратных сплитов"""
    
    @classmethod
    def apply_split(cls, asset_id, old_quantity, new_quantity, split_date, split_type='split'):
        """
        Применение сплита к активу
        split_type: 'split' - обычный сплит (увеличение количества)
                    'reverse_split' - обратный сплит (уменьшение количества)
        """
        asset = Asset.query.get(asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")
        
        ratio = Decimal(str(new_quantity)) / Decimal(str(old_quantity))
        
        # Создаем запись о сплите
        split_event = SplitEvent(
            asset_id=asset_id,
            split_type=split_type,
            old_quantity=Decimal(str(old_quantity)),
            new_quantity=Decimal(str(new_quantity)),
            ratio=ratio,
            split_date=split_date
        )
        db.session.add(split_event)
        
        # Обновляем все позиции по этому активу
        positions = Position.query.filter_by(asset_id=asset_id).all()
        for position in positions:
            old_quantity = position.quantity
            position.quantity = position.quantity * ratio
            position.avg_price = position.avg_price / ratio
            logger.info(f"Split for position {position.id}: {old_quantity} -> {position.quantity}")
        
        # Обновляем все транзакции по этому активу
        transactions = Transaction.query.filter_by(asset_id=asset_id).all()
        for tx in transactions:
            old_quantity = tx.quantity
            old_price = tx.price
            tx.quantity = tx.quantity * ratio
            tx.price = tx.price / ratio
            logger.info(f"Split for transaction {tx.id}: quantity {old_quantity}->{tx.quantity}, price {old_price}->{tx.price}")
        
        db.session.commit()
        
        # Пересчитываем позиции портфелей
        portfolio_ids = set([p.portfolio_id for p in positions])
        for portfolio_id in portfolio_ids:
            PositionService.recalc_portfolio_positions(portfolio_id)
        
        return {
            'asset_id': asset_id,
            'ticker': asset.ticker,
            'split_type': split_type,
            'ratio': float(ratio),
            'affected_positions': len(positions),
            'affected_transactions': len(transactions)
        }
    
    @classmethod
    def get_split_history(cls, asset_id):
        """Получение истории сплитов для актива"""
        splits = SplitEvent.query.filter_by(asset_id=asset_id).order_by(SplitEvent.split_date).all()
        return [s.to_dict() for s in splits]