# app/routes.py
from flask import render_template, request, flash, redirect, make_response, url_for, session
from app.extensions import db
from app.models.broker import Broker
from app.models.exchange import Exchange
from app.models.price_cache import PriceCache
from app.models.user import User
from app.models.portfolio import Portfolio
from app.models.asset import Asset
from app.models.transaction import Transaction

from app.services.price_cache_service import price_cache_service
from app.services.pricing_service import PricingService
from app.services.analytics_service import AnalyticsService
from functools import wraps
from datetime import datetime
import logging

logging.basicConfig(level=logging.DEBUG)

def get_token_from_request():
    """Получение токена из cookie или заголовка"""
    token = request.cookies.get('access_token')
    if not token:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
    return token

def get_current_user():
    """Helper функция для получения текущего пользователя"""
    token = get_token_from_request()
    
    if not token:
        print("DEBUG: No token found")
        return None
    
    try:
        from flask_jwt_extended import decode_token
        decoded = decode_token(token)
        user_id = decoded['sub']
        
        # Конвертируем строку в int для запроса к БД
        if isinstance(user_id, str):
            user_id = int(user_id)
        
        user = User.query.get(user_id)
        print(f"DEBUG: Found user: {user.email if user else 'None'}")
        return user
    except Exception as e:
        print(f"DEBUG: Token decode error: {str(e)}")
        return None

def login_required(f):
    """Декоратор для проверки авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = get_current_user()
        if not current_user:
            print("DEBUG: login_required failed - no user")
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login_html'))
        print(f"DEBUG: login_required success - user: {current_user.email}")
        return f(*args, **kwargs)
    return decorated_function

def register_routes(app):
    """Регистрация всех HTML маршрутов"""
    
    @app.route('/')
    def home():
        current_user = get_current_user()
        return render_template('index.html', current_user=current_user)
    
    # Auth routes
    @app.route('/auth/register', methods=['GET', 'POST'])
    def register_html():
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            if not email or not password:
                flash('Email и пароль обязательны для заполнения', 'danger')
                return render_template('auth/register.html')
            
            if password != confirm_password:
                flash('Пароли не совпадают', 'danger')
                return render_template('auth/register.html')
            
            if len(password) < 6:
                flash('Пароль должен содержать минимум 6 символов', 'danger')
                return render_template('auth/register.html')
            
            if User.query.filter_by(email=email).first():
                flash('Пользователь с таким email уже существует', 'danger')
                return render_template('auth/register.html')
            
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            flash('Регистрация успешна! Теперь войдите в систему', 'success')
            return redirect(url_for('login_html'))
        
        current_user = get_current_user()
        return render_template('auth/register.html', current_user=current_user)
    
    @app.route('/auth/login', methods=['GET', 'POST'])
    def login_html():
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            
            print(f"DEBUG: Login attempt - email: {email}")
            
            if not email or not password:
                flash('Email и пароль обязательны для заполнения', 'danger')
                return render_template('auth/login.html')
            
            user = User.query.filter_by(email=email).first()
            
            if user and user.check_password(password):
                from flask_jwt_extended import create_access_token
                access_token = create_access_token(identity=str(user.id))
                
                print(f"DEBUG: Login success - user_id: {user.id}")
                print(f"DEBUG: Token created: {access_token[:50]}...")
                
                # Создаем ответ с редиректом
                response = make_response(redirect(url_for('portfolios_list')))
                
                # Устанавливаем cookie с правильными параметрами
                response.set_cookie(
                    'access_token', 
                    access_token,
                    httponly=False,  # Временно False для отладки, чтобы JS мог читать
                    max_age=86400,   # 24 часа
                    path='/',        # Доступно на всем сайте
                    samesite='Lax',
                    secure=False     # False для localhost
                )
                
                # Дополнительно установим через session для проверки
                session['user_id'] = user.id
                
                flash(f'Добро пожаловать, {user.email}!', 'success')
                print("DEBUG: Redirecting to portfolios")
                return response
            else:
                print(f"DEBUG: Login failed - user found: {user is not None}")
                flash('Неверный email или пароль', 'danger')
        
        current_user = get_current_user()
        return render_template('auth/login.html', current_user=current_user)
    
    @app.route('/auth/logout')
    def logout_html():
        response = make_response(redirect(url_for('home')))
        response.delete_cookie('access_token', path='/')
        flash('Вы вышли из системы', 'info')
        return response
    
    # Portfolio routes
    @app.route('/portfolios')
    @login_required
    def portfolios_list():
        current_user = get_current_user()
        print(f"DEBUG: portfolios_list - user: {current_user.email if current_user else 'None'}")
        portfolios = Portfolio.query.filter_by(user_id=current_user.id).all()
        return render_template('portfolios/list.html', portfolios=portfolios, current_user=current_user)
    
    @app.route('/portfolios/create', methods=['GET', 'POST'])
    @login_required
    def portfolios_create_html():
        current_user = get_current_user()
        
        if request.method == 'POST':
            portfolio = Portfolio(
                user_id=current_user.id,
                name=request.form['name'],
                currency=request.form['currency']
            )
            db.session.add(portfolio)
            db.session.commit()
            flash('Портфель успешно создан!', 'success')
            return redirect(url_for('portfolios_list'))
        
        return render_template('portfolios/create.html', current_user=current_user)
    
    @app.route('/portfolios/<int:portfolio_id>')
    @login_required
    def portfolios_detail_html(portfolio_id):
        current_user = get_current_user()
        portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=current_user.id).first_or_404()
        
        # Используем кэш из БД
        from app.services.analytics_service import AnalyticsService
        summary = AnalyticsService.get_portfolio_summary(portfolio_id, use_cache=True)
        
        # Получаем информацию по позициям
        positions = portfolio.positions.all()
        portfolio_data = portfolio.to_dict()
        portfolio_data.update(summary)
        portfolio_data['positions'] = summary['positions']
        
        # Добавляем информацию о времени последнего обновления цен
        cache_stats = price_cache_service.get_cache_stats()
        portfolio_data['last_price_update'] = None
        
        if positions:
            first_ticker = positions[0].asset.ticker
            cache_entry = PriceCache.query.filter_by(ticker=first_ticker).first()
            if cache_entry:
                portfolio_data['last_price_update'] = cache_entry.last_update.strftime('%Y-%m-%d %H:%M:%S')
        
        return render_template('portfolios/detail.html', 
                            portfolio=portfolio_data, 
                            current_user=current_user)
    
    @app.route('/portfolios/<int:portfolio_id>/edit', methods=['GET', 'POST'])
    @login_required
    def portfolio_edit_html(portfolio_id):
        """Редактирование портфеля"""
        current_user = get_current_user()
        portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=current_user.id).first_or_404()
        
        if request.method == 'POST':
            portfolio.name = request.form.get('name')
            portfolio.currency = request.form.get('currency')
            
            db.session.commit()
            flash('Портфель успешно обновлен!', 'success')
            return redirect(url_for('portfolios_detail_html', portfolio_id=portfolio.id))
        
        return render_template('portfolios/edit.html', portfolio=portfolio, current_user=current_user)
    
    @app.route('/portfolios/<int:portfolio_id>/delete', methods=['POST'])
    @login_required
    def portfolio_delete_html(portfolio_id):
        """Удаление портфеля"""
        current_user = get_current_user()
        portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=current_user.id).first_or_404()
        
        db.session.delete(portfolio)
        db.session.commit()
        
        flash('Портфель успешно удален!', 'success')
        return redirect(url_for('portfolios_list'))
    
    @app.route('/transactions/create/<int:portfolio_id>')
    @login_required
    def transactions_create_html(portfolio_id):
        current_user = get_current_user()
        portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=current_user.id).first_or_404()
        
        # Получаем список всех активов для выпадающего списка
        assets = Asset.query.order_by(Asset.ticker).all()
        
        # Получаем список брокеров
        brokers = Broker.query.filter_by(is_active=True).order_by(Broker.name).all()
        
        # Получаем список бирж
        exchanges = Exchange.query.filter_by(is_active=True).order_by(Exchange.name).all()
        
        return render_template('transactions/create.html', 
                            portfolio_id=portfolio_id,
                            assets=assets,
                            brokers=brokers,
                            exchanges=exchanges,
                            current_user=current_user)
    
    @app.route('/transactions/<int:transaction_id>/edit', methods=['GET', 'POST'])
    @login_required
    def transaction_edit_html(transaction_id):
        """Редактирование транзакции"""
        current_user = get_current_user()
        transaction = Transaction.query.get_or_404(transaction_id)
        
        # Проверяем, что транзакция принадлежит пользователю
        if transaction.portfolio.user_id != current_user.id:
            flash('Доступ запрещен!', 'danger')
            return redirect(url_for('portfolios_list'))
        
        if request.method == 'POST':
            # Обновляем транзакцию
            transaction.tx_type = request.form.get('tx_type')
            transaction.quantity = float(request.form.get('quantity'))
            transaction.price = float(request.form.get('price'))
            transaction.fee = float(request.form.get('fee', 0))
            transaction.tx_currency = request.form.get('tx_currency')
            transaction.tx_date = datetime.strptime(request.form.get('tx_date'), '%Y-%m-%dT%H:%M')
            
            db.session.commit()
            
            # Пересчитываем позиции портфеля
            from app.services.position_service import PositionService
            PositionService.recalc_portfolio_positions(transaction.portfolio_id)
            
            flash('Транзакция успешно обновлена!', 'success')
            return redirect(url_for('portfolios_detail_html', portfolio_id=transaction.portfolio_id))
        
        return render_template('transactions/edit.html', 
                             transaction=transaction, 
                             portfolio_id=transaction.portfolio_id,
                             current_user=current_user)
    
    @app.route('/transactions/<int:transaction_id>/delete', methods=['POST'])
    @login_required
    def transaction_delete_html(transaction_id):
        """Удаление транзакции"""
        current_user = get_current_user()
        transaction = Transaction.query.get_or_404(transaction_id)
        
        # Проверяем, что транзакция принадлежит пользователю
        if transaction.portfolio.user_id != current_user.id:
            flash('Доступ запрещен!', 'danger')
            return redirect(url_for('portfolios_list'))
        
        portfolio_id = transaction.portfolio_id
        
        db.session.delete(transaction)
        db.session.commit()
        
        # Пересчитываем позиции портфеля
        from app.services.position_service import PositionService
        PositionService.recalc_portfolio_positions(portfolio_id)
        
        flash('Транзакция успешно удалена!', 'success')
        return redirect(url_for('portfolios_detail_html', portfolio_id=portfolio_id))
    
    # Asset routes
    @app.route('/assets')
    @login_required
    def assets_list():
        current_user = get_current_user()
        assets = Asset.query.all()
        return render_template('assets/list.html', assets=assets, current_user=current_user)
    
    @app.route('/assets/create', methods=['GET', 'POST'])
    @login_required
    def asset_create_html():
        """Создание нового актива"""
        current_user = get_current_user()
        
        if request.method == 'POST':
            ticker = request.form.get('ticker').upper()
            isin = request.form.get('isin')
            name = request.form.get('name')
            asset_type = request.form.get('asset_type')
            currency = request.form.get('currency')
            
            # Проверяем, существует ли уже актив
            existing = Asset.query.filter_by(ticker=ticker).first()
            if existing:
                flash('Актив с таким тикером уже существует!', 'danger')
                return render_template('assets/create.html', current_user=current_user)
            
            asset = Asset(
                ticker=ticker,
                isin=isin,
                name=name,
                asset_type=asset_type,
                currency=currency
            )
            
            db.session.add(asset)
            db.session.commit()
            
            flash(f'Актив {ticker} успешно создан!', 'success')
            return redirect(url_for('assets_list'))
        
        return render_template('assets/create.html', current_user=current_user)
    
    @app.route('/assets/<int:asset_id>')
    @login_required
    def asset_detail_html(asset_id):
        """Детальная страница актива"""
        current_user = get_current_user()
        asset = Asset.query.get_or_404(asset_id)
        
        # Получаем исторические цены
        from app.models.historical_price import HistoricalPrice
        prices = HistoricalPrice.query.filter_by(asset_id=asset_id)\
            .order_by(HistoricalPrice.price_date.desc())\
            .limit(30)\
            .all()
        
        # Получаем транзакции с этим активом
        transactions = Transaction.query.filter_by(asset_id=asset_id)\
            .order_by(Transaction.tx_date.desc())\
            .limit(50)\
            .all()
        
        return render_template('assets/detail.html', 
                             asset=asset, 
                             prices=prices,
                             transactions=transactions,
                             current_user=current_user)
    
    @app.route('/assets/<int:asset_id>/edit', methods=['GET', 'POST'])
    @login_required
    def asset_edit_html(asset_id):
        """Редактирование актива"""
        current_user = get_current_user()
        asset = Asset.query.get_or_404(asset_id)
        
        if request.method == 'POST':
            asset.ticker = request.form.get('ticker').upper()
            asset.isin = request.form.get('isin')
            asset.name = request.form.get('name')
            asset.asset_type = request.form.get('asset_type')
            asset.currency = request.form.get('currency')
            
            db.session.commit()
            flash('Актив успешно обновлен!', 'success')
            return redirect(url_for('assets_list'))
        
        return render_template('assets/edit.html', asset=asset, current_user=current_user)
    
    @app.route('/assets/<int:asset_id>/delete', methods=['POST'])
    @login_required
    def asset_delete_html(asset_id):
        """Удаление актива"""
        current_user = get_current_user()
        asset = Asset.query.get_or_404(asset_id)
        
        # Проверяем, есть ли транзакции с этим активом
        if asset.transactions.first():
            flash('Нельзя удалить актив, так как есть связанные транзакции!', 'danger')
            return redirect(url_for('assets_list'))
        
        db.session.delete(asset)
        db.session.commit()
        
        flash('Актив успешно удален!', 'success')
        return redirect(url_for('assets_list'))
    
    # Analytics routes
    @app.route('/analytics')
    @login_required
    def analytics_dashboard():
        current_user = get_current_user()
        portfolios = Portfolio.query.filter_by(user_id=current_user.id).all()
        
        portfolio_summaries = []
        total_value_all = 0
        
        for portfolio in portfolios:
            positions = portfolio.positions.all()
            tickers = [p.asset.ticker for p in positions if p.asset]
            current_prices = PricingService.get_current_prices(tickers)
            summary = AnalyticsService.get_portfolio_summary(portfolio.id, current_prices)
            
            portfolio_summaries.append({
                'id': portfolio.id,
                'name': portfolio.name,
                'value': summary['total_value'],
                'pnl': summary['total_unrealized_pnl'],
                'pnl_pct': summary['total_return_pct']
            })
            total_value_all += summary['total_value']
        
        return render_template('analytics/dashboard.html',
                             portfolios=portfolio_summaries,
                             total_value=total_value_all,
                             current_user=current_user)
    
    # Debug route
    @app.route('/debug/cookie')
    def debug_cookie():
        token = request.cookies.get('access_token')
        if token:
            try:
                from flask_jwt_extended import decode_token
                decoded = decode_token(token)
                user_id = decoded['sub']
                return f"""
                <h2>Cookie Debug Info</h2>
                <p>Token found: {token[:50]}...</p>
                <p>Decoded user_id: {user_id} (type: {type(user_id)})</p>
                <p>Token valid: Yes</p>
                <p><a href='/portfolios'>Перейти к портфелям</a></p>
                """
            except Exception as e:
                return f"""
                <h2>Cookie Debug Info</h2>
                <p>Token found but invalid: {str(e)}</p>
                """
        return "<h2>No token found in cookies</h2>"
    
    # app/routes.py - добавьте новый маршрут для расчета комиссии

    @app.route('/api/calculate-fee', methods=['POST'])
    @login_required
    def calculate_fee():
        """API для расчета комиссии на основе брокера, биржи и суммы сделки"""
        data = request.get_json()
        
        broker_id = data.get('broker_id')
        exchange_name = data.get('exchange')
        amount = float(data.get('amount', 0))
        
        # Получаем брокера
        broker = Broker.query.get(broker_id) if broker_id else None
        
        if not broker or not broker.commission_fee:
            return jsonify({'fee': 0, 'formula': 'Комиссия не установлена'})
        
        commission_percent = float(broker.commission_fee)
        base_fee = amount * commission_percent / 100
        
        # Логика расчета в зависимости от биржи и брокера
        if exchange_name in ['KASE', 'AIX']:
            # Для бирж KASE и AIX
            fee = base_fee
            formula = f"{amount} × {commission_percent}% / 100 = {fee:.2f}"
        else:
            # Для остальных бирж учитываем брокера
            if broker.name == 'Freedom Broker':
                fee = base_fee + 1.2
                formula = f"({amount} × {commission_percent}% / 100) + 1.2 = {fee:.2f}"
            elif broker.name in ['Alatau City Invest', 'Halyk Invest']:
                fee = base_fee + 7.5
                formula = f"({amount} × {commission_percent}% / 100) + 7.5 = {fee:.2f}"
            else:
                fee = base_fee
                formula = f"{amount} × {commission_percent}% / 100 = {fee:.2f}"
        
        return jsonify({
            'fee': round(fee, 2),
            'formula': formula,
            'commission_percent': commission_percent
        })