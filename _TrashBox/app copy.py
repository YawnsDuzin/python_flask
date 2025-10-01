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

# TCP 소켓 클라이언트 설정
TCP_HOST = config.get('socketserver', {}).get('TCP_HOST', '127.0.0.1')
TCP_PORT = config.get('socketserver', {}).get('TCP_PORT', 3000)

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

# TCP 클라이언트 관련 전역 변수
tcp_client = None
tcp_connected = False
latest_sensor_data = {}

# SSE 클라이언트 관리
sse_clients = set()

def tcp_client_thread():
    """TCP 클라이언트 스레드"""
    global tcp_client, tcp_connected, latest_sensor_data
    
    while True:
        try:
            print(f"TCP 서버 연결 시도: {TCP_HOST}:{TCP_PORT}")
            tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_client.settimeout(10)
            tcp_client.connect((TCP_HOST, TCP_PORT))
            
            tcp_connected = True
            print("TCP 연결 성공!")
            
            # 연결 상태를 모든 SSE 클라이언트에 브로드캐스트
            broadcast_to_sse_clients({
                'type': 'connection',
                'connected': True,
                'message': 'TCP 서버에 연결되었습니다.'
            }, is_special=True)
            
            # "ON" 명령 전송 (센서 데이터 스트림 활성화)
            try:
                tcp_client.send("ON\n".encode('utf-8'))
                print("센서 데이터 스트림 활성화 명령(ON) 전송")
                print(f"[DEBUG] TCP 서버 연결 완료: {TCP_HOST}:{TCP_PORT}")
            except Exception as e:
                print(f"ON 명령 전송 실패: {e}")
            
            # 데이터 수신 루프
            buffer = ""
            recv_count = 0
            while tcp_connected:
                try:
                    data = tcp_client.recv(1024).decode('utf-8', errors='ignore')
                    if not data:
                        print("TCP 연결이 서버에 의해 종료되었습니다.")
                        break
                    
                    recv_count += 1
                    print(f"[DEBUG] Raw TCP 데이터 수신 #{recv_count}: {repr(data[:100])}...")
                    
                    buffer += data
                    
                    # 센서 메시지는 패턴: 숫자|타입||데이터^IP
                    # 메시지 경계는 IP 주소 뒤에서 다음 숫자로 시작하는 부분
                    import re
                    
                    # # 완전한 메시지 패턴: 숫자|타입||...^IP주소
                    # pattern = r'(\d+\|[^|]+\|\|[^^]+\^\d+\.\d+\.\d+\.\d+)'
                    # messages = re.findall(pattern, buffer)
                    
                    # if messages:
                    #     # 처리된 메시지들 제거
                    #     for msg in messages:
                    #         buffer = buffer.replace(msg, '', 1)
                    #         print(f"[DEBUG] 파싱된 센서 메시지: {msg[:50]}...")
                    #         process_sensor_data(msg)
                            
                    # 버퍼가 너무 크면 초기화 (메모리 보호)
                    if len(buffer) > 10000:
                        print(f"[DEBUG] 버퍼 초기화 (크기: {len(buffer)})")
                        buffer = ""
                            
                except socket.timeout:
                    # 타임아웃은 정상 (데이터가 없을 때)
                    print(f"[DEBUG] Socket timeout - 데이터 대기중... (recv_count: {recv_count})")
                    continue
                except Exception as e:
                    print(f"데이터 수신 오류: {e}")
                    break
                    
        except socket.timeout:
            print("TCP 연결 타임아웃")
        except ConnectionRefusedError:
            print("TCP 서버에 연결할 수 없습니다. (연결 거부)")
        except Exception as e:
            print(f"TCP 연결 오류: {e}")
        
        # 연결 실패 또는 끊김
        tcp_connected = False
        if tcp_client:
            try:
                tcp_client.close()
            except:
                pass
            tcp_client = None
        
        # 연결 끊김을 모든 SSE 클라이언트에 브로드캐스트
        broadcast_to_sse_clients({
            'type': 'connection',
            'connected': False,
            'message': 'TCP 서버 연결이 끊어졌습니다.'
        }, is_special=True)
        
        print("5초 후 재연결 시도...")
        time.sleep(5)

def process_sensor_data(data_line):
    """수신된 센서 데이터 처리"""
    global latest_sensor_data
    
    try:
        # STX(0x02)와 ETX(0x03) 제거
        if data_line.startswith('\x02') and data_line.endswith('\x03'):
            data_line = data_line[1:-1]
        
        print(f"[DEBUG] 수신된 데이터: {data_line[:100]}...")  # 디버그 로그 활성화
        
        # 센서 타입 추출 (형식: 1|TYPE|...^IP)
        parts = data_line.split('|')
        if len(parts) >= 2:
            sensor_type = parts[1].strip()
            
            # 센서 데이터 저장 (타임스탬프 포함)
            latest_sensor_data[sensor_type] = {
                'data': data_line,
                'timestamp': time.time()
            }
            
            print(f"[DEBUG] SSE 클라이언트 수: {len(sse_clients)}")  # 디버그 로그 활성화
            print(f"[DEBUG] 센서 타입: {sensor_type}, 데이터 저장됨")
            
            # SSE 클라이언트에 브로드캐스트
            broadcast_to_sse_clients(data_line)
            print(f"[DEBUG] broadcast_to_sse_clients 호출됨")
            
    except Exception as e:
        print(f"센서 데이터 처리 오류: {e}")

def broadcast_to_sse_clients(data, is_special=False):
    """모든 SSE 클라이언트에 데이터 브로드캐스트"""
    if not sse_clients:
        # print(f"[DEBUG] SSE 클라이언트가 없습니다.")  # 디버그 로그
        return
    
    # 특수 메시지 (연결 상태 등)
    if is_special:
        message = f"data: {json.dumps(data)}\n\n"
    else:
        # 일반 센서 데이터
        message = f"data: {data}\n\n"
    
    print(f"[DEBUG] 브로드캐스트 메시지: {message[:100]}...")  # 디버그 로그 활성화
    
    # 끊어진 클라이언트 정리용 리스트
    dead_clients = set()
    
    for client_queue in list(sse_clients):
        try:
            client_queue.put(message, timeout=0.1)
        except queue.Full:
            # 큐가 가득 찬 클라이언트 제거
            dead_clients.add(client_queue)
        except Exception as e:
            dead_clients.add(client_queue)
    
    # 끊어진 클라이언트 정리
    for client in dead_clients:
        sse_clients.discard(client)

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
    if 'logged_in' in session:
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

# TCP 클라이언트 스레드는 모듈 로드 시점에 시작 (reloader 문제 해결)
# Flask 개발 서버의 reloader가 활성화되어도 정상 동작하도록 처리
import os
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not config.get('flask', {}).get('debug', True):
    # reloader의 메인 프로세스이거나, debug가 False인 경우에만 실행
    tcp_thread = threading.Thread(target=tcp_client_thread, daemon=True)
    tcp_thread.start()
    print(f"TCP 클라이언트 스레드 시작: {TCP_HOST}:{TCP_PORT}")

if __name__ == '__main__':
    # Flask 서버 설정을 데이터베이스에서 읽기
    flask_config = config.get('flask', {})
    host = flask_config.get('host', '0.0.0.0')
    port = flask_config.get('port', 5000)
    debug = flask_config.get('debug', True)
    
    print(f"Flask 서버 시작: http://{host}:{port} (디버그 모드: {debug})")
    
    app.run(host=host, port=port, debug=debug, threaded=True)