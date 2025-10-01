"""
사용자 관리 블루프린트
사용자 계정 생성, 수정, 삭제 및 권한 관리 기능을 담당합니다.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from user_manager import admin_required
import sys
import os

# 상위 디렉토리의 모듈을 import하기 위한 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

user_admin_bp = Blueprint('user_admin', __name__)

# ========================
# 사용자 관리 라우트
# ========================

@user_admin_bp.route('/admin/users')
@admin_required
def user_list():
    """사용자 목록 조회"""
    from app import user_manager
    users = user_manager.get_all_users()
    return render_template('admin/user_list.html', users=users)


@user_admin_bp.route('/admin/user/add', methods=['GET', 'POST'])
@admin_required
def user_add():
    """새 사용자 추가"""
    from app import user_manager
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        permission = request.form.get('permission', 'viewer')
        full_name = request.form.get('full_name', '')
        email = request.form.get('email', '')
        
        # 비밀번호 확인
        if password != password_confirm:
            flash('비밀번호가 일치하지 않습니다.', 'danger')
            return render_template('admin/user_add.html')
        
        # 사용자 생성
        result = user_manager.create_user(
            username=username,
            password=password,
            permission=permission,
            full_name=full_name,
            email=email
        )
        
        if result['success']:
            flash(f'사용자 "{username}"가 성공적으로 생성되었습니다.', 'success')
            return redirect(url_for('user_admin.user_list'))
        else:
            flash(result.get('error', '사용자 생성에 실패했습니다.'), 'danger')
    
    return render_template('admin/user_add.html')


@user_admin_bp.route('/admin/user/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def user_edit(user_id):
    """사용자 정보 편집"""
    from app import user_manager
    
    user = user_manager.get_user(user_id=user_id)
    
    if not user:
        flash('사용자를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('user_admin.user_list'))
    
    if request.method == 'POST':
        # 자신의 권한은 변경할 수 없음
        if user_id == session.get('user_id'):
            permission = user['permission']
            is_active = user['is_active']
        else:
            permission = request.form.get('permission', user['permission'])
            is_active = int(request.form.get('is_active', 1))
        
        full_name = request.form.get('full_name', '')
        email = request.form.get('email', '')
        
        result = user_manager.update_user(
            user_id=user_id,
            permission=permission,
            full_name=full_name,
            email=email,
            is_active=is_active
        )
        
        if result['success']:
            flash('사용자 정보가 업데이트되었습니다.', 'success')
            return redirect(url_for('user_admin.user_list'))
        else:
            flash(result.get('error', '업데이트에 실패했습니다.'), 'danger')
    
    return render_template('admin/user_edit.html', user=user)


@user_admin_bp.route('/admin/user/password-reset/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def user_password_reset(user_id):
    """비밀번호 재설정"""
    from app import user_manager
    
    user = user_manager.get_user(user_id=user_id)
    
    if not user:
        flash('사용자를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('user_admin.user_list'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('비밀번호가 일치하지 않습니다.', 'danger')
        elif len(new_password) < 8:
            flash('비밀번호는 최소 8자 이상이어야 합니다.', 'danger')
        else:
            result = user_manager.reset_password(user_id, new_password)
            
            if result['success']:
                flash(f'"{user["username"]}"의 비밀번호가 재설정되었습니다.', 'success')
                return redirect(url_for('user_admin.user_list'))
            else:
                flash(result.get('error', '비밀번호 재설정에 실패했습니다.'), 'danger')
    
    return render_template('admin/user_password_reset.html', user=user)


@user_admin_bp.route('/admin/user/delete/<int:user_id>', methods=['POST'])
@admin_required
def user_delete(user_id):
    """사용자 삭제"""
    from app import user_manager
    
    # 자기 자신은 삭제할 수 없음
    if user_id == session.get('user_id'):
        flash('자기 자신은 삭제할 수 없습니다.', 'danger')
        return redirect(url_for('user_admin.user_list'))
    
    user = user_manager.get_user(user_id=user_id)
    
    if not user:
        flash('사용자를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('user_admin.user_list'))
    
    result = user_manager.delete_user(user_id)
    
    if result['success']:
        flash(f'사용자 "{user["username"]}"가 삭제되었습니다.', 'success')
    else:
        flash(result.get('error', '사용자 삭제에 실패했습니다.'), 'danger')
    
    return redirect(url_for('user_admin.user_list'))