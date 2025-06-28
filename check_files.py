#!/usr/bin/env python3
"""
Dosya kontrol scripti - Hangi dosyaların eksik olduğunu gösterir
"""

import os

def check_files():
    """Gerekli dosyaları kontrol et"""
    required_files = [
        'config.py',
        'database.py', 
        'auth.py',
        'api_utils.py',
        'requirements.txt',
        'routes/__init__.py',
        'routes/auth.py',
        'routes/main.py',
        'routes/api.py',
        'routes/debug.py',
        'routes/admin.py'
    ]
    
    missing_files = []
    existing_files = []
    
    print("🔍 Dosya kontrol ediliyor...")
    print("=" * 50)
    
    for file_path in required_files:
        if os.path.exists(file_path):
            existing_files.append(file_path)
            print(f"✅ {file_path}")
        else:
            missing_files.append(file_path)
            print(f"❌ {file_path}")
    
    print("=" * 50)
    print(f"📊 Özet: {len(existing_files)} mevcut, {len(missing_files)} eksik")
    
    if missing_files:
        print("\n🚨 Eksik dosyalar:")
        for file in missing_files:
            print(f"   - {file}")
        
        print("\n💡 Çözüm:")
        print("1. Aşağıdaki dosyaları oluşturun")
        print("2. Her dosyanın içeriğini ilgili artifact'tan kopyalayın")
        return False
    else:
        print("\n🎉 Tüm dosyalar mevcut!")
        return True

def create_missing_directories():
    """Eksik klasörleri oluştur"""
    directories = ['routes', 'templates', 'static', 'logs']
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"📁 Klasör oluşturuldu: {directory}")

if __name__ == '__main__':
    create_missing_directories()
    check_files()