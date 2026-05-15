# app/services/currency_rate_service.py
import requests
from datetime import datetime, timedelta, date
from decimal import Decimal
from app.extensions import db
from app.models.currency_rate import CurrencyRate
import logging

logger = logging.getLogger(__name__)

class CurrencyRateService:
    """Сервис для автоматического обновления курсов валют"""
    
    # Список валют для отслеживания
    CURRENCY_PAIRS = [
        ('USD', 'KZT'),
        ('EUR', 'KZT'),
        ('RUB', 'KZT'),
        ('GBP', 'KZT'),
        ('CNY', 'KZT'),
        ('USD', 'EUR'),
        ('EUR', 'USD'),
    ]
    
    # API для получения курсов (бесплатный, не требует ключа)
    # Используем ExchangeRate-API (до 1500 запросов в месяц бесплатно)
    API_URL = "https://api.exchangerate-api.com/v4/latest/{base}"
    
    # Альтернативный API (тоже бесплатный)
    # API_URL_ALT = "https://api.frankfurter.app/latest?from={base}"
    
    @classmethod
    def get_last_rate_date(cls, base_currency, target_currency):
        """Получение даты последнего курса для пары валют"""
        last_rate = CurrencyRate.query.filter_by(
            base_currency=base_currency,
            target_currency=target_currency
        ).order_by(CurrencyRate.rate_date.desc()).first()
        
        if last_rate:
            return last_rate.rate_date
        return None
    
    @classmethod
    def fetch_current_rates(cls, base_currency='USD'):
        """Получение текущих курсов из API"""
        try:
            url = cls.API_URL.format(base=base_currency)
            logger.info(f"Fetching currency rates from: {url}")
            
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            rates = data.get('rates', {})
            
            return rates
        except requests.RequestException as e:
            logger.error(f"Error fetching currency rates: {e}")
            return None
    
    @classmethod
    def update_rates_for_date(cls, target_date, base_currency='USD'):
        """Обновление курсов для конкретной даты"""
        rates = cls.fetch_current_rates(base_currency)
        
        if not rates:
            logger.error(f"Could not fetch rates for {base_currency}")
            return 0
        
        updated_count = 0
        today = date.today()
        
        for target_currency in ['KZT', 'EUR', 'RUB', 'GBP', 'CNY']:
            if target_currency in rates:
                rate_value = Decimal(str(rates[target_currency]))
                
                # Сохраняем прямой курс
                existing = CurrencyRate.query.filter_by(
                    base_currency=base_currency,
                    target_currency=target_currency,
                    rate_date=target_date
                ).first()
                
                if existing:
                    existing.rate = rate_value
                    existing.source = 'exchange_rate_api'
                    existing.updated_at = datetime.utcnow()
                else:
                    new_rate = CurrencyRate(
                        base_currency=base_currency,
                        target_currency=target_currency,
                        rate=rate_value,
                        rate_date=target_date,
                        source='exchange_rate_api'
                    )
                    db.session.add(new_rate)
                
                updated_count += 1
                
                # Сохраняем обратный курс (например, KZT -> USD)
                if rate_value != 0:
                    inverse_rate = Decimal('1') / rate_value
                    inverse_exists = CurrencyRate.query.filter_by(
                        base_currency=target_currency,
                        target_currency=base_currency,
                        rate_date=target_date
                    ).first()
                    
                    if inverse_exists:
                        inverse_exists.rate = inverse_rate
                        inverse_exists.source = 'exchange_rate_api'
                    else:
                        inverse_rate_obj = CurrencyRate(
                            base_currency=target_currency,
                            target_currency=base_currency,
                            rate=inverse_rate,
                            rate_date=target_date,
                            source='exchange_rate_api'
                        )
                        db.session.add(inverse_rate_obj)
                    
                    updated_count += 1
        
        db.session.commit()
        logger.info(f"Updated {updated_count} currency rates for {target_date}")
        return updated_count
    
    @classmethod
    def update_missing_rates(cls):
        """Обновление недостающих курсов (заполнение пробелов)"""
        today = date.today()
        updated_total = 0
        
        for base, target in cls.CURRENCY_PAIRS:
            last_date = cls.get_last_rate_date(base, target)
            
            if last_date is None:
                # Нет данных - загружаем текущий курс
                logger.info(f"No data for {base}/{target}, fetching current rate")
                rates = cls.fetch_current_rates(base)
                if rates and target in rates:
                    rate_value = Decimal(str(rates[target]))
                    new_rate = CurrencyRate(
                        base_currency=base,
                        target_currency=target,
                        rate=rate_value,
                        rate_date=today,
                        source='exchange_rate_api'
                    )
                    db.session.add(new_rate)
                    updated_total += 1
                    logger.info(f"Added initial rate for {base}/{target}: {rate_value}")
            else:
                # Проверяем, нужно ли обновить сегодняшний курс
                if last_date < today:
                    logger.info(f"Last rate for {base}/{target} is {last_date}, updating...")
                    rates = cls.fetch_current_rates(base)
                    if rates and target in rates:
                        rate_value = Decimal(str(rates[target]))
                        
                        # Проверяем, есть ли уже курс на сегодня
                        existing = CurrencyRate.query.filter_by(
                            base_currency=base,
                            target_currency=target,
                            rate_date=today
                        ).first()
                        
                        if not existing:
                            new_rate = CurrencyRate(
                                base_currency=base,
                                target_currency=target,
                                rate=rate_value,
                                rate_date=today,
                                source='exchange_rate_api'
                            )
                            db.session.add(new_rate)
                            updated_total += 1
                            logger.info(f"Added rate for {base}/{target}: {rate_value}")
        
        db.session.commit()
        logger.info(f"Total rates updated: {updated_total}")
        return updated_total
    
    @classmethod
    def get_rate(cls, from_currency, to_currency, rate_date=None):
        """Получение курса конвертации из базы"""
        if from_currency == to_currency:
            return Decimal('1')
        
        if rate_date is None:
            rate_date = date.today()
        
        # Ищем курс в базе
        rate_obj = CurrencyRate.query.filter_by(
            base_currency=from_currency,
            target_currency=to_currency,
            rate_date=rate_date
        ).first()
        
        if not rate_obj:
            # Пробуем найти ближайший предыдущий курс
            rate_obj = CurrencyRate.query.filter(
                CurrencyRate.base_currency == from_currency,
                CurrencyRate.target_currency == to_currency,
                CurrencyRate.rate_date <= rate_date
            ).order_by(CurrencyRate.rate_date.desc()).first()
        
        if rate_obj:
            return rate_obj.rate
        
        # Если курс не найден, используем текущий из API
        logger.warning(f"Rate not found for {from_currency}->{to_currency} on {rate_date}, fetching current")
        rates = cls.fetch_current_rates(from_currency)
        if rates and to_currency in rates:
            return Decimal(str(rates[to_currency]))
        
        # Последнее средство - возвращаем 1
        logger.error(f"Could not get rate for {from_currency}->{to_currency}")
        return Decimal('1')
    
    # В конец файла currency_rate_service.py добавьте:

    @classmethod
    def convert(cls, amount, from_currency, to_currency, rate_date=None):
        """
        Конвертация суммы (удобный метод для вызова из других сервисов)
        """
        if from_currency == to_currency:
            return amount
        
        rate = cls.get_rate(from_currency, to_currency, rate_date)
        return amount * rate
    
    @classmethod
    def get_stats(cls):
        """Статистика по курсам в базе"""
        total_rates = CurrencyRate.query.count()
        
        # Получаем последние даты по каждой паре
        stats = []
        for base, target in cls.CURRENCY_PAIRS:
            last_rate = CurrencyRate.query.filter_by(
                base_currency=base,
                target_currency=target
            ).order_by(CurrencyRate.rate_date.desc()).first()
            
            if last_rate:
                stats.append({
                    'pair': f"{base}/{target}",
                    'last_date': last_rate.rate_date.isoformat(),
                    'last_rate': float(last_rate.rate)
                })
        
        return {
            'total_rates': total_rates,
            'pairs_stats': stats
        }