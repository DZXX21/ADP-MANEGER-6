from flask import Blueprint, jsonify, session, current_app
from datetime import datetime
import logging
from auth import login_required
from database import db

# Blueprint oluştur
debug_bp = Blueprint('debug_bp', __name__, url_prefix='/debug')

@debug_bp.route('/table-structure')
@login_required
def debug_table_structure():
    """Tablo yapısını kontrol et"""
    try:
        table_info = db.get_table_structure()
        
        if table_info:
            return jsonify({
                'success': True,
                'table_structure': table_info['columns'],
                'sample_data': table_info['sample_data'],
                'columns_list': table_info['columns_list'],
                'total_records': table_info['total_count'],
                'sample_domains': table_info['sample_domains'],
                'recommendations': {
                    'username_columns': [col['Field'] for col in table_info['columns'] 
                                       if any(keyword in col['Field'].lower() for keyword in ['user', 'email', 'login', 'account'])],
                    'password_columns': [col['Field'] for col in table_info['columns'] 
                                       if any(keyword in col['Field'].lower() for keyword in ['pass', 'pwd', 'secret'])],
                    'date_columns': [col['Field'] for col in table_info['columns'] 
                                   if any(keyword in col['Field'].lower() for keyword in ['date', 'time', 'created', 'added'])]
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Tablo yapısı alınamadı'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@debug_bp.route('/session')
@login_required
def debug_session():
    """Session debug bilgileri"""
    if not current_app.debug:
        return jsonify({'error': 'Debug mode disabled'}), 403
    
    return jsonify({
        'session_data': dict(session),
        'session_permanent': session.permanent,
        'session_new': session.new
    })

@debug_bp.route('/test-db')
@login_required
def test_db():
    """Veritabanı bağlantı testi - Gelişmiş versiyon"""
    if db.test_connection():
        try:
            table_info = db.get_table_structure()
            
            if table_info:
                return jsonify({
                    'success': True,
                    'message': f'Veritabanı bağlantısı başarılı! {table_info["total_count"]:,} kayıt bulundu.',
                    'table_exists': True,
                    'record_count': table_info["total_count"],
                    'has_sample_data': table_info["sample_data"] is not None,
                    'table_structure': table_info["columns"],
                    'sample_data': table_info["sample_data"],
                    'sample_domains': table_info["sample_domains"],
                    'available_columns': table_info["columns_list"]
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'fetched_accounts tablosu bulunamadı!',
                    'table_exists': False
                })
                
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Tablo kontrolü hatası: {e}'
            })
    
    return jsonify({
        'success': False,
        'message': 'Veritabanı bağlantısı başarısız!'
    })

@debug_bp.route('/health')
def health_check():
    """Sistem sağlık kontrolü"""
    try:
        db_status = db.test_connection()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected' if db_status else 'disconnected',
            'session_active': 'user_id' in session,
            'version': '1.0.0'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500