#!/usr/bin/env python
"""
Flask 서버 설정 API 테스트 스크립트
config 테이블에서 host와 port 정보를 가져오는 API 테스트
"""

import requests
import json

def test_server_config():
    """서버 설정 API 테스트"""
    print("=== 서버 설정 API 테스트 ===")
    print("-" * 50)
    
    # 로컬 서버로 요청
    url = "http://localhost:5000/api/sensor-dashboard/server-config"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print("-" * 50)
        
        if response.status_code == 200:
            data = response.json()
            print("Response Data:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            if data.get('success'):
                print("\n✓ API 호출 성공!")
                print(f"  - Host: {data.get('host')}")
                print(f"  - Port: {data.get('port')}")
                print(f"  - API Key: {data.get('api_key')}")
                print(f"  - Server URL: {data.get('server_url')}")
            else:
                print("\n✗ API 호출 실패:")
                print(f"  에러: {data.get('error')}")
        else:
            print(f"✗ HTTP 에러: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("✗ 서버에 연결할 수 없습니다. Flask 서버가 실행 중인지 확인하세요.")
    except Exception as e:
        print(f"✗ 테스트 실패: {e}")

if __name__ == "__main__":
    print("\nFlask 서버 설정 API 테스트")
    print("=" * 50)
    print("이 테스트는 config 테이블에서 Flask host/port 설정을 가져옵니다.")
    print("=" * 50)
    
    test_server_config()
    
    print("\n" + "=" * 50)
    print("테스트 완료")
    
    print("\n[참고] config 테이블 확인 SQL:")
    print("-- Flask 서버 설정:")
    print("SELECT * FROM config WHERE section='flask' AND key IN ('host', 'port');")
    print("\n-- API 키 설정:")
    print("SELECT * FROM config WHERE section='api' AND key='sensor_stream_key_client';")