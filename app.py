import sys
import os
from flask import Flask, render_template, redirect, url_for, session, flash, request, jsonify
import logging
from datetime import timedelta
from routes.api2_search import search_domain_with_retry

# Python path'e mevcut dizini ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
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

# API2 Search route'u - Ana app seviyesinde
@app.route('/search-domain', methods=['GET', 'POST'])
def search_domain_route():
    """Global API2 search endpoint"""
    try:
        # GET veya POST'tan domain parametresini al
        if request.method == 'GET':
            domain = request.args.get('domain')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
        else:
            # POST için JSON body'den al
            data = request.get_json() or {}
            domain = data.get('domain')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
        
        # Domain zorunlu parametre kontrolü
        if not domain:
            return jsonify({
                "success": False,
                "error": "Domain parametresi gerekli",
                "example": "/search-domain?domain=example.com"
            }), 400
        
        # API2 search fonksiyonunu çağır
        logging.info(f"Global API2 search: {domain}")
        result = search_domain_with_retry(domain, start_date, end_date)
        
        # Hata kontrolü
        if "error" in result:
            logging.error(f"API2 search error: {result['error']}")
            return jsonify({
                "success": False,
                "error": result["error"],
                "domain": domain
            }), 500
        
        # Başarılı sonuç
        return jsonify({
            "success": True,
            "data": result,
            "domain": domain,
            "endpoint": "global"
        })
        
    except Exception as e:
        logging.error(f"Search domain error: {e}")
        return jsonify({
            "success": False,
            "error": f"Arama sırasında hata: {str(e)}"
        }), 500

def startup_checks():
    """Başlangıç kontrolleri"""
    logging.info("🚀 Lapsus uygulaması başlatılıyor...")
    
    # Veritabanı bağlantı testi
    if db.test_connection():
        logging.info("✅ Veritabanı bağlantısı başarılı")
    else:
        logging.warning("⚠️ Veritabanı bağlantısı başarısız - bazı özellikler çalışmayabilir")
    
    # API2 config kontrolü
    try:
        from config import Config
        api2_url = Config.API2_CONFIG.get('base_url', 'Tanımlı değil')
        logging.info(f"🔗 API2 URL: {api2_url}")
    except Exception as e:
        logging.warning(f"⚠️ API2 config kontrolü başarısız: {e}")
    
    logging.info("🎯 Helix-D sayfası: http://localhost:7071/helix-d")
    logging.info("🔍 Global search: http://localhost:7071/search-domain")

if __name__ == '__main__':
    # Başlangıç kontrolü
    startup_checks()
    
    # Uygulamayı başlat
    app.run(
        debug=Config.FLASK_DEBUG,
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT
    )