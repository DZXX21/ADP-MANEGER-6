from flask import Blueprint, render_template, session
import logging

# Blueprint oluştur
main_bp = Blueprint('main_bp', __name__)

# Import'ları blueprint tanımından SONRA yap
from auth import login_required
from database import db
from api_utils import formatter

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
        # Kategori istatistiklerini al
        categories = db.get_categories_stats()
        
        if categories:
            total_count = sum(category['count'] for category in categories)
            
            # Verileri formatla
            chart_data = formatter.format_categories_stats(categories, total_count)
            
            summary_data = {
                'labels': [item['label'] for item in chart_data],
                'counts': [item['count'] for item in chart_data],
                'percentages': [item['percentage'] for item in chart_data],
                'colors': [item['color'] for item in chart_data]
            }
            
            # Genel istatistikleri al
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

    # Senin templates/index.html dosyanı kullan
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
    # Senin templates/search.html dosyanı kullan
    return render_template('search.html', 
                         user_name=session.get('user_name'),
                         user_role=session.get('user_role'))