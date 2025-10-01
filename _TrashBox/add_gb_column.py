#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sensor.db의 config 테이블에 gb 컬럼(TEXT) 추가 스크립트
"""

import sqlite3
import os
from dotenv import load_dotenv

def add_gb_column():
    """config 테이블에 gb 컬럼 추가"""
    
    # .env 파일 로드
    load_dotenv()
    
    # 데이터베이스 경로 설정
    db_path = os.getenv('DATABASE_PATH', './')
    db_name = os.getenv('DATABASE_DB', 'sensor.db')
    database_full_path = os.path.join(db_path, db_name)
    
    print(f"데이터베이스 경로: {database_full_path}")
    
    # 데이터베이스 파일 확인
    if not os.path.exists(database_full_path):
        print(f"오류: 데이터베이스 파일을 찾을 수 없습니다: {database_full_path}")
        return False
    
    try:
        # 데이터베이스 연결
        conn = sqlite3.connect(database_full_path)
        cursor = conn.cursor()
        
        print("데이터베이스 연결 성공")
        
        # config 테이블 존재 확인
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='config'
        """)
        
        if not cursor.fetchone():
            print("오류: config 테이블이 존재하지 않습니다.")
            conn.close()
            return False
        
        print("config 테이블 확인됨")
        
        # 현재 테이블 구조 확인
        cursor.execute("PRAGMA table_info(config)")
        columns = cursor.fetchall()
        
        print("\n현재 config 테이블 구조:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # gb 컬럼이 이미 존재하는지 확인
        column_names = [col[1] for col in columns]
        if 'gb' in column_names:
            print("\n주의: gb 컬럼이 이미 존재합니다.")
            
            # 기존 데이터 확인
            cursor.execute("SELECT COUNT(*) FROM config WHERE gb IS NOT NULL")
            count = cursor.fetchone()[0]
            print(f"gb 컬럼에 데이터가 있는 레코드 수: {count}")
            
            conn.close()
            return True
        
        # gb 컬럼 추가
        print("\ngb 컬럼 추가 중...")
        cursor.execute("ALTER TABLE config ADD COLUMN gb TEXT")
        
        # 변경사항 커밋
        conn.commit()
        print("gb 컬럼이 성공적으로 추가되었습니다.")
        
        # 변경된 테이블 구조 확인
        cursor.execute("PRAGMA table_info(config)")
        columns = cursor.fetchall()
        
        print("\n수정된 config 테이블 구조:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # 테스트 데이터 삽입 (선택사항)
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO config (category, key, value, gb) 
                VALUES ('test', 'gb_test', 'test_value', 'test_gb_data')
            """)
            conn.commit()
            print("\n테스트 데이터가 추가되었습니다.")
            
            # 테스트 데이터 조회
            cursor.execute("SELECT * FROM config WHERE key = 'gb_test'")
            test_record = cursor.fetchone()
            if test_record:
                print(f"테스트 레코드: {test_record}")
            
        except Exception as e:
            print(f"테스트 데이터 추가 중 오류 (무시됨): {e}")
        
        conn.close()
        print("\n데이터베이스 수정이 완료되었습니다.")
        return True
        
    except sqlite3.Error as e:
        print(f"데이터베이스 오류: {e}")
        return False
    except Exception as e:
        print(f"예상치 못한 오류: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Config 테이블 gb 컬럼 추가 스크립트")
    print("=" * 50)
    
    success = add_gb_column()
    
    if success:
        print("\n✅ 작업이 성공적으로 완료되었습니다.")
    else:
        print("\n❌ 작업 중 오류가 발생했습니다.")
    
    input("\nPress Enter to exit...")