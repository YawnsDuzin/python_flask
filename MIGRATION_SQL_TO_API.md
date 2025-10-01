# sensor_dashboard.js DB 처리 방식 변경 가이드

## 변경 사항 요약

센서 대시보드의 데이터베이스 처리 방식이 브라우저 기반 SQL.js에서 Flask API 기반으로 변경되었습니다.

### 이전 방식 (SQL.js)
- 브라우저에서 직접 `sensor.db` 파일을 다운로드
- SQL.js 라이브러리를 사용하여 브라우저에서 SQLite 쿼리 실행
- 보안 및 파일 크기 문제 있음

### 새 방식 (Flask API)
- 서버에서 데이터베이스 쿼리 실행
- API 엔드포인트를 통해 JSON 형태로 데이터 전달
- API 키 인증으로 보안 강화

## 변경된 파일

### 1. 새로 생성된 파일
- `blueprints/sensor_dashboard.py` - 센서 대시보드 전용 API 블루프린트
- `test_sensor_dashboard_api.py` - API 테스트 스크립트

### 2. 수정된 파일
- `blueprints/__init__.py` - 새 블루프린트 등록 추가
- `static/js/sensor_dashboard.js` - SQL.js 코드를 API 호출로 변경
- `templates/sensor_dashboard/sensor_dashboard.html` - SQL.js 라이브러리 참조 제거

## API 엔드포인트

### 1. CS 테이블 데이터 조회
```
GET /api/sensor-dashboard/cs-table?api_key={API_KEY}
```

### 2. Font 테이블 데이터 조회
```
GET /api/sensor-dashboard/font-table?api_key={API_KEY}
```

### 3. 초기 데이터 (CS + Font) 동시 조회
```
GET /api/sensor-dashboard/init-data?api_key={API_KEY}
```

## 주요 코드 변경 내용

### sensor_dashboard.js

#### 제거된 함수들:
- `initSQLite()` - SQL.js 초기화
- `isTableExists()` - 테이블 존재 확인
- `getTableInfo()` - 테이블 정보 조회
- `getTableData()` - 테이블 데이터 조회

#### 변경된 함수들:
- `initDatabaseAPI()` - API 초기화 (initSQLite 대체)
- `loadLocalDatabase()` - API를 통한 데이터 로드
- `loadCSTableData()` - API 엔드포인트 호출

## 테스트 방법

### 1. 서버 시작
```bash
python app.py
```

### 2. API 테스트
```bash
# 기본 테스트 (localhost:5000, default-key 사용)
python test_sensor_dashboard_api.py

# 커스텀 서버와 API 키 사용
python test_sensor_dashboard_api.py http://192.168.1.100:5000 your-api-key
```

### 3. 웹 브라우저에서 확인
1. 센서 대시보드 페이지 접속
2. 개발자 도구(F12) > Console 탭 확인
3. "데이터베이스 로드 완료" 메시지 확인
4. 센서 데이터가 정상적으로 표시되는지 확인

## API 키 설정

`config` 테이블에서 API 키 설정:
```sql
-- 기본 설정 확인
SELECT * FROM config WHERE key = 'sensor_stream_key_server';

-- API 키 변경
UPDATE config 
SET value = 'your-new-api-key' 
WHERE section = 'api' AND key = 'sensor_stream_key_server';
```

## 트러블슈팅

### 문제: "Invalid API key" 에러
- config 테이블의 `sensor_stream_key_server` 값 확인
- JavaScript의 `API_KEY` 변수가 올바른지 확인

### 문제: CORS 에러
- Flask 서버가 실행 중인지 확인
- `SERVER_URL`이 올바른지 확인

### 문제: 데이터가 표시되지 않음
- 데이터베이스에 CS, font_set 테이블이 있는지 확인
- API 엔드포인트가 정상 응답하는지 테스트 스크립트로 확인

## 롤백 방법

변경사항을 되돌리려면:
1. Git을 사용 중이라면: `git revert` 또는 `git reset`
2. 백업 파일이 있다면 복원
3. 수동 복원이 필요한 경우 이전 SQL.js 코드 복원 필요