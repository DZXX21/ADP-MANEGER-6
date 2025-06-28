from flask import Blueprint, render_template, session
from auth import admin_required

# Blueprint oluştur
admin_bp = Blueprint('admin_bp', __name__, url_prefix='/admin')

@admin_bp.route('/')
@admin_required
def admin_panel():
    """Admin panel"""
    return render_template('admin.html', 
                         user_name=session.get('user_name'),
                         user_role=session.get('user_role'))