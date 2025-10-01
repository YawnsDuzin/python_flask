#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
설정 관리 모듈
데이터베이스 기반 설정 관리를 제공합니다.
"""

import sqlite3
import json
import os
from datetime import datetime

class ConfigManager:
    """설정 관리 클래스"""
    
    def __init__(self, db_path='sensor.db'):
        self.db_path = db_path
        self._ensure_tables_exist()
    
    def _get_connection(self):
        """데이터베이스 연결 가져오기"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_tables_exist(self):
        """필요한 테이블이 존재하는지 확인"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # config 테이블 확인
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='config'
        """)
        
        if not cursor.fetchone():
            # config 테이블이 없는 경우 기본 테이블 생성
            print("config 테이블이 존재하지 않습니다. 기본 테이블을 생성합니다.")
            try:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT,
                        data_type TEXT DEFAULT 'string',
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by INTEGER,
                        updated_by INTEGER,
                        UNIQUE(category, key)
                    )
                """)
                conn.commit()
                print("config 테이블이 성공적으로 생성되었습니다.")
            except Exception as e:
                print(f"config 테이블 생성 중 오류 발생: {e}")
                conn.rollback()
            
            # 마이그레이션 스크립트가 있으면 추가 실행
            migration_path = 'database_migration.sql'
            if os.path.exists(migration_path):
                try:
                    with open(migration_path, 'r', encoding='utf-8') as f:
                        migration_sql = f.read()
                        conn.executescript(migration_sql)
                        conn.commit()
                    print("마이그레이션 스크립트가 성공적으로 실행되었습니다.")
                except Exception as e:
                    print(f"마이그레이션 실행 중 오류 발생: {e}")
                    conn.rollback()
        
        conn.close()
    
    def get_config(self, category=None, key=None):
        """설정 값 가져오기"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if category and key:
            # 특정 설정 값 조회
            cursor.execute("""
                SELECT value, data_type
                FROM config
                WHERE category = ? AND key = ?
            """, (category, key))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return self._convert_value(row['value'], row['data_type'])
            return None
        
        elif category:
            # 카테고리별 설정 조회
            cursor.execute("""
                SELECT key, value, data_type
                FROM config
                WHERE category = ?
            """, (category,))
            
            rows = cursor.fetchall()
            conn.close()
            
            result = {}
            for row in rows:
                result[row['key']] = self._convert_value(row['value'], row['data_type'])
            return result
        
        else:
            # 모든 설정 조회
            cursor.execute("""
                SELECT category, key, value, data_type
                FROM config
                ORDER BY category, key
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            result = {}
            for row in rows:
                if row['category'] not in result:
                    result[row['category']] = {}
                result[row['category']][row['key']] = self._convert_value(row['value'], row['data_type'])
            return result
    
    def set_config(self, category, key, value, data_type='string', description='', user_id=None):
        """설정 값 저장"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 값을 문자열로 변환
        value_str = self._convert_to_string(value, data_type)
        
        try:
            # UPSERT 구현 (INSERT OR REPLACE)
            cursor.execute("""
                INSERT INTO config (category, key, value, data_type, description, created_by, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(category, key) DO UPDATE SET
                    value = excluded.value,
                    data_type = excluded.data_type,
                    description = CASE 
                        WHEN excluded.description != '' THEN excluded.description 
                        ELSE config.description 
                    END,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_by = excluded.updated_by
            """, (category, key, value_str, data_type, description, user_id, user_id))
            
            conn.commit()
            conn.close()
            return {'success': True}
        
        except Exception as e:
            conn.close()
            return {'success': False, 'error': str(e)}
    
    def delete_config(self, category, key=None):
        """설정 삭제"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if key:
                # 특정 설정 삭제
                cursor.execute("""
                    DELETE FROM config
                    WHERE category = ? AND key = ?
                """, (category, key))
            else:
                # 카테고리 전체 삭제
                cursor.execute("""
                    DELETE FROM config
                    WHERE category = ?
                """, (category,))
            
            conn.commit()
            conn.close()
            return {'success': True}
        
        except Exception as e:
            conn.close()
            return {'success': False, 'error': str(e)}
    
    def load_from_file(self, config_file='config.json'):
        """config.json 파일에서 설정 로드 (레거시 지원)"""
        if not os.path.exists(config_file):
            return {'success': False, 'error': f'설정 파일을 찾을 수 없습니다: {config_file}'}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return {'success': True, 'config': config}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def save_to_file(self, config=None, config_file='config.json'):
        """설정을 config.json 파일로 저장 (백업용)"""
        if config is None:
            # 데이터베이스에서 모든 설정 가져오기
            config = self.get_config()
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return {'success': True}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def migrate_from_file(self, user_id=None):
        """config.json 파일의 설정을 데이터베이스로 마이그레이션"""
        result = self.load_from_file()
        
        if not result['success']:
            return result
        
        config = result['config']
        errors = []
        
        # 특별 처리가 필요한 항목들
        special_mappings = {
            'process': {
                'process': 'totalsensor_process',
                'path': 'totalsensor_path',
                'exe': 'totalsensor_exe'
            }
        }
        
        for category, settings in config.items():
            if isinstance(settings, dict):
                for key, value in settings.items():
                    # 특별 매핑 처리
                    if category in special_mappings and key in special_mappings[category]:
                        mapped_key = special_mappings[category][key]
                    else:
                        mapped_key = key
                    
                    # 데이터 타입 추론
                    data_type = self._infer_data_type(value)
                    
                    # 설정 저장
                    result = self.set_config(category, mapped_key, value, data_type, user_id=user_id)
                    
                    if not result['success']:
                        errors.append(f"{category}.{mapped_key}: {result['error']}")
        
        if errors:
            return {'success': False, 'errors': errors}
        
        return {'success': True}
    
    
    def _convert_value(self, value_str, data_type):
        """문자열을 지정된 데이터 타입으로 변환"""
        if data_type == 'integer':
            return int(value_str)
        elif data_type == 'float':
            return float(value_str)
        elif data_type == 'boolean':
            return value_str.lower() in ('true', '1', 'yes', 'y')
        elif data_type == 'json':
            return json.loads(value_str)
        else:  # string
            return value_str
    
    def _convert_to_string(self, value, data_type):
        """값을 문자열로 변환"""
        if data_type == 'json' or isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        elif data_type == 'boolean' or isinstance(value, bool):
            return 'true' if value else 'false'
        else:
            return str(value)
    
    def _infer_data_type(self, value):
        """값에서 데이터 타입 추론"""
        if isinstance(value, bool):
            return 'boolean'
        elif isinstance(value, int):
            return 'integer'
        elif isinstance(value, float):
            return 'float'
        elif isinstance(value, (dict, list)):
            return 'json'
        else:
            return 'string'
    
    def _get_default_config(self):
        """기본 설정 반환"""
        return {
            'security': {
                'secret_key': 'itlog@secret#key$production'
            },
            'process': {
                'totalsensor_process': 'itlog-ss2',
                'totalsensor_path': '/home/pi/itlog-main/program/sensor2',
                'totalsensor_exe': 'itlog-ss2.exe'
            },
            'socketserver': {
                'TCP_HOST': '127.0.0.1',
                'TCP_PORT': 3002
            },
            'flask': {
                'host': '0.0.0.0',
                'port': 5002,
                'debug': True
            }
        }
    
    def get_all_configs_list(self, exe_mode=None):
        """모든 설정을 리스트 형태로 조회 (UI 표시용)
        
        Args:
            exe_mode: 'SERVER' 또는 'CLIENT' - EXE_MODE에 따른 필터링
                     - SERVER: gb가 DEFAULT 또는 SERVER인 항목만
                     - CLIENT: gb가 DEFAULT 또는 CLIENT인 항목만
                     - None: 모든 항목 표시
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if exe_mode == 'SERVER':
            # SERVER 모드: DEFAULT와 SERVER 항목만 표시
            cursor.execute("""
                SELECT id, category, key, value, data_type, description, gb,
                       created_at, updated_at
                FROM config
                WHERE gb IS NULL OR gb = '' OR gb = 'DEFAULT' OR gb = 'SERVER'
                ORDER BY category, key
            """)
        elif exe_mode == 'CLIENT':
            # CLIENT 모드: DEFAULT와 CLIENT 항목만 표시
            cursor.execute("""
                SELECT id, category, key, value, data_type, description, gb,
                       created_at, updated_at
                FROM config
                WHERE gb IS NULL OR gb = '' OR gb = 'DEFAULT' OR gb = 'CLIENT'
                ORDER BY category, key
            """)
        else:
            # 모든 항목 표시
            cursor.execute("""
                SELECT id, category, key, value, data_type, description, gb,
                       created_at, updated_at
                FROM config
                ORDER BY category, key
            """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_config_by_id(self, config_id):
        """ID로 특정 설정 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, category, key, value, data_type, description, gb,
                   created_at, updated_at, created_by, updated_by
            FROM config
            WHERE id = ?
        """, (config_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def update_config_by_id(self, config_id, value, updated_by=None, description=None, gb=None):
        """ID로 설정 업데이트"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 기존 설정 확인
            cursor.execute("SELECT * FROM config WHERE id = ?", (config_id,))
            existing = cursor.fetchone()
            
            if not existing:
                conn.close()
                return {'success': False, 'error': '설정을 찾을 수 없습니다.'}
            
            # 설정 업데이트 (gb 필드 포함)
            if description is not None and gb is not None:
                cursor.execute("""
                    UPDATE config 
                    SET value = ?, description = ?, gb = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
                    WHERE id = ?
                """, (value, description, gb, updated_by, config_id))
            elif description is not None:
                cursor.execute("""
                    UPDATE config 
                    SET value = ?, description = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
                    WHERE id = ?
                """, (value, description, updated_by, config_id))
            elif gb is not None:
                cursor.execute("""
                    UPDATE config 
                    SET value = ?, gb = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
                    WHERE id = ?
                """, (value, gb, updated_by, config_id))
            else:
                cursor.execute("""
                    UPDATE config 
                    SET value = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
                    WHERE id = ?
                """, (value, updated_by, config_id))
            
            conn.commit()
            conn.close()
            
            return {'success': True, 'message': '설정이 성공적으로 업데이트되었습니다.'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}