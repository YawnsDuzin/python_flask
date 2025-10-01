"""
API 엔드포인트 블루프린트
센서 API, 시스템 API, TCP 통신 API 등을 담당합니다.
"""

from flask import Blueprint, request, jsonify, Response, session
from user_manager import login_required, operator_required
import json
import queue
import time
import sqlite3
import subprocess
import sys
import os

# 상위 디렉토리의 모듈을 import하기 위한 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/system-status')
@login_required
def api_system_status():
    """시스템 상태 API"""
    try:
        from system_monitor import get_system_status
        status = get_system_status()
        return jsonify(status)
    except ImportError:
        return jsonify({'error': 'System monitor not available'})
    except Exception as e:
        return jsonify({'error': str(e)})


@api_bp.route('/api/sensor-config')
@login_required
def get_sensor_config():
    """센서 설정 정보를 JSON으로 반환 (캐시 기능 포함, 스레드 안전)"""
    from app import load_sensor_config, refresh_sensor_config_cache, SENSOR_CONFIGS
    
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


@api_bp.route('/api/public-sensor-config')
def get_public_sensor_config():
    """Public API로 센서 설정 정보를 JSON으로 반환 (API 키 인증)"""
    from app import config, load_sensor_config, refresh_sensor_config_cache
    
    # API 키 확인
    api_key = request.args.get('api_key', '')
    
    # API 키 검증 로직 (기존 public-sensor-stream과 동일)
    configured_keys = config.get('api', {}).get('sensor_stream_key_server', ['default-key'])
    
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


@api_bp.route('/api/sensor-data')
@login_required
def get_sensor_data():
    """센서 데이터 API - HTTP 폴링용"""
    from app import latest_sensor_data, tcp_connected
    
    response_data = {
        'connected': tcp_connected,
        'timestamp': time.time(),
        'data': latest_sensor_data
    }
    
    return jsonify(response_data)


@api_bp.route('/api/tcp-command', methods=['POST'])
@login_required
def send_tcp_command():
    """TCP 명령 전송 API"""
    from app import tcp_client, tcp_connected
    
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


@api_bp.route('/api/tcp-server-info')
@login_required
def get_tcp_server_info():
    """TCP 서버 정보 API"""
    from app import TCP_HOST, TCP_PORT, tcp_connected
    
    return jsonify({
        'host': TCP_HOST,
        'port': TCP_PORT,
        'connected': tcp_connected
    })


@api_bp.route('/api/sensor-init', methods=['POST'])
@operator_required  # 센서 초기화는 operator 이상
def sensor_init():
    """센서 초기 값 설정 API"""
    from app import get_db_connection
    
    try:
        data = request.get_json()
        sensor_type = data.get('sensorType', '')
        
        # 현재 세션의 권한 확인
        current_permission = session.get('permission', 'viewer')
        current_username = session.get('username', '')
        
        # 권한 재확인 (operator 또는 admin만 허용)
        if current_permission not in ['operator', 'admin']:
            return jsonify({'success': False, 'error': '권한이 없습니다. operator 또는 admin 권한이 필요합니다.'})
        
        print(f"[센서 초기화] 사용자: {current_username} ({current_permission}), 센서 타입: {sensor_type}")
        
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


@api_bp.route('/api/refresh-stream')
def refresh_stream():
    """브라우저 리프레시 이벤트 전용 SSE 스트림 (인증 불필요)"""
    import app
    from app import EXE_MODE

    def event_generator():
        client_queue = queue.Queue()
        app.sse_clients.add(client_queue)

        try:
            # 초기 연결 메시지
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Refresh stream connected'})}\n\n"

            while True:
                try:
                    # 큐에서 메시지 대기 (30초 타임아웃)
                    message = client_queue.get(timeout=30)
                    yield message
                except queue.Empty:
                    # 타임아웃 시 heartbeat 전송
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            app.sse_clients.discard(client_queue)

    return Response(
        event_generator(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'X-Accel-Buffering': 'no'
        }
    )

@api_bp.route('/api/sensor-stream')
@login_required
def sensor_stream():
    """Server-Sent Events 스트림"""
    import app
    from app import EXE_MODE
    
    # CLIENT 모드에서는 접근 차단
    if EXE_MODE == 'CLIENT':
        return Response(
            'This API is disabled in CLIENT mode',
            status=403,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    def event_generator():
        client_queue = queue.Queue()
        app.sse_clients.add(client_queue)
        
        try:
            # 연결 상태 전송
            yield f"data: {json.dumps({'type': 'connection', 'connected': app.tcp_connected})}\n\n"
            
            # 최근 데이터만 전송 (5초 이내)
            if app.latest_sensor_data:
                current_time = time.time()
                for sensor_type, data in app.latest_sensor_data.items():
                    if current_time - data['timestamp'] < 5:  # 5초 이내 데이터만
                        yield f"data: {data['data']}\n\n"
            
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
            try:
                app.sse_clients.discard(client_queue)
            except:
                pass
    
    return Response(event_generator(), mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'Access-Control-Allow-Origin': '*'
                    })


@api_bp.route('/api/public-sensor-stream')
def public_sensor_stream():
    """공개 센서 스트림 (API 키 인증)"""
    import app
    from app import config, EXE_MODE
    
    # CLIENT 모드에서는 접근 차단
    if EXE_MODE == 'CLIENT':
        return Response(
            'This API is disabled in CLIENT mode',
            status=403,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    # API 키 확인
    api_key = request.args.get('api_key', '')
    
    # 설정에서 API 키 목록 가져오기
    configured_keys = config.get('api', {}).get('sensor_stream_key_server', ['default-key'])
    
    if isinstance(configured_keys, list):
        valid_api_keys = configured_keys
    else:
        valid_api_keys = [configured_keys]
    
    print(f"[DEBUG] API 키: '{api_key}', 유효한 키들: {valid_api_keys}")
    
    if api_key not in valid_api_keys:
        return Response(
            'Unauthorized: Invalid API key',
            status=401,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    def event_generator():
        client_queue = queue.Queue()
        app.sse_clients.add(client_queue)
        
        try:
            # 연결 상태 전송
            yield f"data: {json.dumps({'type': 'connection', 'connected': app.tcp_connected})}\n\n"
            
            # 최근 데이터만 전송 (5초 이내)
            if app.latest_sensor_data:
                current_time = time.time()
                for sensor_type, data in app.latest_sensor_data.items():
                    if current_time - data['timestamp'] < 5:  # 5초 이내 데이터만
                        yield f"data: {data['data']}\n\n"
            
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
            try:
                app.sse_clients.discard(client_queue)
            except:
                pass
    
    return Response(event_generator(), mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'Access-Control-Allow-Origin': '*'
                    })


@api_bp.route('/api/device-config/<int:device_idx>')
@login_required
def api_device_config(device_idx):
    """선택된 디바이스의 LED, CS 설정 조회 (AJAX용)"""
    from app import get_db_connection
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': '데이터베이스 연결 실패'})
    
    try:
        # 디바이스 정보 조회
        device = conn.execute('SELECT * FROM device WHERE idx = ?', (device_idx,)).fetchone()
        if not device:
            return jsonify({'success': False, 'error': '디바이스를 찾을 수 없습니다'})

        device_type = device['type']
        device_mode = device['mode'] if device and 'mode' in device.keys() else ''

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
            'device_mode': device_mode,
            'led_use': led_use,
            'cs_use': cs_use
        })
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': f'데이터베이스 오류: {e}'}), 500


@api_bp.route('/api/restart-sensor', methods=['POST'])
@operator_required
def restart_sensor():
    """센서 프로그램 재시작 API"""
    from app import config_manager
    
    try:
        # 설정에서 프로세스 정보 읽기
        process_config = config_manager.get_config('process')
        
        if not process_config:
            return jsonify({
                'success': False, 
                'message': '프로세스 설정을 찾을 수 없습니다. 시스템 설정에서 프로세스 정보를 확인해주세요.'
            })
        
        process_name = process_config.get('totalsensor_process', 'itlog-ss2')
        process_path = process_config.get('totalsensor_path', '/home/pi/itlog-main/program/sensor2')
        process_exe = process_config.get('totalsensor_exe', 'itlog-ss2.exe')
        
        print(f"[센서 재시작] 프로세스: {process_name}, 경로: {process_path}, 실행파일: {process_exe}")
        
        # 기존 프로세스 종료 시도
        try:
            result = subprocess.run(['sudo', 'pkill', '-f', process_name], 
                                  capture_output=True, text=True, timeout=10)
            print(f"[센서 재시작] 프로세스 종료 결과: {result.returncode}")
            time.sleep(2)  # 종료 대기
        except subprocess.TimeoutExpired:
            print("[센서 재시작] 프로세스 종료 타임아웃")
        except Exception as e:
            print(f"[센서 재시작] 프로세스 종료 중 오류: {e}")
        
        # 새 프로세스 시작
        try:
            cmd = f"cd {process_path} && sudo nohup ./{process_exe} > /dev/null 2>&1 &"
            print(f"[센서 재시작] 실행 명령: {cmd}")
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            print(f"[센서 재시작] 시작 결과: {result.returncode}")
            
            if result.returncode == 0:
                return jsonify({
                    'success': True, 
                    'message': f'센서 프로그램이 재시작되었습니다.\n프로세스: {process_name}\n경로: {process_path}'
                })
            else:
                return jsonify({
                    'success': False, 
                    'message': f'센서 프로그램 시작에 실패했습니다.\n오류: {result.stderr}'
                })
                
        except subprocess.TimeoutExpired:
            return jsonify({
                'success': False, 
                'message': '센서 프로그램 시작 중 타임아웃이 발생했습니다.'
            })
        except Exception as e:
            return jsonify({
                'success': False, 
                'message': f'센서 프로그램 시작 중 오류: {e}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'센서 재시작 중 오류가 발생했습니다: {e}'
        })