import requests
import logging
from config import Config, CategoryConfig

class APIManager:
    """API yönetim sınıfı"""
    
    def __init__(self):
        self.config = Config.API_CONFIG
    
    def make_request(self, endpoint, method='GET', params=None, data=None, retries=0):
        """Güvenli API request helper"""
        try:
            url = f"{self.config['base_url']}{endpoint}"
            headers = {
                'X-API-Key': self.config['api_key'],
                'Content-Type': 'application/json',
                'User-Agent': 'Lapsus-Dashboard/1.0'
            }
            
            logging.info(f"🔄 API çağrısı: {url}")
            
            if method == 'GET':
                response = requests.get(
                    url, 
                    headers=headers, 
                    params=params, 
                    timeout=self.config['timeout']
                )
            elif method == 'POST':
                response = requests.post(
                    url, 
                    headers=headers, 
                    json=data, 
                    timeout=self.config['timeout']
                )
            else:
                raise ValueError(f"Desteklenmeyen HTTP metodu: {method}")
            
            response.raise_for_status()
            logging.info(f"✅ API başarılı: {endpoint} - Status: {response.status_code}")
            return response.json()
            
        except requests.exceptions.Timeout:
            logging.error(f"⏰ API timeout: {endpoint}")
            if retries < self.config['max_retries']:
                logging.info(f"🔄 Yeniden deneniyor ({retries + 1}/{self.config['max_retries']})")
                return self.make_request(endpoint, method, params, data, retries + 1)
            raise Exception("API zaman aşımı - sunucu yanıt vermiyor")
            
        except requests.exceptions.ConnectionError:
            logging.error(f"🔌 API bağlantı hatası: {url}")
            raise Exception("API sunucusuna bağlanılamıyor")
            
        except requests.exceptions.HTTPError as e:
            logging.error(f"❌ API HTTP hatası: {e.response.status_code} - {endpoint}")
            try:
                error_detail = e.response.text
                logging.error(f"API hata detayı: {error_detail}")
            except:
                pass
            
            if e.response.status_code == 401:
                raise Exception("API yetkilendirme hatası")
            elif e.response.status_code == 404:
                raise Exception(f"API endpoint bulunamadı: {endpoint}")
            elif e.response.status_code == 429:
                raise Exception("API rate limit aşıldı")
            else:
                raise Exception(f"API sunucu hatası: {e.response.status_code}")
                
        except Exception as e:
            logging.error(f"💥 API genel hatası: {str(e)}")
            if retries < self.config['max_retries']:
                logging.info(f"🔄 Yeniden deneniyor ({retries + 1}/{self.config['max_retries']})")
                return self.make_request(endpoint, method, params, data, retries + 1)
            raise
    
    def search_accounts(self, query, page=1, limit=20, domain='', region='', source=''):
        """API üzerinden hesap arama"""
        api_params = {
            'q': query,
            'page': page,
            'limit': limit
        }
        
        # Filtreleri ekle
        if domain:
            api_params['domain'] = domain
        if region:
            api_params['region'] = region
        if source:
            api_params['source'] = source
        
        logging.info(f"🔍 API arama: {query} - Parametreler: {api_params}")
        return self.make_request('/api/search', params=api_params)
    
    def get_accounts(self, page=1, limit=10, domain='', region='', source=''):
        """API üzerinden hesap listesi"""
        api_params = {
            'page': page,
            'limit': limit
        }
        
        if domain:
            api_params['domain'] = domain
        if region:
            api_params['region'] = region
        if source:
            api_params['source'] = source
        
        return self.make_request('/api/accounts', params=api_params)
    
    def get_single_account(self, account_id):
        """API üzerinden tekil hesap bilgisi"""
        return self.make_request(f'/api/accounts/{account_id}')
    
    def get_statistics(self):
        """API üzerinden istatistikler"""
        return self.make_request('/api/stats')
    
    def health_check(self):
        """API sağlık kontrolü"""
        return self.make_request('/api/health')


class DataFormatter:
    """Veri formatlama yardımcı sınıfı"""
    
    @staticmethod
    def format_search_results(results, available_columns):
        """Arama sonuçlarını formatla"""
        formatted_results = []
        
        username_columns = ['username', 'user', 'email', 'login', 'user_name', 'account']
        password_columns = ['password', 'pass', 'pwd', 'passwd', 'secret']
        
        for result in results:
            username_value = None
            password_value = None
            
            # Username bulma
            for col in username_columns:
                if col in result and result[col]:
                    username_value = result[col]
                    break
            
            # Password bulma
            for col in password_columns:
                if col in result and result[col]:
                    password_value = result[col]
                    break
            
            formatted_result = {
                'id': result.get('id', 0),
                'domain': result.get('domain', ''),
                'username': username_value or 'N/A',
                'password': password_value or 'N/A',
                'region': result.get('region', 'Unknown'),
                'source': result.get('source', 'TXT'),
                'category': result.get('category', 'uncategorized'),
                'spid': f"SP{1000 + result.get('id', 0)}" if result.get('id', 0) % 3 == 0 else None
            }
            
            # Tarih formatı
            date_value = result.get('fetch_date') or result.get('created_at') or result.get('date_added')
            if date_value:
                formatted_result['date'] = date_value.isoformat() if hasattr(date_value, 'isoformat') else str(date_value)
            else:
                formatted_result['date'] = None
            
            formatted_results.append(formatted_result)
        
        return formatted_results
    
    @staticmethod
    def format_categories_stats(categories, total_count):
        """Kategori istatistiklerini formatla"""
        chart_data = []
        category_dict = {cat['category']: cat['count'] for cat in categories}
        
        # Önce tanımlı sıralamadaki kategorileri ekle
        for cat_key in CategoryConfig.ORDER:
            if cat_key in category_dict:
                count = category_dict[cat_key]
                percentage = round((count / total_count) * 100, 1)
                
                chart_data.append({
                    'category': cat_key,
                    'label': CategoryConfig.TRANSLATIONS.get(cat_key, cat_key.title()),
                    'count': count,
                    'percentage': percentage,
                    'color': CategoryConfig.COLORS.get(cat_key, '#6B7280'),
                    'icon': CategoryConfig.ICONS.get(cat_key, 'folder')
                })
        
        # Sonra tanımlanmamış kategorileri ekle
        for category in categories:
            cat_key = category['category']
            if cat_key not in CategoryConfig.ORDER:
                percentage = round((category['count'] / total_count) * 100, 1)
                chart_data.append({
                    'category': cat_key,
                    'label': CategoryConfig.TRANSLATIONS.get(cat_key, cat_key.title()),
                    'count': category['count'],
                    'percentage': percentage,
                    'color': CategoryConfig.COLORS.get(cat_key, '#6B7280'),
                    'icon': CategoryConfig.ICONS.get(cat_key, 'folder')
                })
        
        return chart_data


# Global instances
api = APIManager()
formatter = DataFormatter()