from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request
import logging

# Blueprint oluştur
main_bp = Blueprint('main_bp', __name__)

# Import'ları blueprint tanımından SONRA yap
from auth import login_required
from database import db
from api_utils import formatter
from routes.api2_search import search_domain_with_retry


@main_bp.route('/')
@login_required
def dashboard():
    """Ana dashboard sayfası"""
    chart_data = []
    summary_data = {'labels': [], 'counts': [], 'percentages': [], 'colors': []}
    error = ""
    stats = {
        'total_accounts': 0,
        'unique_domains': 0,
        'categories': [],
        'last_updated': 'Bilinmiyor'
    }

    try:
        categories = db.get_categories_stats()
        
        if categories:
            total_count = sum(category['count'] for category in categories)
            chart_data = formatter.format_categories_stats(categories, total_count)
            
            summary_data = {
                'labels': [item['label'] for item in chart_data],
                'counts': [item['count'] for item in chart_data],
                'percentages': [item['percentage'] for item in chart_data],
                'colors': [item['color'] for item in chart_data]
            }
            
            total_stats = db.get_total_stats()
            stats.update(total_stats)
            stats['categories'] = chart_data
            
            logging.info(f"Dashboard verileri yüklendi: {len(categories)} kategori, toplam {total_count} kayıt")
        else:
            error = "fetched_accounts tablosunda veri bulunamadı!"
            logging.warning("fetched_accounts tablosunda veri bulunamadı")
            
    except Exception as e:
        error = f"Veri çekme hatası: {str(e)}"
        logging.error(f"Dashboard veri çekme hatası: {e}")

    return render_template('index.html', 
                         chart_data=chart_data, 
                         summary_data=summary_data, 
                         stats=stats,
                         error=error,
                         user_name=session.get('user_name'),
                         user_role=session.get('user_role'))

@main_bp.route('/search')
@login_required
def search_page():
    """Arama sayfası"""
    return render_template('search.html', 
                         user_name=session.get('user_name'),
                         user_role=session.get('user_role'))

@main_bp.route('/leak-logs')
@login_required
def leak_logs_page():
    """Leak logs ana sayfası - TÜM VERİLERİ GETİR"""
    try:
        # Leak logs istatistiklerini al
        leak_stats = db.get_leak_logs_stats()
        
        # 🔥 TÜM LOGS'LARI AL - Limit yok!
        all_logs_result = db.get_leak_logs(page=1, limit=999999)  # Çok yüksek limit
        all_logs = all_logs_result.get('results', [])
        
        # Template formatında hazırla
        total_assets = leak_stats.get('total_logs', 0)
        unique_domains = len(leak_stats.get('sources', []))
        categories_count = len(leak_stats.get('types', []))
        regions_count = len(leak_stats.get('channels', []))
        
        # Grafik verileri - source ve channel isimleri
        category_stats = [source.get('source', 'Bilinmiyor') for source in leak_stats.get('sources', [])[:10]]
        regional_data = [channel.get('channel', 'Bilinmiyor') for channel in leak_stats.get('channels', [])[:10]]
        
        # 🔥 TÜM VERİLERİ RECENT_DATA OLARAK GÖNDER
        recent_data = []
        for log in all_logs:  # Artık sadece 10 değil, hepsi
            recent_data.append({
                'id': log.get('id'),
                'domain': log.get('channel', 'Bilinmiyor'),
                'category': log.get('type', 'Genel'),
                'region': log.get('source', 'Bilinmiyor'),
                'fetch_date': str(log.get('detection_date', 'Bilinmiyor')),
                'content': log.get('content', ''),  # İçeriği de ekle
                'author': log.get('author', 'Anonim')
            })

        logging.info(f"🔥 LEAK LOGS - TÜM VERİLER YÜKLENDİ: {len(recent_data)} kayıt")
        
        return render_template('leak_logs.html', 
                             total_assets=total_assets,
                             unique_domains=unique_domains,
                             categories_count=categories_count,
                             regions_count=regions_count,
                             category_stats=category_stats,
                             regional_data=regional_data,
                             recent_data=recent_data,  # Tüm veriler burada
                             all_data_count=len(recent_data))  # Kaç kayıt olduğunu göster
                             
    except Exception as e:
        logging.error(f"Leak logs sayfa hatası: {e}")
        
        # Hata durumunda boş veri
        return render_template('leak_logs.html',
                             total_assets=0,
                             unique_domains=0,
                             categories_count=0,
                             regions_count=0,
                             category_stats=[],
                             regional_data=[],
                             recent_data=[],
                             all_data_count=0)

@main_bp.route('/leak-logs/api/all')
@login_required
def api_leak_logs_all():
    """🔥 TÜM LEAK LOGS VERİLERİNİ AL - LİMİT YOK"""
    try:
        logging.info("🔥 TÜM leak logs verileri istendi")
        
        # Filtreler (opsiyonel)
        source_filter = request.args.get('source', '').strip()
        type_filter = request.args.get('type', '').strip()
        channel_filter = request.args.get('channel', '').strip()
        
        # 🔥 TÜM VERİLERİ AL - Çok yüksek limit
        result = db.get_leak_logs(page=1, limit=999999, 
                                 source_filter=source_filter, 
                                 type_filter=type_filter, 
                                 channel_filter=channel_filter)
        
        if 'error' in result:
            logging.error(f"Tüm leak logs alma hatası: {result['error']}")
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        
        # Tüm sonuçları formatla
        formatted_results = []
        for log in result['results']:
            formatted_log = {
                'id': log.get('id', 0),
                'channel': log.get('channel') or 'Bilinmiyor',
                'source': log.get('source') or 'Bilinmiyor',
                'content': log.get('content') or '',  # Tam içerik
                'author': log.get('author') or 'Anonim',
                'detection_date': str(log.get('detection_date')) if log.get('detection_date') else 'Bilinmiyor',
                'type': log.get('type') or 'Genel',
                'created_at': str(log.get('created_at')) if log.get('created_at') else 'Bilinmiyor'
            }
            formatted_results.append(formatted_log)
        
        response_data = {
            'success': True,
            'results': formatted_results,
            'total_count': len(formatted_results),
            'message': f'TÜM VERİLER - {len(formatted_results)} kayıt',
            'filters_applied': {
                'source': source_filter or 'Yok',
                'type': type_filter or 'Yok',
                'channel': channel_filter or 'Yok'
            }
        }
        
        logging.info(f"🔥 TÜM leak logs başarılı - {len(formatted_results)} kayıt döndürüldü")
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Tüm leak logs alma hatası: {e}")
        return jsonify({
            'success': False,
            'error': f"Sunucu hatası: {str(e)}"
        }), 500

@main_bp.route('/leak-logs/api/list')
@login_required
def api_leak_logs_list():
    """Leak logs listesi API - ŞİMDİ LİMİTSİZ"""
    try:
        page = request.args.get('page', 1, type=int)
        # 🔥 Limit'i kaldır veya çok yüksek yap
        limit = request.args.get('limit', 999999, type=int)  # Varsayılan çok yüksek
        source_filter = request.args.get('source', '').strip()
        type_filter = request.args.get('type', '').strip()
        channel_filter = request.args.get('channel', '').strip()
        
        result = db.get_leak_logs(page, limit, source_filter, type_filter, channel_filter)
        
        if 'error' in result:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        
        formatted_results = []
        for log in result['results']:
            content = log.get('content') or ''
            
            formatted_log = {
                'id': log.get('id', 0),
                'channel': log.get('channel') or 'Bilinmiyor',
                'source': log.get('source') or 'Bilinmiyor',
                'content': content,  # Tam içerik, kısaltma yok
                'full_content': content,
                'author': log.get('author') or 'Anonim',
                'detection_date': str(log.get('detection_date')) if log.get('detection_date') else 'Bilinmiyor',
                'type': log.get('type') or 'Genel',
                'created_at': str(log.get('created_at')) if log.get('created_at') else 'Bilinmiyor'
            }
            formatted_results.append(formatted_log)
        
        return jsonify({
            'success': True,
            'results': formatted_results,
            'pagination': {
                'page': page,
                'pages': result.get('pages', 1),
                'total': result.get('total', 0),
                'has_next': page < result.get('pages', 1),
                'has_prev': page > 1
            },
            'message': f'Toplam {len(formatted_results)} kayıt döndürüldü'
        })
        
    except Exception as e:
        logging.error(f"Leak logs liste API hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/leak-logs/api/search')
@login_required
def api_leak_logs_search():
    """Leak logs arama API - LİMİTSİZ"""
    try:
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        # 🔥 Arama için de limit kaldır
        limit = request.args.get('limit', 999999, type=int)
        
        if not query or len(query) < 2:
            return jsonify({
                'success': False,
                'error': 'Arama sorgusu en az 2 karakter olmalıdır'
            }), 400
        
        result = db.search_leak_logs(query, page, limit)
        
        if 'error' in result:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        
        formatted_results = []
        for log in result['results']:
            content = log.get('content') or ''
            
            # Arama terimini vurgula
            highlighted_content = content
            if query.lower() in content.lower():
                import re
                pattern = re.compile(re.escape(query), re.IGNORECASE)
                highlighted_content = pattern.sub(f"<mark>{query}</mark>", content)
            
            formatted_log = {
                'id': log.get('id', 0),
                'channel': log.get('channel') or 'Bilinmiyor',
                'source': log.get('source') or 'Bilinmiyor',
                'content': highlighted_content,  # Kısaltma yok
                'full_content': content,
                'author': log.get('author') or 'Anonim',
                'detection_date': str(log.get('detection_date')) if log.get('detection_date') else 'Bilinmiyor',
                'type': log.get('type') or 'Genel',
                'created_at': str(log.get('created_at')) if log.get('created_at') else 'Bilinmiyor'
            }
            formatted_results.append(formatted_log)
        
        return jsonify({
            'success': True,
            'results': formatted_results,
            'pagination': {
                'page': page,
                'pages': result.get('pages', 1),
                'total': result.get('total', 0),
                'has_next': page < result.get('pages', 1),
                'has_prev': page > 1
            },
            'query': query,
            'message': f"'{query}' için {len(formatted_results)} sonuç bulundu"
        })
        
    except Exception as e:
        logging.error(f"Leak logs arama hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    

@main_bp.route('/helix-d')
@login_required
def helix_d_page():
    """Helix-D API2 Search sayfası"""
    return render_template('helix-d.html', 
                         user_name=session.get('user_name'),
                         user_role=session.get('user_role'))

@main_bp.route('/helix-d/search', methods=['POST'])
@login_required
def helix_d_search():
    """Helix-D domain arama API"""
    try:
        data = request.get_json() or {}
        domain = data.get('domain', '').strip()
        start_date = data.get('start_date', '').strip()
        end_date = data.get('end_date', '').strip()
        
        # Domain kontrolü
        if not domain:
            return jsonify({
                "success": False,
                "error": "Domain parametresi gerekli"
            }), 400
        
        # API2 search çağır
        logging.info(f"Helix-D arama başlatıldı: {domain}")
        result = search_domain_with_retry(domain, start_date, end_date)
        
        # Hata kontrolü
        if "error" in result:
            logging.error(f"Helix-D arama hatası: {result['error']}")
            return jsonify({
                "success": False,
                "error": result["error"],
                "domain": domain
            }), 500
        
        # Başarılı sonuç
        logging.info(f"Helix-D arama başarılı: {domain}")
        return jsonify({
            "success": True,
            "data": result,
            "domain": domain,
            "search_params": {
                "start_date": start_date or "Belirtilmedi",
                "end_date": end_date or "Belirtilmedi"
            }
        })
        
    except Exception as e:
        logging.error(f"Helix-D search hatası: {e}")
        return jsonify({
            "success": False,
            "error": f"Arama sırasında hata: {str(e)}"
        }), 500


@main_bp.route('/leak-logs/api/detail/<int:log_id>')
@login_required
def api_leak_log_detail(log_id):
    """Tekil leak log detayı"""
    try:
        connection = db.get_connection()
        if not connection:
            return jsonify({
                'success': False,
                'error': 'Veritabanı bağlantısı başarısız'
            }), 500
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM leak_logs WHERE id = %s
        """, (log_id,))
        
        log = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not log:
            return jsonify({
                'success': False,
                'error': 'Log bulunamadı'
            }), 404
        
        formatted_log = {
            'id': log.get('id', 0),
            'channel': log.get('channel') or 'Bilinmiyor',
            'source': log.get('source') or 'Bilinmiyor',
            'content': log.get('content'),  # Tam içerik
            'author': log.get('author') or 'Anonim',
            'detection_date': str(log.get('detection_date')) if log.get('detection_date') else 'Bilinmiyor',
            'type': log.get('type') or 'Genel',
            'created_at': str(log.get('created_at')) if log.get('created_at') else 'Bilinmiyor'
        }
        
        return jsonify({
            'success': True,
            'log': formatted_log
        })
        
    except Exception as e:
        logging.error(f"Leak log detay hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
