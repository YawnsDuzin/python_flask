#!/usr/bin/env python
"""
센서 대시보드 API 엔드포인트 테스트 스크립트
"""

import requests
import json
import sys

# 테스트 설정
BASE_URL = "http://localhost:5000"
API_KEY = "default-key"  # config 테이블에서 설정된 키 사용

def test_cs_table():
    """CS 테이블 API 테스트"""
    print("\n=== CS 테이블 API 테스트 ===")
    url = f"{BASE_URL}/api/sensor-dashboard/cs-table?api_key={API_KEY}"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Columns: {data.get('columns', [])[:5]}...")  # 처음 5개 컬럼만
            print(f"Data rows: {len(data.get('data', []))}")
            
            # 첫 번째 데이터 샘플 출력
            if data.get('data'):
                print(f"First row sample: {json.dumps(data['data'][0], indent=2)}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Test failed: {e}")

def test_font_table():
    """Font 테이블 API 테스트"""
    print("\n=== Font 테이블 API 테스트 ===")
    url = f"{BASE_URL}/api/sensor-dashboard/font-table?api_key={API_KEY}"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Columns: {data.get('columns', [])[:5]}...")  # 처음 5개 컬럼만
            
            # 첫 번째 폰트 코드 데이터 샘플 출력
            font_data = data.get('data', {})
            if font_data:
                first_key = list(font_data.keys())[0]
                print(f"First font code: {first_key}")
                print(f"Options count: {len(font_data[first_key].get('options', []))}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Test failed: {e}")

def test_init_data():
    """초기 데이터 API 테스트"""
    print("\n=== 초기 데이터 API 테스트 ===")
    url = f"{BASE_URL}/api/sensor-dashboard/init-data?api_key={API_KEY}"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success')}")
            
            # CS 데이터
            cs_data = data.get('cs', {})
            print(f"\nCS Data:")
            print(f"  - Columns: {len(cs_data.get('columns', []))}")
            print(f"  - Rows: {len(cs_data.get('data', []))}")
            
            # Font 데이터
            font_data = data.get('font', {})
            print(f"\nFont Data:")
            print(f"  - Columns: {len(font_data.get('columns', []))}")
            print(f"  - Font codes: {len(font_data.get('data', {}))}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Test failed: {e}")

def test_invalid_api_key():
    """잘못된 API 키 테스트"""
    print("\n=== 잘못된 API 키 테스트 ===")
    url = f"{BASE_URL}/api/sensor-dashboard/cs-table?api_key=invalid-key"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print("✓ 올바르게 401 Unauthorized 반환")
        else:
            print(f"✗ 예상과 다른 응답: {response.text}")
            
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    print("센서 대시보드 API 엔드포인트 테스트")
    print("=" * 50)
    
    # 기본 URL과 API 키 설정 확인
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
    if len(sys.argv) > 2:
        API_KEY = sys.argv[2]
        
    print(f"Server URL: {BASE_URL}")
    print(f"API Key: {API_KEY}")
    
    # 테스트 실행
    test_cs_table()
    test_font_table()
    test_init_data()
    test_invalid_api_key()
    
    print("\n" + "=" * 50)
    print("테스트 완료")