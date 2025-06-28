import sys
import os
from flask import Flask, render_template, redirect, url_for, session, flash
import logging
from datetime import timedelta

# Python path'e mevcut dizini ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Konfigürasyon ve modül importları
try:
    from config import Config
    from database import db
    
    # Route blueprint'leri
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.api import api_bp
    from routes.debug import debug_bp
    from routes.admin import admin_bp
except ImportError as e:
    print(f"Import hatası: {e}")
    print("Lütfen tüm dosyaların doğru konumda olduğundan emin olun.")
    sys.exit(1)

def create_app():
    """Flask uygulaması factory fonksiyonu"""
    app = Flask(__name__)
    
    # Konfigürasyon ayarları
    app.secret_key = Config.SECRET_KEY
    app.permanent_session_lifetime = Config.PERMANENT_SESSION_LIFETIME
    
    # Loglama ayarları
    configure_logging()
    
    # Blueprint'leri kaydet
    register_blueprints(app)
    
    # Error handler'ları kaydet
    register_error_handlers(app)
    
    # Context processor'ları kaydet
    register_context_processors(app)
    
    return app

def configure_logging():
    """Loglama konfigürasyonu"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('lapsus.log'),
            logging.StreamHandler()
        ]
    )

def register_blueprints(app):
    """Blueprint'leri kaydet"""
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(debug_bp)
    app.register_blueprint(admin_bp)

def register_error_handlers(app):
    """Error handler'ları kaydet"""
    
    @app.errorhandler(404)
    def not_found(error):
        if 'user_id' in session:
            return render_template('404.html'), 404
        return redirect(url_for('auth_bp.login'))

    @app.errorhandler(500)
    def internal_error(error):
        logging.error(f"Internal server error: {error}")
        return render_template('500.html'), 500

    @app.errorhandler(403)
    def forbidden(error):
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('main_bp.dashboard'))

def register_context_processors(app):
    """Context processor'ları kaydet"""
    
    @app.context_processor
    def inject_user():
        """Template'lere kullanıcı bilgilerini enjekte et"""
        return dict(
            current_user=session.get('user_name', 'Misafir'),
            user_role=session.get('user_role', 'guest'),
            is_logged_in='user_id' in session
        )

# Flask uygulamasını oluştur
app = create_app()

def startup_checks():
    """Başlangıç kontrolleri"""
    logging.info("Lapsus uygulaması başlatılıyor...")
    
    # Veritabanı bağlantı testi
    if db.test_connection():
        logging.info("✅ Veritabanı bağlantısı başarılı")
    else:
        logging.warning("⚠️ Veritabanı bağlantısı başarısız - bazı özellikler çalışmayabilir")

if __name__ == '__main__':
    # Başlangıç kontrolü
    startup_checks()
    
    # Uygulamayı başlat
    app.run(
        debug=Config.FLASK_DEBUG,
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT
    )