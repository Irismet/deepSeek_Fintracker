# run_with_web.py
from datetime import timedelta

from flask import jsonify, redirect, request
from flask_jwt_extended import JWTManager, decode_token

from app import create_app
from app.routes import register_routes

app = create_app('development')

app = create_app('development')

# Настройка JWT для работы с cookies
app.config['JWT_SECRET_KEY'] = 'jwt-secret-key-change-in-production'
app.config['JWT_TOKEN_LOCATION'] = ['cookies', 'headers']
app.config['JWT_COOKIE_SECURE'] = False  # True только для HTTPS
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)  # 24 часа
app.config['JWT_COOKIE_SAMESITE'] = 'Lax'

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

# Инициализируем JWT
jwt = JWTManager(app)


# Регистрируем HTML маршруты
register_routes(app)

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

if __name__ == '__main__':
    print("=" * 50)
    print("Investment Tracker запущен!")
    print("Доступные страницы:")
    print("  - Главная: http://localhost:5000/")
    print("  - Регистрация: http://localhost:5000/auth/register")
    print("  - Вход: http://localhost:5000/auth/login")
    print("  - Портфели: http://localhost:5000/portfolios")
    print("  - Debug token: http://localhost:5000/debug/check-token")
    print("  - Manual login (user_id=1): http://localhost:5000/debug/manual-login/1")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)