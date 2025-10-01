"""
센서 관련 블루프린트
실시간 센서 데이터, 센서 설정, 센서 쿼리 기능을 담당합니다.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from user_manager import login_required, operator_required
import json
import sqlite3
import time
import csv
from io import StringIO
from datetime import datetime, timedelta
import sys
import os

# 상위 디렉토리의 모듈을 import하기 위한 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sensor_bp = Blueprint('sensor', __name__)

@sensor_bp.route('/realtime-data')
@login_required
def realtime_data():
    """실시간 데이터 모니터링"""
    return render_template('realtime_data.html')


@sensor_bp.route('/sensor/dashboard')
@login_required
def sensor_dashboard():
    """센서 대시보드 - CLIENT 모드용"""
    return render_template('sensor_dashboard/sensor_dashboard.html')


@sensor_bp.route('/sensor/query', methods=['GET', 'POST'])
@login_required
def sensor_query():
    """센서 데이터 조회"""
    from app import get_db_connection, check_table_exists
    
    # standalone 파라미터 확인 (base.html 사용 여부)
    standalone = request.args.get('standalone', '').lower() in ('true', '1', 'yes')
    
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
        all_data = request.form.get('all_data') == 'on'
        
        # 센서 타입 검증
        valid_types = [table for table, name in sensor_types]
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
        
        # 테이블 존재 확인
        if not check_table_exists(sensor_type, conn):
            flash(f'센서 데이터 테이블({sensor_type})이 존재하지 않습니다.', 'error')
            conn.close()
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
            
            conn.close()
            
            return render_template('sensor_query.html',
                                 sensor_types=sensor_types,
                                 sensor_data=sensor_data,
                                 sensor_name=sensor_name,
                                 selected_sensor=sensor_type,
                                 selected_start=start_date,
                                 selected_end=end_date,
                                 selected_start_time=start_time,
                                 selected_end_time=end_time,
                                 selected_all=all_data,
                                 data_count=len(sensor_data))
            
        except sqlite3.Error as e:
            conn.close()
            flash(f'데이터베이스 오류: {e}', 'error')
            return render_template('sensor_query.html', 
                                 sensor_types=sensor_types,
                                 selected_sensor=sensor_type,
                                 selected_start=start_date,
                                 selected_end=end_date,
                                 selected_start_time=start_time,
                                 selected_end_time=end_time,
                                 selected_all=all_data)
    
    # GET 요청 - 조회 폼 표시
    return render_template('sensor_query.html', 
                         sensor_types=sensor_types,
                         default_sensor_type=default_sensor_type,
                         selected_sensor=default_sensor_type)


@sensor_bp.route('/sensor/config', methods=['GET', 'POST'])
@operator_required  # operator 이상 권한 필요
def sensor_config():
    """사용센서 설정"""
    from app import get_db_connection, check_table_exists, config_manager, refresh_sensor_config_cache
    
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
                    return redirect(url_for('sensor.sensor_config'))
                
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
                device_mode = request.form.get('device_mode', '')
                led_use = request.form.get('led_use', 'N')
                com_mode = request.form.get('com_mode', '')

                if not device_idx:
                    flash('디바이스를 선택해주세요.', 'error')
                    return redirect(url_for('sensor.sensor_config'))

                if not com_mode:
                    flash('통신모드를 선택해주세요.', 'error')
                    return redirect(url_for('sensor.sensor_config'))

                # 선택된 디바이스 정보 조회
                selected_device = conn.execute('SELECT * FROM device WHERE idx = ?', (device_idx,)).fetchone()
                if not selected_device:
                    flash('선택된 디바이스를 찾을 수 없습니다.', 'error')
                    return redirect(url_for('sensor.sensor_config'))

                device_type = selected_device['type']

                # 트랜잭션 시작
                conn.execute('BEGIN')

                # 1. 모든 디바이스 비활성화
                conn.execute('UPDATE device SET use = "N"')

                # 2. 선택된 디바이스만 활성화 및 mode 업데이트
                conn.execute('UPDATE device SET use = "Y", mode = ? WHERE idx = ?', (device_mode, device_idx))
                
                # 3. 모든 LED 비활성화 후 선택된 타입만 설정
                conn.execute('UPDATE led SET use = "N"')
                if led_use == 'Y':
                    conn.execute('UPDATE led SET use = "Y" WHERE type = ?', (device_type,))
                
                # 4. 모든 CS의 use를 "N"으로 설정
                conn.execute('UPDATE cs SET use = "N"')
                
                # 5. 선택된 디바이스 타입의 CS 레코드 업데이트
                cs_record = conn.execute('SELECT * FROM cs WHERE type = ?', (device_type,)).fetchone()
                if cs_record:
                    # 기존 레코드 업데이트
                    if com_mode == 'SERVER':
                        # SERVER 모드인 경우 use = "Y"
                        conn.execute('UPDATE cs SET use = "Y", com_mode = ? WHERE type = ?', 
                                   (com_mode, device_type))
                    else:
                        # StandAlone 모드인 경우 use = "N"
                        conn.execute('UPDATE cs SET use = "N", com_mode = ? WHERE type = ?', 
                                   (com_mode, device_type))
                else:
                    # 새 레코드 생성
                    cs_use = 'Y' if com_mode == 'SERVER' else 'N'
                    conn.execute('INSERT INTO cs (type, use, com_mode) VALUES (?, ?, ?)',
                               (device_type, cs_use, com_mode))
                
                # 6. setting 테이블의 mode 업데이트
                conn.execute('UPDATE setting SET mode = ? WHERE rowid = (SELECT MIN(rowid) FROM setting)', 
                           (com_mode,))
                
                # 트랜잭션 커밋
                conn.commit()
                
                flash(f'"{selected_device["name"]}" 디바이스가 활성화되었습니다. (통신모드: {com_mode})', 'success')
                
            else:
                flash('잘못된 요청입니다.', 'error')
            
            conn.close()
            return redirect(url_for('sensor.sensor_config'))
            
        except sqlite3.Error as e:
            conn.rollback()
            conn.close()
            flash(f'설정 저장 중 오류가 발생했습니다: {e}', 'error')
            return redirect(url_for('sensor.sensor_config'))
    
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