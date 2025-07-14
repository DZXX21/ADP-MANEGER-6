import os
import secrets
from datetime import timedelta

class Config:
    """Temel konfigürasyon sınıfı"""
    
    # Flask ayarları
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Veritabanı ayarları
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', '192.168.70.70'),
        'database': os.getenv('DB_NAME', 'lapsusacc'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', 'daaqwWdas21as'),
        'charset': 'utf8mb4',
        'port': int(os.getenv('DB_PORT', 3306)),
        'autocommit': True,
        'raise_on_warnings': True
    }
    
    # API ayarları - SEN NE İSTEDİYSEN O!
    API_CONFIG = {
        'base_url': os.getenv('API_BASE_URL', 'http://192.168.70.71:5000'),
        'api_key': os.getenv('API_KEY', 'demo_key_123'),
        'timeout': int(os.getenv('API_TIMEOUT', 300)),
        'max_retries': int(os.getenv('API_MAX_RETRIES', 3))
    }
    
    API2_CONFIG = {
    'base_url': os.getenv('API_BASE_URL', 'https://api2.tahaeryetisozen.com.tr'),  # .com eklendi
    'api_key': os.getenv('API_KEY', 'mysecretkey123'),
    'timeout': int(os.getenv('API_TIMEOUT', 30)),
    'max_retries': int(os.getenv('API_MAX_RETRIES', 3))
    }
    # Flask çalıştırma ayarları
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 7071))


class CategoryConfig:
    """Kategori konfigürasyonları"""
    
    # Kategori çevirileri
    TRANSLATIONS = {
        'government': 'Kamu Kurumları',
        'banks': 'Finansal Kuruluşlar', 
        'popular_turkish': 'Öne Çıkan Türk Siteler',
        'turkish_extensions': 'Türkiye Uzantılı Platformlar',
        'universities': 'Yükseköğretim Kurumları',
        'social_media': 'Sosyal Medya',
        'email_providers': 'E-posta Sağlayıcıları',
        'tech_companies': 'Teknoloji Şirketleri'
    }
    
    # Kategori renkleri
    COLORS = {
        'government': '#1e90ff',
        'banks': '#87ceeb',
        'popular_turkish': '#00bfff',
        'turkish_extensions': '#4682b4',
        'universities': '#5f9ea0',
        'social_media': '#ff6b6b',
        'email_providers': '#4ecdc4',
        'tech_companies': '#45b7d1'
    }
    
    # Kategori ikonları
    ICONS = {
        'government': 'building',
        'banks': 'landmark',
        'popular_turkish': 'star',
        'turkish_extensions': 'globe',
        'universities': 'graduation-cap',
        'social_media': 'users',
        'email_providers': 'mail',
        'tech_companies': 'cpu'
    }
    
    # Kategori sıralama öncelikleri
    ORDER = [
        'government', 'banks', 'popular_turkish', 'turkish_extensions', 
        'universities', 'social_media', 'email_providers', 'tech_companies'
    ]


class UserConfig:
    """Kullanıcı konfigürasyonları"""
    
    import hashlib
    
    # Admin kullanıcılar - PRODUCTION'da veritabanından alınmalı!
    ADMIN_USERS = {
        'admin': {
            'password_hash': hashlib.sha256('admin123'.encode()).hexdigest(),
            'role': 'admin',
            'name': 'Admin User'
        },
        'lapsus': {
            'password_hash': hashlib.sha256('lapsus2025'.encode()).hexdigest(),
            'role': 'admin', 
            'name': 'Lapsus Admin'
        }
    }