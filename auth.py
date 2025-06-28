import hashlib
import logging
from functools import wraps
from flask import session, redirect, url_for, flash
from config import UserConfig

class AuthManager:
    """Kimlik doğrulama yönetim sınıfı"""
    
    def __init__(self):
        self.admin_users = UserConfig.ADMIN_USERS
    
    def verify_user(self, username, password):
        """Kullanıcı doğrulama"""
        user = self.admin_users.get(username)
        if user:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if password_hash == user['password_hash']:
                return user
        return None
    
    def login_user(self, username, user_data, remember=False):
        """Kullanıcıyı sisteme giriş yaptır"""
        from datetime import datetime
        
        session.permanent = bool(remember)
        session['user_id'] = username
        session['user_name'] = user_data['name']
        session['user_role'] = user_data['role']
        session['login_time'] = datetime.now().isoformat()
        
        logging.info(f"Başarılı giriş: {username}")
        return True
    
    def logout_user(self):
        """Kullanıcıyı sistemden çıkış yaptır"""
        username = session.get('user_id', 'Bilinmeyen')
        session.clear()
        logging.info(f"Çıkış yapıldı: {username}")
        return username
    
    def is_logged_in(self):
        """Kullanıcının giriş yapıp yapmadığını kontrol et"""
        return 'user_id' in session
    
    def is_admin(self):
        """Kullanıcının admin olup olmadığını kontrol et"""
        if not self.is_logged_in():
            return False
        
        user = self.admin_users.get(session['user_id'])
        return user and user['role'] == 'admin'
    
    def get_current_user(self):
        """Mevcut kullanıcı bilgilerini getir"""
        if not self.is_logged_in():
            return None
        
        return {
            'user_id': session.get('user_id'),
            'user_name': session.get('user_name'),
            'user_role': session.get('user_role'),
            'login_time': session.get('login_time')
        }


# Decorator fonksiyonları
def login_required(f):
    """Giriş gerekli decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Bu sayfaya erişmek için giriş yapmalısınız.', 'error')
            return redirect(url_for('auth_bp.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Admin yetkisi gerekli decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Bu sayfaya erişmek için giriş yapmalısınız.', 'error')
            return redirect(url_for('auth_bp.login'))
        
        user = UserConfig.ADMIN_USERS.get(session['user_id'])
        if not user or user['role'] != 'admin':
            flash('Bu sayfaya erişim yetkiniz yok.', 'error')
            return redirect(url_for('main_bp.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# Global auth instance
auth = AuthManager()