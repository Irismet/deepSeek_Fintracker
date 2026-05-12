# app/decorators.py
from functools import wraps
from flask import flash, redirect, url_for
from flask_jwt_extended import get_jwt_identity
from app.models.user import User

def admin_required(f):
    """Декоратор для проверки прав администратора"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request
        from app.routes import get_current_user
        
        current_user = get_current_user()
        if not current_user or not current_user.is_admin:
            flash('Доступ запрещен. Требуются права администратора.', 'danger')
            return redirect(url_for('portfolios_list'))
        return f(*args, **kwargs)
    return decorated_function