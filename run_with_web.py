# run_with_web.py
import atexit

from flask import flash, jsonify, redirect, request
from redis.background import BackgroundScheduler

from app import create_app
from app.routes import login_required, register_routes
from app.services import price_cache_service
from app.services.price_cache_service import price_cache_service
from app import create_app
from app.routes import register_routes
from flask import request, jsonify
from flask_jwt_extended import JWTManager, decode_token
from datetime import datetime, timedelta
import threading
import time
import logging

app = create_app('development')

# Настройка JWT для работы с cookies
app.config['JWT_SECRET_KEY'] = 'jwt-secret-key-change-in-production'
app.config['JWT_TOKEN_LOCATION'] = ['cookies', 'headers']
app.config['JWT_COOKIE_SECURE'] = False  # True только для HTTPS
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)  # 24 часа
app.config['JWT_COOKIE_SAMESITE'] = 'Lax'

# Инициализируем JWT
jwt = JWTManager(app)

# Регистрируем HTML маршруты
register_routes(app)

# Глобальные переменные для фонового обновления
_background_running = False
_background_thread = None

# Настройка планировщика
scheduler = BackgroundScheduler()

# Настройка CSP (отключаем для разработки)
# run_with_web.py - для production
@app.after_request
def set_csp_headers(response):
    csp = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com 'unsafe-inline'; "
        "style-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com 'unsafe-inline'; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self'"
    )
    response.headers['Content-Security-Policy'] = csp
    return response


# Маршрут для проверки токена
@app.route('/debug/check-token')
def debug_check_token():
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "No token found", "cookies": dict(request.cookies)}), 401
    
    try:
        decoded = decode_token(token)
        return jsonify({
            "token_valid": True,
            "user_id": decoded['sub'],
            "token_preview": token[:50] + "...",
            "expires": decoded.get('exp')
        })
    except Exception as e:
        return jsonify({
            "token_valid": False,
            "error": str(e),
            "token_preview": token[:50] + "..."
        }), 401


@app.route('/debug/set-token')
def debug_set_token():
    """Временный маршрут для установки токена вручную"""
    from flask_jwt_extended import create_access_token
    from app.models.user import User
    
    # Берем первого пользователя
    user = User.query.first()
    if not user:
        return "No user found", 404
    
    access_token = create_access_token(identity=str(user.id))
    response = redirect('/transactions/create/1')
    response.set_cookie('access_token', access_token, httponly=False, max_age=86400, path='/')
    return response


@app.route('/debug/set-test-cookie')
def set_test_cookie():
    """Установка тестовой cookie для проверки"""
    response = make_response("Test cookie set. Check browser cookies.")
    response.set_cookie('test_cookie', 'test_value', path='/')
    return response

@app.route('/debug/show-cookies')
def show_cookies():
    """Показывает все cookies"""
    cookies = dict(request.cookies)
    return jsonify({
        'cookies': cookies,
        'has_access_token': 'access_token' in cookies
    })

# Маршрут для ручного входа (на случай проблем с формой)
@app.route('/debug/manual-login/<int:user_id>')
def manual_login(user_id):
    from flask_jwt_extended import create_access_token
    from app.models.user import User
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    access_token = create_access_token(identity=str(user.id))
    response = jsonify({"message": "Login successful", "user_id": user.id})
    response.set_cookie(
        'access_token', 
        access_token, 
        httponly=True, 
        max_age=86400,
        path='/',
        samesite='Lax'
    )
    return response

def background_price_updater():
    """Фоновый поток для обновления цен"""
    global _background_running
    from app.services.price_cache_service import price_cache_service
    
    print("🔄 Background price updater thread started")
    
    with app.app_context():
        while _background_running:
            try:
                print("\n" + "="*50)
                print(f"🔄 Updating prices at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                result = price_cache_service.update_all_prices()
                
                if 'error' in result:
                    print(f"❌ Error: {result['error']}")
                else:
                    print(f"✅ {result['message']}")
                    
                stats = price_cache_service.get_cache_stats()
                print(f"📊 Cache: {stats['fresh_entries']} fresh, {stats['outdated_entries']} outdated")
                
            except Exception as e:
                print(f"❌ Update error: {e}")
                import traceback
                traceback.print_exc()
            
            # Ждем 2 часа (7200 секунд)
            print(f"⏰ Next update in 2 hours...")
            for _ in range(7200):
                if not _background_running:
                    break
                time.sleep(1)
        
        print("🛑 Background price updater thread stopped")

def start_background_updater():
    """Запуск фонового обновления"""
    global _background_running, _background_thread
    
    if not _background_running:
        _background_running = True
        _background_thread = threading.Thread(target=background_price_updater, daemon=True)
        _background_thread.start()
        print("🚀 Background price updater started (updates every 2 hours)")
        return True
    else:
        print("⚠️ Background updater already running")
        return False

def stop_background_updater():
    """Остановка фонового обновления"""
    global _background_running
    
    if _background_running:
        _background_running = False
        print("🛑 Stopping background updater...")
        return True
    else:
        print("⚠️ Background updater is not running")
        return False

# Запускаем фоновое обновление через 10 секунд
def delayed_start():
    """Запуск с задержкой после старта приложения"""
    time.sleep(10)
    start_background_updater()

# Запускаем поток с задержкой
delayed_start_thread = threading.Thread(target=delayed_start, daemon=True)
delayed_start_thread.start()
print("⏰ Background updater will start in 10 seconds")

# Маршруты для управления кэшем
@app.route('/admin/update-prices')
def admin_update_prices():
    """Принудительное обновление всех цен"""
    from app.services.price_cache_service import price_cache_service
    
    try:
        result = price_cache_service.update_all_prices()
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 500
        else:
            return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/cache-stats')
def admin_cache_stats():
    """Статистика кэша"""
    from app.services.price_cache_service import price_cache_service
    from app.routes import get_current_user
    
    # Проверка авторизации (опционально)
    # current_user = get_current_user()
    # if not current_user:
    #     return jsonify({'error': 'Unauthorized'}), 401
    
    stats = price_cache_service.get_cache_stats()
    stats['background_updater_running'] = _background_running
    
    return jsonify(stats)

@app.route('/admin/clear-cache', methods=['POST'])
def admin_clear_cache():
    """Очистка кэша"""
    from app.services.price_cache_service import price_cache_service
    
    try:
        result = price_cache_service.clear_cache()
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 500
        else:
            return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/start-updater')
def admin_start_updater():
    """Запуск фонового обновления"""
    result = start_background_updater()
    return jsonify({'success': result, 'message': 'Background updater started' if result else 'Already running'})

@app.route('/admin/stop-updater')
def admin_stop_updater():
    """Остановка фонового обновления"""
    result = stop_background_updater()
    return jsonify({'success': result, 'message': 'Background updater stopped' if result else 'Not running'})

@app.route('/admin/updater-status')
def admin_updater_status():
    """Статус фонового обновления"""
    return jsonify({
        'running': _background_running,
        'thread_alive': _background_thread.is_alive() if _background_thread else False
    })


@app.route('/admin/recalc-portfolio/<int:portfolio_id>')
@login_required
def admin_recalc_portfolio(portfolio_id):
    """Принудительный пересчет позиций портфеля"""
    from app.services.position_service import PositionService
    from app.models.portfolio import Portfolio
    from app.routes import get_current_user
    
    current_user = get_current_user()
    portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=current_user.id).first_or_404()
    
    try:
        PositionService.recalc_portfolio_positions(portfolio_id)
        flash(f'Позиции портфеля "{portfolio.name}" успешно пересчитаны!', 'success')
    except Exception as e:
        flash(f'Ошибка при пересчете: {e}', 'danger')
        logger.error(f"Recalc error: {e}")
    
    return redirect(url_for('portfolios_detail_html', portfolio_id=portfolio_id))


if __name__ == '__main__':
    print("=" * 70)
    print("🚀 Investment Tracker запущен!")
    print("=" * 70)
    print("📋 Доступные страницы:")
    print("  - Главная: http://localhost:5000/")
    print("  - Регистрация: http://localhost:5000/auth/register")
    print("  - Вход: http://localhost:5000/auth/login")
    print("  - Портфели: http://localhost:5000/portfolios")
    print("  - Аналитика: http://localhost:5000/analytics")
    print("  - Активы: http://localhost:5000/assets")
    print("\n📊 Управление кэшем (Admin API):")
    print("  - Обновить цены: GET /admin/update-prices")
    print("  - Статистика: GET /admin/cache-stats")
    print("  - Очистить кэш: POST /admin/clear-cache")
    print("  - Остановить обновление: GET /admin/stop-updater")
    print("  - Запустить обновление: GET /admin/start-updater")
    print("=" * 70)
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
