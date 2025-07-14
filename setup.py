#!/usr/bin/env python3
"""
Lapsus Flask Uygulaması Kurulum Scripti
Bu script projeyi doğru şekilde kurar ve gerekli dosyaları oluşturur.
"""

import os
import sys

def create_directory_structure():
    """Gerekli klasör yapısını oluştur"""
    directories = [
        'routes',
        'templates',
        'static/css',
        'static/js',
        'static/images',
        'logs'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Klasör oluşturuldu: {directory}")

def create_init_files():
    """__init__.py dosyalarını oluştur"""
    init_files = [
        'routes/__init__.py'
    ]
    
    for init_file in init_files:
        with open(init_file, 'w', encoding='utf-8') as f:
            f.write('# Package initialization\n')
        print(f"✅ Init dosyası oluşturuldu: {init_file}")

def create_env_template():
    """Örnek .env dosyası oluştur"""
    env_content = """# Lapsus Flask Uygulaması - Çevre Değişkenleri
# Production'da bu değerleri gerçek verilerle değiştirin!

# Flask Ayarları
SECRET_KEY=your_secret_key_here_change_in_production
FLASK_DEBUG=False
FLASK_HOST=0.0.0.0
FLASK_PORT=7072

# Veritabanı Ayarları
DB_HOST=192.168.70.70
DB_NAME=lapsusacc
DB_USER=root
DB_PASSWORD=your_password_here
DB_PORT=3306

# API Ayarları
API_BASE_URL=http://192.168.70.71:5000
API_KEY=your_api_key_here
API_TIMEOUT=30
API_MAX_RETRIES=3
"""
    
    with open('.env.example', 'w', encoding='utf-8') as f:
        f.write(env_content)
    print("✅ Örnek .env dosyası oluşturuldu: .env.example")

def check_requirements():
    """requirements.txt dosyasını kontrol et"""
    if os.path.exists('requirements.txt'):
        print("✅ requirements.txt dosyası mevcut")
        print("📦 Bağımlılıkları yüklemek için: pip install -r requirements.txt")
    else:
        print("❌ requirements.txt dosyası bulunamadı!")

def create_run_script():
    """Kolay çalıştırma scripti oluştur"""
    run_content = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lapsus Flask Uygulaması Başlatıcı
"""

import os
import sys

# Mevcut dizini Python path'e ekle
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from app import app, startup_checks
    
    if __name__ == '__main__':
        print("🚀 Lapsus uygulaması başlatılıyor...")
        startup_checks()
        app.run()
        
except ImportError as e:
    print(f"❌ Import hatası: {e}")
    print("Lütfen tüm dosyaların doğru konumda olduğundan emin olun.")
    sys.exit(1)
except Exception as e:
    print(f"❌ Başlatma hatası: {e}")
    sys.exit(1)
"""
    
    with open('run.py', 'w', encoding='utf-8') as f:
        f.write(run_content)
    
    # Unix sistemlerde executable yapma
    if os.name != 'nt':  # Windows değilse
        os.chmod('run.py', 0o755)
    
    print("✅ Çalıştırma scripti oluşturuldu: run.py")

def main():
    """Ana kurulum fonksiyonu"""
    print("🔧 Lapsus Flask Uygulaması Kurulum Scripti")
    print("=" * 50)
    
    # Klasör yapısını oluştur
    create_directory_structure()
    
    # Init dosyalarını oluştur
    create_init_files()
    
    # Env template oluştur
    create_env_template()
    
    # Requirements kontrol
    check_requirements()
    
    # Run script oluştur
    create_run_script()
    
    print("\n" + "=" * 50)
    print("🎉 Kurulum tamamlandı!")
    print("\n📋 Sonraki adımlar:")
    print("1. pip install -r requirements.txt")
    print("2. .env.example dosyasını .env olarak kopyalayın ve düzenleyin")
    print("3. python run.py ile uygulamayı başlatın")
    print("\n🔍 Dosya yapısı:")
    
    # Dosya yapısını göster
    for root, dirs, files in os.walk('.'):
        level = root.replace('.', '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            if not file.startswith('.') and file.endswith('.py'):
                print(f"{subindent}{file}")

if __name__ == '__main__':
    main()