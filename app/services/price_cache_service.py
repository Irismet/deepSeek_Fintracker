# app/services/price_cache_service.py
from app.extensions import db
from app.models.price_cache import PriceCache
from app.models.asset import Asset
from app.services.kase_parser import KaseParser
from datetime import datetime, timedelta
import yfinance as yf
import logging

logger = logging.getLogger(__name__)

class PriceCacheService:
    """Сервис для кэширования цен в БД"""
    
    # Цены считаются устаревшими через 2 часа
    CACHE_TTL_HOURS = 2
    
    # app/services/price_cache_service.py - обновите метод get_current_prices

    @classmethod
    def get_current_prices(cls, tickers, force_update=False):
        """Получение текущих цен с использованием БД кэша"""
        if not tickers:
            return {}
        
        result = {}
        tickers_to_update = []
        
        for ticker in tickers:
            # Получаем актив для проверки типа
            asset = Asset.query.filter_by(ticker=ticker).first()
            
            # Для облигаций используем номинал как текущую цену
            if asset and asset.asset_type == 'bond' and asset.face_value:
                result[ticker] = float(asset.face_value)
                continue
            
            # Для остальных активов - обычная логика
            cache_entry = PriceCache.query.filter_by(ticker=ticker).first()
            
            if cache_entry and not force_update:
                age = datetime.utcnow() - cache_entry.last_update
                if age < timedelta(hours=cls.CACHE_TTL_HOURS):
                    result[ticker] = float(cache_entry.price)
                    logger.debug(f"Cache hit for {ticker}: {cache_entry.price}")
                else:
                    tickers_to_update.append(ticker)
            else:
                tickers_to_update.append(ticker)
        
        if tickers_to_update:
            cls._update_prices(tickers_to_update, result)
        
        return result
    
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
    def _get_price_from_kase(cls, ticker, asset):
        """Получение цены с KASE для казахстанских акций"""
        price = KaseParser.get_price(ticker)
        if price is not None:
            return float(price)
        
        # Если не нашли на KASE, пробуем yfinance
        try:
            ticker_obj = yf.Ticker(ticker)
            price = ticker_obj.info.get('regularMarketPrice', 0)
            return float(price) if price else 0
        except:
            return 0
    
    @classmethod
    def _update_prices(cls, tickers, result_dict):
        """Обновление цен через yfinance и KASE"""
        if not tickers:
            return
        
        # Разделяем тикеры на казахстанские и остальные
        kz_tickers = []
        other_tickers = []
        
        for ticker in tickers:
            # Проверяем ISIN актива
            asset = Asset.query.filter_by(ticker=ticker).first()
            if asset and asset.isin and asset.isin.startswith('KZ'):
                kz_tickers.append(ticker)
            else:
                other_tickers.append(ticker)
        
        # Обновляем казахстанские акции через KASE
        for ticker in kz_tickers:
            try:
                asset = Asset.query.filter_by(ticker=ticker).first()
                price = cls._get_price_from_kase(ticker, asset)
                result_dict[ticker] = price
                cls._save_price_to_db(ticker, price)
                logger.info(f"Updated KASE price for {ticker}: {price}")
            except Exception as e:
                logger.error(f"Error updating KASE price for {ticker}: {e}")
                # Fallback: пробуем yfinance
                try:
                    ticker_obj = yf.Ticker(ticker)
                    price = ticker_obj.info.get('regularMarketPrice', 0)
                    price = float(price) if price else 0
                    result_dict[ticker] = price
                    cls._save_price_to_db(ticker, price)
                except:
                    result_dict[ticker] = 0
        
        # Обновляем остальные акции через yfinance
        if other_tickers:
            try:
                tickers_str = ' '.join(other_tickers)
                data = yf.download(tickers_str, period='1d', group_by='ticker', progress=False)
                
                for ticker in other_tickers:
                    try:
                        if len(other_tickers) == 1:
                            price = data['Close'].iloc[-1] if not data.empty else 0
                        else:
                            if ticker in data:
                                price = data[ticker]['Close'].iloc[-1]
                            else:
                                ticker_obj = yf.Ticker(ticker)
                                price = ticker_obj.info.get('regularMarketPrice', 0)
                        
                        price = float(price) if price and price > 0 else 0
                        result_dict[ticker] = price
                        cls._save_price_to_db(ticker, price)
                    except Exception as e:
                        logger.error(f"Error updating price for {ticker}: {e}")
                        result_dict[ticker] = 0
                        
            except Exception as e:
                logger.error(f"Error in batch price update: {e}")
                for ticker in other_tickers:
                    cls._update_single_price(ticker, result_dict)
    
    @classmethod
    def update_all_prices(cls):
        """Принудительное обновление всех цен с учетом KASE"""
        assets = Asset.query.filter(Asset.ticker.isnot(None)).all()
        
        # Разделяем по источникам
        kz_assets = [a for a in assets if a.isin and a.isin.startswith('KZ')]
        other_assets = [a for a in assets if not (a.isin and a.isin.startswith('KZ'))]
        
        results = {
            'kase_updated': 0,
            'yfinance_updated': 0,
            'total': len(assets),
            'errors': []
        }
        
        # Обновляем KZ акции через KASE
        for asset in kz_assets:
            try:
                price = cls._get_price_from_kase(asset.ticker, asset)
                if price > 0:
                    cls._save_price_to_db(asset.ticker, price)
                    results['kase_updated'] += 1
                else:
                    results['errors'].append(f"KASE: {asset.ticker} - price not found")
            except Exception as e:
                results['errors'].append(f"KASE: {asset.ticker} - {str(e)}")
        
        # Обновляем остальные через yfinance
        if other_assets:
            other_tickers = [a.ticker for a in other_assets]
            try:
                tickers_str = ' '.join(other_tickers)
                data = yf.download(tickers_str, period='1d', group_by='ticker', progress=False)
                
                for asset in other_assets:
                    try:
                        ticker = asset.ticker
                        if len(other_assets) == 1:
                            price = data['Close'].iloc[-1] if not data.empty else 0
                        else:
                            if ticker in data:
                                price = data[ticker]['Close'].iloc[-1]
                            else:
                                ticker_obj = yf.Ticker(ticker)
                                price = ticker_obj.info.get('regularMarketPrice', 0)
                        
                        price = float(price) if price and price > 0 else 0
                        if price > 0:
                            cls._save_price_to_db(ticker, price)
                            results['yfinance_updated'] += 1
                    except Exception as e:
                        results['errors'].append(f"yfinance: {asset.ticker} - {str(e)}")
                        
            except Exception as e:
                results['errors'].append(f"Batch update error: {str(e)}")
        
        return {
            "message": f"Updated {results['kase_updated']} KASE + {results['yfinance_updated']} yfinance prices",
            "updated": results['kase_updated'] + results['yfinance_updated'],
            "total": results['total'],
            "errors": results['errors'][:10]  # Показываем первые 10 ошибок
        }

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
