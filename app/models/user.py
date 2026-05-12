# app/models/user.py
from app.extensions import db
from datetime import datetime
from flask_jwt_extended import create_access_token, create_refresh_token
import secrets
import hashlib

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.BigInteger, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    hashed_password = db.Column(db.String(255), nullable=False)
    
    # Личные данные
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)  # Заметки о пользователе
    
    # Портфель
    portfolio_type = db.Column(db.String(20), default='moderate')  # speculative, aggressive, moderate, conservative, other
    
    # Права доступа
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)  # Деактивация пользователя
    
    # Восстановление пароля
    reset_token = db.Column(db.String(64), unique=True, nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    portfolios = db.relationship('Portfolio', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.hashed_password = generate_password_hash(password)
    
    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.hashed_password, password)
    
    def generate_reset_token(self):
        """Генерация токена для восстановления пароля"""
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires = datetime.utcnow() + timedelta(hours=24)
        return self.reset_token
    
    def verify_reset_token(self, token):
        """Проверка токена восстановления"""
        return (self.reset_token == token and 
                self.reset_token_expires and 
                self.reset_token_expires > datetime.utcnow())
    
    def clear_reset_token(self):
        """Очистка токена после использования"""
        self.reset_token = None
        self.reset_token_expires = None
    
    def get_full_name(self):
        """Получение полного имени"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.email.split('@')[0]
    
    def get_tokens(self):
        return {
            'access_token': create_access_token(identity=str(self.id)),
            'refresh_token': create_refresh_token(identity=str(self.id))
        }
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.get_full_name(),
            'portfolio_type': self.portfolio_type,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'notes': self.notes
        }
    
    def __repr__(self):
        return f'<User {self.email}>'

from datetime import timedelta