
# pip install flask

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
import queue
import sqlite3
import os
import sys
import json
import subprocess
import re
from datetime import datetime
import socket
import threading
import time
from functools import wraps
from system_monitor import get_system_status
from dotenv import load_dotenv

from user_manager import UserManager, login_required, permission_required, admin_required, operator_required
from config_manager import ConfigManager


# .env 파일 로드
load_dotenv()

# PyInstaller 빌드 환경 확인 및 경로 설정
if getattr(sys, 'frozen', False):
    # 빌드된 실행 파일인 경우
    application_path = os.path.dirname(sys.executable)
    template_folder = os.path.join(application_path, 'templates')
    static_folder = os.path.join(application_path, 'static')
else:
    # 개발 환경인 경우
    application_path = os.path.dirname(__file__)
    template_folder = 'templates'
    static_folder = 'static'

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)

# .env 파일에서 DATABASE_PATH와 DATABASE_DB 읽기
db_path = os.getenv('DATABASE_PATH', './')
db_name = os.getenv('DATABASE_DB', 'sensor.db')
database_full_path = os.path.join(db_path, db_name)

# 설정 관리자 초기화 (데이터베이스 전용)
config_manager = ConfigManager(db_path=database_full_path)
config = config_manager.get_config()  # 데이터베이스에서만 로드

# 사용자 관리자 초기화
user_manager = UserManager(db_path=database_full_path)

# TCP 소켓 클라이언트 설정
TCP_HOST = config.get('socketserver', {}).get('TCP_HOST', '127.0.0.1')
TCP_PORT = config.get('socketserver', {}).get('TCP_PORT', 3000)

# Flask 앱 설정
app.secret_key = config.get('security', {}).get('secret_key', 'itlog@secret#key$production')

# 블루프린트 등록
from blueprints import register_blueprints
register_blueprints(app)

# 권한 체크 헬퍼 함수
def check_permission(required_level):
    """사용자 권한 확인 헬퍼"""
    user_permission = session.get('permission', 'viewer')
    permission_levels = {
        'viewer': 1,
        'operator': 2,
        'admin': 3
    }
    user_level = permission_levels.get(user_permission, 0)
    required = permission_levels.get(required_level, 999)
    return user_level >= required

# 템플릿에서 사용할 수 있도록 전역 함수로 등록
app.jinja_env.globals['check_permission'] = check_permission

# 데이터베이스 경로 (기존 변수명 호환성 유지)
DB_PATH = db_path
DB_NAME = db_name
DATABASE_PATH = database_full_path

# 로그인 정보 (이전 버전 호환성용 - 실제로는 user_manager 사용)
LOGIN_CREDENTIALS = {
    'username': config.get('authentication', {}).get('username', 'admin'),
    'password': config.get('authentication', {}).get('password', 'admin1234')
}


# 센서 설정 관련 변수
_sensor_config_lock = threading.RLock()  # 재진입 가능한 락
_cached_sensor_config = None
_config_cache_time = None
_config_cache_duration = 5  # 5초간 캐시 유지

# 센서 설정 로드 함수 (스레드 안전, 캐시 기능 포함)
def load_sensor_config():
    """config_sensor.json 파일에서 센서 설정을 로드합니다. (캐시 및 스레드 안전)"""
    global _cached_sensor_config, _config_cache_time
    
    with _sensor_config_lock:
        # 캐시가 유효한지 확인
        current_time = time.time()
        if (_cached_sensor_config is not None and 
            _config_cache_time is not None and 
            (current_time - _config_cache_time) < _config_cache_duration):
            return _cached_sensor_config.copy()  # 딕셔너리 복사본 반환
        
        # 캐시가 없거나 만료된 경우 파일에서 로드
        try:
            # PyInstaller 빌드 시 실행 파일과 같은 디렉토리에서 config_sensor.json 찾기
            if getattr(sys, 'frozen', False):
                # 빌드된 실행 파일인 경우
                base_path = os.path.dirname(sys.executable)
            else:
                # 개발 환경인 경우
                base_path = os.path.dirname(__file__)
            
            config_path = os.path.join(base_path, 'config_sensor.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                
            # 캐시 업데이트
            _cached_sensor_config = config_data
            _config_cache_time = current_time
            
            return config_data.copy()  # 딕셔너리 복사본 반환
            
        except FileNotFoundError:
            print("경고: config_sensor.json 파일을 찾을 수 없습니다. 기본값을 사용합니다.")
            return {}
        except json.JSONDecodeError as e:
            print(f"경고: config_sensor.json 파일 파싱 오류: {e}. 기본값을 사용합니다.")
            return {}
        except Exception as e:
            print(f"경고: config_sensor.json 파일 읽기 오류: {e}. 기본값을 사용합니다.")
            return {}

# 캐시 강제 새로고침 함수
def refresh_sensor_config_cache():
    """센서 설정 캐시를 강제로 새로고침합니다."""
    global _cached_sensor_config, _config_cache_time
    
    with _sensor_config_lock:
        _cached_sensor_config = None
        _config_cache_time = None
        return load_sensor_config()

# 전역 센서 설정 변수
SENSOR_CONFIGS = load_sensor_config()


# TCP 소켓 클라이언트 설정 (데이터베이스에서 로드됨)

latest_sensor_data = {}
tcp_client = None
tcp_connected = False
sse_clients = set()  # SSE 클라이언트 목록

def tcp_client_thread():
    """TCP 클라이언트 스레드"""
    global tcp_client, tcp_connected, latest_sensor_data
    
    while True:
        try:
            if not tcp_connected:
                tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_client.connect((TCP_HOST, TCP_PORT))
                tcp_connected = True
                print(f"TCP: {TCP_HOST}:{TCP_PORT}에 연결되었습니다.")
                
                # SSE 클라이언트들에게 연결 상태 알림
                connection_msg = json.dumps({'type': 'connection', 'connected': True})
                broadcast_to_sse_clients(f"data: {connection_msg}\n\n", is_special=True)
                
                # ON 메시지 전송
                tcp_client.send(b'ON')
                print("TCP: ON 메시지 전송")
            
            # 데이터 수신
            data = tcp_client.recv(1024)
            if data:
                received_data = data.decode('utf-8').strip()
                print(f"TCP: 받은 데이터: {received_data}")
                
                # 데이터 파싱 및 저장
                if received_data.endswith('|ON'):
                    print("TCP: ON 응답 받음")
                else:
                    # 센서 데이터 저장
                    parts = received_data.split('|')
                    if len(parts) >= 3:
                        device_id = parts[0]
                        sensor_type = parts[1]
                        latest_sensor_data[sensor_type] = {
                            'device_id': device_id,
                            'sensor_type': sensor_type,
                            'data': received_data,
                            'timestamp': time.time()
                        }
                        
                        # SSE 클라이언트들에게 브로드캐스트
                        broadcast_to_sse_clients(f"data: {received_data}\n\n")
            else:
                # 연결 끊김
                if tcp_connected:  # 이전에 연결되어 있었다면 알림
                    disconnection_msg = json.dumps({'type': 'connection', 'connected': False})
                    broadcast_to_sse_clients(f"data: {disconnection_msg}\n\n", is_special=True)
                
                tcp_connected = False
                tcp_client.close()
                print("TCP: 연결이 끊어졌습니다.")
                
        except Exception as e:
            print(f"TCP 오류: {e}")
            if tcp_connected:  # 이전에 연결되어 있었다면 알림
                disconnection_msg = json.dumps({'type': 'connection', 'connected': False})
                broadcast_to_sse_clients(f"data: {disconnection_msg}\n\n", is_special=True)
            
            tcp_connected = False
            if tcp_client:
                tcp_client.close()
            time.sleep(5)  # 5초 후 재연결 시도

def broadcast_to_sse_clients(data, is_special=False):
    """SSE 클라이언트들에게 데이터 브로드캐스트"""
    global sse_clients
    disconnected_clients = set()
    
    # 데이터 형식 조정
    if is_special:
        # 이미 포맷된 특수 메시지 (연결 상태 등)
        formatted_data = data
    else:
        # 일반 센서 데이터
        if not data.startswith("data: "):
            formatted_data = f"data: {data}\n\n"
        else:
            formatted_data = data
    
    for client in sse_clients.copy():
        try:
            client.put(formatted_data)
        except:
            disconnected_clients.add(client)
    
    # 연결이 끊어진 클라이언트 제거
    sse_clients -= disconnected_clients

# TCP 클라이언트 스레드 시작
tcp_thread = threading.Thread(target=tcp_client_thread, daemon=True)
tcp_thread.start()




def login_required(f):
    """로그인 필요 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    """데이터베이스 연결을 반환합니다."""
    try:
        conn = sqlite3.connect(database_full_path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        flash(f'데이터베이스 연결 오류: {e}', 'error')
        return None


def check_table_exists(table_name, conn=None):
    """테이블 존재 여부를 확인합니다."""
    if conn is None:
        conn = get_db_connection()
        if conn is None:
            return False
        should_close = True
    else:
        should_close = False
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        result = cursor.fetchone()
        return result is not None
    except sqlite3.Error:
        return False
    finally:
        if should_close:
            conn.close()


@app.route('/')
def index():
    """메인 페이지 - 로그인된 경우 대시보드로 리다이렉트"""
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """대시보드 페이지 - 시스템 모니터링 상태 표시"""
    try:
        # 시스템 상태 정보 가져오기
        system_info = get_system_status()
        
        return render_template('dashboard.html', system_info=system_info)
    except Exception as e:
        flash(f'대시보드 로딩 중 오류: {e}', 'error')
        return render_template('dashboard.html', system_info=None)

# API 라우트들은 api 블루프린트로 이동됨



# 로그인, 로그아웃 라우트는 auth 블루프린트로 이동됨

# 디바이스 관련 라우트들은 device 블루프린트로 이동됨
    """디바이스 목록 조회"""
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


@app.route('/device/add', methods=['GET', 'POST'])
@operator_required  # operator 이상 권한 필요
def add_device():
    """디바이스 추가"""
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
                flash(f'디바이스가 추가되고 활성화되었습니다. 다른 디바이스는 자동으로 비활성화되었습니다.', 'success')
            else:
                flash('디바이스가 성공적으로 추가되었습니다.', 'success')
            return redirect(url_for('device_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    return render_template('device_form.html', title='디바이스 추가', action='add')


@app.route('/device/edit/<int:idx>', methods=['GET', 'POST'])
@operator_required  # operator 이상 권한 필요
def edit_device(idx):
    """디바이스 수정"""
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
                flash(f'디바이스가 활성화되었습니다. 다른 디바이스는 자동으로 비활성화되었습니다.', 'success')
            else:
                flash('디바이스가 성공적으로 수정되었습니다.', 'success')
            return redirect(url_for('device_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    # GET 요청 - 수정 폼 표시
    try:
        device = conn.execute('SELECT * FROM device WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        
        if device is None:
            flash('해당 디바이스를 찾을 수 없습니다.', 'error')
            return redirect(url_for('device_list'))
        
        return render_template('device_form.html', title='디바이스 수정', action='edit', device=device)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('device_list'))


@app.route('/device/delete/<int:idx>', methods=['POST'])
@operator_required  # operator 이상 권한 필요
def delete_device(idx):
    """디바이스 삭제"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '데이터베이스 연결 실패'})
    
    try:
        # 먼저 해당 디바이스가 존재하는지 확인
        device = conn.execute('SELECT * FROM device WHERE idx = ?', (idx,)).fetchone()
        if device is None:
            conn.close()
            return jsonify({'success': False, 'message': '해당 디바이스를 찾을 수 없습니다.'})
        
        # 디바이스 삭제
        conn.execute('DELETE FROM device WHERE idx = ?', (idx,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '디바이스가 성공적으로 삭제되었습니다.'})
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'message': f'데이터베이스 오류: {e}'})


@app.route('/device/view/<int:idx>')
@login_required
def view_device(idx):
    """디바이스 상세 조회"""
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        device = conn.execute('SELECT * FROM device WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        
        if device is None:
            flash('해당 디바이스를 찾을 수 없습니다.', 'error')
            return redirect(url_for('device_list'))
        
        return render_template('device_view.html', device=device)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('device_list'))

# CS 설정 관련 라우트
@app.route('/cs')
@login_required
def cs_list():
    """CS 목록 조회"""
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

@app.route('/cs/add', methods=['GET', 'POST'])
@operator_required  # operator 이상 권한 필요
def add_cs():
    """CS 추가"""
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
            
            # 트랜잭션 시작
            conn.execute('BEGIN')
            
            # 사용유무가 'Y'로 설정되는 경우, 다른 모든 CS를 'N'으로 변경
            if data['use'] == 'Y':
                conn.execute('UPDATE cs SET use = "N"')
            
            sql = '''INSERT INTO cs (idx, name, use, com_mode, device, type, mode, ip, port, monitor, dv_no)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
            
            conn.execute(sql, tuple(data.values()))
            
            # 트랜잭션 커밋
            conn.commit()
            conn.close()
            
            if data['use'] == 'Y':
                flash(f'CS가 추가되고 활성화되었습니다. 다른 CS는 자동으로 비활성화되었습니다.', 'success')
            else:
                flash('CS가 성공적으로 추가되었습니다.', 'success')
            return redirect(url_for('cs_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    return render_template('cs_form.html', title='CS 추가', action='add')

@app.route('/cs/edit/<int:idx>', methods=['GET', 'POST'])
@operator_required  # operator 이상 권한 필요
def edit_cs(idx):
    """CS 수정"""
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
            
            # 트랜잭션 시작
            conn.execute('BEGIN')
            
            # 사용유무가 'Y'로 설정되는 경우, 다른 모든 CS를 'N'으로 변경
            if data['use'] == 'Y':
                conn.execute('UPDATE cs SET use = "N" WHERE idx != ?', (idx,))
            
            sql = '''UPDATE cs SET idx=?, name=?, use=?, com_mode=?, device=?, type=?, mode=?, ip=?, port=?, monitor=?, dv_no=?
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
            return redirect(url_for('cs_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    try:
        cs_item = conn.execute('SELECT * FROM cs WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        
        if cs_item is None:
            flash('해당 CS를 찾을 수 없습니다.', 'error')
            return redirect(url_for('cs_list'))
        
        return render_template('cs_form.html', title='CS 수정', action='edit', cs_item=cs_item)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('cs_list'))

@app.route('/cs/delete/<int:idx>', methods=['POST'])
@operator_required  # operator 이상 권한 필요
def delete_cs(idx):
    """CS 삭제"""
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

@app.route('/cs/view/<int:idx>')
@login_required
def view_cs(idx):
    """CS 상세 조회"""
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        cs_item = conn.execute('SELECT * FROM cs WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        
        if cs_item is None:
            flash('해당 CS를 찾을 수 없습니다.', 'error')
            return redirect(url_for('cs_list'))
        
        return render_template('cs_view.html', cs_item=cs_item)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('cs_list'))

# setting 설정 관련 라우트
@app.route('/setting')
@login_required
def setting_list():
    """setting 목록 조회"""
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        settings = conn.execute('SELECT * FROM setting').fetchall()
        conn.close()
        return render_template('setting_list.html', settings=settings)
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return render_template('error.html', message=str(e))

@app.route('/setting/add', methods=['GET', 'POST'])
@operator_required
def add_setting():
    """setting 추가"""
    if request.method == 'POST':
        conn = get_db_connection()
        if conn is None:
            return render_template('error.html', message='데이터베이스 연결 실패')
        
        try:
            data = {
                'code': request.form.get('code', ''),
                'dv_no': request.form.get('dv_no', ''),
                'mode': request.form.get('mode', ''),
                'sound': request.form.get('sound', ''),
                'siren_cnt': request.form.get('siren_cnt', ''),
                'log': request.form.get('log', ''),
                'log_del': request.form.get('log_del', ''),
                'send_data': request.form.get('send_data', ''),
                'reboot_time': request.form.get('reboot_time', ''),
                'debug': request.form.get('debug', ''),
                'monitor_use': request.form.get('monitor_use', '')
            }
            
            sql = '''INSERT INTO setting (code, dv_no, mode, sound, siren_cnt, log, log_del, send_data, reboot_time, debug, monitor_use)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
            
            conn.execute(sql, tuple(data.values()))
            conn.commit()
            conn.close()
            
            flash('setting이 성공적으로 추가되었습니다.', 'success')
            return redirect(url_for('setting_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    return render_template('setting_form.html', title='setting 추가', action='add')

@app.route('/setting/edit/<code>', methods=['GET', 'POST'])
@operator_required
def edit_setting(code):
    """setting 수정"""
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    if request.method == 'POST':
        try:
            data = {
                'code': request.form.get('code', ''),
                'dv_no': request.form.get('dv_no', ''),
                'mode': request.form.get('mode', ''),
                'sound': request.form.get('sound', ''),
                'siren_cnt': request.form.get('siren_cnt', ''),
                'log': request.form.get('log', ''),
                'log_del': request.form.get('log_del', ''),
                'send_data': request.form.get('send_data', ''),
                'reboot_time': request.form.get('reboot_time', ''),
                'debug': request.form.get('debug', ''),
                'monitor_use': request.form.get('monitor_use', '')
            }
            
            sql = '''UPDATE setting SET code=?, dv_no=?, mode=?, sound=?, siren_cnt=?, log=?, log_del=?, send_data=?, reboot_time=?, debug=?, monitor_use=?
                     WHERE code=?'''
            
            values = list(data.values()) + [code]
            conn.execute(sql, values)
            conn.commit()
            conn.close()
            
            flash('setting이 성공적으로 수정되었습니다.', 'success')
            return redirect(url_for('setting_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    try:
        setting = conn.execute('SELECT * FROM setting WHERE code = ?', (code,)).fetchone()
        conn.close()
        
        if setting is None:
            flash('해당 setting을 찾을 수 없습니다.', 'error')
            return redirect(url_for('setting_list'))
        
        return render_template('setting_form.html', title='setting 수정', action='edit', setting=setting)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('setting_list'))

@app.route('/setting/delete/<code>', methods=['POST'])
@operator_required
def delete_setting(code):
    """setting 삭제"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '데이터베이스 연결 실패'})
    
    try:
        setting = conn.execute('SELECT * FROM setting WHERE code = ?', (code,)).fetchone()
        if setting is None:
            conn.close()
            return jsonify({'success': False, 'message': '해당 setting을 찾을 수 없습니다.'})
        
        conn.execute('DELETE FROM setting WHERE code = ?', (code,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'setting이 성공적으로 삭제되었습니다.'})
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'message': f'데이터베이스 오류: {e}'})

@app.route('/setting/view/<code>')
@login_required
def view_setting(code):
    """setting 상세 조회"""
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        setting = conn.execute('SELECT * FROM setting WHERE code = ?', (code,)).fetchone()
        conn.close()
        
        if setting is None:
            flash('해당 setting을 찾을 수 없습니다.', 'error')
            return redirect(url_for('setting_list'))
        
        return render_template('setting_view.html', setting=setting)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('setting_list'))

# setting2 설정 관련 라우트
@app.route('/setting2')
@login_required
def setting2_list():
    """setting2 목록 조회"""
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

@app.route('/setting2/add', methods=['GET', 'POST'])
@operator_required
def add_setting2():
    """setting2 추가"""
    if request.method == 'POST':
        conn = get_db_connection()
        if conn is None:
            return render_template('error.html', message='데이터베이스 연결 실패')
        
        try:
            data = {
                'width': request.form.get('width', ''),
                'height': request.form.get('height', ''),
                'col': request.form.get('col', ''),
                'row': request.form.get('row', ''),
                'multi': request.form.get('multi', ''),
                'mmonitor': request.form.get('mmonitor', ''),
                'rest': request.form.get('rest', ''),
                'op1': request.form.get('op1', ''),
                'op2': request.form.get('op2', ''),
                'op3': request.form.get('op3', ''),
                'op4': request.form.get('op4', ''),
                'op5': request.form.get('op5', '')
            }
            
            sql = '''INSERT INTO setting2 (width, height, col, row, multi, mmonitor, rest, op1, op2, op3, op4, op5)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
            
            conn.execute(sql, tuple(data.values()))
            conn.commit()
            conn.close()
            
            flash('setting2가 성공적으로 추가되었습니다.', 'success')
            return redirect(url_for('setting2_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    return render_template('setting2_form.html', title='setting2 추가', action='add')

@app.route('/setting2/edit/<int:rowid>', methods=['GET', 'POST'])
@operator_required
def edit_setting2(rowid):
    """setting2 수정"""
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    if request.method == 'POST':
        try:
            data = {
                'width': request.form.get('width', ''),
                'height': request.form.get('height', ''),
                'col': request.form.get('col', ''),
                'row': request.form.get('row', ''),
                'multi': request.form.get('multi', ''),
                'mmonitor': request.form.get('mmonitor', ''),
                'rest': request.form.get('rest', ''),
                'op1': request.form.get('op1', ''),
                'op2': request.form.get('op2', ''),
                'op3': request.form.get('op3', ''),
                'op4': request.form.get('op4', ''),
                'op5': request.form.get('op5', '')
            }
            
            sql = '''UPDATE setting2 SET width=?, height=?, col=?, row=?, multi=?, mmonitor=?, rest=?, op1=?, op2=?, op3=?, op4=?, op5=?
                     WHERE rowid=?'''
            
            values = list(data.values()) + [rowid]
            conn.execute(sql, values)
            conn.commit()
            conn.close()
            
            flash('setting2가 성공적으로 수정되었습니다.', 'success')
            return redirect(url_for('setting2_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    try:
        setting2_item = conn.execute('SELECT rowid, * FROM setting2 WHERE rowid = ?', (rowid,)).fetchone()
        conn.close()
        
        if setting2_item is None:
            flash('해당 setting2를 찾을 수 없습니다.', 'error')
            return redirect(url_for('setting2_list'))
        
        return render_template('setting2_form.html', title='setting2 수정', action='edit', setting2_item=setting2_item)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('setting2_list'))

@app.route('/setting2/delete/<int:rowid>', methods=['POST'])
@operator_required
def delete_setting2(rowid):
    """setting2 삭제"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '데이터베이스 연결 실패'})
    
    try:
        conn.execute('DELETE FROM setting2 WHERE rowid = ?', (rowid,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'setting2가 성공적으로 삭제되었습니다.'})
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'message': f'데이터베이스 오류: {e}'})

@app.route('/setting2/view/<int:rowid>')
@login_required
def view_setting2(rowid):
    """setting2 상세 조회"""
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        setting2_item = conn.execute('SELECT rowid, * FROM setting2 WHERE rowid = ?', (rowid,)).fetchone()
        conn.close()
        
        if setting2_item is None:
            flash('해당 setting2를 찾을 수 없습니다.', 'error')
            return redirect(url_for('setting2_list'))
        
        return render_template('setting2_view.html', setting2_item=setting2_item)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('setting2_list'))

# led 설정 관련 라우트
@app.route('/led')
@login_required
def led_list():
    """LED 목록 조회"""
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

@app.route('/led/add', methods=['GET', 'POST'])
@operator_required
def add_led():
    """LED 추가"""
    if request.method == 'POST':
        conn = get_db_connection()
        if conn is None:
            return render_template('error.html', message='데이터베이스 연결 실패')
        
        try:
            # LED 테이블의 모든 필드 처리
            data = {}
            led_fields = ['type', 'mode', 'port', 'use', 'display_sec', 'line1_mode', 'line1_header', 
                         'line1_hcolor', 'line1_tail', 'line1_tcolor', 'line1_gcolor', 'line1_ncolor', 
                         'line1_wcolor', 'line1_dcolor', 'line1_sec', 'line1_msg', 'line1_len', 'line1_act',
                         'line2_mode', 'line2_header', 'line2_hcolor', 'line2_tail', 'line2_tcolor', 
                         'line2_gcolor', 'line2_ncolor', 'line2_wcolor', 'line2_dcolor', 'line2_sec', 
                         'line2_msg', 'line2_len', 'line2_act', 'led_ad', 'ad_sec', 'ad_intv', 'ad_line1', 
                         'ad_line2', 'bright_start', 'bright_end', 'bright_max', 'bright_min']
            
            for field in led_fields:
                data[field] = request.form.get(field, '')
            
            # 트랜잭션 시작
            conn.execute('BEGIN')
            
            # 사용유무가 'Y'로 설정되는 경우, 다른 모든 LED를 'N'으로 변경
            if data.get('use') == 'Y':
                conn.execute('UPDATE led SET use = "N"')
            
            placeholders = ', '.join(['?' for _ in led_fields])
            fields_str = ', '.join(led_fields)
            sql = f'INSERT INTO led ({fields_str}) VALUES ({placeholders})'
            
            conn.execute(sql, tuple(data.values()))
            
            # 트랜잭션 커밋
            conn.commit()
            conn.close()
            
            if data.get('use') == 'Y':
                flash(f'전광판이 추가되고 활성화되었습니다. 다른 전광판은 자동으로 비활성화되었습니다.', 'success')
            else:
                flash('LED가 성공적으로 추가되었습니다.', 'success')
            return redirect(url_for('led_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    return render_template('led_form.html', title='LED 추가', action='add')

@app.route('/led/edit/<int:idx>', methods=['GET', 'POST'])
@operator_required
def edit_led(idx):
    """LED 수정"""
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    if request.method == 'POST':
        try:
            # LED 테이블의 모든 필드 처리
            data = {}
            led_fields = ['type', 'mode', 'port', 'use', 'display_sec', 'line1_mode', 'line1_header', 
                         'line1_hcolor', 'line1_tail', 'line1_tcolor', 'line1_gcolor', 'line1_ncolor', 
                         'line1_wcolor', 'line1_dcolor', 'line1_sec', 'line1_msg', 'line1_len', 'line1_act',
                         'line2_mode', 'line2_header', 'line2_hcolor', 'line2_tail', 'line2_tcolor', 
                         'line2_gcolor', 'line2_ncolor', 'line2_wcolor', 'line2_dcolor', 'line2_sec', 
                         'line2_msg', 'line2_len', 'line2_act', 'led_ad', 'ad_sec', 'ad_intv', 'ad_line1', 
                         'ad_line2', 'bright_start', 'bright_end', 'bright_max', 'bright_min']
            
            for field in led_fields:
                data[field] = request.form.get(field, '')
            
            # 트랜잭션 시작
            conn.execute('BEGIN')
            
            # 사용유무가 'Y'로 설정되는 경우, 다른 모든 LED를 'N'으로 변경
            if data.get('use') == 'Y':
                conn.execute('UPDATE led SET use = "N" WHERE idx != ?', (idx,))
            
            # UPDATE 쿼리 구성
            set_clause = ', '.join([f'{field}=?' for field in led_fields])
            sql = f'UPDATE led SET {set_clause} WHERE idx=?'
            
            values = list(data.values()) + [idx]
            conn.execute(sql, values)
            
            # 트랜잭션 커밋
            conn.commit()
            conn.close()
            
            if data.get('use') == 'Y':
                flash(f'전광판이 활성화되었습니다. 다른 전광판은 자동으로 비활성화되었습니다.', 'success')
            else:
                flash('LED가 성공적으로 수정되었습니다.', 'success')
            return redirect(url_for('led_list'))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
    
    try:
        led_item = conn.execute('SELECT * FROM led WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        
        if led_item is None:
            flash('해당 LED를 찾을 수 없습니다.', 'error')
            return redirect(url_for('led_list'))
        
        return render_template('led_form.html', title='LED 수정', action='edit', led_item=led_item)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('led_list'))

@app.route('/led/delete/<int:idx>', methods=['POST'])
@operator_required
def delete_led(idx):
    """LED 삭제"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '데이터베이스 연결 실패'})
    
    try:
        conn.execute('DELETE FROM led WHERE idx = ?', (idx,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'LED가 성공적으로 삭제되었습니다.'})
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'message': f'데이터베이스 오류: {e}'})

@app.route('/led/view/<int:idx>')
@login_required
def view_led(idx):
    """LED 상세 조회"""
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    try:
        led_item = conn.execute('SELECT * FROM led WHERE idx = ?', (idx,)).fetchone()
        conn.close()
        
        if led_item is None:
            flash('해당 LED를 찾을 수 없습니다.', 'error')
            return redirect(url_for('led_list'))
        
        return render_template('led_view.html', led_item=led_item)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return redirect(url_for('led_list'))

# 센서 데이터 조회 관련 라우트

@app.route('/realtime-data')
@login_required
def realtime_data():
    """실시간 데이터 모니터링"""
    return render_template('realtime_data.html')

@app.route('/api/sensor-config')
@login_required
def get_sensor_config():
    """센서 설정 정보를 JSON으로 반환 (캐시 기능 포함, 스레드 안전)"""
    # refresh 파라미터로 강제 새로고침 요청 확인
    force_refresh = request.args.get('refresh', '').lower() in ('true', '1', 'yes')
    
    if force_refresh:
        # 캐시 강제 새로고침
        fresh_configs = refresh_sensor_config_cache()
    else:
        # 일반적인 캐시 로직으로 로드
        fresh_configs = load_sensor_config()
    
    # 전역 변수도 업데이트 (다른 부분에서 사용될 수 있으므로)
    global SENSOR_CONFIGS
    SENSOR_CONFIGS = fresh_configs
    
    return jsonify(fresh_configs)

@app.route('/api/public-sensor-config')
def get_public_sensor_config():
    """Public API로 센서 설정 정보를 JSON으로 반환 (API 키 인증)"""
    # API 키 확인
    api_key = request.args.get('api_key', '')
    
    # API 키 검증 로직 (기존 public-sensor-stream과 동일)
    configured_keys = config.get('api', {}).get('sensor_stream_key', ['default-key'])
    
    if isinstance(configured_keys, list):
        valid_api_keys = configured_keys
    else:
        valid_api_keys = [configured_keys]
    
    # 디버그 로그
    print(f"[DEBUG] sensor-config API 키: '{api_key}'")
    print(f"[DEBUG] 유효한 API 키들: {valid_api_keys}")
    
    if api_key not in valid_api_keys:
        return Response(
            'Unauthorized: Invalid API key',
            status=401,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    # refresh 파라미터로 강제 새로고침 요청 확인
    force_refresh = request.args.get('refresh', '').lower() in ('true', '1', 'yes')
    
    if force_refresh:
        # 캐시 강제 새로고침
        fresh_configs = refresh_sensor_config_cache()
    else:
        # 일반적인 캐시 로직으로 로드
        fresh_configs = load_sensor_config()
    
    response = jsonify(fresh_configs)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/api/sensor-data')
@login_required
def get_sensor_data():
    """센서 데이터 API - HTTP 폴링용"""
    global latest_sensor_data, tcp_connected
    
    response_data = {
        'connected': tcp_connected,
        'timestamp': time.time(),
        'data': latest_sensor_data
    }
    
    return jsonify(response_data)

@app.route('/api/tcp-command', methods=['POST'])
@login_required
def send_tcp_command():
    """TCP 명령 전송 API"""
    global tcp_client, tcp_connected
    
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        if not tcp_connected or not tcp_client:
            return jsonify({'success': False, 'message': 'TCP 연결이 끊어져 있습니다.'})
        
        # 명령 전송
        tcp_client.send(command.encode('utf-8'))
        return jsonify({'success': True, 'message': f'명령 전송: {command}'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'오류: {str(e)}'})

@app.route('/api/tcp-server-info')
@login_required
def get_tcp_server_info():
    """TCP 서버 정보 API"""
    return jsonify({
        'host': TCP_HOST,
        'port': TCP_PORT,
        'connected': tcp_connected
    })

@app.route('/api/sensor-init', methods=['POST'])
@operator_required  # 센서 초기화는 operator 이상
def sensor_init():
    """센서 초기 값 설정 API"""
    try:
        data = request.get_json()
        sensor_type = data.get('sensorType', '')
        username = data.get('username', '')
        password = data.get('password', '')
        
        # 사용자 인증 확인
        if (username != LOGIN_CREDENTIALS['username'] or 
            password != LOGIN_CREDENTIALS['password']):
            return jsonify({'success': False, 'error': '인증 실패: 사용자명 또는 비밀번호가 올바르지 않습니다.'})
        
        # 데이터베이스 연결
        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'error': '데이터베이스 연결 실패'})
        
        try:
            # 현재 활성화된 디바이스 찾기
            device = conn.execute('SELECT * FROM device WHERE use = "Y" LIMIT 1').fetchone()
            
            if not device:
                conn.close()
                return jsonify({'success': False, 'error': '활성화된 디바이스가 없습니다.'})
            
            device_type = device['type']
            device_idx = device['idx']
            
            # 센서 타입 확인 및 option 값 업데이트
            if sensor_type == 'TILT' and device_type == 'TILT':
                # 경사계: option4 = "N", option5 = "N"
                conn.execute('UPDATE device SET option4 = "N", option5 = "N" WHERE idx = ?', (device_idx,))
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'message': 'TILT 센서 초기 값이 설정되었습니다.'})
                
            elif sensor_type == 'CRACK' and device_type == 'CRACK':
                # 균열계: option4 = "N"
                conn.execute('UPDATE device SET option4 = "N" WHERE idx = ?', (device_idx,))
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'message': 'CRACK 센서 초기 값이 설정되었습니다.'})
                
            else:
                conn.close()
                return jsonify({'success': False, 'error': f'센서 타입이 일치하지 않습니다. (요청: {sensor_type}, 현재: {device_type})'})
                
        except sqlite3.Error as e:
            conn.close()
            return jsonify({'success': False, 'error': f'데이터베이스 오류: {str(e)}'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'오류: {str(e)}'})
    

@app.route('/api/sensor-stream')
@login_required
def sensor_stream():
    """Server-Sent Events 스트림"""
    def event_generator():
        client_queue = queue.Queue()
        sse_clients.add(client_queue)
        
        try:
            # 연결 상태 전송
            yield f"data: {json.dumps({'type': 'connection', 'connected': tcp_connected})}\n\n"
            
            # 2025.08.29 duzin / 센서 데이터 캐시에서 가장 최근 데이터 전송
            # =====================================================================
            # # 기존 데이터 전송
            # if latest_sensor_data:
            #     for sensor_type, data in latest_sensor_data.items():
            #         yield f"data: {data['data']}\n\n"
             # 수정 방향: 최근 데이터만 전송 (예: 5초 이내)
            if latest_sensor_data:
                current_time = time.time()
                for sensor_type, data in latest_sensor_data.items():
                    if current_time - data['timestamp'] < 5:  # 5초 이내 데이터만
                        yield f"data: {data['data']}\n\n"
            # =====================================================================

            
            # 실시간 데이터 대기
            while True:
                try:
                    data = client_queue.get(timeout=30)  # 30초 타임아웃
                    yield data
                except queue.Empty:
                    # 연결 유지를 위한 heartbeat
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': time.time()})}\n\n"
                    
        except GeneratorExit:
            pass
        finally:
            sse_clients.discard(client_queue)
    
    return Response(
        event_generator(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )

@app.route('/api/public-sensor-stream')
def public_sensor_stream():
    """Public Server-Sent Events 스트림 (API 키 인증)"""
    # API 키 확인
    api_key = request.args.get('api_key', '')
    
    # 간단한 API 키 검증 (데이터베이스에서 가져오기)
    configured_keys = config.get('api', {}).get('sensor_stream_key', ['default-key'])
    
    # config의 키가 배열이면 그대로 사용, 아니면 배열로 변환
    if isinstance(configured_keys, list):
        valid_api_keys = configured_keys
    else:
        valid_api_keys = [configured_keys]
    
    # 디버그 로그
    print(f"[DEBUG] 요청된 API 키: '{api_key}'")
    print(f"[DEBUG] 유효한 API 키들: {valid_api_keys}")
    
    if api_key not in valid_api_keys:
        return Response(
            'Unauthorized: Invalid API key',
            status=401,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    def event_generator():
        client_queue = queue.Queue()
        sse_clients.add(client_queue)
        
        try:
            # 연결 상태 전송
            yield f"data: {json.dumps({'type': 'connection', 'connected': tcp_connected})}\n\n"
            
            # 2025.08.29 duzin / 센서 데이터 캐시에서 가장 최근 데이터 전송
            # =====================================================================
            # # 기존 데이터 전송
            # if latest_sensor_data:
            #     for sensor_type, data in latest_sensor_data.items():
            #         yield f"data: {data['data']}\n\n"
             # 수정 방향: 최근 데이터만 전송 (예: 5초 이내)
            if latest_sensor_data:
                current_time = time.time()
                for sensor_type, data in latest_sensor_data.items():
                    if current_time - data['timestamp'] < 5:  # 5초 이내 데이터만
                        yield f"data: {data['data']}\n\n"
            # =====================================================================


            # 실시간 데이터 대기
            while True:
                try:
                    data = client_queue.get(timeout=30)  # 30초 타임아웃
                    yield data
                except queue.Empty:
                    # 연결 유지를 위한 heartbeat
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': time.time()})}\n\n"
                    
        except GeneratorExit:
            pass
        finally:
            sse_clients.discard(client_queue)
    
    response = Response(
        event_generator(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': 'true',
            'X-Accel-Buffering': 'no'
        }
    )
    return response

@app.route('/sensor/query', methods=['GET', 'POST'])
@login_required
def sensor_query():
    """센서 데이터 조회"""
    # 전체 센서 타입 목록 (모든 센서타입 표시)
    sensor_types = [
        ('data_wind', '풍속계(WIND)'),
        ('data_sound', '소음계(SOUND)'),
        ('data_pm', '미세먼지(PM)'),
        ('data_o2', '산소센서(O2)'),
        ('data_mq', 'MQ센서(MQ)'),
        ('data_nox', 'NOx센서(NOX)'),
        ('data_gasm', '가스센서(GASM)'),
        ('data_vibro', '진동센서(VIBRO)'),
        ('data_tilt', '기울기센서(TILT)'),
        ('data_crack', '균열센서(CRACK)')
    ]
    
    # 전체 센서 타입 매핑 (type 값에서 테이블명으로 변환)
    type_mapping = {
        'WIND': 'data_wind',
        'SOUND': 'data_sound',
        'PM': 'data_pm',
        'O2': 'data_o2',
        'MQ': 'data_mq',
        'NOX': 'data_nox',
        'GASM': 'data_gasm',
        'VIBRO': 'data_vibro',
        'TILT': 'data_tilt',
        'CRACK': 'data_crack'
    }
    
    # 기본 선택값 설정: device.use = "Y"인 센서타입 중 첫 번째
    default_sensor_type = None
    
    # GET 요청일 때만 기본값 조회
    if request.method == 'GET':
        conn = get_db_connection()
        if conn is not None:
            try:
                # device 테이블에서 사용유무가 'Y'인 센서 타입들 조회 (첫 번째를 기본값으로)
                active_devices = conn.execute('SELECT DISTINCT type FROM device WHERE use = "Y" ORDER BY type').fetchall()
                if active_devices:
                    first_active_type = active_devices[0]['type']
                    if first_active_type in type_mapping:
                        default_sensor_type = type_mapping[first_active_type]
            except sqlite3.Error as e:
                print(f"기본 센서 타입 조회 오류: {e}")
            finally:
                conn.close()
    
    if request.method == 'POST':
        sensor_type = request.form.get('sensor_type')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        start_time = request.form.get('start_time', '00:00')
        end_time = request.form.get('end_time', '23:59')
        all_data = request.form.get('all_data') == 'on'  # 전체조회 체크박스
        
        # 입력값 검증
        if not sensor_type:
            flash('센서 타입을 선택해주세요.', 'error')
            return render_template('sensor_query.html', 
                                 sensor_types=sensor_types,
                                 selected_sensor=sensor_type,
                                 selected_start=start_date,
                                 selected_end=end_date,
                                 selected_start_time=start_time,
                                 selected_end_time=end_time,
                                 selected_all=all_data)
        
        if not all_data and (not start_date or not end_date):
            flash('전체조회가 체크되지 않은 경우 조회 시작일과 종료일을 모두 입력해주세요.', 'error')
            return render_template('sensor_query.html', 
                                 sensor_types=sensor_types,
                                 selected_sensor=sensor_type,
                                 selected_start=start_date,
                                 selected_end=end_date,
                                 selected_start_time=start_time,
                                 selected_end_time=end_time,
                                 selected_all=all_data)
        
        # 센서 타입 유효성 검사
        valid_types = [t[0] for t in sensor_types]
        if sensor_type not in valid_types:
            flash('유효하지 않은 센서 타입입니다.', 'error')
            return render_template('sensor_query.html', 
                                 sensor_types=sensor_types,
                                 selected_sensor=sensor_type,
                                 selected_start=start_date,
                                 selected_end=end_date,
                                 selected_start_time=start_time,
                                 selected_end_time=end_time,
                                 selected_all=all_data)
        
        # 데이터베이스에서 센서 데이터 조회
        conn = get_db_connection()
        if conn is None:
            flash('데이터베이스 연결 실패', 'error')
            return render_template('sensor_query.html', 
                                 sensor_types=sensor_types,
                                 selected_sensor=sensor_type,
                                 selected_start=start_date,
                                 selected_end=end_date,
                                 selected_start_time=start_time,
                                 selected_end_time=end_time,
                                 selected_all=all_data)
        
        try:
            if all_data:
                # 전체 데이터 조회
                query = f'''
                    SELECT * FROM {sensor_type} 
                    ORDER BY check_time DESC 
                    LIMIT 1000
                '''
                rows = conn.execute(query).fetchall()
            else:
                # 날짜와 시간 범위로 조회 (check_time 컬럼 사용)
                start_datetime = f"{start_date} {start_time}:00"
                end_datetime = f"{end_date} {end_time}:59"
                
                query = f'''
                    SELECT * FROM {sensor_type} 
                    WHERE check_time BETWEEN ? AND ? 
                    ORDER BY check_time DESC 
                    LIMIT 1000
                '''
                rows = conn.execute(query, (start_datetime, end_datetime)).fetchall()
            
            # sqlite3.Row 객체를 딕셔너리로 변환
            sensor_data = []
            for row in rows:
                row_dict = {}
                for key in row.keys():
                    row_dict[key] = row[key]
                sensor_data.append(row_dict)
            
            # 센서 타입 한글명 찾기
            sensor_name = next((name for table, name in sensor_types if table == sensor_type), sensor_type)
            
            # 조회된 데이터가 없는 경우 알림 표시
            if not sensor_data:
                flash('조회된 데이터가 없습니다.', 'info')
            
            return render_template('sensor_query.html', 
                                 sensor_data=sensor_data,
                                 sensor_type=sensor_type,
                                 sensor_name=sensor_name,
                                 start_date=start_date,
                                 end_date=end_date,
                                 start_time=start_time,
                                 end_time=end_time,
                                 all_data=all_data,
                                 sensor_types=sensor_types,
                                 selected_sensor=sensor_type,
                                 selected_start=start_date,
                                 selected_end=end_date,
                                 selected_start_time=start_time,
                                 selected_end_time=end_time,
                                 selected_all=all_data)
            
        except sqlite3.Error as e:
            flash(f'데이터베이스 오류: {e}', 'error')
            return render_template('sensor_query.html', 
                                 sensor_types=sensor_types,
                                 selected_sensor=sensor_type,
                                 selected_start=start_date,
                                 selected_end=end_date,
                                 selected_start_time=start_time,
                                 selected_end_time=end_time,
                                 selected_all=all_data)
        finally:
            conn.close()
    
    # GET 요청시 조회 폼 표시 (기본 선택값 포함)
    return render_template('sensor_query.html', sensor_types=sensor_types, selected_sensor=default_sensor_type)

@app.route('/sensor/config', methods=['GET', 'POST'])
@operator_required  # 센서 설정 변경은 operator 이상
def sensor_config():
    """사용센서 설정"""
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message='데이터베이스 연결 실패')
    
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        try:
            if form_type == 'site_code':
                # 현장구분코드 설정
                site_code = request.form.get('site_code', '').strip()
                
                if not site_code:
                    flash('현장구분코드를 입력해주세요.', 'error')
                    return redirect(url_for('sensor_config'))
                
                # setting 테이블에서 code 업데이트 (첫 번째 레코드)
                conn.execute('UPDATE setting SET code = ? WHERE rowid = (SELECT MIN(rowid) FROM setting)', (site_code,))
                conn.commit()
                
                flash('현장구분코드가 저장되었습니다.', 'success')
                
            elif form_type == 'pms_config':
                # PMS 전송 설정
                pms_send = request.form.get('pms_send', 'N')
                pms_url = request.form.get('pms_url', '')
                
                # setting 테이블에서 send_data 업데이트
                conn.execute('UPDATE setting SET send_data = ? WHERE rowid = (SELECT MIN(rowid) FROM setting)', (pms_send,))
                
                # setting2 테이블에서 op1 업데이트
                conn.execute('UPDATE setting2 SET op1 = ? WHERE rowid = (SELECT MIN(rowid) FROM setting2)', (pms_url,))
                
                conn.commit()
                
                flash('PMS 전송 설정이 저장되었습니다.', 'success')
                
            elif form_type == 'sensor_config':
                # 센서 사용 설정
                device_idx = request.form.get('device_idx')
                led_use = request.form.get('led_use', 'N')
                cs_use = request.form.get('cs_use', 'N')
                
                if not device_idx:
                    flash('디바이스를 선택해주세요.', 'error')
                    return redirect(url_for('sensor_config'))
                
                # 선택된 디바이스 정보 조회
                selected_device = conn.execute('SELECT * FROM device WHERE idx = ?', (device_idx,)).fetchone()
                if not selected_device:
                    flash('선택된 디바이스를 찾을 수 없습니다.', 'error')
                    return redirect(url_for('sensor_config'))
                
                device_type = selected_device['type']
                
                # 트랜잭션 시작
                conn.execute('BEGIN')
                
                # 1. 모든 디바이스 비활성화
                conn.execute('UPDATE device SET use = "N"')
                
                # 2. 선택된 디바이스만 활성화
                conn.execute('UPDATE device SET use = "Y" WHERE idx = ?', (device_idx,))
                
                # 3. 모든 LED 비활성화 후 선택된 타입만 설정
                conn.execute('UPDATE led SET use = "N"')
                if led_use == 'Y':
                    conn.execute('UPDATE led SET use = "Y" WHERE type = ?', (device_type,))
                
                # 4. 모든 CS 비활성화 후 선택된 타입만 설정
                conn.execute('UPDATE cs SET use = "N"')
                if cs_use == 'Y':
                    conn.execute('UPDATE cs SET use = "Y" WHERE type = ?', (device_type,))
                
                # 트랜잭션 커밋
                conn.commit()
                
                flash(f'"{selected_device["name"]}" 디바이스가 활성화되었습니다.', 'success')
                
            elif form_type == 'socket_config':
                # 센서 소켓서버 설정
                cs_use = request.form.get('cs_use', 'N')
                cs_com_mode = request.form.get('cs_com_mode', 'SERVER')
                setting_mode = request.form.get('setting_mode', 'SERVER')
                cs_ip = request.form.get('cs_ip', '').strip()
                cs_port = request.form.get('cs_port', '').strip()
                
                # 현재 활성화된 디바이스 조회
                current_device = conn.execute('SELECT * FROM device WHERE use = "Y"').fetchone()
                if not current_device:
                    flash('활성화된 디바이스가 없습니다. 먼저 디바이스를 설정해주세요.', 'error')
                    return redirect(url_for('sensor_config'))
                
                device_type = current_device['type']
                
                # CS 테이블에서 해당 타입의 데이터 업데이트
                cs_record = conn.execute('SELECT * FROM cs WHERE type = ?', (device_type,)).fetchone()
                if cs_record:
                    # 기존 레코드 업데이트
                    conn.execute('''UPDATE cs SET use = ?, com_mode = ?, ip = ?, port = ? WHERE type = ?''',
                               (cs_use, cs_com_mode, cs_ip, cs_port, device_type))
                else:
                    # 새 레코드 생성
                    conn.execute('''INSERT INTO cs (type, use, com_mode, ip, port) VALUES (?, ?, ?, ?, ?)''',
                               (device_type, cs_use, cs_com_mode, cs_ip, cs_port))
                
                # setting 테이블에서 mode 업데이트
                conn.execute('UPDATE setting SET mode = ? WHERE rowid = (SELECT MIN(rowid) FROM setting)', (setting_mode,))
                
                conn.commit()
                
                flash('센서 소켓서버 설정이 저장되었습니다.', 'success')
                
            else:
                flash('잘못된 요청입니다.', 'error')
            
            conn.close()
            return redirect(url_for('sensor_config'))
            
        except sqlite3.Error as e:
            conn.rollback()
            conn.close()
            flash(f'설정 저장 중 오류가 발생했습니다: {e}', 'error')
            return redirect(url_for('sensor_config'))
    
    # GET 요청 처리
    try:
        # 모든 디바이스 조회
        devices = conn.execute('SELECT * FROM device ORDER BY name').fetchall()
        
        # 현재 활성화된 디바이스 조회
        current_device = conn.execute('SELECT * FROM device WHERE use = "Y"').fetchone()
        
        # 현재 LED, CS 설정 조회
        current_led = None
        current_cs = None
        led_use = 'N'
        cs_use = 'N'
        
        if current_device:
            device_type = current_device['type']
            current_led = conn.execute('SELECT * FROM led WHERE type = ?', (device_type,)).fetchone()
            current_cs = conn.execute('SELECT * FROM cs WHERE type = ?', (device_type,)).fetchone()
            
            if current_led:
                led_use = current_led['use']
            if current_cs:
                cs_use = current_cs['use']
        
        # 현장구분코드 조회 (setting 테이블의 code 필드)
        try:
            site_code_row = conn.execute('SELECT code FROM setting LIMIT 1').fetchone()
            site_code = site_code_row['code'] if site_code_row else ''
        except sqlite3.Error:
            site_code = ''
        
        # PMS 전송 설정 조회
        try:
            pms_send_row = conn.execute('SELECT send_data FROM setting LIMIT 1').fetchone()
            pms_send = pms_send_row['send_data'] if pms_send_row else 'N'
        except sqlite3.Error:
            pms_send = 'N'
        
        # PMS URL 조회 (setting2 테이블의 op1 필드)
        try:
            pms_url_row = conn.execute('SELECT op1 FROM setting2 LIMIT 1').fetchone()
            pms_url = pms_url_row['op1'] if pms_url_row else 'https://itlogtest.prosafe.kr/api2'
        except sqlite3.Error:
            pms_url = 'https://itlogtest.prosafe.kr/api2'
        
        # 소켓서버 설정 조회 - device.use = "Y"이고 device.type = cs.type인 데이터
        cs = None
        setting = None
        active_cs = None  # 활성화된 CS 정보
        
        if current_device:
            device_type = current_device['type']
            # CS 설정 조회
            cs = conn.execute('SELECT * FROM cs WHERE type = ?', (device_type,)).fetchone()
        
        # 활성화된 CS 조회 (use = 'Y')
        try:
            active_cs = conn.execute('SELECT * FROM cs WHERE use = "Y" LIMIT 1').fetchone()
        except sqlite3.Error:
            active_cs = None
        
        # setting 테이블 조회
        try:
            setting = conn.execute('SELECT * FROM setting LIMIT 1').fetchone()
        except sqlite3.Error:
            setting = None
        
        conn.close()
        
        return render_template('sensor_config.html',
                             devices=devices,
                             current_device=current_device,
                             current_led=current_led,
                             current_cs=current_cs,
                             selected_device=current_device,
                             led_use=led_use,
                             cs_use=cs_use,
                             site_code=site_code,
                             pms_send=pms_send,
                             pms_url=pms_url,
                             cs=cs,
                             setting=setting,
                             active_cs=active_cs)
        
    except sqlite3.Error as e:
        conn.close()
        flash(f'데이터베이스 오류: {e}', 'error')
        return render_template('error.html', message=str(e))

@app.route('/api/device-config/<int:device_idx>')
@login_required
def api_device_config(device_idx):
    """선택된 디바이스의 LED, CS 설정 조회 (AJAX용)"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': '데이터베이스 연결 실패'})
    
    try:
        # 디바이스 정보 조회
        device = conn.execute('SELECT * FROM device WHERE idx = ?', (device_idx,)).fetchone()
        if not device:
            return jsonify({'success': False, 'error': '디바이스를 찾을 수 없습니다'})
        
        device_type = device['type']
        
        # LED 설정 조회
        led = conn.execute('SELECT * FROM led WHERE type = ?', (device_type,)).fetchone()
        led_use = led['use'] if led else 'N'
        
        # CS 설정 조회
        cs = conn.execute('SELECT * FROM cs WHERE type = ?', (device_type,)).fetchone()
        cs_use = cs['use'] if cs else 'N'
        
        conn.close()
        
        return jsonify({
            'success': True,
            'device_type': device_type,
            'led_use': led_use,
            'cs_use': cs_use
        })
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/restart-sensor', methods=['POST'])
@operator_required  # 센서 재시작은 operator 이상
def restart_sensor():
    """통합센서 프로그램 재시작 API"""
    try:
        # 데이터베이스에서 프로세스 정보 가져오기
        sensor_process = config.get('process', {}).get('totalsensor', {}).get('process', 'itlog-ss2')
        sensor_path = config.get('process', {}).get('totalsensor', {}).get('path', '/home/pi/itlog-main/program/sensor2')
        sensor_exe = config.get('process', {}).get('totalsensor', {}).get('exe', 'itlog-ss2.exe')
        
        # 1. 먼저 기존 프로세스 강제종료
        try:
            # sudo pkill로 프로세스명으로 종료 시도
            subprocess.run(['sudo', 'pkill', '-f', sensor_process], timeout=10)
            time.sleep(2)  # 프로세스 종료 대기
            
            # 혹시 남아있는 프로세스 재확인 후 강제종료
            subprocess.run(['sudo', 'pkill', '-9', '-f', sensor_process], timeout=10)
            time.sleep(1)
        except subprocess.TimeoutExpired:
            print(f"경고: 프로세스 {sensor_process} 종료 시간 초과")
        except Exception as e:
            print(f"프로세스 종료 중 오류: {e}")
        
        # 2. 디렉토리 이동 후 프로그램 실행
        try:
            # 디렉토리 변경 후 백그라운드에서 실행
            full_exe_path = os.path.join(sensor_path, sensor_exe)
            
            # sudo 권한으로 실행 (백그라운드)
            subprocess.Popen(
                ['sudo', full_exe_path],
                cwd=sensor_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setpgrp  # 새 프로세스 그룹 생성
            )
            
            time.sleep(2)  # 프로세스 시작 대기
            
            # 프로세스가 정상적으로 시작되었는지 확인
            result = subprocess.run(['sudo', 'pgrep', '-f', sensor_process], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and result.stdout.strip():
                return jsonify({
                    'success': True,
                    'message': f'통합센서 프로그램이 성공적으로 재시작되었습니다.',
                    'process_info': {
                        'name': sensor_process,
                        'path': sensor_path,
                        'exe': sensor_exe,
                        'pid': result.stdout.strip().split('\n')[0] if result.stdout.strip() else None
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'message': f'통합센서 프로그램이 시작되었지만 프로세스 확인에 실패했습니다.',
                    'process_info': {
                        'name': sensor_process,
                        'path': sensor_path,
                        'exe': sensor_exe
                    }
                })
                
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'프로그램 실행 중 오류가 발생했습니다: {str(e)}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'시스템 오류가 발생했습니다: {str(e)}'
        })


# 라즈베리파이 설정 관련 라우트

def read_network_config():
    """현재 네트워크 설정 정보를 읽어옵니다"""
    try:
        # 현재 IP 주소 정보
        current_config = {
            'hostname': '',
            'current_ip': '',
            'static_ip': '',
            'gateway': '',
            'dns': '',
            'dns_server1': '',
            'dns_server2': '',
            'is_static': False
        }
        
        # hostname 읽기
        try:
            with open('/etc/hostname', 'r') as f:
                current_config['hostname'] = f.read().strip()
        except:
            current_config['hostname'] = 'Unknown'
        
        # 현재 IP 주소 확인
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                current_config['current_ip'] = result.stdout.strip().split()[0]
        except:
            current_config['current_ip'] = 'Unknown'
        
        # dhcpcd.conf에서 고정 IP 설정 확인
        try:
            with open('/etc/dhcpcd.conf', 'r') as f:
                content = f.read()
                
            # 고정 IP 설정 있는지 확인
            if 'static ip_address=' in content:
                current_config['is_static'] = True
                # 설정값들 추출
                ip_match = re.search(r'static ip_address=([^\s]+)', content)
                gateway_match = re.search(r'static routers=([^\s]+)', content)
                dns_match = re.search(r'static domain_name_servers=([^\n]+)', content)
                
                if ip_match:
                    current_config['static_ip'] = ip_match.group(1)
                if gateway_match:
                    current_config['gateway'] = gateway_match.group(1)
                if dns_match:
                    dns_servers = dns_match.group(1).strip().split()
                    current_config['dns'] = dns_match.group(1).strip()
                    if len(dns_servers) >= 1:
                        current_config['dns_server1'] = dns_servers[0]
                    if len(dns_servers) >= 2:
                        current_config['dns_server2'] = dns_servers[1]
        except:
            pass
            
        return current_config
    except Exception as e:
        return {
            'hostname': 'Unknown',
            'current_ip': 'Unknown',
            'static_ip': '',
            'gateway': '',
            'dns': '',
            'dns_server1': '',
            'dns_server2': '',
            'is_static': False,
            'error': str(e)
        }

@app.route('/raspi/settings')
@login_required  # 조회는 모든 사용자 가능
def raspi_settings():
    """라즈베리파이 설정 페이지"""
    try:
        network_config = read_network_config()
        return render_template('raspi_settings.html', config=network_config)
    except Exception as e:
        flash(f'설정 정보를 불러오는 중 오류가 발생했습니다: {e}', 'error')
        return render_template('raspi_settings.html', config=None)

@app.route('/raspi/set-static-ip', methods=['POST'])
@operator_required  # 네트워크 설정은 operator 이상
def set_static_ip():
    """고정 IP 설정"""
    try:
        ip_address = request.form.get('ip_address', '').strip()
        gateway = request.form.get('gateway', '').strip()
        dns_server1 = request.form.get('dns_server1', '168.126.63.1').strip()
        dns_server2 = request.form.get('dns_server2', '168.126.63.2').strip()
        
        # 입력값 검증
        if not ip_address or not gateway:
            flash('IP 주소와 게이트웨이는 필수 입력 항목입니다.', 'error')
            return redirect(url_for('raspi_settings'))
        
        # IP 주소 형식 검증 (간단한 검증)
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?$'
        if not re.match(ip_pattern, ip_address):
            flash('올바른 IP 주소 형식이 아닙니다. (예: 192.168.1.100/24)', 'error')
            return redirect(url_for('raspi_settings'))
        
        # DNS 서버 설정 구성
        dns_servers = dns_server1
        if dns_server2:
            dns_servers += f' {dns_server2}'
        
        # dhcpcd.conf 백업 및 수정
        try:
            # 기존 파일 백업
            subprocess.run(['sudo', 'cp', '/etc/dhcpcd.conf', '/etc/dhcpcd.conf.backup'], 
                         check=True, timeout=10)
            
            # 기존 설정 파일 읽기
            with open('/etc/dhcpcd.conf', 'r') as f:
                existing_content = f.read()
            
            # 기존 고정 IP 설정이 있는지 확인하고 제거
            # interface eth0 블록 찾기 및 제거
            pattern = r'# 고정 IP 설정.*?(?=\n(?:[a-zA-Z#]|\Z))'
            cleaned_content = re.sub(pattern, '', existing_content, flags=re.DOTALL)
            
            # interface eth0/wlan0로 시작하는 기존 static 설정 블록들도 제거
            eth_pattern = r'interface eth0\s*\nstatic.*?(?=\n(?:interface|\n[a-zA-Z#]|\Z))'
            wlan_pattern = r'interface wlan0\s*\nstatic.*?(?=\n(?:interface|\n[a-zA-Z#]|\Z))'
            
            cleaned_content = re.sub(eth_pattern, '', cleaned_content, flags=re.DOTALL)
            cleaned_content = re.sub(wlan_pattern, '', cleaned_content, flags=re.DOTALL)
            
            # 새로운 설정 작성
            config_content = f"""
# 고정 IP 설정 (IT Log Device Manager에서 설정됨)
interface eth0
static ip_address={ip_address}
static routers={gateway}
static domain_name_servers={dns_servers}
"""
            
            # 최종 설정 파일 내용 구성
            final_content = cleaned_content.rstrip() + '\n' + config_content
            
            # 임시 파일에 저장 후 sudo로 복사
            temp_file = '/tmp/dhcpcd.conf.tmp'
            with open(temp_file, 'w') as f:
                f.write(final_content)
            
            subprocess.run(['sudo', 'cp', temp_file, '/etc/dhcpcd.conf'], 
                         check=True, timeout=10)
            subprocess.run(['rm', temp_file], timeout=5)
            
            flash('고정 IP 설정이 완료되었습니다. 재부팅 후 적용됩니다.', 'success')
            
        except subprocess.CalledProcessError as e:
            flash(f'네트워크 설정 중 오류가 발생했습니다: {e}', 'error')
        except Exception as e:
            flash(f'설정 파일 작성 중 오류가 발생했습니다: {e}', 'error')
            
    except Exception as e:
        flash(f'고정 IP 설정 중 오류가 발생했습니다: {e}', 'error')
    
    return redirect(url_for('raspi_settings'))

@app.route('/raspi/set-hostname', methods=['POST'])
@operator_required  # 호스트명 변경은 operator 이상
def set_hostname():
    """hostname 설정"""
    try:
        new_hostname = request.form.get('hostname', '').strip()
        
        # 입력값 검증
        if not new_hostname:
            flash('호스트명을 입력해주세요.', 'error')
            return redirect(url_for('raspi_settings'))
        
        # 호스트명 형식 검증 (영문자, 숫자, 하이픈만 허용)
        if not re.match(r'^[a-zA-Z0-9-]+$', new_hostname):
            flash('호스트명은 영문자, 숫자, 하이픈만 사용할 수 있습니다.', 'error')
            return redirect(url_for('raspi_settings'))
        
        if len(new_hostname) > 63:
            flash('호스트명은 63자를 초과할 수 없습니다.', 'error')
            return redirect(url_for('raspi_settings'))
        
        try:
            # /etc/hostname 수정
            temp_file = '/tmp/hostname.tmp'
            with open(temp_file, 'w') as f:
                f.write(new_hostname + '\n')
            
            subprocess.run(['sudo', 'cp', temp_file, '/etc/hostname'], 
                         check=True, timeout=10)
            subprocess.run(['rm', temp_file], timeout=5)
            
            # /etc/hosts 수정
            try:
                with open('/etc/hosts', 'r') as f:
                    hosts_content = f.read()
                
                # 기존 127.0.1.1 라인 수정
                hosts_lines = hosts_content.split('\n')
                updated_lines = []
                found_local = False
                
                for line in hosts_lines:
                    if line.startswith('127.0.1.1'):
                        updated_lines.append(f'127.0.1.1\t{new_hostname}')
                        found_local = True
                    else:
                        updated_lines.append(line)
                
                # 127.0.1.1 라인이 없으면 추가
                if not found_local:
                    # 127.0.0.1 다음에 추가
                    for i, line in enumerate(updated_lines):
                        if line.startswith('127.0.0.1'):
                            updated_lines.insert(i + 1, f'127.0.1.1\t{new_hostname}')
                            break
                
                # 임시 파일로 저장 후 복사
                temp_hosts = '/tmp/hosts.tmp'
                with open(temp_hosts, 'w') as f:
                    f.write('\n'.join(updated_lines))
                
                subprocess.run(['sudo', 'cp', temp_hosts, '/etc/hosts'], 
                             check=True, timeout=10)
                subprocess.run(['rm', temp_hosts], timeout=5)
                
            except Exception as e:
                print(f'hosts 파일 수정 실패 (무시됨): {e}')
            
            flash('호스트명이 성공적으로 변경되었습니다. 재부팅 후 적용됩니다.', 'success')
            
        except subprocess.CalledProcessError as e:
            flash(f'호스트명 설정 중 오류가 발생했습니다: {e}', 'error')
        except Exception as e:
            flash(f'설정 파일 작성 중 오류가 발생했습니다: {e}', 'error')
            
    except Exception as e:
        flash(f'호스트명 설정 중 오류가 발생했습니다: {e}', 'error')
    
    return redirect(url_for('raspi_settings'))

@app.route('/raspi/reboot', methods=['POST'])
@operator_required  # 재부팅은 operator 이상
def raspi_reboot():
    """라즈베리파이 재부팅"""
    try:
        # 재부팅 확인
        confirm = request.form.get('confirm_reboot')
        if confirm != 'yes':
            flash('재부팅을 취소했습니다.', 'info')
            return redirect(url_for('raspi_settings'))
        
        # 통합센서 프로그램 종료
        try:
            totalsensor_name = config.get('process', {}).get('totalsensor', {}).get('process', 'itlog-ss2')
            print(f"통합센서 프로그램 종료 시도: {totalsensor_name}")
            
            # pkill을 사용하여 프로세스 종료
            result = subprocess.run(['sudo', 'pkill', '-f', totalsensor_name], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print(f"통합센서 프로그램 '{totalsensor_name}' 종료 성공")
            else:
                print(f"통합센서 프로그램 '{totalsensor_name}' 종료 시도 완료 (프로세스가 실행 중이 아니거나 이미 종료됨)")
                
        except subprocess.TimeoutExpired:
            print("통합센서 프로그램 종료 시간 초과")
        except Exception as e:
            print(f"통합센서 프로그램 종료 중 오류: {e}")
        
        # 10초 후 재부팅 실행
        subprocess.Popen(['sudo', 'bash', '-c', 'sleep 10 && reboot'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        
        flash('통합센서 프로그램을 종료하고 시스템이 10초 후 재부팅됩니다. 재부팅이 완료될 때까지 잠시 기다려주세요.', 'warning')
        
    except Exception as e:
        flash(f'재부팅 실행 중 오류가 발생했습니다: {e}', 'error')
    
    return redirect(url_for('raspi_settings'))


# ========================
# 사용자 관리 라우트
# ========================

@app.route('/admin/users')
@admin_required
def user_list():
    """사용자 목록 조회"""
    users = user_manager.get_all_users()
    return render_template('admin/user_list.html', users=users)


@app.route('/admin/user/add', methods=['GET', 'POST'])
@admin_required
def user_add():
    """새 사용자 추가"""
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
            return redirect(url_for('user_list'))
        else:
            flash(result.get('error', '사용자 생성에 실패했습니다.'), 'danger')
    
    return render_template('admin/user_add.html')


@app.route('/admin/user/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def user_edit(user_id):
    """사용자 정보 편집"""
    user = user_manager.get_user(user_id=user_id)
    
    if not user:
        flash('사용자를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('user_list'))
    
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
            return redirect(url_for('user_list'))
        else:
            flash(result.get('error', '업데이트에 실패했습니다.'), 'danger')
    
    return render_template('admin/user_edit.html', user=user)


@app.route('/admin/user/password-reset/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def user_password_reset(user_id):
    """비밀번호 재설정"""
    user = user_manager.get_user(user_id=user_id)
    
    if not user:
        flash('사용자를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('user_list'))
    
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
                return redirect(url_for('user_list'))
            else:
                flash(result.get('error', '비밀번호 재설정에 실패했습니다.'), 'danger')
    
    return render_template('admin/user_password_reset.html', user=user)


@app.route('/admin/user/delete/<int:user_id>', methods=['POST'])
@admin_required
def user_delete(user_id):
    """사용자 삭제"""
    # 자기 자신은 삭제할 수 없음
    if user_id == session.get('user_id'):
        flash('자기 자신은 삭제할 수 없습니다.', 'danger')
        return redirect(url_for('user_list'))
    
    user = user_manager.get_user(user_id=user_id)
    
    if not user:
        flash('사용자를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('user_list'))
    
    result = user_manager.delete_user(user_id)
    
    if result['success']:
        flash(f'사용자 "{user["username"]}"가 삭제되었습니다.', 'success')
    else:
        flash(result.get('error', '사용자 삭제에 실패했습니다.'), 'danger')
    
    return redirect(url_for('user_list'))


# ========================
# 설정 관리 라우트
# ========================

@app.route('/admin/config')
@operator_required
def config_list():
    """설정 목록 조회"""
    configs = config_manager.get_all_configs_list()
    return render_template('admin/config_list.html', configs=configs)


@app.route('/admin/config/view/<int:config_id>')
@operator_required
def config_view(config_id):
    """설정 상세 조회"""
    try:
        config_item = config_manager.get_config_by_id(config_id)
        if not config_item:
            flash('해당 설정을 찾을 수 없습니다.', 'error')
            return redirect(url_for('config_list'))
        
        return render_template('admin/config_view.html', config_item=config_item)
    
    except Exception as e:
        flash(f'설정 조회 중 오류가 발생했습니다: {e}', 'error')
        return redirect(url_for('config_list'))


@app.route('/admin/config/edit/<int:config_id>', methods=['GET', 'POST'])
@admin_required
def config_edit(config_id):
    """설정 수정"""
    try:
        config_item = config_manager.get_config_by_id(config_id)
        if not config_item:
            flash('해당 설정을 찾을 수 없습니다.', 'error')
            return redirect(url_for('config_list'))
        
        if request.method == 'POST':
            value = request.form.get('value', '').strip()
            description = request.form.get('description', '').strip() or None
            
            result = config_manager.update_config_by_id(
                config_id, 
                value, 
                session.get('user_id'),
                description=description
            )
            
            if result['success']:
                # 설정이 변경되면 config 다시 로드
                global config
                config = config_manager.get_hybrid_config()
                
                flash('설정이 성공적으로 수정되었습니다.', 'success')
                return redirect(url_for('config_list'))
            else:
                flash(f'설정 수정 중 오류가 발생했습니다: {result["error"]}', 'error')
        
        return render_template('admin/config_edit.html', config_item=config_item)
    
    except Exception as e:
        flash(f'설정 수정 중 오류가 발생했습니다: {e}', 'error')
        return redirect(url_for('config_list'))


@app.route('/api/config/update/<int:config_id>', methods=['POST'])
@operator_required
def api_config_update(config_id):
    """설정 값 업데이트 API"""
    data = request.json
    value = data.get('value')
    
    if value is None:
        return jsonify({'success': False, 'error': '값이 제공되지 않았습니다.'})
    
    result = config_manager.update_config_by_id(
        config_id,
        value,
        session.get('user_id')
    )
    
    if result['success']:
        # 설정이 변경되면 config 다시 로드
        global config
        config = config_manager.get_hybrid_config()
    
    return jsonify(result)


@app.route('/api/config/migrate', methods=['POST'])
@admin_required
def api_config_migrate():
    """config.json에서 데이터베이스로 설정 마이그레이션 API (레거시 지원)"""
    result = config_manager.migrate_from_file(session.get('user_id'))
    
    if result['success']:
        # 설정이 변경되면 config 다시 로드
        global config
        config = config_manager.get_hybrid_config()
    
    return jsonify(result)


@app.route('/api/config/export', methods=['POST'])
@admin_required
def api_config_export():
    """데이터베이스 설정을 config.json으로 내보내기 API (백업용)"""
    result = config_manager.save_to_file()
    return jsonify(result)


# ========================
# 비밀번호 변경 (모든 사용자)
# ========================

@app.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """현재 사용자 비밀번호 변경"""
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


if __name__ == '__main__':
    # Flask 서버 설정을 데이터베이스에서 읽기
    flask_config = config.get('flask', {})
    host = flask_config.get('host', '0.0.0.0')
    port = flask_config.get('port', 5000)
    debug = flask_config.get('debug', True)
    
    print(f"Flask 서버 시작: http://{host}:{port} (디버그 모드: {debug})")
    app.run(host=host, port=port, debug=debug)
