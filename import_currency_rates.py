# import_currency_rates.py
import csv
import sys
import os
from datetime import datetime
from decimal import Decimal

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.currency_rate import CurrencyRate

def parse_date(date_str):
    """Парсинг даты из формата DD.MM.YYYY"""
    return datetime.strptime(date_str, '%d.%m.%Y').date()

def import_rates_from_csv(csv_file_path):
    """Импорт курсов валют из CSV файла"""
    
    app = create_app('development')
    
    with app.app_context():
        print("\n" + "="*60)
        print("🔄 ИМПОРТ КУРСОВ ВАЛЮТ ИЗ CSV")
        print("="*60)
        
        print(f"📁 Файл: {csv_file_path}")
        
        if not os.path.exists(csv_file_path):
            print(f"❌ Файл не найден: {csv_file_path}")
            return
        
        imported_count = 0
        skipped_count = 0
        error_count = 0
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                # Читаем CSV с разделителем ;
                reader = csv.DictReader(file, delimiter=';')
                
                for row in reader:
                    try:
                        date_str = row['Date'].strip()
                        usd_rate_str = row['USD'].strip().replace(',', '.')
                        
                        # Парсим дату
                        rate_date = parse_date(date_str)
                        
                        # Парсим курс (разделитель - запятая, заменяем на точку)
                        usd_rate = Decimal(usd_rate_str)
                        
                        # Создаем запись курса KZT -> USD
                        # 1 USD = XX KZT, значит 1 KZT = 1/XX USD
                        kzt_to_usd = Decimal('1') / usd_rate
                        
                        # Проверяем, существует ли уже запись на эту дату
                        existing = CurrencyRate.query.filter_by(
                            base_currency='KZT',
                            target_currency='USD',
                            rate_date=rate_date
                        ).first()
                        
                        if existing:
                            # Обновляем существующую запись
                            existing.rate = kzt_to_usd
                            existing.source = 'NBK_import'
                            print(f"  ✏️ Обновлен курс на {rate_date}: 1 KZT = {kzt_to_usd:.6f} USD")
                            skipped_count += 1
                        else:
                            # Создаем новую запись
                            rate = CurrencyRate(
                                base_currency='KZT',
                                target_currency='USD',
                                rate=kzt_to_usd,
                                rate_date=rate_date,
                                source='NBK_import'
                            )
                            db.session.add(rate)
                            imported_count += 1
                            
                            if imported_count % 100 == 0:
                                print(f"  📊 Импортировано {imported_count} записей...")
                    
                    except Exception as e:
                        print(f"  ❌ Ошибка обработки строки {row}: {e}")
                        error_count += 1
                
                # Сохраняем все записи
                db.session.commit()
        
        except Exception as e:
            print(f"❌ Ошибка чтения файла: {e}")
            db.session.rollback()
            return
        
        print("\n" + "="*60)
        print("📊 РЕЗУЛЬТАТЫ ИМПОРТА")
        print("="*60)
        print(f"✅ Импортировано новых записей: {imported_count}")
        print(f"✏️ Обновлено существующих записей: {skipped_count}")
        print(f"❌ Ошибок: {error_count}")
        print("="*60)
        
        # Показываем примеры импортированных курсов
        if imported_count > 0:
            print("\n📈 Примеры импортированных курсов:")
            samples = CurrencyRate.query.filter_by(
                base_currency='KZT',
                target_currency='USD'
            ).order_by(CurrencyRate.rate_date.desc()).limit(5).all()
            
            for sample in samples:
                print(f"  {sample.rate_date}: 1 KZT = {sample.rate:.6f} USD")

def import_usd_to_kzt_rates(csv_file_path):
    """Импорт курсов USD -> KZT (прямой курс)"""
    
    app = create_app('development')
    
    with app.app_context():
        print("\n" + "="*60)
        print("🔄 ИМПОРТ КУРСОВ USD -> KZT")
        print("="*60)
        
        if not os.path.exists(csv_file_path):
            print(f"❌ Файл не найден: {csv_file_path}")
            return
        
        imported_count = 0
        updated_count = 0
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file, delimiter=';')
                
                for row in reader:
                    try:
                        date_str = row['Date'].strip()
                        usd_rate_str = row['USD'].strip().replace(',', '.')
                        
                        rate_date = parse_date(date_str)
                        usd_to_kzt = Decimal(usd_rate_str)
                        
                        # Проверяем существующую запись
                        existing = CurrencyRate.query.filter_by(
                            base_currency='USD',
                            target_currency='KZT',
                            rate_date=rate_date
                        ).first()
                        
                        if existing:
                            existing.rate = usd_to_kzt
                            existing.source = 'NBK_import'
                            updated_count += 1
                        else:
                            rate = CurrencyRate(
                                base_currency='USD',
                                target_currency='KZT',
                                rate=usd_to_kzt,
                                rate_date=rate_date,
                                source='NBK_import'
                            )
                            db.session.add(rate)
                            imported_count += 1
                        
                        if (imported_count + updated_count) % 500 == 0:
                            print(f"  📊 Обработано {imported_count + updated_count} записей...")
                    
                    except Exception as e:
                        print(f"  ❌ Ошибка: {e}")
                
                db.session.commit()
        
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            db.session.rollback()
            return
        
        print("\n" + "="*60)
        print("📊 РЕЗУЛЬТАТЫ ИМПОРТА")
        print("="*60)
        print(f"✅ Создано новых записей: {imported_count}")
        print(f"✏️ Обновлено записей: {updated_count}")
        print("="*60)

def import_both_rates(csv_file_path):
    """Импорт обоих направлений курсов"""
    
    print("\n" + "="*60)
    print("🔄 ИМПОРТ КУРСОВ ВАЛЮТ KZT/USD")
    print("="*60)
    
    # Импортируем KZT -> USD
    import_rates_from_csv(csv_file_path)
    
    # Импортируем USD -> KZT
    import_usd_to_kzt_rates(csv_file_path)
    
    # Проверяем итоговую статистику
    app = create_app('development')
    with app.app_context():
        total_kzt_usd = CurrencyRate.query.filter_by(
            base_currency='KZT',
            target_currency='USD'
        ).count()
        
        total_usd_kzt = CurrencyRate.query.filter_by(
            base_currency='USD',
            target_currency='KZT'
        ).count()
        
        print("\n" + "="*60)
        print("📊 ИТОГОВАЯ СТАТИСТИКА В БАЗЕ ДАННЫХ")
        print("="*60)
        print(f"📈 Курсов KZT -> USD: {total_kzt_usd}")
        print(f"📈 Курсов USD -> KZT: {total_usd_kzt}")
        print("="*60)

if __name__ == '__main__':
    # Укажите путь к вашему CSV файлу
    csv_path = 'official_rates2024-2026.csv'
    
    # Проверяем, существует ли файл в текущей директории
    if not os.path.exists(csv_path):
        # Пробуем найти в поддиректориях
        possible_paths = [
            csv_path,
            f'data/{csv_path}',
            f'../{csv_path}',
            f'./data/{csv_path}'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                csv_path = path
                break
        else:
            print(f"❌ Файл {csv_path} не найден!")
            print("Укажите правильный путь к файлу в переменной csv_path")
            sys.exit(1)
    
    print(f"📁 Найден файл: {csv_path}")
    
    # Импортируем оба направления
    import_both_rates(csv_path)