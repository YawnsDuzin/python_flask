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

# .env 파일에서 EXE_MODE 읽기 (SERVER 또는 CLIENT)
EXE_MODE = os.getenv('EXE_MODE', 'SERVER')
print(f"\n*** 디버그: EXE_MODE = '{EXE_MODE}' ***\n")

# 설정 관리자 초기화 (데이터베이스 전용)
config_manager = ConfigManager(db_path=database_full_path)
config = config_manager.get_config()  # 데이터베이스에서만 로드

# 사용자 관리자 초기화
user_manager = UserManager(db_path=database_full_path)

# TCP 소켓 클라이언트 설정 (SERVER 모드에서만 활성화)
if EXE_MODE == 'SERVER':
    TCP_HOST = config.get('socketserver', {}).get('TCP_HOST', '127.0.0.1')
    TCP_PORT = config.get('socketserver', {}).get('TCP_PORT', 3000)
else:
    TCP_HOST = None
    TCP_PORT = None

# Flask 앱 설정
app.secret_key = config.get('security', {}).get('secret_key', 'itlog@secret#key$production')

# 블루프린트 등록
from blueprints import register_blueprints
register_blueprints(app)

# 템플릿 전역 변수 설정
@app.context_processor
def inject_global_vars():
    """템플릿에 전역 변수 주입"""
    print(f"*** Context Processor: exe_mode = '{EXE_MODE}' ***")
    return {
        'exe_mode': EXE_MODE
    }

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
DATABASE_DB = db_name  # blueprints에서 사용하기 위해 export

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
            current_time - _config_cache_time < _config_cache_duration):
            return _cached_sensor_config
        
        # 캐시가 없거나 만료된 경우 파일에서 로드
        config_file = os.path.join(application_path, 'config_sensor.json')
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    sensor_configs = json.load(f)
                    _cached_sensor_config = sensor_configs
                    _config_cache_time = current_time
                    return sensor_configs
            except Exception as e:
                print(f"config_sensor.json 로드 오류: {e}")
                return {}
        else:
            print(f"config_sensor.json 파일을 찾을 수 없습니다: {config_file}")
            return {}

def refresh_sensor_config_cache():
    """센서 설정 캐시를 강제로 새로고침합니다."""
    global _cached_sensor_config, _config_cache_time
    
    with _sensor_config_lock:
        _cached_sensor_config = None
        _config_cache_time = None
        return load_sensor_config()


# TCP 소켓 클라이언트 설정
latest_sensor_data = {}
tcp_client = None
tcp_connected = False
sse_clients = set()  # SSE 클라이언트 목록

def tcp_client_thread():
    """TCP 클라이언트 스레드 (SERVER 모드 전용)"""
    global tcp_client, tcp_connected, latest_sensor_data
    
    # SERVER 모드가 아니면 스레드 종료
    if EXE_MODE != 'SERVER':
        print("TCP 클라이언트: CLIENT 모드에서는 비활성화됩니다.")
        return
    
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
        # 이미 포맷된 특수 메시지 (연결 상태, 리프레시 등)
        formatted_data = data
        print(f"[SSE BROADCAST] 특수 메시지 브로드캐스트: {data[:100]}...")  # 디버깅 로그
    else:
        # 일반 센서 데이터
        if not data.startswith("data: "):
            formatted_data = f"data: {data}\n\n"
        else:
            formatted_data = data

    # 현재 연결된 클라이언트 수 로그
    print(f"[SSE BROADCAST] 현재 연결된 클라이언트 수: {len(sse_clients)}")

    for client in sse_clients.copy():
        try:
            client.put(formatted_data)
        except Exception as e:
            disconnected_clients.add(client)
            print(f"[SSE BROADCAST] 클라이언트 연결 끊김: {e}")  # 디버깅 로그

    # 연결이 끊어진 클라이언트 제거
    sse_clients -= disconnected_clients

    # 브로드캐스트 결과 로그
    if is_special:
        print(f"[SSE BROADCAST] 메시지 전송 완료: {len(sse_clients) - len(disconnected_clients)}개 클라이언트")



# login_required는 user_manager에서 import됨
def login_required(f):
    """로그인 필수 데코레이터 - 블루프린트 호환성용"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session.get('logged_in'):
            flash('로그인이 필요합니다.', 'warning')
            return redirect(url_for('auth.login'))
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
    """테이블 존재 여부 확인"""
    should_close = False
    
    if conn is None:
        conn = get_db_connection()
        if conn is None:
            return False
        should_close = True
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """, (table_name,))
        
        result = cursor.fetchone() is not None
        
        if should_close:
            conn.close()
            
        return result
        
    except sqlite3.Error as e:
        print(f"테이블 존재 확인 오류: {e}")
        if should_close and conn:
            conn.close()
        return False

# 전역 변수 - 블루프린트에서 접근 가능
SENSOR_CONFIGS = load_sensor_config()

@app.route('/')
def index():
    """메인 페이지 - 로그인된 경우 대시보드로 리다이렉트"""
    # CLIENT 모드에서 자동 로그인 처리
    if EXE_MODE == 'CLIENT' and 'logged_in' not in session:
        session['logged_in'] = True
        session['username'] = 'viewer'
        session['permission'] = 'viewer'
        session['is_auto_login'] = True  # 자동 로그인 표시
        # flash('센서 모니터링 모드로 자동 접속되었습니다.', 'info')
        return redirect(url_for('sensor.sensor_dashboard'))
    
    if 'logged_in' in session:
        # CLIENT 모드에서는 항상 센서 대시보드로
        if EXE_MODE == 'CLIENT':
            return redirect(url_for('sensor.sensor_dashboard'))
        else : # EXE_MODE == 'SERVER':
            return redirect(url_for('dashboard'))
        
    return redirect(url_for('auth.login'))

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

# TCP 클라이언트 스레드는 SERVER 모드에서만 시작
# Flask 개발 서버의 reloader가 활성화되어도 정상 동작하도록 처리
import os
if EXE_MODE == 'SERVER':
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not config.get('flask', {}).get('debug', True):
        # reloader의 메인 프로세스이거나, debug가 False인 경우에만 실행
        tcp_thread = threading.Thread(target=tcp_client_thread, daemon=True)
        tcp_thread.start()
        print(f"TCP 클라이언트 스레드 시작: {TCP_HOST}:{TCP_PORT}")
else:
    print(f"TCP 클라이언트: {EXE_MODE} 모드에서는 비활성화됩니다.")

if __name__ == '__main__':
    # Flask 서버 설정을 데이터베이스에서 읽기
    flask_config = config.get('flask', {})
    host = flask_config.get('host', '0.0.0.0')
    port = flask_config.get('port', 5000)
    debug = flask_config.get('debug', True)
    
    print(f"Flask 서버 시작: http://{host}:{port} (디버그 모드: {debug})")
    
    app.run(host=host, port=port, debug=debug, threaded=True)