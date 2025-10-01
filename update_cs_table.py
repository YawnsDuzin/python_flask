#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CS 테이블 idx 컬럼을 자동 증가로 변경하는 마이그레이션 스크립트

주의: 이 스크립트는 기존 데이터를 보존하면서 테이블 구조를 변경합니다.
실행 전 반드시 데이터베이스를 백업하세요.
"""

import sqlite3
import os
from datetime import datetime

def backup_database(db_path):
    """데이터베이스 백업 생성"""
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        # 백업 생성
        conn = sqlite3.connect(db_path)
        backup_conn = sqlite3.connect(backup_path)
        conn.backup(backup_conn)
        backup_conn.close()
        conn.close()

        print(f"✓ 데이터베이스 백업 생성: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"✗ 백업 생성 실패: {e}")
        return None

def update_cs_table(db_path):
    """CS 테이블의 idx 컬럼을 자동 증가로 변경"""

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print("\n1. 현재 CS 테이블 구조 확인...")
        cursor.execute("PRAGMA table_info(cs)")
        columns = cursor.fetchall()
        print("   현재 컬럼:")
        for col in columns:
            print(f"   - {col['name']}: {col['type']}")

        print("\n2. 기존 데이터 백업...")
        cursor.execute("SELECT * FROM cs")
        existing_data = cursor.fetchall()
        print(f"   백업된 레코드 수: {len(existing_data)}")

        print("\n3. 새 테이블 생성 (idx 자동 증가)...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cs_new (
                idx INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                use TEXT,
                com_mode TEXT,
                device TEXT,
                type TEXT,
                mode TEXT,
                ip TEXT,
                port TEXT,
                monitor TEXT,
                dv_no TEXT
            )
        """)

        print("\n4. 데이터 이전...")
        for row in existing_data:
            cursor.execute("""
                INSERT INTO cs_new (idx, name, use, com_mode, device, type, mode, ip, port, monitor, dv_no)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['idx'], row['name'], row['use'], row['com_mode'],
                row['device'], row['type'], row['mode'], row['ip'],
                row['port'], row['monitor'], row['dv_no']
            ))
        print(f"   이전된 레코드 수: {len(existing_data)}")

        print("\n5. 테이블 교체...")
        cursor.execute("DROP TABLE cs")
        cursor.execute("ALTER TABLE cs_new RENAME TO cs")

        print("\n6. 시퀀스 재설정...")
        # 현재 최대 idx 값 확인
        cursor.execute("SELECT MAX(idx) FROM cs")
        max_idx = cursor.fetchone()[0]
        if max_idx:
            # AUTOINCREMENT 시퀀스를 현재 최대값으로 설정
            cursor.execute(f"UPDATE sqlite_sequence SET seq = {max_idx} WHERE name = 'cs'")
            print(f"   시퀀스 값 설정: {max_idx}")

        # 변경사항 커밋
        conn.commit()

        print("\n7. 변경 후 테이블 구조 확인...")
        cursor.execute("PRAGMA table_info(cs)")
        columns = cursor.fetchall()
        print("   새 컬럼 구조:")
        for col in columns:
            pk = " (PRIMARY KEY AUTOINCREMENT)" if col['pk'] == 1 else ""
            print(f"   - {col['name']}: {col['type']}{pk}")

        print("\n✓ CS 테이블이 성공적으로 업데이트되었습니다!")
        print("  idx 컬럼이 이제 자동 증가로 설정되었습니다.")

        conn.close()
        return True

    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

def main():
    """메인 실행 함수"""
    # 데이터베이스 경로 설정
    db_path = "sensor.db"

    if not os.path.exists(db_path):
        print(f"✗ 데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        return

    print("=" * 60)
    print("CS 테이블 idx 자동 증가 마이그레이션")
    print("=" * 60)

    # 백업 생성
    backup_path = backup_database(db_path)
    if not backup_path:
        print("\n백업 생성에 실패했습니다. 마이그레이션을 중단합니다.")
        return

    # 사용자 확인
    print(f"\n⚠ 주의: 이 작업은 CS 테이블 구조를 변경합니다.")
    print(f"백업 파일: {backup_path}")
    response = input("\n계속하시겠습니까? (y/N): ")

    if response.lower() != 'y':
        print("마이그레이션이 취소되었습니다.")
        return

    # 테이블 업데이트 실행
    if update_cs_table(db_path):
        print("\n✅ 마이그레이션이 성공적으로 완료되었습니다!")
        print(f"백업 파일은 {backup_path}에 보관되어 있습니다.")
    else:
        print("\n❌ 마이그레이션 실패!")
        print(f"백업 파일에서 복원하려면: {backup_path}")
        print(f"복원 명령: copy {backup_path} {db_path}")

if __name__ == "__main__":
    main()