# app/init_data.py
from app import db
from app.models.broker import Broker
from app.models.exchange import Exchange
from app.models.asset_class import AssetClass
from app.models.sector import Sector

def init_reference_data():
    """Инициализация справочных данных"""
    
    # Брокеры
    brokers = [
        Broker(name='Freedom Broker', country='Kazakhstan', website='https://fbroker.kz/', commission_fee=0.12),
        Broker(name='Paidax', country='Kazakhstan', website='https://www.paidax.kz', commission_fee=0.2),
        Broker(name='Alatau City Invest', country='Kazakhstan', website='https://alataucityinvest.kz/', commission_fee=0.03),
        Broker(name='Binance', country='Kazakhstan', website='https://www.binance.com', commission_fee=0.1),
        Broker(name='Halyk Finance', country='Kazakhstan', website='https://halykfinance.kz/', commission_fee=0.1),
        Broker(name='Halyk Invest', country='Kazakhstan', website='https://halykinvest.kz/', commission_fee=0.1),
        Broker(name='BCC Invest', country='Kazakhstan', website='https://www.bcc.kz', commission_fee=0.1)
    ]
    
    for broker in brokers:
        if not Broker.query.filter_by(name=broker.name).first():
            db.session.add(broker)
    
    # Биржи
    exchanges = [
        Exchange(name='NYSE', country='USA', city='New York', timezone='America/New_York', currency='USD'),
        Exchange(name='NASDAQ', country='USA', city='New York', timezone='America/New_York', currency='USD'),
        Exchange(name='KASE', country='Kazakhstan', city='Almaty', timezone='Asia/Astana', currency='KZT'),
        Exchange(name='KASE', country='Kazakhstan', city='Astana', timezone='Asia/Astana', currency='KZT'),
        Exchange(name='LSE', country='UK', city='London', timezone='Europe/London', currency='GBP'),
        Exchange(name='Binance', country='Kazakhstan', city='Almaty', timezone='Asia/Astana', currency='USD')
    ]
    
    for exchange in exchanges:
        if not Exchange.query.filter_by(name=exchange.name).first():
            db.session.add(exchange)
    
    # Классы активов
    asset_classes = [
        AssetClass(name='Equity', description='Акции', risk_level=7),
        AssetClass(name='Fixed Income', description='Облигации', risk_level=3),
        AssetClass(name='ETF', description='ETF', risk_level=4),
        AssetClass(name='Cash', description='Денежные средства', risk_level=1),
        AssetClass(name='Commodities', description='Товарные активы', risk_level=6),
        AssetClass(name='Real Estate', description='Недвижимость', risk_level=5),
        AssetClass(name='Crypto', description='Криптовалюты', risk_level=9)
    ]
    
    for ac in asset_classes:
        if not AssetClass.query.filter_by(name=ac.name).first():
            db.session.add(ac)
    
    # Сектора экономики (GICS классификация)
    sectors = [
        Sector(name='Technology', description='Технологии', gics_code='35'),
        Sector(name='Healthcare', description='Здравоохранение', gics_code='35'),
        Sector(name='Financials', description='Финансы', gics_code='40'),
        Sector(name='Energy', description='Энергетика', gics_code='10'),
        Sector(name='Consumer Cyclical', description='Потребительский сектор', gics_code='25'),
        Sector(name='Consumer Defensive', description='Защитный потребительский', gics_code='30'),
        Sector(name='Industrials', description='Промышленность', gics_code='20'),
        Sector(name='Utilities', description='Коммунальные услуги', gics_code='55'),
        Sector(name='Real Estate', description='Недвижимость', gics_code='60'),
        Sector(name='Communication Services', description='Связь', gics_code='50'),
    ]
    
    for sector in sectors:
        if not Sector.query.filter_by(name=sector.name).first():
            db.session.add(sector)
    
    db.session.commit()
    print("Reference data initialized successfully!")