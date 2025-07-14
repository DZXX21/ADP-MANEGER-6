import requests
from datetime import datetime
from typing import Optional, Dict, Any
from config import Config

# API2 Config'i class'tan al
API2_CONFIG = Config.API2_CONFIG

def search_domain(domain: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[Any, Any]:
    """
    Domain arama işlemi yapar
    
    Args:
        domain: Aranacak domain (örn: app.szutest.com.tr, gmail.com)
        start_date: Başlangıç tarihi (YYYY-MM-DD formatında, opsiyonel)
        end_date: Bitiş tarihi (YYYY-MM-DD formatında, opsiyonel)
    
    Returns:
        API'den dönen response
    """
    
    # Base URL ve endpoint
    url = f"{API2_CONFIG['base_url']}/search"
    
    # Query parametrelerini hazırla
    params = {
        'domain': domain,
        'key': API2_CONFIG['api_key']
    }
    
    # Tarih parametrelerini ekle (varsa)
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date
    
    try:
        # API isteği gönder
        response = requests.get(
            url, 
            params=params, 
            timeout=API2_CONFIG['timeout']
        )
        
        # Status code kontrolü
        response.raise_for_status()
        
        # JSON response'u döndür
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"API isteği sırasında hata: {e}")
        return {"error": str(e)}
    except Exception as e:
        print(f"Beklenmeyen hata: {e}")
        return {"error": str(e)}

def search_domain_with_retry(domain: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[Any, Any]:
    """
    Retry mekanizması ile domain arama
    """
    max_retries = API2_CONFIG['max_retries']
    
    for attempt in range(max_retries):
        try:
            result = search_domain(domain, start_date, end_date)
            
            # Eğer error yoksa başarılı
            if "error" not in result:
                return result
                
            # Son deneme değilse tekrar dene
            if attempt < max_retries - 1:
                print(f"Deneme {attempt + 1} başarısız, tekrar deneniyor...")
                continue
            else:
                return result
                
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Deneme {attempt + 1} başarısız: {e}, tekrar deneniyor...")
                continue
            else:
                return {"error": f"Tüm denemeler başarısız: {e}"}

# Test fonksiyonu - sadece manuel test için
def example_usage():
    """
    API kullanım örnekleri - Manuel test
    """
    print("=== API2 Search Test ===")
    print("Manuel test için bu fonksiyonu çağırın")

# Otomatik test kaldırıldı
if __name__ == "__main__":
    print("API2 Search modülü yüklendi - test için example_usage() çağırın")