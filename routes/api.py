from flask import Blueprint, jsonify, request, session
import logging
from auth import login_required
from database import db
from api_utils import api, formatter

# Blueprint oluştur
api_bp = Blueprint('api_bp', __name__, url_prefix='/api')

# API Proxy Endpoints
@api_bp.route('/proxy/search')
@login_required
def proxy_search():
    """Güvenli arama proxy"""
    try:
        # Frontend'den gelen parametreleri al ve doğrula
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        limit = min(request.args.get('limit', 20, type=int), 100)
        domain = request.args.get('domain', '')
        region = request.args.get('region', '')
        source = request.args.get('source', '')
        
        if not query or len(query) < 2:
            return jsonify({
                'success': False,
                'error': 'Arama sorgusu en az 2 karakter olmalıdır'
            }), 400
        
        # Güvenli API çağrısı yap
        api_response = api.search_accounts(query, page, limit, domain, region, source)
        
        # Log the search
        logging.info(f"Arama yapıldı: '{query}' - Kullanıcı: {session.get('user_name')}")
        
        return jsonify(api_response)
        
    except Exception as e:
        logging.error(f"Search proxy error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/proxy/accounts')
@login_required
def proxy_accounts():
    """Güvenli hesap listesi proxy"""
    try:
        page = request.args.get('page', 1, type=int)
        limit = min(request.args.get('limit', 10, type=int), 100)
        domain = request.args.get('domain', '')
        region = request.args.get('region', '')
        source = request.args.get('source', '')
        
        api_response = api.get_accounts(page, limit, domain, region, source)
        return jsonify(api_response)
        
    except Exception as e:
        logging.error(f"Accounts proxy error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/proxy/account/<int:account_id>')
@login_required
def proxy_single_account(account_id):
    """Tekil hesap bilgisi proxy"""
    try:
        api_response = api.get_single_account(account_id)
        return jsonify(api_response)
        
    except Exception as e:
        logging.error(f"Single account proxy error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/proxy/statistics')
@login_required
def proxy_statistics():
    """İstatistik proxy"""
    try:
        api_response = api.get_statistics()
        return jsonify(api_response)
        
    except Exception as e:
        logging.error(f"Statistics proxy error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/proxy/health')
@login_required
def proxy_health():
    """Sistem sağlık kontrolü proxy"""
    try:
        api_response = api.health_check()
        return jsonify(api_response)
        
    except Exception as e:
        logging.error(f"Health proxy error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Local API Endpoints
@api_bp.route('/stats')
@login_required
def api_stats():
    """Gerçek zamanlı istatistikler"""
    try:
        # Kategori istatistiklerini al
        categories = db.get_categories_stats()
        
        if categories:
            total_count = sum(category['count'] for category in categories)
            
            # API formatında veri hazırla
            stats_data = formatter.format_categories_stats(categories, total_count)
            
            # Toplam istatistikler
            total_stats = db.get_total_stats()
            
            response_data = {
                'success': True,
                'total_accounts': total_stats['total_accounts'],
                'unique_domains': total_stats['unique_domains'],
                'categories': stats_data,
                'last_updated': total_stats['last_updated'],
                'user': session.get('user_name', 'Kullanıcı')
            }
            
            return jsonify(response_data)
        else:
            return jsonify({
                'success': False,
                'error': 'fetched_accounts tablosunda veri bulunamadı',
                'total_accounts': 0,
                'unique_domains': 0,
                'categories': []
            })
        
    except Exception as e:
        logging.error(f"API veri çekme hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'total_accounts': 0,
            'unique_domains': 0,
            'categories': []
        })

@api_bp.route('/search')
@login_required
def api_search():
    """API'den arama - Veritabanı fallback ile"""
    try:
        # Parametreleri al
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        limit = min(request.args.get('limit', 20, type=int), 100)
        domain_filter = request.args.get('domain', '')
        region_filter = request.args.get('region', '')
        source_filter = request.args.get('source', '')
        
        if not query or len(query) < 2:
            return jsonify({
                'success': False,
                'error': 'Arama sorgusu en az 2 karakter olmalıdır'
            }), 400
        
        logging.info(f"API'den arama başlatılıyor: '{query}'")
        
        # API'den veri çek
        try:
            api_response = api.search_accounts(query, page, limit, domain_filter, region_filter, source_filter)
            
            # API yanıtını logla
            logging.info(f"API arama başarılı: '{query}' - {len(api_response.get('results', []))} sonuç")
            
            # Eğer API yanıtında debug bilgisi yoksa ekle
            if 'debug' not in api_response:
                api_response['debug'] = {
                    'data_source': 'external_api',
                    'query': query
                }
            
            return jsonify(api_response)
            
        except Exception as api_error:
            logging.warning(f"API arama başarısız, fallback'e geçiliyor: {str(api_error)}")
            
            # API başarısız olursa fallback olarak veritabanından ara
            return fallback_database_search(query, page, limit, domain_filter, region_filter, source_filter)
        
    except Exception as e:
        logging.error(f"Arama hatası: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'data_source': 'error'
        }), 500

def fallback_database_search(query, page=1, limit=20, domain_filter='', region_filter='', source_filter=''):
    """API başarısız olduğunda veritabanından arama yap"""
    try:
        logging.info(f"Fallback veritabanı araması başlatılıyor: '{query}'")
        
        # Veritabanından arama yap
        search_result = db.search_accounts(query, page, limit, domain_filter, region_filter, source_filter)
        
        if 'error' in search_result:
            return jsonify({
                'success': False,
                'error': search_result['error'],
                'data_source': 'fallback_failed'
            }), 500
        
        # Sonuçları formatla
        formatted_results = formatter.format_search_results(
            search_result['results'], 
            search_result['available_columns']
        )
        
        response_data = {
            'success': True,
            'results': formatted_results,
            'pagination': {
                'page': page,
                'pages': search_result['pages'],
                'total': search_result['total'],
                'has_next': page < search_result['pages'],
                'has_prev': page > 1
            },
            'summary': {
                'exact_matches': len([r for r in formatted_results if query.lower() in r['domain'].lower()]),
                'partial_matches': len(formatted_results)
            },
            'debug': {
                'data_source': 'fallback_database',
                'search_columns': search_result['search_columns'],
                'available_columns': search_result['available_columns'],
                'query': query,
                'warning': 'API başarısız oldu, veritabanından arama yapıldı'
            }
        }
        
        logging.info(f"Fallback arama tamamlandı: '{query}' - {len(formatted_results)} sonuç")
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Fallback arama hatası: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'data_source': 'fallback_error'
        }), 500

@api_bp.route('/user')
@login_required
def user_info():
    """Kullanıcı bilgileri"""
    return jsonify({
        'success': True,
        'user_id': session.get('user_id'),
        'user_name': session.get('user_name'),
        'user_role': session.get('user_role'),
        'login_time': session.get('login_time')
    })

@api_bp.route('/config')
@login_required
def api_config():
    """Frontend için güvenli API konfigürasyonu"""
    return jsonify({
        'success': True,
        'endpoints': {
            'search': '/api/search',
            'accounts': '/api/proxy/accounts',
            'statistics': '/api/stats',
            'health': '/api/proxy/health'
        },
        'user': session.get('user_name', 'Kullanıcı')
    })