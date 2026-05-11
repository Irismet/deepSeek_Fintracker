# app/services/kase_parser.py
import requests
from bs4 import BeautifulSoup
from decimal import Decimal
import logging
import re
from time import sleep

logger = logging.getLogger(__name__)

class KaseParser:
    """Парсер цен с сайта KASE для казахстанских акций"""
    
    # Базовый URL для акций KASE
    BASE_URL = "https://kase.kz/ru/investors/shares/"
    
    @classmethod
    def get_price(cls, ticker):
        """Получение цены акции с KASE по тикеру"""
        try:
            url = cls.BASE_URL + ticker.upper()
            logger.info(f"Fetching KASE price for {ticker} from {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем блок с ценой (первый способ)
            price_element = soup.find('app-security-price')
            if price_element:
                # Ищем элемент с нужной меткой
                price_value = price_element.find(attrs={'label': 'цена последней сделки'})
                if price_value:
                    # Извлекаем числовое значение
                    price_text = price_value.get_text(strip=True)
                    # Извлекаем число из текста (может быть с пробелами как разделителями тысяч)
                    price_match = re.search(r'([\d\s,]+(?:\.\d+)?)', price_text)
                    if price_match:
                        price_str = price_match.group(1).replace(' ', '').replace(',', '.')
                        price = Decimal(price_str)
                        logger.info(f"KASE price for {ticker}: {price}")
                        return float(price)
            
            # Альтернативный поиск - ищем в div с классом price
            price_div = soup.find('div', class_=re.compile(r'price|Price|PRICE'))
            if price_div:
                price_text = price_div.get_text(strip=True)
                price_match = re.search(r'([\d\s,]+(?:\.\d+)?)', price_text)
                if price_match:
                    price_str = price_match.group(1).replace(' ', '').replace(',', '.')
                    price = Decimal(price_str)
                    logger.info(f"KASE price for {ticker} (alt): {price}")
                    return float(price)
            
            logger.warning(f"Could not find price for {ticker} on KASE")
            return None
            
        except requests.RequestException as e:
            logger.error(f"Request error for {ticker}: {e}")
            return None
        except Exception as e:
            logger.error(f"Parse error for {ticker}: {e}")
            return None
    
    @classmethod
    def get_price_batch(cls, tickers):
        """Массовое получение цен с KASE"""
        results = {}
        for ticker in tickers:
            price = cls.get_price(ticker)
            if price is not None:
                results[ticker] = price
            sleep(0.5)  # Задержка чтобы не перегружать сервер
        return results