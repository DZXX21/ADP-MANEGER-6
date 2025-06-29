from flask import Blueprint, render_template, request, jsonify, session
import logging
from auth import login_required
from database import db

# Blueprint oluştur
leak_logs_bp = Blueprint('leak_logs_bp', __name__, url_prefix='/leak-logs')

@leak_logs_bp.route('/')
@login_required
def leak_logs_page():
    """Leak logs ana sayfası"""
    try:
        # İstatistikleri al
        stats = db.get_leak_logs_stats()
        
        # Son 10 log'u al
        recent_logs_result = db.get_leak_logs(page=1, limit=10)
        recent_logs = recent_logs_result.get('results', [])
        
        # Template için veri formatla
        formatted_recent_logs = []
        for log in recent_logs:
            formatted_log = {
                'id': log.get('id', 0),
                'channel': log.get('channel') or 'Bilinmiyor',
                'source': log.get('source') or 'Bilinmiyor',
                'content': log.get('content') or '',
                'author': log.get('author') or 'Anonim',
                'detection_date': str(log.get('detection_date')) if log.get('detection_date') else 'Bilinmiyor',
                'type': log.get('type') or 'Genel',
                'created_at': str(log.get('created_at')) if log.get('created_at') else 'Bilinmiyor'
            }
            formatted_recent_logs.append(formatted_log)
        
        logging.info(f"Leak logs sayfası yüklendi - {stats['total_logs']} toplam log")
        
        return render_template('leak_logs.html',
                             stats=stats,
                             recent_logs=formatted_recent_logs,
                             user_name=session.get('user_name'),
                             user_role=session.get('user_role'))
                             
    except Exception as e:
        logging.error(f"Leak logs sayfa hatası: {e}")
        # Hata durumunda boş veri ile template'i yükle
        empty_stats = {
            'total_logs': 0,
            'sources': [],
            'types': [],
            'channels': []
        }
        return render_template('leak_logs.html',
                             stats=empty_stats,
                             recent_logs=[],
                             user_name=session.get('user_name'),
                             user_role=session.get('user_role'),
                             error=f"Veri yükleme hatası: {str(e)}")

@leak_logs_bp.route('/api/list')
@login_required
def api_leak_logs_list():
    """Leak logs listesi API"""
    try:
        page = request.args.get('page', 1, type=int)
        limit = min(request.args.get('limit', 20, type=int), 100)
        source_filter = request.args.get('source', '').strip()
        type_filter = request.args.get('type', '').strip()
        channel_filter = request.args.get('channel', '').strip()
        
        # Parametreleri logla
        logging.info(f"Leak logs liste API - Sayfa: {page}, Limit: {limit}, Filtreler: source='{source_filter}', type='{type_filter}', channel='{channel_filter}'")
        
        # Verileri al
        result = db.get_leak_logs(page, limit, source_filter, type_filter, channel_filter)
        
        if 'error' in result:
            logging.error(f"Leak logs liste hatası: {result['error']}")
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        
        # Sonuçları formatla
        formatted_results = []
        for log in result['results']:
            # İçeriği kısalt
            content = log.get('content') or ''
            short_content = content[:200] + '...' if len(content) > 200 else content
            
            formatted_log = {
                'id': log.get('id', 0),
                'channel': log.get('channel') or 'Bilinmiyor',
                'source': log.get('source') or 'Bilinmiyor',
                'content': short_content,
                'full_content': content,
                'author': log.get('author') or 'Anonim',
                'detection_date': str(log.get('detection_date')) if log.get('detection_date') else 'Bilinmiyor',
                'type': log.get('type') or 'Genel',
                'created_at': str(log.get('created_at')) if log.get('created_at') else 'Bilinmiyor'
            }
            formatted_results.append(formatted_log)
        
        response_data = {
            'success': True,
            'results': formatted_results,
            'pagination': {
                'page': page,
                'pages': result.get('pages', 1),
                'total': result.get('total', 0),
                'has_next': page < result.get('pages', 1),
                'has_prev': page > 1
            },
            'filters': {
                'source': source_filter,
                'type': type_filter,
                'channel': channel_filter
            }
        }
        
        logging.info(f"Leak logs liste API başarılı - {len(formatted_results)} sonuç döndü")
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Leak logs liste API hatası: {e}")
        return jsonify({
            'success': False,
            'error': f"Sunucu hatası: {str(e)}"
        }), 500

@leak_logs_bp.route('/api/search')
@login_required
def api_leak_logs_search():
    """Leak logs arama API"""
    try:
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        limit = min(request.args.get('limit', 20, type=int), 100)
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Arama sorgusu boş olamaz'
            }), 400
            
        if len(query) < 2:
            return jsonify({
                'success': False,
                'error': 'Arama sorgusu en az 2 karakter olmalıdır'
            }), 400
        
        logging.info(f"Leak logs arama API - Sorgu: '{query}', Sayfa: {page}, Limit: {limit}")
        
        # Arama yap
        result = db.search_leak_logs(query, page, limit)
        
        if 'error' in result:
            logging.error(f"Leak logs arama hatası: {result['error']}")
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        
        # Sonuçları formatla ve arama terimini vurgula
        formatted_results = []
        for log in result['results']:
            content = log.get('content') or ''
            
            # Arama terimini vurgula (case-insensitive)
            highlighted_content = content
            if query.lower() in content.lower():
                # Büyük/küçük harf duyarlı olmayan vurgulama
                import re
                pattern = re.compile(re.escape(query), re.IGNORECASE)
                highlighted_content = pattern.sub(f"<mark>{query}</mark>", content)
            
            # İçeriği kısalt
            if len(highlighted_content) > 300:
                highlighted_content = highlighted_content[:300] + '...'
            
            formatted_log = {
                'id': log.get('id', 0),
                'channel': log.get('channel') or 'Bilinmiyor',
                'source': log.get('source') or 'Bilinmiyor',
                'content': highlighted_content,
                'full_content': content,
                'author': log.get('author') or 'Anonim',
                'detection_date': str(log.get('detection_date')) if log.get('detection_date') else 'Bilinmiyor',
                'type': log.get('type') or 'Genel',
                'created_at': str(log.get('created_at')) if log.get('created_at') else 'Bilinmiyor'
            }
            formatted_results.append(formatted_log)
        
        response_data = {
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
            'summary': {
                'search_term': query,
                'results_count': len(formatted_results),
                'total_matches': result.get('total', 0)
            }
        }
        
        logging.info(f"Leak logs arama başarılı - '{query}' için {len(formatted_results)} sonuç")
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Leak logs arama API hatası: {e}")
        return jsonify({
            'success': False,
            'error': f"Arama hatası: {str(e)}"
        }), 500

@leak_logs_bp.route('/api/stats')
@login_required
def api_leak_logs_stats():
    """Leak logs istatistikleri API"""
    try:
        stats = db.get_leak_logs_stats()
        
        # İstatistikleri formatla
        formatted_stats = {
            'total_logs': stats.get('total_logs', 0),
            'sources': stats.get('sources', []),
            'types': stats.get('types', []),
            'channels': stats.get('channels', []),
            'summary': {
                'unique_sources': len(stats.get('sources', [])),
                'unique_types': len(stats.get('types', [])),
                'unique_channels': len(stats.get('channels', []))
            }
        }
        
        response_data = {
            'success': True,
            'stats': formatted_stats,
            'user': session.get('user_name', 'Kullanıcı'),
            'timestamp': str(db.get_connection() is not None)  # Bağlantı durumu
        }
        
        logging.info(f"Leak logs istatistik API - {formatted_stats['total_logs']} toplam log")
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Leak logs istatistik API hatası: {e}")
        return jsonify({
            'success': False,
            'error': f"İstatistik hatası: {str(e)}",
            'stats': {
                'total_logs': 0,
                'sources': [],
                'types': [],
                'channels': []
            }
        }), 500

@leak_logs_bp.route('/api/detail/<int:log_id>')
@login_required
def api_leak_log_detail(log_id):
    """Tekil leak log detayı"""
    try:
        if log_id <= 0:
            return jsonify({
                'success': False,
                'error': 'Geçersiz log ID'
            }), 400
        
        logging.info(f"Leak log detay istendi - ID: {log_id}")
        
        connection = db.get_connection()
        if not connection:
            return jsonify({
                'success': False,
                'error': 'Veritabanı bağlantısı başarısız'
            }), 500
        
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, channel, source, content, author, detection_date, type, created_at
                FROM leak_logs 
                WHERE id = %s
            """, (log_id,))
            
            log = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if not log:
                logging.warning(f"Log bulunamadı - ID: {log_id}")
                return jsonify({
                    'success': False,
                    'error': f'ID {log_id} numaralı log bulunamadı'
                }), 404
            
            # Log detayını formatla
            formatted_log = {
                'id': log.get('id', 0),
                'channel': log.get('channel') or 'Bilinmiyor',
                'source': log.get('source') or 'Bilinmiyor',
                'content': log.get('content') or 'İçerik mevcut değil',
                'author': log.get('author') or 'Anonim',
                'detection_date': str(log.get('detection_date')) if log.get('detection_date') else 'Bilinmiyor',
                'type': log.get('type') or 'Genel',
                'created_at': str(log.get('created_at')) if log.get('created_at') else 'Bilinmiyor',
                'content_length': len(log.get('content', '')),
                'has_author': bool(log.get('author')),
                'has_detection_date': bool(log.get('detection_date'))
            }
            
            response_data = {
                'success': True,
                'log': formatted_log,
                'meta': {
                    'requested_id': log_id,
                    'found': True,
                    'user': session.get('user_name', 'Kullanıcı')
                }
            }
            
            logging.info(f"Leak log detay başarılı - ID: {log_id}, İçerik uzunluğu: {formatted_log['content_length']}")
            return jsonify(response_data)
            
        except Exception as db_error:
            if connection:
                connection.close()
            logging.error(f"Veritabanı sorgu hatası - ID: {log_id}, Hata: {db_error}")
            return jsonify({
                'success': False,
                'error': f'Veritabanı hatası: {str(db_error)}'
            }), 500
        
    except Exception as e:
        logging.error(f"Leak log detay genel hatası - ID: {log_id}, Hata: {e}")
        return jsonify({
            'success': False,
            'error': f"Sunucu hatası: {str(e)}"
        }), 500

@leak_logs_bp.route('/api/export')
@login_required
def api_leak_logs_export():
    """Leak logs export (CSV/JSON)"""
    try:
        format_type = request.args.get('format', 'json').lower()
        limit = min(request.args.get('limit', 1000, type=int), 5000)  # Max 5000
        source_filter = request.args.get('source', '').strip()
        type_filter = request.args.get('type', '').strip()
        
        if format_type not in ['json', 'csv']:
            return jsonify({
                'success': False,
                'error': 'Desteklenen formatlar: json, csv'
            }), 400
        
        logging.info(f"Leak logs export - Format: {format_type}, Limit: {limit}")
        
        # Verileri al
        result = db.get_leak_logs(page=1, limit=limit, source_filter=source_filter, type_filter=type_filter)
        
        if 'error' in result:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        
        logs = result.get('results', [])
        
        if format_type == 'json':
            # JSON export
            export_data = {
                'export_info': {
                    'format': 'json',
                    'timestamp': str(db.get_connection() is not None),
                    'total_records': len(logs),
                    'filters': {
                        'source': source_filter or None,
                        'type': type_filter or None
                    },
                    'exported_by': session.get('user_name', 'Kullanıcı')
                },
                'logs': []
            }
            
            for log in logs:
                export_data['logs'].append({
                    'id': log.get('id'),
                    'channel': log.get('channel'),
                    'source': log.get('source'),
                    'content': log.get('content'),
                    'author': log.get('author'),
                    'detection_date': str(log.get('detection_date')) if log.get('detection_date') else None,
                    'type': log.get('type'),
                    'created_at': str(log.get('created_at')) if log.get('created_at') else None
                })
            
            return jsonify(export_data)
            
        elif format_type == 'csv':
            # CSV export
            import io
            import csv
            from flask import Response
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow(['ID', 'Channel', 'Source', 'Content', 'Author', 'Type', 'Detection Date', 'Created At'])
            
            # Data
            for log in logs:
                writer.writerow([
                    log.get('id', ''),
                    log.get('channel', ''),
                    log.get('source', ''),
                    log.get('content', '').replace('\n', ' ').replace('\r', ' '),  # CSV için newline temizle
                    log.get('author', ''),
                    log.get('type', ''),
                    str(log.get('detection_date', '')),
                    str(log.get('created_at', ''))
                ])
            
            output.seek(0)
            
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename=leak_logs_export.csv',
                    'Content-Type': 'text/csv; charset=utf-8'
                }
            )
        
    except Exception as e:
        logging.error(f"Leak logs export hatası: {e}")
        return jsonify({
            'success': False,
            'error': f"Export hatası: {str(e)}"
        }), 500

# Test endpoint
@leak_logs_bp.route('/test')
@login_required
def test_leak_logs():
    """Test endpoint - leak logs tablonun çalışıp çalışmadığını kontrol et"""
    try:
        # Basit bağlantı testi
        connection = db.get_connection()
        if not connection:
            return jsonify({
                'success': False,
                'error': 'Veritabanı bağlantısı başarısız',
                'tests': ['connection_failed']
            })
        
        tests_passed = []
        tests_failed = []
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Test 1: Tablo var mı?
            cursor.execute("SHOW TABLES LIKE 'leak_logs'")
            if cursor.fetchone():
                tests_passed.append('table_exists')
            else:
                tests_failed.append('table_not_found')
            
            # Test 2: Tablo yapısı
            cursor.execute("DESCRIBE leak_logs")
            columns = cursor.fetchall()
            if columns:
                tests_passed.append('table_structure_ok')
                column_names = [col['Field'] for col in columns]
            else:
                tests_failed.append('table_structure_error')
                column_names = []
            
            # Test 3: Veri var mı?
            cursor.execute("SELECT COUNT(*) as count FROM leak_logs")
            count_result = cursor.fetchone()
            total_count = count_result['count'] if count_result else 0
            
            if total_count > 0:
                tests_passed.append('has_data')
            else:
                tests_failed.append('no_data')
            
            # Test 4: Örnek veri çek
            cursor.execute("SELECT * FROM leak_logs LIMIT 1")
            sample_data = cursor.fetchone()
            
            if sample_data:
                tests_passed.append('sample_data_ok')
            else:
                tests_failed.append('no_sample_data')
            
            cursor.close()
            connection.close()
            
            return jsonify({
                'success': len(tests_failed) == 0,
                'tests_passed': tests_passed,
                'tests_failed': tests_failed,
                'table_info': {
                    'exists': 'table_exists' in tests_passed,
                    'columns': column_names,
                    'total_records': total_count,
                    'sample_data': dict(sample_data) if sample_data else None
                },
                'recommendations': {
                    'create_table': 'table_not_found' in tests_failed,
                    'add_data': 'no_data' in tests_failed,
                    'check_permissions': len(tests_failed) > 2
                }
            })
            
        except Exception as query_error:
            if connection:
                connection.close()
            return jsonify({
                'success': False,
                'error': f'Test sorgu hatası: {str(query_error)}',
                'tests_failed': ['query_error']
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Test genel hatası: {str(e)}',
            'tests_failed': ['general_error']
        })