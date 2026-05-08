import yfinance as yf
from flask import current_app
from functools import lru_cache
from datetime import datetime, timedelta
import redis
import json

class PricingService:
    
    def __init__(self):
        try:
            self.redis_client = redis.from_url(current_app.config['REDIS_URL'])
        except:
            self.redis_client = None
    
    @staticmethod
    def get_current_prices(tickers, use_cache=True):
        """Получение текущих цен с кешированием"""
        if not tickers:
            return {}
        
        result = {}
        uncached_tickers = []
        
        # Проверяем кеш
        if use_cache:
            try:
                redis_client = redis.from_url(current_app.config['REDIS_URL'])
                for ticker in tickers:
                    cached = redis_client.get(f'price:{ticker}')
                    if cached:
                        result[ticker] = float(cached)
                    else:
                        uncached_tickers.append(ticker)
            except:
                uncached_tickers = tickers
        else:
            uncached_tickers = tickers
        
        # Запрашиваем у yfinance
        if uncached_tickers:
            yf_tickers = ' '.join(uncached_tickers)
            try:
                data = yf.download(yf_tickers, period='1d', group_by='ticker')
                
                for ticker in uncached_tickers:
                    if ticker in data:
                        price = data[ticker]['Close'].iloc[-1]
                        result[ticker] = float(price)
                        
                        # Сохраняем в кеш
                        if use_cache:
                            try:
                                redis_client.setex(f'price:{ticker}', 300, price)  # TTL 5 минут
                            except:
                                pass
                    else:
                        price = yf.Ticker(ticker).info.get('regularMarketPrice')
                        if price:
                            result[ticker] = float(price)
                        else:
                            result[ticker] = 0.0
            except Exception as e:
                current_app.logger.error(f"Error fetching prices: {e}")
                for ticker in uncached_tickers:
                    result[ticker] = 0.0
        
        return result
    
    @staticmethod
    def get_historical_prices(asset_id, start_date, end_date):
        """Получение исторических цен из БД"""
        from app.models.historical_price import HistoricalPrice
        
        prices = HistoricalPrice.query.filter(
            HistoricalPrice.asset_id == asset_id,
            HistoricalPrice.price_date >= start_date,
            HistoricalPrice.price_date <= end_date
        ).order_by(HistoricalPrice.price_date).all()
        
        return prices