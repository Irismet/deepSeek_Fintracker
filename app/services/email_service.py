# app/services/email_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import render_template, url_for
import logging

logger = logging.getLogger(__name__)

class EmailService:
    """Сервис для отправки email (настройте под свой SMTP)"""
    
    # Настройки SMTP (замените на свои)
    SMTP_HOST = 'smtp.yandex.ru'  # или smtp.mail.ru, smtp.yandex.ru и т.д.
    SMTP_PORT = 587
    SMTP_USER = 'irismetkhaimov@yandex.kz'
    SMTP_PASSWORD = 'owsvyljsyqcbmfcf'
    FROM_EMAIL = 'irismetkhaimov@yandex.kz'
    FROM_NAME = 'Investment Tracker'
    
    @classmethod
    def send_reset_password_email(cls, to_email, reset_token, user_name=''):
        """Отправка письма для восстановления пароля"""
        
        reset_link = f"{cls.get_base_url()}/auth/reset-password-page/{reset_token}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4facfe; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background-color: #f9f9f9; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #4facfe; 
                          color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Investment Tracker</h2>
                </div>
                <div class="content">
                    <h3>Здравствуйте, {user_name}!</h3>
                    <p>Вы запросили восстановление пароля для вашей учетной записи.</p>
                    <p>Для установки нового пароля нажмите на кнопку ниже:</p>
                    <div style="text-align: center;">
                        <a href="{reset_link}" class="button">Сбросить пароль</a>
                    </div>
                    <p>Если вы не запрашивали восстановление пароля, просто проигнорируйте это письмо.</p>
                    <p>Ссылка действительна в течение 24 часов.</p>
                    <p>Если кнопка не работает, скопируйте ссылку в браузер:<br>
                    <small>{reset_link}</small></p>
                </div>
                <div class="footer">
                    <p>© 2024 Investment Tracker. Все права защищены.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Здравствуйте, {user_name}!
        
        Вы запросили восстановление пароля для вашей учетной записи.
        
        Для установки нового пароля перейдите по ссылке:
        {reset_link}
        
        Если вы не запрашивали восстановление пароля, просто проигнорируйте это письмо.
        
        Ссылка действительна в течение 24 часов.
        """
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = 'Восстановление пароля - Investment Tracker'
            msg['From'] = f"{cls.FROM_NAME} <{cls.FROM_EMAIL}>"
            msg['To'] = to_email
            
            part1 = MIMEText(text_content, 'plain', 'utf-8')
            part2 = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(part1)
            msg.attach(part2)
            
            with smtplib.SMTP(cls.SMTP_HOST, cls.SMTP_PORT) as server:
                server.starttls()
                server.login(cls.SMTP_USER, cls.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Reset password email sent to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    @classmethod
    def get_base_url(cls):
        """Получение базового URL (настройте под свой домен)"""
        from flask import request
        if request:
            return request.host_url.rstrip('/')
        return 'http://localhost:5000'