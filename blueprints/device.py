"""
디바이스 관리 블루프린트
device, cs, setting, setting2, led 테이블의 CRUD 기능을 담당합니다.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from user_manager import login_required, operator_required, admin_required
import sqlite3
import sys
import os

# 상위 디렉토리의 모듈을 import하기 위한 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

device_bp = Blueprint('device', __name__)

@device_bp.route('/devices')
@admin_required
def device_list():
    """디바이스 목록 조회"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        devices = conn.execute('SELECT * FROM device ORDER BY idx').fetchall()
        conn.close()
        return render_template('device_list.html', devices=devices)
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return render_template('error.html', message=str(e))


@device_bp.route('/device/add', methods=['GET', 'POST'])
@operator_required  # operator 이상 권한 필요
def add_device():
    """센서 추가"""
    from app import get_db_connection
    
    if request.method == 'POST':
        conn = get_db_connection()
        if conn is None:
            return render_template('error.html', message='데이터베이스 연결 실패')
        
        try:
            # 폼 데이터 수집
            data = {
                'name': request.form.get('name', ''),
                'use': request.form.get('use', ''),
                'type': request.form.get('type', ''),
                'mode': request.form.get('mode', ''),
                'port': request.form.get('port', ''),
                'delay': request.form.get('delay', ''),
                'save_sec': request.form.get('save_sec', ''),
                'point': request.form.get('point', ''),
                'math': request.form.get('math', ''),
                'good': request.form.get('good', ''),
                'normal': request.form.get('normal', ''),
                'warning': request.form.get('warning', ''),
                'danger': request.form.get('danger', ''),
                'option1': request.form.get('option1', ''),
                'option2': request.form.get('option2', ''),
                'option3': request.form.get('option3', ''),
                'option4': request.form.get('option4', ''),
                'option5': request.form.get('option5', ''),
                'option6': request.form.get('option6', ''),
                'option7': request.form.get('option7', ''),
                'option8': request.form.get('option8', ''),
                'option9': request.form.get('option9', ''),
                'option10': request.form.get('option10', '')
            }
            
            # 트랜잭션 시작
            conn.execute('BEGIN')
            
            # 사용유무가 'Y'로 설정되는 경우, 다른 모든 디바이스를 'N'으로 변경
            if data['use'] == 'Y':
                conn.execute('UPDATE device SET use = "N"')
            
            sql = '''INSERT INTO device 
                     (name, use, type, mode, port, delay, save_sec, point, math, good, normal, warning, danger,
                      option1, option2, option3, option4, option5, option6, option7, option8, option9, option10)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
            
            conn.execute(sql, tuple(data.values()))
            
            # 트랜잭션 커밋
            conn.commit()
            conn.close()
            
            if data['use'] == 'Y':
                flash(f'센서가 추가되고 활성화되었습니다. 다른 센서는 자동으로 비활성화되었습니다.', 'success')
            else:
                flash('센서가 성공적으로 추가되었습니다.', 'success')
            return redirect(url_for('device.device_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    return render_template('device_form.html', title='센서 추가', action='add')


@device_bp.route('/device/edit/<int:idx>', methods=['GET', 'POST'])
@operator_required  # operator 이상 권한 필요
def edit_device(idx):
    """센서 수정"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    if request.method == 'POST':
        try:
            # 폼 데이터 수집
            data = {
                'name': request.form.get('name', ''),
                'use': request.form.get('use', ''),
                'type': request.form.get('type', ''),
                'mode': request.form.get('mode', ''),
                'port': request.form.get('port', ''),
                'delay': request.form.get('delay', ''),
                'save_sec': request.form.get('save_sec', ''),
                'point': request.form.get('point', ''),
                'math': request.form.get('math', ''),
                'good': request.form.get('good', ''),
                'normal': request.form.get('normal', ''),
                'warning': request.form.get('warning', ''),
                'danger': request.form.get('danger', ''),
                'option1': request.form.get('option1', ''),
                'option2': request.form.get('option2', ''),
                'option3': request.form.get('option3', ''),
                'option4': request.form.get('option4', ''),
                'option5': request.form.get('option5', ''),
                'option6': request.form.get('option6', ''),
                'option7': request.form.get('option7', ''),
                'option8': request.form.get('option8', ''),
                'option9': request.form.get('option9', ''),
                'option10': request.form.get('option10', '')
            }
            
            # 트랜잭션 시작
            conn.execute('BEGIN')
            
            # 사용유무가 'Y'로 설정되는 경우, 다른 모든 디바이스를 'N'으로 변경
            if data['use'] == 'Y':
                conn.execute('UPDATE device SET use = "N" WHERE idx != ?', (idx,))
            
            sql = '''UPDATE device SET 
                     name=?, use=?, type=?, mode=?, port=?, delay=?, save_sec=?, point=?, math=?, 
                     good=?, normal=?, warning=?, danger=?, option1=?, option2=?, option3=?, option4=?, 
                     option5=?, option6=?, option7=?, option8=?, option9=?, option10=?
                     WHERE idx=?'''
            
            values = list(data.values()) + [idx]
            conn.execute(sql, values)
            
            # 트랜잭션 커밋
            conn.commit()
            conn.close()
            
            if data['use'] == 'Y':
                flash(f'센서가 활성화되었습니다. 다른 센서는 자동으로 비활성화되었습니다.', 'success')
            else:
                flash('센서가 성공적으로 수정되었습니다.', 'success')
            return redirect(url_for('device.device_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    # GET 요청 - 수정 폼 표시
    try:
        device = conn.execute('SELECT * FROM device WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        
        if device is None:
            flash('해당 센서를 찾을 수 없습니다.', 'error')
            return redirect(url_for('device.device_list'))
        
        return render_template('device_form.html', title='센서 수정', action='edit', device=device)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('device.device_list'))


@device_bp.route('/device/delete/<int:idx>', methods=['POST'])
@operator_required  # operator 이상 권한 필요
def delete_device(idx):
    """디바이스 삭제"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '데이터베이스 연결 실패'})
    
    try:
        # 먼저 해당 센서가 존재하는지 확인
        device = conn.execute('SELECT * FROM device WHERE idx = ?', (idx,)).fetchone()
        if device is None:
            conn.close()
            return jsonify({'success': False, 'message': '해당 센서를 찾을 수 없습니다.'})
        
        # 센서 삭제
        conn.execute('DELETE FROM device WHERE idx = ?', (idx,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '센서가 성공적으로 삭제되었습니다.'})
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'message': f'데이터베이스 오류: {e}'})


@device_bp.route('/device/view/<int:idx>')
@login_required
def view_device(idx):
    """디바이스 상세 조회"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        device = conn.execute('SELECT * FROM device WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        
        if device is None:
            flash('해당 센서를 찾을 수 없습니다.', 'error')
            return redirect(url_for('device.device_list'))
        
        return render_template('device_view.html', device=device)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('device.device_list'))


# CS 관련 기능들
@device_bp.route('/cs')
@admin_required
def cs_list():
    """CS 목록 조회"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        cs_items = conn.execute('SELECT * FROM cs ORDER BY idx').fetchall()
        conn.close()
        return render_template('cs_list.html', cs_items=cs_items)
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return render_template('error.html', message=str(e))


@device_bp.route('/cs/add', methods=['GET', 'POST'])
@operator_required  # operator 이상 권한 필요
def add_cs():
    """CS 추가"""
    from app import get_db_connection
    
    if request.method == 'POST':
        conn = get_db_connection()
        if conn is None:
            return render_template('error.html', message='데이터베이스 연결 실패')
        
        try:
            data = {
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

            # 트랜잭션 시작
            conn.execute('BEGIN')

            # 사용유무가 'Y'로 설정되는 경우, 다른 모든 CS를 'N'으로 변경
            if data['use'] == 'Y':
                conn.execute('UPDATE cs SET use = "N"')

            # idx 없이 INSERT (자동 증가)
            sql = '''INSERT INTO cs (name, use, com_mode, device, type, mode, ip, port, monitor, dv_no)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''

            conn.execute(sql, tuple(data.values()))
            
            # 트랜잭션 커밋
            conn.commit()
            conn.close()
            
            if data['use'] == 'Y':
                flash(f'CS가 추가되고 활성화되었습니다. 다른 CS는 자동으로 비활성화되었습니다.', 'success')
            else:
                flash('CS가 성공적으로 추가되었습니다.', 'success')
            return redirect(url_for('device.cs_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    return render_template('cs_form.html', title='CS 추가', action='add')


@device_bp.route('/cs/edit/<int:idx>', methods=['GET', 'POST'])
@operator_required  # operator 이상 권한 필요
def edit_cs(idx):
    """CS 수정"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    if request.method == 'POST':
        try:
            # idx는 자동 증가 필드이므로 UPDATE에서 제외
            data = {
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

            # 트랜잭션 시작
            conn.execute('BEGIN')

            # 사용유무가 'Y'로 설정되는 경우, 다른 모든 CS를 'N'으로 변경
            if data['use'] == 'Y':
                conn.execute('UPDATE cs SET use = "N" WHERE idx != ?', (idx,))

            # idx는 PRIMARY KEY이므로 변경하지 않음
            sql = '''UPDATE cs SET name=?, use=?, com_mode=?, device=?, type=?, mode=?, ip=?, port=?, monitor=?, dv_no=?
                     WHERE idx=?'''

            values = list(data.values()) + [idx]
            conn.execute(sql, values)
            
            # 트랜잭션 커밋
            conn.commit()
            conn.close()
            
            if data['use'] == 'Y':
                flash(f'CS가 활성화되었습니다. 다른 CS는 자동으로 비활성화되었습니다.', 'success')
            else:
                flash('CS가 성공적으로 수정되었습니다.', 'success')
            return redirect(url_for('device.cs_list'))
            
        except sqlite3.Error as e:
            conn.rollback()  # 오류 발생시 롤백
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
            return redirect(url_for('device.cs_list'))

    # GET 요청 처리
    try:
        cs_item = conn.execute('SELECT * FROM cs WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        
        if cs_item is None:
            flash('해당 CS를 찾을 수 없습니다.', 'error')
            return redirect(url_for('device.cs_list'))
        
        return render_template('cs_form.html', title='CS 수정', action='edit', cs_item=cs_item)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('device.cs_list'))


@device_bp.route('/cs/delete/<int:idx>', methods=['POST'])
@operator_required  # operator 이상 권한 필요
def delete_cs(idx):
    """CS 삭제"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '데이터베이스 연결 실패'})
    
    try:
        cs_item = conn.execute('SELECT * FROM cs WHERE idx = ?', (idx,)).fetchone()
        if cs_item is None:
            conn.close()
            return jsonify({'success': False, 'message': '해당 CS를 찾을 수 없습니다.'})
        
        conn.execute('DELETE FROM cs WHERE idx = ?', (idx,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'CS가 성공적으로 삭제되었습니다.'})
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'message': f'데이터베이스 오류: {e}'})


@device_bp.route('/cs/view/<int:idx>')
@login_required
def view_cs(idx):
    """CS 상세 조회"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        cs_item = conn.execute('SELECT * FROM cs WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        
        if cs_item is None:
            flash('해당 CS를 찾을 수 없습니다.', 'error')
            return redirect(url_for('device.cs_list'))
        
        return render_template('cs_view.html', cs_item=cs_item)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('device.cs_list'))


# Setting 관련 라우트들
@device_bp.route('/setting')
@admin_required
def setting_list():
    """setting 목록 조회"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        # rowid를 포함해서 조회
        settings = conn.execute('SELECT rowid, * FROM setting').fetchall()
        conn.close()
        return render_template('setting_list.html', settings=settings)
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return render_template('error.html', message=str(e))


@device_bp.route('/setting/add', methods=['GET', 'POST'])
@operator_required
def add_setting():
    """setting 추가 (기본 구현)"""
    if request.method == 'POST':
        flash('Setting 추가 기능이 구현되었습니다.', 'success')
        return redirect(url_for('device.setting_list'))
    
    return render_template('setting_form.html', title='Setting 추가', action='add')


@device_bp.route('/setting/edit/<int:rowid>', methods=['GET', 'POST'])
@operator_required
def edit_setting(rowid):
    """setting 수정 (rowid 기반)"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        if request.method == 'POST':
            # POST 요청 처리 - 설정 업데이트
            code = request.form.get('code', '')  # 현장구분 코드 추가
            dv_no = request.form.get('dv_no', '')
            mode = request.form.get('mode', '')
            sound = request.form.get('sound', '')
            siren_cnt = request.form.get('siren_cnt', '')
            log = request.form.get('log', '')
            log_del = request.form.get('log_del', '')
            send_data = request.form.get('send_data', '')
            reboot_time = request.form.get('reboot_time', '')
            debug = request.form.get('debug', '')
            monitor_use = request.form.get('monitor_use', '')

            # 데이터베이스 업데이트 (rowid 기반, code 필드 포함)
            conn.execute('''UPDATE setting SET
                code = ?, dv_no = ?, mode = ?, sound = ?, siren_cnt = ?, log = ?,
                log_del = ?, send_data = ?, reboot_time = ?, debug = ?, monitor_use = ?
                WHERE rowid = ?''',
                (code, dv_no, mode, sound, siren_cnt, log, log_del, send_data,
                 reboot_time, debug, monitor_use, rowid))
            conn.commit()
            conn.close()
            
            flash('Setting이 성공적으로 수정되었습니다.', 'success')
            return redirect(url_for('device.setting_list'))
            
        else:
            # GET 요청 처리 - 폼 표시 (rowid 기반)
            setting = conn.execute('SELECT rowid, * FROM setting WHERE rowid = ?', (rowid,)).fetchone()
            conn.close()

            if setting is None:
                flash('해당 설정을 찾을 수 없습니다.', 'error')
                return redirect(url_for('device.setting_list'))

            return render_template('setting_form.html', title='Setting 수정', action='edit', setting=setting)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('device.setting_list'))


@device_bp.route('/setting/delete/<code>', methods=['POST'])
@operator_required
def delete_setting(code):
    """setting 삭제"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '데이터베이스 연결 실패'})
    
    try:
        setting = conn.execute('SELECT * FROM setting WHERE code = ?', (code,)).fetchone()
        if setting is None:
            conn.close()
            return jsonify({'success': False, 'message': '해당 설정을 찾을 수 없습니다.'})
        
        conn.execute('DELETE FROM setting WHERE code = ?', (code,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Setting이 성공적으로 삭제되었습니다.'})
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'message': f'데이터베이스 오류: {e}'})


@device_bp.route('/setting/view/<int:rowid>')
@login_required
def view_setting(rowid):
    """setting 상세 조회 (rowid 기반)"""
    from app import get_db_connection

    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')

    try:
        setting = conn.execute('SELECT rowid, * FROM setting WHERE rowid = ?', (rowid,)).fetchone()
        conn.close()

        if setting is None:
            flash('해당 설정을 찾을 수 없습니다.', 'error')
            return redirect(url_for('device.setting_list'))

        return render_template('setting_view.html', setting=setting)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('device.setting_list'))


# Setting2, LED 관련 라우트들은 기본 구현으로 추가
@device_bp.route('/setting2')
@admin_required
def setting2_list():
    """setting2 목록 조회"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        setting2_items = conn.execute('SELECT rowid, * FROM setting2').fetchall()
        conn.close()
        return render_template('setting2_list.html', setting2_items=setting2_items)
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return render_template('error.html', message=str(e))


@device_bp.route('/setting2/add', methods=['GET', 'POST'])
@operator_required
def add_setting2():
    """setting2 추가"""
    if request.method == 'POST':
        flash('Setting2 추가 기능이 구현되었습니다.', 'success')
        return redirect(url_for('device.setting2_list'))
    return render_template('setting2_form.html', title='Setting2 추가', action='add')


@device_bp.route('/setting2/edit/<int:rowid>', methods=['GET', 'POST'])
@operator_required
def edit_setting2(rowid):
    """setting2 수정"""
    from app import get_db_connection
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')

    try:
        if request.method == 'POST':
            # POST 요청 처리 - 설정 업데이트
            width = request.form.get('width', '')
            height = request.form.get('height', '')
            col = request.form.get('col', '')
            row = request.form.get('row', '')
            multi = request.form.get('multi', '')
            mmonitor = request.form.get('mmonitor', '')
            rest = request.form.get('rest', '')
            op1 = request.form.get('op1', '')
            op2 = request.form.get('op2', '')
            op3 = request.form.get('op3', '')
            op4 = request.form.get('op4', '')
            op5 = request.form.get('op5', '')

            # 데이터베이스 업데이트
            conn.execute('''UPDATE setting2 SET
                width = ?, height = ?, col = ?, row = ?, multi = ?,
                mmonitor = ?, rest = ?, op1 = ?, op2 = ?, op3 = ?, op4 = ?, op5 = ?
                WHERE rowid = ?''',
                (width, height, col, row, multi, mmonitor, rest,
                 op1, op2, op3, op4, op5, rowid))
            conn.commit()
            conn.close()

            flash('Setting2가 성공적으로 수정되었습니다.', 'success')
            return redirect(url_for('device.setting2_list'))

        else:
            # GET 요청 처리 - 폼 표시
            setting = conn.execute('SELECT rowid, * FROM setting2 WHERE rowid = ?', (rowid,)).fetchone()
            conn.close()
            if setting is None:
                flash('해당 설정을 찾을 수 없습니다.', 'error')
                return redirect(url_for('device.setting2_list'))
            return render_template('setting2_form.html', title='Setting2 수정', action='edit', setting2_item=setting)
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('device.setting2_list'))


@device_bp.route('/setting2/delete/<int:rowid>', methods=['POST'])
@operator_required
def delete_setting2(rowid):
    """setting2 삭제"""
    from app import get_db_connection
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '데이터베이스 연결 실패'})
    
    try:
        setting = conn.execute('SELECT rowid, * FROM setting2 WHERE rowid = ?', (rowid,)).fetchone()
        if setting is None:
            conn.close()
            return jsonify({'success': False, 'message': '해당 설정을 찾을 수 없습니다.'})
        
        conn.execute('DELETE FROM setting2 WHERE rowid = ?', (rowid,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Setting2가 성공적으로 삭제되었습니다.'})
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'message': f'데이터베이스 오류: {e}'})


@device_bp.route('/setting2/view/<int:rowid>')
@login_required
def view_setting2(rowid):
    """setting2 상세 조회"""
    from app import get_db_connection
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    try:
        setting = conn.execute('SELECT rowid, * FROM setting2 WHERE rowid = ?', (rowid,)).fetchone()
        conn.close()
        if setting is None:
            flash('해당 설정을 찾을 수 없습니다.', 'error')
            return redirect(url_for('device.setting2_list'))
        return render_template('setting2_view.html', setting2_item=setting)
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('device.setting2_list'))


# LED 관련 라우트들
@device_bp.route('/led')
@admin_required
def led_list():
    """LED 목록 조회"""
    from app import get_db_connection
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    try:
        led_items = conn.execute('SELECT * FROM led ORDER BY idx').fetchall()
        conn.close()
        return render_template('led_list.html', led_items=led_items)
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return render_template('error.html', message=str(e))


@device_bp.route('/led/add', methods=['GET', 'POST'])
@operator_required
def add_led():
    """LED 추가"""
    from app import get_db_connection

    if request.method == 'POST':
        conn = get_db_connection()
        if conn is None:
            flash('데이터베이스 연결 실패', 'error')
            return redirect(url_for('device.led_list'))

        try:
            # 폼 데이터 수집
            type = request.form.get('type', '')
            use = request.form.get('use', '')
            mode = request.form.get('mode', '')
            port = request.form.get('port', '')
            display_sec = request.form.get('display_sec', '')

            # 라인1 설정
            line1_mode = request.form.get('line1_mode', '')
            line1_header = request.form.get('line1_header', '')
            line1_hcolor = request.form.get('line1_hcolor', '')
            line1_tail = request.form.get('line1_tail', '')
            line1_tcolor = request.form.get('line1_tcolor', '')
            line1_gcolor = request.form.get('line1_gcolor', '')
            line1_ncolor = request.form.get('line1_ncolor', '')
            line1_wcolor = request.form.get('line1_wcolor', '')
            line1_dcolor = request.form.get('line1_dcolor', '')
            line1_sec = request.form.get('line1_sec', '')
            line1_msg = request.form.get('line1_msg', '')
            line1_len = request.form.get('line1_len', '')
            line1_act = request.form.get('line1_act', '')

            # 라인2 설정
            line2_mode = request.form.get('line2_mode', '')
            line2_header = request.form.get('line2_header', '')
            line2_hcolor = request.form.get('line2_hcolor', '')
            line2_tail = request.form.get('line2_tail', '')
            line2_tcolor = request.form.get('line2_tcolor', '')
            line2_gcolor = request.form.get('line2_gcolor', '')
            line2_ncolor = request.form.get('line2_ncolor', '')
            line2_wcolor = request.form.get('line2_wcolor', '')
            line2_dcolor = request.form.get('line2_dcolor', '')
            line2_sec = request.form.get('line2_sec', '')
            line2_msg = request.form.get('line2_msg', '')
            line2_len = request.form.get('line2_len', '')
            line2_act = request.form.get('line2_act', '')

            # 광고 및 밝기 설정
            led_ad = request.form.get('led_ad', '')
            ad_sec = request.form.get('ad_sec', '')
            ad_intv = request.form.get('ad_intv', '')
            ad_line1 = request.form.get('ad_line1', '')
            ad_line2 = request.form.get('ad_line2', '')
            bright_start = request.form.get('bright_start', '')
            bright_end = request.form.get('bright_end', '')
            bright_max = request.form.get('bright_max', '')
            bright_min = request.form.get('bright_min', '')

            # 데이터베이스에 삽입
            conn.execute('''INSERT INTO led (
                type, use, mode, port, display_sec,
                line1_mode, line1_header, line1_hcolor, line1_tail, line1_tcolor,
                line1_gcolor, line1_ncolor, line1_wcolor, line1_dcolor,
                line1_sec, line1_msg, line1_len, line1_act,
                line2_mode, line2_header, line2_hcolor, line2_tail, line2_tcolor,
                line2_gcolor, line2_ncolor, line2_wcolor, line2_dcolor,
                line2_sec, line2_msg, line2_len, line2_act,
                led_ad, ad_sec, ad_intv, ad_line1, ad_line2,
                bright_start, bright_end, bright_max, bright_min
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (type, use, mode, port, display_sec,
                 line1_mode, line1_header, line1_hcolor, line1_tail, line1_tcolor,
                 line1_gcolor, line1_ncolor, line1_wcolor, line1_dcolor,
                 line1_sec, line1_msg, line1_len, line1_act,
                 line2_mode, line2_header, line2_hcolor, line2_tail, line2_tcolor,
                 line2_gcolor, line2_ncolor, line2_wcolor, line2_dcolor,
                 line2_sec, line2_msg, line2_len, line2_act,
                 led_ad, ad_sec, ad_intv, ad_line1, ad_line2,
                 bright_start, bright_end, bright_max, bright_min))
            conn.commit()
            conn.close()

            flash('전광판이 성공적으로 추가되었습니다.', 'success')
            return redirect(url_for('device.led_list'))

        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
            return redirect(url_for('device.led_list'))

    return render_template('led_form.html', title='전광판 추가', action='add')


@device_bp.route('/led/edit/<int:idx>', methods=['GET', 'POST'])
@operator_required
def edit_led(idx):
    """LED 수정"""
    from app import get_db_connection
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')

    try:
        if request.method == 'POST':
            # POST 요청 처리 - 데이터 업데이트
            type = request.form.get('type', '')
            use = request.form.get('use', '')
            mode = request.form.get('mode', '')
            port = request.form.get('port', '')
            display_sec = request.form.get('display_sec', '')

            # 라인1 설정
            line1_mode = request.form.get('line1_mode', '')
            line1_header = request.form.get('line1_header', '')
            line1_hcolor = request.form.get('line1_hcolor', '')
            line1_tail = request.form.get('line1_tail', '')
            line1_tcolor = request.form.get('line1_tcolor', '')
            line1_gcolor = request.form.get('line1_gcolor', '')
            line1_ncolor = request.form.get('line1_ncolor', '')
            line1_wcolor = request.form.get('line1_wcolor', '')
            line1_dcolor = request.form.get('line1_dcolor', '')
            line1_sec = request.form.get('line1_sec', '')
            line1_msg = request.form.get('line1_msg', '')
            line1_len = request.form.get('line1_len', '')
            line1_act = request.form.get('line1_act', '')

            # 라인2 설정
            line2_mode = request.form.get('line2_mode', '')
            line2_header = request.form.get('line2_header', '')
            line2_hcolor = request.form.get('line2_hcolor', '')
            line2_tail = request.form.get('line2_tail', '')
            line2_tcolor = request.form.get('line2_tcolor', '')
            line2_gcolor = request.form.get('line2_gcolor', '')
            line2_ncolor = request.form.get('line2_ncolor', '')
            line2_wcolor = request.form.get('line2_wcolor', '')
            line2_dcolor = request.form.get('line2_dcolor', '')
            line2_sec = request.form.get('line2_sec', '')
            line2_msg = request.form.get('line2_msg', '')
            line2_len = request.form.get('line2_len', '')
            line2_act = request.form.get('line2_act', '')

            # 광고 및 밝기 설정
            led_ad = request.form.get('led_ad', '')
            ad_sec = request.form.get('ad_sec', '')
            ad_intv = request.form.get('ad_intv', '')
            ad_line1 = request.form.get('ad_line1', '')
            ad_line2 = request.form.get('ad_line2', '')
            bright_start = request.form.get('bright_start', '')
            bright_end = request.form.get('bright_end', '')
            bright_max = request.form.get('bright_max', '')
            bright_min = request.form.get('bright_min', '')

            # 데이터베이스 업데이트
            conn.execute('''UPDATE led SET
                type = ?, use = ?, mode = ?, port = ?, display_sec = ?,
                line1_mode = ?, line1_header = ?, line1_hcolor = ?, line1_tail = ?, line1_tcolor = ?,
                line1_gcolor = ?, line1_ncolor = ?, line1_wcolor = ?, line1_dcolor = ?,
                line1_sec = ?, line1_msg = ?, line1_len = ?, line1_act = ?,
                line2_mode = ?, line2_header = ?, line2_hcolor = ?, line2_tail = ?, line2_tcolor = ?,
                line2_gcolor = ?, line2_ncolor = ?, line2_wcolor = ?, line2_dcolor = ?,
                line2_sec = ?, line2_msg = ?, line2_len = ?, line2_act = ?,
                led_ad = ?, ad_sec = ?, ad_intv = ?, ad_line1 = ?, ad_line2 = ?,
                bright_start = ?, bright_end = ?, bright_max = ?, bright_min = ?
                WHERE idx = ?''',
                (type, use, mode, port, display_sec,
                 line1_mode, line1_header, line1_hcolor, line1_tail, line1_tcolor,
                 line1_gcolor, line1_ncolor, line1_wcolor, line1_dcolor,
                 line1_sec, line1_msg, line1_len, line1_act,
                 line2_mode, line2_header, line2_hcolor, line2_tail, line2_tcolor,
                 line2_gcolor, line2_ncolor, line2_wcolor, line2_dcolor,
                 line2_sec, line2_msg, line2_len, line2_act,
                 led_ad, ad_sec, ad_intv, ad_line1, ad_line2,
                 bright_start, bright_end, bright_max, bright_min, idx))
            conn.commit()
            conn.close()

            flash('전광판이 성공적으로 수정되었습니다.', 'success')
            return redirect(url_for('device.led_list'))

        else:
            # GET 요청 처리 - 폼 표시
            led_item = conn.execute('SELECT * FROM led WHERE idx = ?', (idx,)).fetchone()
            conn.close()
            if led_item is None:
                flash('해당 전광판을 찾을 수 없습니다.', 'error')
                return redirect(url_for('device.led_list'))
            return render_template('led_form.html', title='전광판 수정', action='edit', led_item=led_item)
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('device.led_list'))


@device_bp.route('/led/delete/<int:idx>', methods=['POST'])
@operator_required
def delete_led(idx):
    """LED 삭제"""
    from app import get_db_connection
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '데이터베이스 연결 실패'})
    
    try:
        led_item = conn.execute('SELECT * FROM led WHERE idx = ?', (idx,)).fetchone()
        if led_item is None:
            conn.close()
            return jsonify({'success': False, 'message': '해당 LED를 찾을 수 없습니다.'})
        
        conn.execute('DELETE FROM led WHERE idx = ?', (idx,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'LED가 성공적으로 삭제되었습니다.'})
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'message': f'데이터베이스 오류: {e}'})


@device_bp.route('/led/view/<int:idx>')
@login_required
def view_led(idx):
    """LED 상세 조회"""
    from app import get_db_connection
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    try:
        led_item = conn.execute('SELECT * FROM led WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        if led_item is None:
            flash('해당 LED를 찾을 수 없습니다.', 'error')
            return redirect(url_for('device.led_list'))
        return render_template('led_view.html', led_item=led_item)
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('device.led_list'))