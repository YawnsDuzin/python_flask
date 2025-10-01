"""
센서 대시보드 전용 API 블루프린트
CS 테이블, Font 테이블 등 센서 대시보드에서 필요한 데이터를 제공합니다.
"""

from flask import Blueprint, jsonify, request, Response
from user_manager import login_required
import sqlite3
import os
import sys
import json

# 상위 디렉토리의 모듈을 import하기 위한 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sensor_dashboard_bp = Blueprint('sensor_dashboard', __name__)

@sensor_dashboard_bp.route('/api/sensor-dashboard/cs-table')
def get_cs_table():
    """CS 테이블 데이터 조회 API - API 키 인증"""
    from app import config_manager, DATABASE_PATH
    
    # API 키 확인
    api_key = request.args.get('api_key')
    if not api_key:
        return jsonify({'error': 'API key required'}), 401
    
    # 설정에서 허용된 API 키 목록 가져오기
    configured_keys = config_manager.get_config('api', 'sensor_stream_key_server')
    if not configured_keys:
        configured_keys = ['default-key']
    
    # 문자열인 경우 리스트로 변환
    if isinstance(configured_keys, str):
        if ',' in configured_keys:
            configured_keys = [k.strip() for k in configured_keys.split(',')]
        else:
            configured_keys = [configured_keys.strip()]
    
    # API 키 검증
    if api_key not in configured_keys:
        print(f"[API] 잘못된 API 키 시도: {api_key}")
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # CS 테이블 데이터 조회 - use 조건 제거하여 모든 데이터 반환
        # sensor_dashboard.js에서 필터링하도록 함
        cursor.execute('SELECT * FROM cs ORDER BY idx ASC')
        rows = cursor.fetchall()
        
        # 결과를 딕셔너리 리스트로 변환
        cs_data = [dict(row) for row in rows]
        
        # 컬럼 정보도 함께 반환
        columns = list(rows[0].keys()) if rows else []
        
        return jsonify({
            'success': True,
            'columns': columns,
            'data': cs_data
        })
        
    except Exception as e:
        print(f"[오류] CS 테이블 조회 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@sensor_dashboard_bp.route('/api/sensor-dashboard/font-table')
def get_font_table():
    """Font 테이블 데이터 조회 API - API 키 인증"""
    from app import config_manager, DATABASE_PATH
    
    # API 키 확인
    api_key = request.args.get('api_key')
    if not api_key:
        return jsonify({'error': 'API key required'}), 401
    
    # 설정에서 허용된 API 키 목록 가져오기
    configured_keys = config_manager.get_config('api', 'sensor_stream_key_server')
    if not configured_keys:
        configured_keys = ['default-key']
    
    # 문자열인 경우 리스트로 변환
    if isinstance(configured_keys, str):
        if ',' in configured_keys:
            configured_keys = [k.strip() for k in configured_keys.split(',')]
        else:
            configured_keys = [configured_keys.strip()]
    
    # API 키 검증
    if api_key not in configured_keys:
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # font_set 테이블 데이터 조회
        cursor.execute('SELECT * FROM font_set')
        rows = cursor.fetchall()
        
        # 결과를 processFontData 포맷으로 가공
        font_data = {}
        for row in rows:
            fcode = row['fcode']
            
            if fcode not in font_data:
                font_data[fcode] = {
                    'id': fcode,
                    'options': []
                }
            
            font_size = int(float(row['fsize'] or 24))
            option = {
                'id': row['fname'],
                'value': row['ftext'] or '',
                'fontSize': font_size,
                'isSize': font_size != 0,
                'fontName': row['ffont'] or '굴림',
                'fontWeight': row['fstyle'] or 'Normal',
                'fontColor': row['fcolor'] or 'White',
                'bgColor': row['fbg'] or 'Transparent'
            }
            
            font_data[fcode]['options'].append(option)
        
        # 컬럼 정보도 함께 반환 (필요시)
        columns = list(rows[0].keys()) if rows else []
        
        return jsonify({
            'success': True,
            'columns': columns,
            'data': font_data
        })
        
    except Exception as e:
        print(f"[오류] Font 테이블 조회 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@sensor_dashboard_bp.route('/api/sensor-dashboard/table/<table_name>')
@login_required
def get_table_data(table_name):
    """범용 테이블 데이터 조회 API - 로그인 필요"""
    from app import DATABASE_PATH
    
    # 허용된 테이블 목록 (보안을 위해 화이트리스트 방식 사용)
    allowed_tables = ['cs', 'font_set', 'device', 'setting', 'led']
    
    if table_name not in allowed_tables:
        return jsonify({'error': 'Table not allowed'}), 403
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 테이블 데이터 조회
        cursor.execute(f'SELECT * FROM {table_name}')
        rows = cursor.fetchall()
        
        # 결과를 딕셔너리 리스트로 변환
        data = [dict(row) for row in rows]
        
        # 컬럼 정보
        columns = list(rows[0].keys()) if rows else []
        
        return jsonify({
            'success': True,
            'table': table_name,
            'columns': columns,
            'data': data
        })
        
    except Exception as e:
        print(f"[오류] {table_name} 테이블 조회 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@sensor_dashboard_bp.route('/api/sensor-dashboard/server-config')
def get_server_config():
    """Flask 서버 설정 정보 조회 API - 공개 접근 가능"""
    from app import DATABASE_PATH
    
    try:
        print(f"[info] DATABASE_PATH: {DATABASE_PATH}")

        # DATABASE_PATH는 이미 전체 경로를 포함함
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Flask host 조회
        cursor.execute('''
            SELECT value FROM config 
            WHERE category = 'flask' AND key = 'host'
        ''')
        host_row = cursor.fetchone()
        host = host_row[0] if host_row else '127.0.0.1'
        
        # Flask port 조회
        cursor.execute('''
            SELECT value FROM config 
            WHERE category = 'flask' AND key = 'port'
        ''')
        port_row = cursor.fetchone()
        port = port_row[0] if port_row else '5000'
        
        # API 키 조회 (client용)
        cursor.execute('''
            SELECT value FROM config 
            WHERE category = 'api' AND key = 'sensor_stream_key_client'
        ''')
        api_key_row = cursor.fetchone()
        api_key = api_key_row[0] if api_key_row else 'default-key'
        
        conn.close()
        
        # 현재 요청의 프로토콜 확인
        protocol = 'https' if request.is_secure else 'http'
        
        # host가 0.0.0.0인 경우 실제 호스트 주소로 변경
        if host == '0.0.0.0':
            # 요청이 들어온 호스트 사용
            host = request.host.split(':')[0]
        
        print(f"[info] host: {host}")
        print(f"[info] port: {port}")
        print(f"[info] api_key: {api_key}")
        print(f"[info] server_url: {protocol}://{host}:{port}")

        return jsonify({
            'success': True,
            'host': host,
            'port': port,
            'api_key': api_key,
            'server_url': f'{protocol}://{host}:{port}'
        })
        
    except Exception as e:
        print(f"[오류] 서버 설정 조회 실패: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'server_url': 'http://127.0.0.1:5000'  # 기본값
        }), 500

@sensor_dashboard_bp.route('/api/sensor-dashboard/init-data')
def get_init_data():
    """센서 대시보드 초기 데이터 조회 API - CS와 Font 테이블 동시 조회"""
    from app import config_manager, DATABASE_PATH
    
    # API 키 확인
    api_key = request.args.get('api_key')
    if not api_key:
        return jsonify({'error': 'API key required'}), 401
    
    # API 키 검증
    configured_keys = config_manager.get_config('api', 'sensor_stream_key_server')
    if not configured_keys:
        configured_keys = ['default-key']
    
    if isinstance(configured_keys, str):
        configured_keys = [configured_keys.strip()] if ',' not in configured_keys else [k.strip() for k in configured_keys.split(',')]
    
    if api_key not in configured_keys:
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # CS 테이블 데이터 조회
        cursor.execute('SELECT * FROM cs ORDER BY idx ASC')
        cs_rows = cursor.fetchall()
        cs_data = [dict(row) for row in cs_rows]
        cs_columns = list(cs_rows[0].keys()) if cs_rows else []
        
        # Font 테이블 데이터 조회 및 가공
        cursor.execute('SELECT * FROM font_set')
        font_rows = cursor.fetchall()
        
        font_data = {}
        for row in font_rows:
            fcode = row['fcode']
            
            if fcode not in font_data:
                font_data[fcode] = {
                    'id': fcode,
                    'options': []
                }
            
            font_size = int(float(row['fsize'] or 24))
            option = {
                'id': row['fname'],
                'value': row['ftext'] or '',
                'fontSize': font_size,
                'isSize': font_size != 0,
                'fontName': row['ffont'] or '굴림',
                'fontWeight': row['fstyle'] or 'Normal',
                'fontColor': row['fcolor'] or 'White',
                'bgColor': row['fbg'] or 'Transparent'
            }
            
            font_data[fcode]['options'].append(option)
        
        font_columns = list(font_rows[0].keys()) if font_rows else []
        
        return jsonify({
            'success': True,
            'cs': {
                'columns': cs_columns,
                'data': cs_data
            },
            'font': {
                'columns': font_columns,
                'data': font_data
            }
        })
        
    except Exception as e:
        print(f"[오류] 초기 데이터 조회 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()