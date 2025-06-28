from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import logging
from datetime import datetime
from auth import auth

# Blueprint oluştur
auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Giriş sayfası"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            flash('Kullanıcı adı ve şifre gereklidir.', 'error')
            return render_template('login.html')
        
        user = auth.verify_user(username, password)
        if user:
            auth.login_user(username, user, remember)
            flash(f'Hoş geldiniz, {user["name"]}!', 'success')
            logging.info(f"Başarılı giriş: {username} - {request.remote_addr}")
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main_bp.dashboard'))
        else:
            flash('Geçersiz kullanıcı adı veya şifre.', 'error')
            logging.warning(f"Başarısız giriş denemesi: {username} - {request.remote_addr}")
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """Çıkış"""
    username = auth.logout_user()
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('auth_bp.login'))