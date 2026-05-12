# app/services/currency_service.py
from app.extensions import db
from app.models.currency_rate import CurrencyRate
from decimal import Decimal
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)

class CurrencyService:
    """Сервис для конвертации валют"""
    
    # Кэш курсов на текущую сессию
    _rates_cache = {}
    
    @classmethod
    def get_rate(cls, from_currency, to_currency, rate_date=None):
        """Получение курса конвертации"""
        if from_currency == to_currency:
            return Decimal('1')
        
        if rate_date is None:
            rate_date = date.today()
        
        # Проверяем кэш
        cache_key = f"{from_currency}_{to_currency}_{rate_date}"
        if cache_key in cls._rates_cache:
            return cls._rates_cache[cache_key]
        
        # Ищем курс в базе
        rate = CurrencyRate.query.filter_by(
            base_currency=from_currency,
            target_currency=to_currency,
            rate_date=rate_date
        ).first()
        
        if not rate:
            # Пробуем обратный курс
            rate = CurrencyRate.query.filter_by(
                base_currency=to_currency,
                target_currency=from_currency,
                rate_date=rate_date
            ).first()
            if rate:
                rate_value = Decimal('1') / rate.rate
                cls._rates_cache[cache_key] = rate_value
                return rate_value
        
        if rate:
            cls._rates_cache[cache_key] = rate.rate
            logger.warning(f"Currency rate: {rate.rate}")    
            return rate.rate
        
        # Если курс не найден, возвращаем 1 (без конвертации)
        logger.warning(f"Currency rate not found: {from_currency} -> {to_currency} for {rate_date}")
        return Decimal('1')
    
    @classmethod
    def convert(cls, amount, from_currency, to_currency, rate_date=None):
        """Конвертация суммы из одной валюты в другую"""
        if from_currency == to_currency:
            return amount
        
        rate = cls.get_rate(from_currency, to_currency, rate_date)
        logger.info(f"convert value from currency: {from_currency} to {to_currency}, rate = { rate}")
        return amount * rate
    
    @classmethod
    def clear_cache(cls):
        """Очистка кэша курсов"""
        cls._rates_cache = {}