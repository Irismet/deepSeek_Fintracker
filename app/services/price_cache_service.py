# app/services/price_cache_service.py
from app.extensions import db
from app.models.price_cache import PriceCache
from app.models.asset import Asset
from datetime import datetime, timedelta
import yfinance as yf
import logging

logger = logging.getLogger(__name__)

class PriceCacheService:
    """Сервис для кэширования цен в БД"""
    
    # Цены считаются устаревшими через 2 часа
    CACHE_TTL_HOURS = 2
    
    @classmethod
    def get_current_prices(cls, tickers, force_update=False):
        """
        Получение текущих цен с использованием БД кэша
        Если цены устарели - обновляем
        """
        if not tickers:
            return {}
        
        result = {}
        tickers_to_update = []
        
        # Проверяем кэш в БД
        for ticker in tickers:
            cache_entry = PriceCache.query.filter_by(ticker=ticker).first()
            
            if cache_entry and not force_update:
                # Проверяем, не устарела ли цена
                age = datetime.utcnow() - cache_entry.last_update
                if age < timedelta(hours=cls.CACHE_TTL_HOURS):
                    result[ticker] = float(cache_entry.price)
                    logger.debug(f"Cache hit for {ticker}: {cache_entry.price} (age: {age.total_seconds()/3600:.1f}h)")
                else:
                    tickers_to_update.append(ticker)
            else:
                tickers_to_update.append(ticker)
        
        # Обновляем устаревшие цены
        if tickers_to_update:
            cls._update_prices(tickers_to_update, result)
        
        return result
    
    @classmethod
    def _update_prices(cls, tickers, result_dict):
        """Обновление цен через yfinance"""
        if not tickers:
            return
        
        logger.info(f"Updating prices for {len(tickers)} tickers: {tickers}")
        
        try:
            # Группируем для batch запроса
            tickers_str = ' '.join(tickers)
            data = yf.download(tickers_str, period='1d', group_by='ticker', progress=False)
            
            for ticker in tickers:
                try:
                    # Получаем цену
                    if len(tickers) == 1:
                        price = data['Close'].iloc[-1] if not data.empty else 0
                    else:
                        if ticker in data:
                            price = data[ticker]['Close'].iloc[-1]
                        else:
                            # Fallback через Ticker
                            ticker_obj = yf.Ticker(ticker)
                            price = ticker_obj.info.get('regularMarketPrice', 0)
                    
                    price = float(price) if price and price > 0 else 0
                    result_dict[ticker] = price
                    
                    # Сохраняем в БД
                    cls._save_price_to_db(ticker, price)
                    
                except Exception as e:
                    logger.error(f"Error updating price for {ticker}: {e}")
                    # Если не удалось обновить, используем старую цену если есть
                    old_entry = PriceCache.query.filter_by(ticker=ticker).first()
                    if old_entry:
                        result_dict[ticker] = float(old_entry.price)
                        logger.info(f"Using cached price for {ticker}: {old_entry.price}")
                    else:
                        result_dict[ticker] = 0
                        
        except Exception as e:
            logger.error(f"Error in batch price update: {e}")
            # Fallback: обновляем по одному
            for ticker in tickers:
                cls._update_single_price(ticker, result_dict)
    
    @classmethod
    def _update_single_price(cls, ticker, result_dict):
        """Обновление цены для одного тикера"""
        try:
            ticker_obj = yf.Ticker(ticker)
            price = ticker_obj.info.get('regularMarketPrice', 0)
            price = float(price) if price else 0
            result_dict[ticker] = price
            cls._save_price_to_db(ticker, price)
        except Exception as e:
            logger.error(f"Error updating single price for {ticker}: {e}")
            result_dict[ticker] = 0
    
    @classmethod
    def _save_price_to_db(cls, ticker, price):
        """Сохранение цены в БД"""
        try:
            # Находим актив по тикеру
            asset = Asset.query.filter_by(ticker=ticker).first()
            if not asset:
                logger.warning(f"Asset not found for ticker: {ticker}")
                return
            
            # Обновляем или создаем запись кэша
            cache_entry = PriceCache.query.filter_by(ticker=ticker).first()
            if cache_entry:
                cache_entry.price = price
                cache_entry.last_update = datetime.utcnow()
            else:
                cache_entry = PriceCache(
                    asset_id=asset.id,
                    ticker=ticker,
                    price=price,
                    currency=asset.currency,
                    last_update=datetime.utcnow()
                )
                db.session.add(cache_entry)
            
            db.session.commit()
            logger.debug(f"Saved price for {ticker}: {price}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving price to DB for {ticker}: {e}")
    
    @classmethod
    def update_all_prices(cls):
        """Принудительное обновление всех цен (для фоновой задачи)"""
        assets = Asset.query.filter(Asset.ticker.isnot(None)).all()
        tickers = [a.ticker for a in assets if a.ticker]
        
        if not tickers:
            return {"message": "No assets found"}
        
        logger.info(f"Updating all prices for {len(tickers)} assets")
        
        try:
            # Batch обновление
            tickers_str = ' '.join(tickers)
            data = yf.download(tickers_str, period='1d', group_by='ticker', progress=False)
            
            updated_count = 0
            for ticker in tickers:
                try:
                    if len(tickers) == 1:
                        price = data['Close'].iloc[-1] if not data.empty else 0
                    else:
                        if ticker in data:
                            price = data[ticker]['Close'].iloc[-1]
                        else:
                            continue
                    
                    price = float(price) if price and price > 0 else 0
                    if price > 0:
                        cls._save_price_to_db(ticker, price)
                        updated_count += 1
                        
                except Exception as e:
                    logger.error(f"Error updating {ticker}: {e}")
            
            return {
                "message": f"Updated {updated_count} out of {len(tickers)} prices",
                "updated": updated_count,
                "total": len(tickers)
            }
            
        except Exception as e:
            logger.error(f"Error in batch update: {e}")
            return {"error": str(e)}
    
    @classmethod
    def get_cache_stats(cls):
        """Получение статистики кэша"""
        total_entries = PriceCache.query.count()
        outdated = PriceCache.query.filter(
            PriceCache.last_update < datetime.utcnow() - timedelta(hours=cls.CACHE_TTL_HOURS)
        ).count()
        
        # Средний возраст кэша
        from sqlalchemy import func
        avg_age = db.session.query(
            func.avg(datetime.utcnow() - PriceCache.last_update)
        ).scalar()
        
        return {
            'total_entries': total_entries,
            'outdated_entries': outdated,
            'fresh_entries': total_entries - outdated,
            'cache_hit_rate': f"{(total_entries - outdated) / total_entries * 100:.1f}%" if total_entries > 0 else "0%",
            'ttl_hours': cls.CACHE_TTL_HOURS
        }
    
    @classmethod
    def clear_cache(cls):
        """Очистка всего кэша"""
        try:
            deleted = PriceCache.query.delete()
            db.session.commit()
            logger.info(f"Cleared {deleted} cache entries")
            return {"deleted": deleted}
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error clearing cache: {e}")
            return {"error": str(e)}

# Глобальный экземпляр
price_cache_service = PriceCacheService()