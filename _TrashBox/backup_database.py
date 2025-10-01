#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
데이터베이스 백업 스크립트
sensor.db 파일을 타임스탬프가 포함된 이름으로 백업합니다.
"""

import os
import shutil
import json
from datetime import datetime

def load_config():
    """config.json 파일 로드"""
    config_path = 'config.json'
    if not os.path.exists(config_path):
        print(f"설정 파일을 찾을 수 없습니다: {config_path}")
        return None
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_database_path(config):
    """데이터베이스 경로 가져오기"""
    db_config = config.get('database', {})
    
    # path 우선 확인
    db_path = db_config.get('path', './')
    db_file = db_config.get('db', 'sensor.db')
    full_path = os.path.join(db_path, db_file)
    
    if os.path.exists(full_path):
        return full_path
    
    # path1, path2, path3 순차적으로 확인
    for key in ['path1', 'path2', 'path3']:
        if key in db_config:
            alt_path = os.path.join(db_config[key])
            if os.path.exists(alt_path):
                return alt_path
    
    # 기본값 반환
    return full_path

def backup_database():
    """데이터베이스 백업 실행"""
    # 설정 로드
    config = load_config()
    if not config:
        return False
    
    # 데이터베이스 경로 확인
    db_path = get_database_path(config)
    
    if not os.path.exists(db_path):
        print(f"데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        return False
    
    # 백업 디렉토리 생성
    backup_dir = 'backups'
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        print(f"백업 디렉토리 생성: {backup_dir}")
    
    # 타임스탬프 생성
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 백업 파일명 생성
    db_filename = os.path.basename(db_path)
    backup_filename = f"{os.path.splitext(db_filename)[0]}_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        # 파일 복사
        shutil.copy2(db_path, backup_path)
        
        # 파일 크기 확인
        original_size = os.path.getsize(db_path)
        backup_size = os.path.getsize(backup_path)
        
        if original_size == backup_size:
            print(f"백업 성공!")
            print(f"원본 파일: {db_path}")
            print(f"백업 파일: {backup_path}")
            print(f"파일 크기: {backup_size:,} bytes")
            return True
        else:
            print(f"경고: 백업 파일 크기가 일치하지 않습니다!")
            print(f"원본: {original_size:,} bytes")
            print(f"백업: {backup_size:,} bytes")
            return False
            
    except Exception as e:
        print(f"백업 중 오류 발생: {e}")
        return False

def list_backups():
    """백업 파일 목록 표시"""
    backup_dir = 'backups'
    
    if not os.path.exists(backup_dir):
        print("백업 디렉토리가 존재하지 않습니다.")
        return
    
    backups = []
    for filename in os.listdir(backup_dir):
        if filename.endswith('.db'):
            filepath = os.path.join(backup_dir, filename)
            file_stat = os.stat(filepath)
            backups.append({
                'filename': filename,
                'size': file_stat.st_size,
                'modified': datetime.fromtimestamp(file_stat.st_mtime)
            })
    
    if not backups:
        print("백업 파일이 없습니다.")
        return
    
    # 날짜순 정렬 (최신 먼저)
    backups.sort(key=lambda x: x['modified'], reverse=True)
    
    print("\n=== 백업 파일 목록 ===")
    print(f"{'파일명':<40} {'크기':>15} {'수정일시':<20}")
    print("-" * 80)
    
    for backup in backups:
        print(f"{backup['filename']:<40} {backup['size']:>15,} bytes  {backup['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n총 {len(backups)}개의 백업 파일")

if __name__ == "__main__":
    print("=== 데이터베이스 백업 유틸리티 ===\n")
    
    # 백업 실행
    if backup_database():
        print("\n백업이 완료되었습니다.")
    else:
        print("\n백업에 실패했습니다.")
    
    # 백업 목록 표시
    print("")
    list_backups()