#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
사용자 관리 모듈
사용자 인증, 권한 관리, 세션 관리 기능을 제공합니다.
"""

import sqlite3
import bcrypt
import json
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import session, redirect, url_for, flash

class UserManager:
    """사용자 관리 클래스"""
    
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
        
        # users 테이블 확인
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='users'
        """)
        
        if not cursor.fetchone():
            # 테이블이 없으면 마이그레이션 스크립트 실행
            migration_path = 'database_migration.sql'
            if os.path.exists(migration_path):
                with open(migration_path, 'r', encoding='utf-8') as f:
                    migration_sql = f.read()
                    conn.executescript(migration_sql)
                    conn.commit()
        
        conn.close()
    
    def create_user(self, username, password, permission='viewer', full_name='', email=''):
        """새 사용자 생성"""
        # 비밀번호 해시화
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO users (username, password_hash, permission, full_name, email)
                VALUES (?, ?, ?, ?, ?)
            """, (username, password_hash.decode('utf-8'), permission, full_name, email))
            
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            return {'success': True, 'user_id': user_id}
        
        except sqlite3.IntegrityError as e:
            conn.close()
            if 'UNIQUE constraint failed' in str(e):
                return {'success': False, 'error': '이미 존재하는 사용자명입니다.'}
            return {'success': False, 'error': str(e)}
        
        except Exception as e:
            conn.close()
            return {'success': False, 'error': str(e)}
    
    def authenticate(self, username, password):
        """사용자 인증"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, password_hash, permission, is_active
            FROM users
            WHERE username = ?
        """, (username,))
        
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return {'success': False, 'error': '사용자를 찾을 수 없습니다.'}
        
        if not user['is_active']:
            conn.close()
            return {'success': False, 'error': '비활성화된 계정입니다.'}
        
        # 비밀번호 확인
        if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            # 마지막 로그인 시간 업데이트
            cursor.execute("""
                UPDATE users SET last_login = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (user['id'],))
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'permission': user['permission']
                }
            }
        else:
            conn.close()
            return {'success': False, 'error': '비밀번호가 일치하지 않습니다.'}
    
    def get_user(self, user_id=None, username=None):
        """사용자 정보 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("""
                SELECT id, username, permission, full_name, email, created_at, last_login, is_active
                FROM users
                WHERE id = ?
            """, (user_id,))
        elif username:
            cursor.execute("""
                SELECT id, username, permission, full_name, email, created_at, last_login, is_active
                FROM users
                WHERE username = ?
            """, (username,))
        else:
            conn.close()
            return None
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return dict(user)
        return None
    
    def get_all_users(self):
        """모든 사용자 목록 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, permission, full_name, email, created_at, last_login, is_active
            FROM users
            ORDER BY username
        """)
        
        users = cursor.fetchall()
        conn.close()
        
        return [dict(user) for user in users]
    
    def update_user(self, user_id, **kwargs):
        """사용자 정보 업데이트"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 허용된 필드만 업데이트
        allowed_fields = ['permission', 'full_name', 'email', 'is_active']
        updates = []
        values = []
        
        for field in allowed_fields:
            if field in kwargs:
                updates.append(f"{field} = ?")
                values.append(kwargs[field])
        
        if not updates:
            conn.close()
            return {'success': False, 'error': '업데이트할 필드가 없습니다.'}
        
        values.append(user_id)
        
        try:
            cursor.execute(f"""
                UPDATE users
                SET {', '.join(updates)}
                WHERE id = ?
            """, values)
            
            conn.commit()
            conn.close()
            return {'success': True}
        
        except Exception as e:
            conn.close()
            return {'success': False, 'error': str(e)}
    
    def change_password(self, user_id, old_password, new_password):
        """비밀번호 변경"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 현재 비밀번호 확인
        cursor.execute("""
            SELECT password_hash
            FROM users
            WHERE id = ?
        """, (user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return {'success': False, 'error': '사용자를 찾을 수 없습니다.'}
        
        # 이전 비밀번호 확인
        if not bcrypt.checkpw(old_password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            conn.close()
            return {'success': False, 'error': '현재 비밀번호가 일치하지 않습니다.'}
        
        # 새 비밀번호 해시화
        new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        try:
            cursor.execute("""
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
            """, (new_password_hash.decode('utf-8'), user_id))
            
            conn.commit()
            conn.close()
            return {'success': True}
        
        except Exception as e:
            conn.close()
            return {'success': False, 'error': str(e)}
    
    def reset_password(self, user_id, new_password):
        """비밀번호 재설정 (관리자용)"""
        # 새 비밀번호 해시화
        new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
            """, (new_password_hash.decode('utf-8'), user_id))
            
            conn.commit()
            conn.close()
            return {'success': True}
        
        except Exception as e:
            conn.close()
            return {'success': False, 'error': str(e)}
    
    def delete_user(self, user_id):
        """사용자 삭제"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM users
                WHERE id = ?
            """, (user_id,))
            
            conn.commit()
            conn.close()
            return {'success': True}
        
        except Exception as e:
            conn.close()
            return {'success': False, 'error': str(e)}
    
    def check_permission(self, user_id, required_permission):
        """권한 확인"""
        permission_levels = {
            'viewer': 1,
            'operator': 2,
            'admin': 3
        }
        
        user = self.get_user(user_id=user_id)
        
        if not user:
            return False
        
        user_level = permission_levels.get(user['permission'], 0)
        required_level = permission_levels.get(required_permission, 999)
        
        return user_level >= required_level


# Flask 데코레이터 헬퍼 함수들
def login_required(f):
    """로그인 필수 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session.get('logged_in'):
            flash('로그인이 필요합니다.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission):
    """권한 필수 데코레이터"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 로그인 체크
            if 'logged_in' not in session or not session.get('logged_in'):
                flash('로그인이 필요합니다.', 'warning')
                return redirect(url_for('auth.login'))
            
            # 레거시 로그인 (config.json)의 경우 permission이 admin으로 설정됨
            user_permission = session.get('permission', 'viewer')
            
            # 권한 레벨 확인
            permission_levels = {
                'viewer': 1,
                'operator': 2,
                'admin': 3
            }
            
            user_level = permission_levels.get(user_permission, 0)
            required_level = permission_levels.get(permission, 999)
            
            if user_level < required_level:
                flash(f'{permission} 권한이 필요합니다. 현재 권한: {user_permission}', 'danger')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """관리자 권한 필수 데코레이터"""
    return permission_required('admin')(f)

def operator_required(f):
    """운영자 권한 필수 데코레이터"""
    return permission_required('operator')(f)