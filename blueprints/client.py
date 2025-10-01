"""
CLIENT 관리 블루프린트
CLIENT 설정 관리 기능을 담당합니다.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from user_manager import login_required, operator_required
import sqlite3
import sys
import os

# 상위 디렉토리의 모듈을 import하기 위한 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

client_bp = Blueprint('client', __name__)

# ========================
# CLIENT 관리 라우트
# ========================

@client_bp.route('/client')
@login_required
def client_list():
    """CLIENT 목록 조회"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        # CLIENT는 CS 테이블을 사용하되, 별도로 구분하여 표시
        client_items = conn.execute('SELECT * FROM cs ORDER BY idx').fetchall()
        conn.close()
        return render_template('client_list.html', client_items=client_items)
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return render_template('error.html', message=str(e))


@client_bp.route('/client/add', methods=['GET', 'POST'])
@operator_required  # operator 이상 권한 필요
def add_client():
    """CLIENT 추가"""
    from app import get_db_connection
    
    if request.method == 'POST':
        conn = get_db_connection()
        if conn is None:
            return render_template('error.html', message='데이터베이스 연결 실패')
        
        try:
            data = {
                'idx': request.form.get('idx', ''),
                'name': request.form.get('name', ''),
                'use': request.form.get('use', ''),
                'com_mode': request.form.get('com_mode', ''),
                'device': request.form.get('device', ''),
                'type': request.form.get('type', ''),
                'mode': request.form.get('mode', ''),
                'ip': request.form.get('ip', ''),
                'port': request.form.get('port', ''),
                'monitor': request.form.get('monitor', ''),
                'dv_no': request.form.get('dv_no', '')
            }
            
            sql = '''INSERT INTO cs (idx, name, use, com_mode, device, type, mode, ip, port, monitor, dv_no)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
            
            conn.execute(sql, tuple(data.values()))
            conn.commit()
            conn.close()
            
            flash('CLIENT가 성공적으로 추가되었습니다.', 'success')
            return redirect(url_for('client.client_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    return render_template('client_form.html', title='CLIENT 추가', action='add')


@client_bp.route('/client/edit/<int:idx>', methods=['GET', 'POST'])
@operator_required  # operator 이상 권한 필요
def edit_client(idx):
    """CLIENT 수정"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    if request.method == 'POST':
        try:
            data = {
                'idx': request.form.get('idx', ''),
                'name': request.form.get('name', ''),
                'use': request.form.get('use', ''),
                'com_mode': request.form.get('com_mode', ''),
                'device': request.form.get('device', ''),
                'type': request.form.get('type', ''),
                'mode': request.form.get('mode', ''),
                'ip': request.form.get('ip', ''),
                'port': request.form.get('port', ''),
                'monitor': request.form.get('monitor', ''),
                'dv_no': request.form.get('dv_no', '')
            }
            
            sql = '''UPDATE cs SET idx=?, name=?, use=?, com_mode=?, device=?, type=?, mode=?, ip=?, port=?, monitor=?, dv_no=?
                     WHERE idx=?'''
            
            values = list(data.values()) + [idx]
            conn.execute(sql, values)
            conn.commit()
            conn.close()
            
            flash('CLIENT가 성공적으로 수정되었습니다.', 'success')
            return redirect(url_for('client.client_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    try:
        client_item = conn.execute('SELECT * FROM cs WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        
        if client_item is None:
            flash('해당 CLIENT를 찾을 수 없습니다.', 'error')
            return redirect(url_for('client.client_list'))
        
        return render_template('client_form.html', title='CLIENT 수정', action='edit', client_item=client_item)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('client.client_list'))


@client_bp.route('/client/delete/<int:idx>', methods=['POST'])
@operator_required  # operator 이상 권한 필요
def delete_client(idx):
    """CLIENT 삭제"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '데이터베이스 연결 실패'})
    
    try:
        client_item = conn.execute('SELECT * FROM cs WHERE idx = ?', (idx,)).fetchone()
        if client_item is None:
            conn.close()
            return jsonify({'success': False, 'message': '해당 CLIENT를 찾을 수 없습니다.'})
        
        conn.execute('DELETE FROM cs WHERE idx = ?', (idx,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'CLIENT가 성공적으로 삭제되었습니다.'})
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'message': f'데이터베이스 오류: {e}'})


@client_bp.route('/client/view/<int:idx>')
@login_required
def view_client(idx):
    """CLIENT 상세 조회"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        client_item = conn.execute('SELECT * FROM cs WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        
        if client_item is None:
            flash('해당 CLIENT를 찾을 수 없습니다.', 'error')
            return redirect(url_for('client.client_list'))
        
        return render_template('client_view.html', client_item=client_item)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('client.client_list'))


# ========================
# 센서 대시보드 설정 (font_set 테이블 관리)
# ========================

@client_bp.route('/sensor-dashboard/font-settings')
@operator_required
def font_settings_list():
    """센서 대시보드 설정 (font_set 테이블) 목록 조회"""
    from app import get_db_connection, EXE_MODE

    # CLIENT 모드에서만 접근 가능
    if EXE_MODE != 'CLIENT':
        flash('이 기능은 CLIENT 모드에서만 사용 가능합니다.', 'error')
        return redirect(url_for('dashboard'))

    # 검색 조건 가져오기
    search_fcode = request.args.get('fcode', '').strip()
    search_fname = request.args.get('fname', '').strip()

    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')

    try:
        # 쿼리 생성
        query = '''
            SELECT fcode, fname, ftext, fsize, ffont, fstyle, fcolor, fbg
            FROM font_set
            WHERE 1=1
        '''
        params = []

        # fcode 검색 조건 추가
        if search_fcode:
            query += ' AND fcode LIKE ?'
            params.append(f'%{search_fcode}%')

        # fname 검색 조건 추가
        if search_fname:
            query += ' AND fname LIKE ?'
            params.append(f'%{search_fname}%')

        query += ' ORDER BY fcode'

        # font_set 테이블 조회
        font_items = conn.execute(query, params).fetchall()
        conn.close()

        return render_template('font_settings_list.html',
                             font_items=font_items,
                             search_fcode=search_fcode,
                             search_fname=search_fname)

    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return render_template('error.html', message=str(e))


@client_bp.route('/sensor-dashboard/font-settings/add', methods=['GET', 'POST'])
@operator_required
def add_font_settings():
    """센서 대시보드 설정 추가"""
    from app import get_db_connection, EXE_MODE

    # CLIENT 모드에서만 접근 가능
    if EXE_MODE != 'CLIENT':
        flash('이 기능은 CLIENT 모드에서만 사용 가능합니다.', 'error')
        return redirect(url_for('dashboard'))

    # 목록 페이지의 검색 조건 파라미터 가져오기
    search_fcode = request.args.get('search_fcode', '')
    search_fname = request.args.get('search_fname', '')
    
    if request.method == 'POST':
        conn = get_db_connection()
        if conn is None:
            return render_template('error.html', message='데이터베이스 연결 실패')
        
        try:
            fcode = request.form.get('fcode', '')
            fname = request.form.get('fname', '')
            
            # fcode와 fname 조합이 이미 존재하는지 확인
            existing = conn.execute('SELECT 1 FROM font_set WHERE fcode = ? AND fname = ?', (fcode, fname)).fetchone()
            if existing:
                conn.close()
                flash(f'동일한 코드({fcode})와 이름({fname}) 조합이 이미 존재합니다.', 'error')
                return render_template('font_settings_form.html', title='센서 대시보드 설정 추가', action='add',
                                     search_fcode=search_fcode, search_fname=search_fname)
            
            data = {
                'fcode': fcode,
                'fname': fname,
                'ftext': request.form.get('ftext', ''),
                'fsize': request.form.get('fsize', ''),
                'ffont': request.form.get('ffont', ''),
                'fstyle': request.form.get('fstyle', ''),
                'fcolor': request.form.get('fcolor', ''),
                'fbg': request.form.get('fbg', '')
            }
            
            sql = '''INSERT INTO font_set (fcode, fname, ftext, fsize, ffont, fstyle, fcolor, fbg)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)'''
            
            conn.execute(sql, tuple(data.values()))
            conn.commit()
            conn.close()
            
            flash('센서 대시보드 설정이 성공적으로 추가되었습니다.', 'success')
            # 검색 조건을 유지하면서 목록으로 돌아가기
            return redirect(url_for('client.font_settings_list', fcode=search_fcode, fname=search_fname))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    return render_template('font_settings_form.html', title='센서 대시보드 설정 추가', action='add',
                          search_fcode=search_fcode, search_fname=search_fname)


@client_bp.route('/sensor-dashboard/font-settings/edit/<fcode>/<fname>', methods=['GET', 'POST'])
@operator_required
def edit_font_settings(fcode, fname):
    """센서 대시보드 설정 수정"""
    from app import get_db_connection, EXE_MODE

    # CLIENT 모드에서만 접근 가능
    if EXE_MODE != 'CLIENT':
        flash('이 기능은 CLIENT 모드에서만 사용 가능합니다.', 'error')
        return redirect(url_for('dashboard'))

    # 목록 페이지의 검색 조건 파라미터 가져오기
    search_fcode = request.args.get('search_fcode', '')
    search_fname = request.args.get('search_fname', '')

    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    if request.method == 'POST':
        try:
            data = {
                'ftext': request.form.get('ftext', ''),
                'fsize': request.form.get('fsize', ''),
                'ffont': request.form.get('ffont', ''),
                'fstyle': request.form.get('fstyle', ''),
                'fcolor': request.form.get('fcolor', ''),
                'fbg': request.form.get('fbg', '')
            }
            
            sql = '''UPDATE font_set 
                     SET ftext=?, fsize=?, ffont=?, fstyle=?, fcolor=?, fbg=?
                     WHERE fcode=? AND fname=?'''
            
            values = list(data.values()) + [fcode, fname]
            conn.execute(sql, values)
            conn.commit()
            conn.close()
            
            flash('센서 대시보드 설정이 성공적으로 수정되었습니다.', 'success')
            # 검색 조건을 유지하면서 목록으로 돌아가기
            return redirect(url_for('client.font_settings_list', fcode=search_fcode, fname=search_fname))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    try:
        # 명시적으로 모든 컬럼 선택
        cursor = conn.execute('''
            SELECT fcode, fname, ftext, fsize, ffont, fstyle, fcolor, fbg 
            FROM font_set 
            WHERE fcode = ? AND fname = ?
        ''', (fcode, fname))
        font_item = cursor.fetchone()
        conn.close()
        
        if font_item is None:
            flash('해당 설정을 찾을 수 없습니다.', 'error')
            return redirect(url_for('client.font_settings_list'))
        
        # sqlite3.Row 객체를 딕셔너리로 변환 (템플릿에서 안전하게 접근하기 위해)
        font_item_dict = dict(font_item) if font_item else {}
        
        return render_template('font_settings_form.html',
                             title='센서 대시보드 설정 수정',
                             action='edit',
                             font_item=font_item_dict,
                             search_fcode=search_fcode,
                             search_fname=search_fname)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        # 검색 조건을 유지하면서 목록으로 돌아가기
        return redirect(url_for('client.font_settings_list', fcode=search_fcode, fname=search_fname))


@client_bp.route('/sensor-dashboard/font-settings/delete/<fcode>/<fname>', methods=['POST'])
@operator_required
def delete_font_settings(fcode, fname):
    """센서 대시보드 설정 삭제"""
    from app import get_db_connection, EXE_MODE
    
    # CLIENT 모드에서만 접근 가능
    if EXE_MODE != 'CLIENT':
        return jsonify({'success': False, 'message': '이 기능은 CLIENT 모드에서만 사용 가능합니다.'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '데이터베이스 연결 실패'})
    
    try:
        font_item = conn.execute('SELECT * FROM font_set WHERE fcode = ? AND fname = ?', (fcode, fname)).fetchone()
        if font_item is None:
            conn.close()
            return jsonify({'success': False, 'message': '해당 설정을 찾을 수 없습니다.'})
        
        conn.execute('DELETE FROM font_set WHERE fcode = ? AND fname = ?', (fcode, fname))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '센서 대시보드 설정이 성공적으로 삭제되었습니다.'})

    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'message': f'데이터베이스 오류: {e}'})


@client_bp.route('/client/refresh-browsers', methods=['POST'])
@operator_required
def refresh_browsers():
    """모든 센서 대시보드 브라우저에 리프레시 명령 전송"""
    import json
    import time
    from datetime import datetime

    try:
        # app 모듈에서 필요한 것들 import
        from app import broadcast_to_sse_clients, sse_clients

        # 디버깅용 로그
        print("[REFRESH] 브라우저 리프레시 요청 수신")
        print(f"[REFRESH] 현재 연결된 SSE 클라이언트 수: {len(sse_clients)}")

        # SSE를 통해 리프레시 이벤트 브로드캐스트
        refresh_event = json.dumps({
            'type': 'browser_refresh',
            'timestamp': time.time(),
            'message': '관리자가 브라우저 리프레시를 요청했습니다.'
        })

        # SSE 형식으로 이벤트 전송
        formatted_event = f"data: {refresh_event}\n\n"

        # broadcast_to_sse_clients 함수 사용
        broadcast_to_sse_clients(formatted_event, is_special=True)

        # 전송된 클라이언트 수 계산
        client_count = len(sse_clients)

        # 디버깅용 상세 로그
        print(f"[REFRESH] 리프레시 이벤트 전송 완료: {client_count}개 클라이언트")
        print(f"[REFRESH] 전송된 이벤트: {refresh_event}")

        # 로그 기록 (필요시 데이터베이스에 저장 가능)
        log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[REFRESH LOG] {log_time} - 브라우저 리프레시 명령 전송 (대상: {client_count}개 클라이언트)")

        return jsonify({
            'success': True,
            'message': f'리프레시 명령이 {client_count}개의 클라이언트에 전송되었습니다.',
            'client_count': client_count,
            'timestamp': time.time()
        })

    except Exception as e:
        print(f"[REFRESH ERROR] 브라우저 리프레시 오류: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'브라우저 리프레시 중 오류가 발생했습니다: {str(e)}'
        })