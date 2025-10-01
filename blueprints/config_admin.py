"""
설정 관리 블루프린트
시스템 설정 조회, 수정 및 관리 기능을 담당합니다.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from user_manager import admin_required
import sys
import os

# 상위 디렉토리의 모듈을 import하기 위한 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

config_admin_bp = Blueprint('config_admin', __name__)

# ========================
# 설정 관리 라우트
# ========================

@config_admin_bp.route('/admin/config')
@admin_required
def config_list():
    """설정 목록 조회"""
    from app import config_manager, EXE_MODE
    
    # EXE_MODE에 따라 필터링된 설정 목록 조회
    configs = config_manager.get_all_configs_list(exe_mode=EXE_MODE)
    
    return render_template('admin/config_list.html', configs=configs, exe_mode=EXE_MODE)


@config_admin_bp.route('/admin/config/view/<int:config_id>')
@admin_required
def config_view(config_id):
    """설정 상세 조회"""
    from app import config_manager
    config = config_manager.get_config_by_id(config_id)
    
    if not config:
        flash('설정을 찾을 수 없습니다.', 'danger')
        return redirect(url_for('config_admin.config_list'))
    
    return render_template('admin/config_view.html', config_item=config)


@config_admin_bp.route('/admin/config/edit/<int:config_id>', methods=['GET', 'POST'])
@admin_required
def config_edit(config_id):
    """설정 편집"""
    from app import config_manager
    
    config = config_manager.get_config_by_id(config_id)
    
    if not config:
        flash('설정을 찾을 수 없습니다.', 'danger')
        return redirect(url_for('config_admin.config_list'))
    
    if request.method == 'POST':
        new_value = request.form.get('value')
        description = request.form.get('description', config['description'])
        gb = request.form.get('gb', config.get('gb', 'DEFAULT'))  # gb 필드 추가
        updated_by = session.get('user_id')
        
        result = config_manager.update_config_by_id(
            config_id=config_id,
            value=new_value,
            updated_by=updated_by,
            description=description,
            gb=gb  # gb 파라미터 추가
        )
        
        if result['success']:
            flash('설정이 성공적으로 업데이트되었습니다.', 'success')
            return redirect(url_for('config_admin.config_list'))
        else:
            flash(result.get('error', '설정 업데이트에 실패했습니다.'), 'danger')
    
    return render_template('admin/config_edit.html', config_item=config)


# ========================
# 설정 관리 API 라우트
# ========================

@config_admin_bp.route('/api/config/update/<int:config_id>', methods=['POST'])
@admin_required
def api_config_update(config_id):
    """설정 업데이트 API"""
    from app import config_manager
    
    try:
        data = request.get_json()
        new_value = data.get('value')
        updated_by = session.get('user_id')
        
        result = config_manager.update_config_by_id(
            config_id=config_id,
            value=new_value,
            updated_by=updated_by
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@config_admin_bp.route('/api/config/migrate', methods=['POST'])
@admin_required
def api_config_migrate():
    """config.json을 데이터베이스로 마이그레이션"""
    from app import config_manager
    
    try:
        updated_by = session.get('user_id')
        result = config_manager.migrate_from_file(user_id=updated_by)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@config_admin_bp.route('/api/config/export', methods=['POST'])
@admin_required
def api_config_export():
    """데이터베이스 설정을 config.json으로 내보내기"""
    from app import config_manager
    
    try:
        result = config_manager.save_to_file()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ========================
# 설정 카테고리별 관리 라우트
# ========================

@config_admin_bp.route('/admin/config/category/<category>')
@admin_required
def config_by_category(category):
    """카테고리별 설정 조회"""
    from app import config_manager
    configs = config_manager.get_configs_by_category(category)
    return render_template('admin/config_category.html', configs=configs, category=category)


@config_admin_bp.route('/api/config/categories', methods=['GET'])
@admin_required
def api_config_categories():
    """설정 카테고리 목록 조회 API"""
    from app import config_manager
    
    try:
        categories = config_manager.get_all_categories()
        return jsonify({'success': True, 'categories': categories})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})