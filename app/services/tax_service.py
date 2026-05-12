# app/services/tax_service.py
from app.extensions import db
from app.models.tax_event import TaxEvent
from app.models.transaction import Transaction
from app.models.asset import Asset
from app.models.exchange import Exchange
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class TaxService:
    """Сервис для расчета налогов"""
    
    # Налоговые ставки
    US_WITHHOLDING_RATE = Decimal('15')  # 15% налог у источника в США
    LOCAL_DIVIDEND_RATE_KASE = Decimal('5')  # 5% местный налог на дивиденды для KASE
    LOCAL_DIVIDEND_RATE_OTHER = Decimal('10')  # 10% местный налог на дивиденды для других бирж
    LOCAL_CAPITAL_GAINS_RATE = Decimal('10')  # 10% налог на прирост капитала
    
    @classmethod
    def calculate_dividend_tax(cls, dividend_amount, asset_id, portfolio_currency='USD'):
        """Расчет налогов на дивиденды"""
        asset = Asset.query.get(asset_id)
        if not asset:
            return {'withholding_us': 0, 'local': 0, 'total': 0}
        
        # Определяем биржу
        exchange_name = asset.exchange.name if asset.exchange else None
        isin = asset.isin or ''
        
        # Базовый расчет местного налога
        local_tax_rate = cls.LOCAL_DIVIDEND_RATE_OTHER
        withholding_us_rate = cls.US_WITHHOLDING_RATE
        
        # Особые правила для KASE и AIX
        if exchange_name in ['KASE', 'AIX']:
            if isin.startswith('KZ'):
                # Казахстанские бумаги - налог у источника в Казахстане
                withholding_us_rate = Decimal('0')
                local_tax_rate = cls.LOCAL_DIVIDEND_RATE_KASE
            else:
                # Иностранные бумаги на KASE
                withholding_us_rate = cls.US_WITHHOLDING_RATE
                local_tax_rate = cls.LOCAL_DIVIDEND_RATE_KASE
        else:
            # Для других бирж
            if isin.startswith('US'):
                # Американские бумаги
                withholding_us_rate = cls.US_WITHHOLDING_RATE
                local_tax_rate = cls.LOCAL_DIVIDEND_RATE_OTHER
            else:
                # Прочие бумаги
                withholding_us_rate = Decimal('0')
                local_tax_rate = cls.LOCAL_DIVIDEND_RATE_OTHER
        
        withholding_us_tax = dividend_amount * withholding_us_rate / 100
        local_tax = dividend_amount * local_tax_rate / 100
        
        return {
            'withholding_us': float(withholding_us_tax),
            'local': float(local_tax),
            'total': float(withholding_us_tax + local_tax),
            'withholding_rate': float(withholding_us_rate),
            'local_rate': float(local_tax_rate)
        }
    
    @classmethod
    def calculate_capital_gains_tax(cls, profit_amount):
        """Расчет налога на прирост капитала"""
        tax = profit_amount * cls.LOCAL_CAPITAL_GAINS_RATE / 100
        return {
            'tax_amount': float(tax),
            'tax_rate': float(cls.LOCAL_CAPITAL_GAINS_RATE)
        }
    
    @classmethod
    def create_tax_event(cls, portfolio_id, asset_id, transaction_id, tax_type, 
                         taxable_amount, tax_amount, currency, tax_date, notes=None):
        """Создание записи о налоговом событии"""
        tax_event = TaxEvent(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            transaction_id=transaction_id,
            tax_type=tax_type,
            tax_rate=Decimal(str(tax_amount / taxable_amount * 100)) if taxable_amount > 0 else 0,
            taxable_amount=Decimal(str(taxable_amount)),
            tax_amount=Decimal(str(tax_amount)),
            currency=currency,
            tax_date=tax_date,
            notes=notes,
            is_paid=False
        )
        db.session.add(tax_event)
        return tax_event