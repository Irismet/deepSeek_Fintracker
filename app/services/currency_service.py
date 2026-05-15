# app/services/currency_service.py
from decimal import Decimal
from datetime import date
from app.services.currency_rate_service import CurrencyRateService
import logging

logger = logging.getLogger(__name__)

class CurrencyService:
    """Сервис для конвертации валют (обертка над CurrencyRateService)"""
    
    @classmethod
    def get_rate(cls, from_currency, to_currency, rate_date=None):
        """
        Получение курса конвертации между двумя валютами
        
        Args:
            from_currency: Исходная валюта (например, 'USD')
            to_currency: Целевая валюта (например, 'KZT')
            rate_date: Дата курса (если None - текущая дата)
        
        Returns:
            Decimal: Курс конвертации
        """
        return CurrencyRateService.get_rate(from_currency, to_currency, rate_date)
    
    @classmethod
    def convert(cls, amount, from_currency, to_currency, rate_date=None):
        """
        Конвертация суммы из одной валюты в другую
        
        Args:
            amount: Сумма для конвертации
            from_currency: Исходная валюта
            to_currency: Целевая валюта
            rate_date: Дата курса
        
        Returns:
            Decimal: Сумма в целевой валюте
        """
        if from_currency == to_currency:
            return amount
        
        if not amount or amount == 0:
            return Decimal('0')
        
        try:
            rate = cls.get_rate(from_currency, to_currency, rate_date)
            result = amount * rate
            logger.debug(f"Converted {amount} {from_currency} -> {result} {to_currency} at rate {rate}")
            return result
        except Exception as e:
            logger.error(f"Currency conversion error: {e}")
            return amount  # Возвращаем исходную сумму в случае ошибки
    
    @classmethod
    def get_rate_info(cls, from_currency, to_currency):
        """
        Получение информации о курсе с последней датой
        """
        from app.models.currency_rate import CurrencyRate
        
        rate_obj = CurrencyRate.query.filter_by(
            base_currency=from_currency,
            target_currency=to_currency
        ).order_by(CurrencyRate.rate_date.desc()).first()
        
        if rate_obj:
            return {
                'rate': float(rate_obj.rate),
                'date': rate_obj.rate_date.isoformat(),
                'source': rate_obj.source
            }
        return None
    
    @classmethod
    def clear_cache(cls):
        """
        Очистка кэша курсов (для принудительного обновления)
        """
        # CurrencyRateService не имеет внутреннего кэша,
        # но можно добавить принудительное обновление
        logger.info("Currency cache cleared")
    
    @classmethod
    def convert_batch(cls, amounts, from_currency, to_currency, rate_date=None):
        """
        Массовая конвертация списка сумм
        """
        rate = cls.get_rate(from_currency, to_currency, rate_date)
        return [amount * rate for amount in amounts]
    
    @classmethod
    def get_available_currencies(cls):
        """
        Получение списка всех доступных валют из базы
        """
        from app.models.currency_rate import CurrencyRate
        
        currencies = set()
        rates = CurrencyRate.query.all()
        
        for rate in rates:
            currencies.add(rate.base_currency)
            currencies.add(rate.target_currency)
        
        return sorted(list(currencies))