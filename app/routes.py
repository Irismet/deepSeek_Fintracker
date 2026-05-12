# app/routes.py
from decimal import Decimal
from venv import logger

from flask import jsonify, render_template, request, flash, redirect, make_response, url_for, session
from flask_jwt_extended import get_jwt_identity, jwt_required
from app.extensions import db
from app.models.broker import Broker
from app.models.currency_rate import CurrencyRate
from app.models.exchange import Exchange
from app.models.price_cache import PriceCache
from app.models.tax_event import TaxEvent
from app.models.user import User
from app.models.portfolio import Portfolio
from app.models.asset import Asset
from app.models.transaction import Transaction
from app.models.closed_positions import ClosedPosition

from app.services.currency_service import CurrencyService
from app.services.price_cache_service import price_cache_service
from app.services.pricing_service import PricingService
from app.services.analytics_service import AnalyticsService
from functools import wraps
from datetime import datetime
import logging
# app/routes.py - добавьте в начало файла
from flask import session

from app.services.split_service import SplitService

def set_current_portfolio(portfolio_id):
    """Сохраняет ID текущего портфеля в сессии"""
    session['current_portfolio_id'] = portfolio_id

def get_current_portfolio_id():
    """Получает ID текущего портфеля из сессии"""
    return session.get('current_portfolio_id')

def clear_current_portfolio():
    """Очищает текущий портфель из сессии"""
    session.pop('current_portfolio_id', None)

#logging.basicConfig(level=logging.DEBUG)

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
    
    # app/routes.py - добавьте или обновите маршруты
    @app.route('/auth/register-page', methods=['GET', 'POST'])  # изменено с '/auth/register'
    def register_page():
        """HTML страница регистрации"""
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            portfolio_type = request.form.get('portfolio_type', 'moderate')
            
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
            
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                portfolio_type=portfolio_type
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            flash('Регистрация успешна! Теперь войдите в систему', 'success')
            return redirect(url_for('login_page'))
        
        return render_template('auth/register.html')

    @app.route('/auth/login-page', methods=['GET', 'POST'])  # изменено с '/auth/login'
    def login_page():
        """HTML страница входа"""
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            
            user = User.query.filter_by(email=email).first()
            
            if user and user.check_password(password):
                if not user.is_active:
                    flash('Аккаунт деактивирован. Обратитесь к администратору.', 'danger')
                    return render_template('auth/login.html')
                
                from flask_jwt_extended import create_access_token
                access_token = create_access_token(identity=str(user.id))
                
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                response = make_response(redirect(url_for('portfolios_list')))
                response.set_cookie('access_token', access_token, httponly=False, max_age=86400, path='/', samesite='Lax')
                
                flash(f'Добро пожаловать, {user.get_full_name()}!', 'success')
                return response
            else:
                flash('Неверный email или пароль', 'danger')
        
        return render_template('auth/login.html')

    @app.route('/auth/forgot-password-page', methods=['GET', 'POST'])  # изменено
    def forgot_password_page():
        """Запрос на восстановление пароля"""
        if request.method == 'POST':
            email = request.form.get('email')
            user = User.query.filter_by(email=email).first()
            
            if user:
                reset_token = user.generate_reset_token()
                db.session.commit()
                
                from app.services.email_service import EmailService
                success = EmailService.send_reset_password_email(
                    email, 
                    reset_token, 
                    user.get_full_name()
                )
                
                if success:
                    flash('Инструкции по восстановлению пароля отправлены на ваш email', 'success')
                else:
                    flash('Не удалось отправить email. Попробуйте позже.', 'danger')
            else:
                flash('Если аккаунт существует, инструкции по восстановлению отправлены на email', 'success')
            
            return redirect(url_for('login_page'))
        
        return render_template('auth/forgot_password.html')

    @app.route('/auth/reset-password-page/<token>', methods=['GET', 'POST'])  # изменено
    def reset_password_page(token):
        """Установка нового пароля"""
        user = User.query.filter_by(reset_token=token).first()
        
        if not user or not user.verify_reset_token(token):
            flash('Ссылка для восстановления пароля недействительна или истекла', 'danger')
            return redirect(url_for('login_page'))
        
        if request.method == 'POST':
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            if not password or len(password) < 6:
                flash('Пароль должен содержать минимум 6 символов', 'danger')
                return render_template('auth/reset_password.html', token=token)
            
            if password != confirm_password:
                flash('Пароли не совпадают', 'danger')
                return render_template('auth/reset_password.html', token=token)
            
            user.set_password(password)
            user.clear_reset_token()
            db.session.commit()
            
            flash('Пароль успешно изменен! Теперь вы можете войти.', 'success')
            return redirect(url_for('login_page'))
        
        return render_template('auth/reset_password.html', token=token)

    @app.route('/auth/logout-page')  # изменено с '/auth/logout'
    def logout_page():
        """Выход из системы"""
        response = make_response(redirect(url_for('home')))
        response.delete_cookie('access_token', path='/')
        flash('Вы вышли из системы', 'info')
        return response
    
    # app/routes.py - добавьте этот маршрут

    @app.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile_html():
        """Профиль пользователя"""
        current_user = get_current_user()
        
        if request.method == 'POST':
            # Обновляем личные данные
            current_user.first_name = request.form.get('first_name')
            current_user.last_name = request.form.get('last_name')
            current_user.email = request.form.get('email')
            current_user.portfolio_type = request.form.get('portfolio_type')
            current_user.notes = request.form.get('notes')
            
            # Смена пароля
            new_password = request.form.get('new_password')
            if new_password and new_password.strip():
                old_password = request.form.get('old_password')
                if current_user.check_password(old_password):
                    if len(new_password) >= 6:
                        current_user.set_password(new_password)
                        flash('Пароль успешно изменен!', 'success')
                    else:
                        flash('Новый пароль должен содержать минимум 6 символов', 'danger')
                        return redirect(url_for('profile_html'))
                else:
                    flash('Неверный старый пароль', 'danger')
                    return redirect(url_for('profile_html'))
            
            db.session.commit()
            flash('Профиль обновлен!', 'success')
            return redirect(url_for('profile_html'))
        
        return render_template('auth/profile.html', user=current_user, current_user=current_user)
    
    @app.route('/portfolios')
    @login_required
    def portfolios_list():
        """Список портфелей - очищаем текущий портфель"""
        current_user = get_current_user()
        portfolios = Portfolio.query.filter_by(user_id=current_user.id).all()
    
        # Очищаем сохраненный портфель, так как мы на странице списка
        clear_current_portfolio()
        
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
    
   # В app/routes.py обновите portfolios_detail_html

    @app.route('/portfolios/<int:portfolio_id>')
    @login_required
    def portfolios_detail_html(portfolio_id):
        current_user = get_current_user()
        portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=current_user.id).first_or_404()
        
        # Сохраняем текущий портфель в сессии
        set_current_portfolio(portfolio_id)
        
        # Получаем валюту портфеля
        portfolio_currency = portfolio.currency
        
        # Получаем аналитику с учетом валюты
        from app.services.analytics_service import AnalyticsService
        summary = AnalyticsService.get_portfolio_summary(portfolio_id, portfolio_currency, use_cache=True)
        
        # Получаем закрытые позиции
        from app.models.closed_positions import ClosedPosition
        closed_positions = ClosedPosition.query.filter_by(portfolio_id=portfolio_id).all()
        
        # Формируем данные для закрытых позиций
        closed_positions_data = []
        total_realized_from_closed = 0
        total_dividends_from_closed = 0
        
        for closed in closed_positions:
            asset = closed.asset
            ticker = asset.ticker if asset else 'Unknown'
            name = asset.name if asset else 'Unknown'
            asset_currency = asset.currency if asset else 'USD'
            
            # Конвертируем в валюту портфеля
            from app.services.currency_service import CurrencyService
            realized_pnl_converted = CurrencyService.convert(
                closed.realized_pnl, 
                asset_currency, 
                portfolio_currency
            )
            
            dividends_converted = CurrencyService.convert(
                closed.total_dividends, 
                asset_currency, 
                portfolio_currency
            )
            
            total_realized_from_closed += float(realized_pnl_converted)
            total_dividends_from_closed += float(dividends_converted)
            
            closed_positions_data.append({
                'asset_id': closed.asset_id,
                'ticker': ticker,
                'name': name,
                'asset_type': asset.asset_type if asset else 'Unknown',
                'total_quantity': float(closed.total_quantity),
                'avg_buy_price': float(closed.total_buy_cost / closed.total_quantity) if closed.total_quantity > 0 else 0,
                'avg_buy_currency': asset_currency,
                'realized_pnl': float(realized_pnl_converted),
                'dividends': float(dividends_converted),
                'total_pnl': float(realized_pnl_converted + dividends_converted),
                'return_percentage': float(closed.return_percentage),
                'total_return_percentage': float(closed.total_return_percentage),
                'first_buy_date': closed.first_buy_date.strftime('%Y-%m-%d') if closed.first_buy_date else '-',
                'last_sell_date': closed.last_sell_date.strftime('%Y-%m-%d') if closed.last_sell_date else '-'
            })
        
        # Получаем время последнего обновления цен
        last_price_update = None
        positions = portfolio.positions.all()
        if positions:
            first_asset = positions[0].asset
            if first_asset:
                from app.models.price_cache import PriceCache
                cache_entry = PriceCache.query.filter_by(asset_id=first_asset.id).first()
                if cache_entry:
                    last_price_update = cache_entry.last_update.strftime('%Y-%m-%d %H:%M:%S')
        
        portfolio_data = {
            'id': portfolio.id,
            'name': portfolio.name,
            'currency': portfolio_currency,
            'created_at': portfolio.created_at,
            'total_value': summary['total_value'],
            'total_cost': summary['total_cost'],
            'total_dividends': summary.get('total_dividends', 0),
            'total_realized_pnl': summary.get('total_realized_pnl', 0),
            'total_unrealized_pnl': summary['total_unrealized_pnl'],
            'total_pnl': summary.get('total_pnl', summary['total_unrealized_pnl']),
            'total_return_pct': summary['total_return_pct'],
            'positions': summary['positions'],
            'closed_positions': closed_positions_data,
            'last_price_update': last_price_update
        }
        
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
        
        # Сохраняем портфель в сессии если передан явно
        if portfolio_id:
            set_current_portfolio(portfolio_id)
    
        # Получаем список всех активов для выпадающего списка
        assets = Asset.query.order_by(Asset.ticker).all()
        
        # Получаем список брокеров
        brokers = Broker.query.filter_by(is_active=True).order_by(Broker.name).all()
        
        # Получаем список бирж
        exchanges = Exchange.query.filter_by(is_active=True).order_by(Exchange.name).all()
        
        # Если передан asset_id в параметрах, выбираем его
        pre_selected_asset_id = request.args.get('asset_id', type=int)
        
        return render_template('transactions/create.html', 
                            portfolio_id=portfolio_id,
                            assets=assets,
                            brokers=brokers,
                            exchanges=exchanges,
                            pre_selected_asset_id=pre_selected_asset_id,
                            current_user=current_user)
    
    @app.route('/api/transactions/<int:transaction_id>', methods=['GET'])
    @jwt_required()
    def get_transaction(transaction_id):
        """Получение данных одной транзакции для API"""
        user_id = get_jwt_identity()
        if isinstance(user_id, str):
            user_id = int(user_id)
        
        transaction = Transaction.query.get_or_404(transaction_id)
        
        if transaction.portfolio.user_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Добавляем название биржи и брокера
        result = transaction.to_dict()
        result['exchange_name'] = transaction.exchange_ref.name if transaction.exchange_ref else None
        result['broker_name'] = transaction.broker_ref.name if transaction.broker_ref else None
        
        return jsonify(result), 200
    
    @app.route('/transactions/<int:transaction_id>/edit', methods=['GET', 'POST'])
    @login_required
    def transaction_edit_html(transaction_id):
        """Редактирование транзакции"""
        current_user = get_current_user()
        transaction = Transaction.query.get_or_404(transaction_id)
        
        # Проверяем права доступа
        if transaction.portfolio.user_id != current_user.id:
            flash('Доступ запрещен!', 'danger')
            return redirect(url_for('portfolios_list'))
        
        # Получаем списки для выпадающих меню
        assets = Asset.query.order_by(Asset.ticker).all()
        brokers = Broker.query.filter_by(is_active=True).order_by(Broker.name).all()
        exchanges = Exchange.query.filter_by(is_active=True).order_by(Exchange.name).all()
        
        # Получаем налоговые события для этой транзакции (если есть)
        tax_events = TaxEvent.query.filter_by(transaction_id=transaction_id).all()
        us_tax = 0
        local_tax = 0
        
        for tax in tax_events:
            if tax.tax_type == 'withholding_us':
                us_tax = float(tax.tax_amount)
            elif tax.tax_type == 'local_dividend':
                local_tax = float(tax.tax_amount)
        
        if request.method == 'POST':
            try:
                # Обновляем основные поля транзакции
                transaction.tx_type = request.form.get('tx_type')
                transaction.quantity = Decimal(str(request.form.get('quantity')))
                transaction.price = Decimal(str(request.form.get('price')))
                transaction.fee = Decimal(str(request.form.get('fee', 0)))
                transaction.tx_currency = request.form.get('tx_currency')
                transaction.tx_date = datetime.strptime(request.form.get('tx_date'), '%Y-%m-%dT%H:%M')
                transaction.broker_id = request.form.get('broker_id') or None
                transaction.notes = request.form.get('notes')
                
                # Обновляем биржу
                exchange_name = request.form.get('exchange')
                if exchange_name:
                    exchange = Exchange.query.filter_by(name=exchange_name).first()
                    transaction.exchange_id = exchange.id if exchange else None
                else:
                    transaction.exchange_id = None
                
                # Обновляем актив
                asset_id = request.form.get('asset_id')
                if asset_id:
                    transaction.asset_id = int(asset_id)
                else:
                    transaction.asset_id = None
                
                db.session.commit()
                
                # Если это дивиденды - обновляем налоговые события
                if transaction.tx_type == 'dividend' and transaction.asset_id:
                    # Удаляем старые налоговые события
                    TaxEvent.query.filter_by(transaction_id=transaction_id).delete()
                    
                    # Рассчитываем налоги заново
                    gross_amount = transaction.quantity * transaction.price
                    asset = transaction.asset
                    exchange_name = exchange.name if exchange else (asset.exchange.name if asset.exchange else '')
                    isin = asset.isin or ''
                    
                    # Определяем ставки налогов
                    us_tax_rate = 0
                    local_tax_rate = 0
                    
                    if exchange_name in ['KASE', 'AIX']:
                        if asset.asset_type in ['etf', 'stock']:
                            if isin.startswith('KZ'):
                                us_tax_rate = 0
                                local_tax_rate = 5
                            elif isin.startswith('US'):
                                us_tax_rate = 15
                                local_tax_rate = 10
                        elif asset.asset_type in ['bond']:
                                us_tax_rate = 0
                                local_tax_rate = 0
                    else:
                        if isin.startswith('US'):
                            us_tax_rate = 15
                            local_tax_rate = 10
                        else:
                            us_tax_rate = 15
                            local_tax_rate = 10
                    
                    # Создаем налоговые события
                    if us_tax_rate > 0:
                        us_tax_amount = gross_amount * Decimal(str(us_tax_rate)) / 100
                        tax_event_us = TaxEvent(
                            portfolio_id=transaction.portfolio_id,
                            asset_id=transaction.asset_id,
                            transaction_id=transaction.id,
                            tax_type='withholding_us',
                            tax_rate=us_tax_rate,
                            taxable_amount=gross_amount,
                            tax_amount=us_tax_amount,
                            currency=transaction.tx_currency,
                            tax_date=transaction.tx_date,
                            notes=f'Налог у источника в США ({us_tax_rate}%) на дивиденды по {asset.ticker}'
                        )
                        db.session.add(tax_event_us)
                    
                    if local_tax_rate > 0:
                        local_tax_amount = gross_amount * Decimal(str(local_tax_rate)) / 100
                        tax_event_local = TaxEvent(
                            portfolio_id=transaction.portfolio_id,
                            asset_id=transaction.asset_id,
                            transaction_id=transaction.id,
                            tax_type='local_dividend',
                            tax_rate=local_tax_rate,
                            taxable_amount=gross_amount,
                            tax_amount=local_tax_amount,
                            currency=transaction.tx_currency,
                            tax_date=transaction.tx_date,
                            notes=f'Местный налог ({local_tax_rate}%) на дивиденды по {asset.ticker}'
                        )
                        db.session.add(tax_event_local)
                    
                    db.session.commit()
                
                # Пересчитываем позиции портфеля
                from app.services.position_service import PositionService
                PositionService.recalc_portfolio_positions(transaction.portfolio_id)
                
                flash('Транзакция успешно обновлена!', 'success')
                return redirect(url_for('portfolios_detail_html', portfolio_id=transaction.portfolio_id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка при сохранении: {str(e)}', 'danger')
        
        return render_template('transactions/edit.html', 
                            transaction=transaction,
                            portfolio_id=transaction.portfolio_id,
                            assets=assets,
                            brokers=brokers,
                            exchanges=exchanges,
                            us_tax=us_tax,
                            local_tax=local_tax,
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
        
        # Используем текущий портфель из сессии
        portfolio_id = get_current_portfolio_id()
        
        # Если нет текущего портфеля, берем первый
        if not portfolio_id:
            first_portfolio = Portfolio.query.filter_by(user_id=current_user.id).first()
            portfolio_id = first_portfolio.id if first_portfolio else None
        
        return render_template('assets/list.html', assets=assets, current_user=current_user, portfolio_id=portfolio_id)
    
    @app.route('/assets/create', methods=['GET', 'POST'])
    @login_required
    def asset_create_html():
        current_user = get_current_user()
        
        if request.method == 'POST':
            ticker = request.form.get('ticker').upper()
            name = request.form.get('name')
            asset_type = request.form.get('asset_type')
            currency = request.form.get('currency')
            isin = request.form.get('isin') or None
            # Поля для облигаций
            face_value = request.form.get('face_value') or None
            coupon_rate = request.form.get('coupon_rate') or None
            maturity_date = request.form.get('maturity_date') or None
            
            if face_value:
                face_value = Decimal(face_value)
            if coupon_rate:
                coupon_rate = Decimal(coupon_rate)
            if maturity_date:
                maturity_date = datetime.strptime(maturity_date, '%Y-%m-%d').date()
            
            existing = Asset.query.filter_by(ticker=ticker).first()
            if existing:
                flash('Актив с таким тикером уже существует!', 'danger')
                return render_template('assets/create.html', current_user=current_user)
            
            asset = Asset(
                ticker=ticker,
                name=name,
                asset_type=asset_type,
                currency=currency,
                isin=isin,
                face_value=face_value,
                coupon_rate=coupon_rate,
                maturity_date=maturity_date
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
        
        # Используем текущий портфель из сессии
        portfolio_id = get_current_portfolio_id()
    
        # Если нет текущего портфеля, берем первый
        if not portfolio_id:
            first_portfolio = Portfolio.query.filter_by(user_id=current_user.id).first()
            portfolio_id = first_portfolio.id if first_portfolio else None
        
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
                            portfolio_id=portfolio_id,
                            current_user=current_user)
    
    @app.route('/assets/<int:asset_id>/edit', methods=['GET', 'POST'])
    @login_required
    def asset_edit_html(asset_id):
        """Редактирование актива"""
        current_user = get_current_user()
        asset = Asset.query.get_or_404(asset_id)
        
        if request.method == 'POST':
            asset.ticker = request.form.get('ticker').upper()
            asset.isin = request.form.get('isin') or None
            asset.name = request.form.get('name')
            asset.asset_type = request.form.get('asset_type')
            asset.currency = request.form.get('currency')
            
            # Поля для облигаций
            face_value = request.form.get('face_value')
            coupon_rate = request.form.get('coupon_rate')
            maturity_date = request.form.get('maturity_date')
            
            if face_value and face_value.strip():
                asset.face_value = Decimal(face_value)
            else:
                asset.face_value = None
                
            if coupon_rate and coupon_rate.strip():
                asset.coupon_rate = Decimal(coupon_rate)
            else:
                asset.coupon_rate = None
                
            if maturity_date and maturity_date.strip():
                asset.maturity_date = datetime.strptime(maturity_date, '%Y-%m-%d').date()
            else:
                asset.maturity_date = None
            
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
        
        # Получаем ID портфеля: из параметра URL или из сессии
        selected_portfolio_id = request.args.get('portfolio_id', type=int)
    
        # Если нет в URL, берем из сессии
        if not selected_portfolio_id:
            selected_portfolio_id = get_current_portfolio_id()

         # Получаем все портфели пользователя
        all_portfolios = Portfolio.query.filter_by(user_id=current_user.id).all()
        
        # Если портфель не выбран, показываем все
        if selected_portfolio_id:
            selected_portfolio = Portfolio.query.filter_by(
                id=selected_portfolio_id, 
                user_id=current_user.id
            ).first()
            if not selected_portfolio:
                selected_portfolio_id = None
                selected_portfolio = None
        else:
            selected_portfolio = None
        
        portfolio_summaries = []
        total_value_all = 0
        
        for portfolio in portfolios:
            # Если выбран конкретный портфель, показываем только его
            if selected_portfolio and portfolio.id != selected_portfolio.id:
                continue
                
            positions = portfolio.positions.all()
            tickers = [p.asset.ticker for p in positions if p.asset]
            current_prices = price_cache_service.get_current_prices(tickers)
            summary = AnalyticsService.get_portfolio_summary(portfolio.id, portfolio.currency, use_cache=True)
            
            portfolio_summaries.append({
                'id': portfolio.id,
                'name': portfolio.name,
                'currency': portfolio.currency,
                'value': summary['total_value'],
                'pnl': summary['total_unrealized_pnl'],
                'pnl_pct': summary['total_return_pct'],
                'created_at': portfolio.created_at.strftime('%Y-%m-%d') if portfolio.created_at else None
            })
            total_value_all += summary['total_value']
        
        return render_template('analytics/dashboard.html',
                            portfolios=portfolio_summaries,
                            total_value=total_value_all,
                            selected_portfolio=selected_portfolio,
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
    
    @app.route('/api/currency-rates')
    @login_required
    def get_currency_rates():
        """API для получения курсов валют"""
        rates = CurrencyRate.query.order_by(CurrencyRate.rate_date.desc()).limit(100).all()
        return jsonify([r.to_dict() for r in rates])

    @app.route('/api/currency-rates/update', methods=['POST'])
    @login_required
    def update_currency_rates():
        """Обновление курсов валют (можно вызывать из фоновой задачи)"""
        from app.services.currency_service import CurrencyService
        
        # Здесь можно добавить загрузку курсов из внешнего API
        # Например, из Центробанка или Fixer.io
        
        CurrencyService.clear_cache()
        return jsonify({'message': 'Currency rates cache cleared'})
    

    # Добавьте в app/routes.py

    @app.route('/admin/splits/apply', methods=['GET', 'POST'])
    @login_required
    def apply_split_admin():
        """Применение сплита к активу"""
        current_user = get_current_user()
        if current_user.email not in ['iriska_4@bk.ru']:
            flash('Доступ запрещен', 'danger')
            return redirect(url_for('portfolios_list'))
        
        if request.method == 'POST':
            asset_id = request.form.get('asset_id')
            old_quantity = Decimal(request.form.get('old_quantity'))
            new_quantity = Decimal(request.form.get('new_quantity'))
            split_date = datetime.strptime(request.form.get('split_date'), '%Y-%m-%d').date()
            split_type = request.form.get('split_type', 'split')
            
            try:
                result = SplitService.apply_split(asset_id, old_quantity, new_quantity, split_date, split_type)
                flash(f"Сплит успешно применен: {result['ticker']} x{result['ratio']}", 'success')
            except Exception as e:
                flash(f"Ошибка: {e}", 'danger')
            
            return redirect(url_for('apply_split_admin'))
        
        assets = Asset.query.filter(Asset.asset_type.in_(['stock', 'etf'])).all()
        return render_template('admin/apply_split.html', assets=assets, current_user=current_user)

    @app.route('/admin/splits/history/<int:asset_id>')
    @login_required
    def split_history(asset_id):
        """История сплитов актива"""
        splits = SplitService.get_split_history(asset_id)
        return jsonify(splits)