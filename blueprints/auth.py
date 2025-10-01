"""
인증 관련 블루프린트
로그인, 로그아웃, 비밀번호 변경 기능을 담당합니다.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from user_manager import login_required
import sys
import os

# 상위 디렉토리의 모듈을 import하기 위한 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """로그인 페이지"""
    from app import user_manager, LOGIN_CREDENTIALS, EXE_MODE    
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 레거시 인증 확인 (데이터베이스 설정 사용)
        if (username == LOGIN_CREDENTIALS['username'] and 
            password == LOGIN_CREDENTIALS['password']):
            session['logged_in'] = True
            session['username'] = username
            session['permission'] = 'admin'  # 기본 관리자 권한
            flash('로그인 성공!', 'success')

            # CLIENT 모드에서는 항상 센서 대시보드로
            if EXE_MODE == 'CLIENT':
                return redirect(url_for('sensor.sensor_dashboard'))
            else : # EXE_MODE == 'SERVER':
                return redirect(url_for('dashboard'))
        
        # 데이터베이스 인증 시도
        try:
            result = user_manager.authenticate(username, password)
            
            if result['success']:
                session['logged_in'] = True
                session['user_id'] = result['user']['id']
                session['username'] = result['user']['username']
                session['permission'] = result['user']['permission']
                flash('로그인 성공!', 'success')

                # CLIENT 모드에서는 항상 센서 대시보드로
                if EXE_MODE == 'CLIENT':
                    return redirect(url_for('sensor.sensor_dashboard'))
                else : # EXE_MODE == 'SERVER':
                    return redirect(url_for('dashboard'))
            else:
                flash(result.get('error', '잘못된 사용자명 또는 비밀번호입니다.'), 'error')
        except Exception as e:
            # 데이터베이스 인증 실패 시 에러 메시지
            print(f"데이터베이스 인증 오류: {e}")
            flash('인증 중 오류가 발생했습니다. 관리자에게 문의하세요.', 'error')
    
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """로그아웃"""
    session.clear()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """현재 사용자 비밀번호 변경"""
    from app import user_manager
    
    if request.method == 'POST':
        user_id = session.get('user_id')
        
        # 레거시 로그인인 경우
        if not user_id:
            flash('비밀번호 변경은 데이터베이스 사용자만 가능합니다.', 'warning')
            return redirect(url_for('dashboard'))
        
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('새 비밀번호가 일치하지 않습니다.', 'danger')
        elif len(new_password) < 8:
            flash('비밀번호는 최소 8자 이상이어야 합니다.', 'danger')
        else:
            result = user_manager.change_password(user_id, old_password, new_password)
            
            if result['success']:
                flash('비밀번호가 성공적으로 변경되었습니다.', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash(result.get('error', '비밀번호 변경에 실패했습니다.'), 'danger')
    
    return render_template('profile/change_password.html')