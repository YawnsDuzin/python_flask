# Product Requirements Document (PRD)
# IoT 통합 센서 모니터링 시스템

## 1. 제품 개요

### 1.1 제품명
**ITLog Device Manager** - IoT 센서 통합 관리 및 모니터링 시스템

### 1.2 제품 목적
산업 현장의 다양한 IoT 센서 데이터를 실시간으로 수집, 모니터링하고 관리하는 웹 기반 통합 플랫폼 제공

### 1.3 대상 사용자
- **주 사용자**: 산업 현장 관리자, 시설 운영자
- **부 사용자**: 시스템 관리자, 데이터 분석가
- **배포 환경**: Raspberry Pi 기반 엣지 컴퓨팅 환경

## 2. 핵심 기능

### 2.1 실시간 센서 모니터링
- **지원 센서 타입** (10종)
  - PM (미세먼지)
  - O2 (산소)
  - MQ (가스 감지)
  - NOX (질소산화물)
  - GASM (복합 가스)
  - WIND (풍향/풍속)
  - VIBRO (진동)
  - CRACK (균열)
  - TILT (경사)
  - SOUND (소음)

- **실시간 데이터 스트리밍**
  - TCP Socket 통신 (포트 3000)
  - Server-Sent Events (SSE) 웹 스트리밍
  - 5초 이내 데이터 자동 갱신
  - 30초 heartbeat 연결 유지

### 2.2 이중 실행 모드

#### SERVER 모드
- 전체 관리 기능 활성화
- TCP 소켓 서버 연결
- 실시간 데이터 수집
- 모든 설정 변경 가능
- 사용자 관리 기능

#### CLIENT 모드
- 읽기 전용 모니터링
- 자동 viewer 권한 로그인
- 센서 대시보드 중심 UI
- TCP 소켓 비활성화
- 제한된 메뉴 접근

### 2.3 사용자 권한 관리
- **3단계 권한 체계**
  - Admin: 전체 시스템 관리
  - Operator: 운영 및 설정 변경
  - Viewer: 읽기 전용 모니터링
- **보안 기능**
  - Bcrypt 암호화
  - 세션 기반 인증
  - 자동 로그아웃
  - 감사 로그 (옵션)

### 2.4 데이터 관리
- **시계열 데이터 저장**
  - SQLite 데이터베이스
  - 센서별 개별 테이블
  - 타임스탬프 기반 인덱싱
- **데이터 조회 기능**
  - 날짜/시간 범위 검색
  - 페이지네이션 (1000건/페이지)
  - CSV 내보내기
  - 실시간 쿼리 결과

## 3. 시스템 아키텍처

### 3.1 기술 스택
- **Backend**: Flask 2.0+ (Python)
- **Database**: SQLite 3
- **Frontend**: Bootstrap 5, JavaScript (ES6)
- **실시간 통신**: TCP Socket, SSE
- **배포**: PyInstaller (실행파일)

### 3.2 모듈 구조
```
app.py                 # 메인 애플리케이션
├── blueprints/       # 모듈화된 라우트
│   ├── api.py       # REST API 엔드포인트
│   ├── auth.py      # 인증 관리
│   ├── device.py    # 디바이스 CRUD
│   ├── sensor.py    # 센서 설정/조회
│   ├── system.py    # 시스템 관리
│   └── client.py    # CLIENT 모드 전용
├── user_manager.py   # 사용자 관리
├── config_manager.py # 설정 관리
└── system_monitor.py # 시스템 모니터링
```

### 3.3 데이터베이스 스키마
- **device**: 센서 디바이스 정보
- **cs**: 통신 설정
- **setting/setting2**: 시스템 설정
- **led**: LED 디스플레이 설정
- **data_[sensor]**: 센서별 시계열 데이터
- **users**: 사용자 계정
- **config**: 시스템 설정 (key-value)

## 4. 설정 관리

### 4.1 다층 설정 시스템
1. **.env 파일**: 데이터베이스 경로, 실행 모드(SERVER, CLIENT)
2. **config 테이블**: 시스템 설정 (카테고리별)
3. **config_sensor.json**: 센서 UI 설정

### 4.2 설정 카테고리
- database: DB 연결 설정
- socketserver: TCP 서버 설정
- flask: 웹 서버 설정
- authentication: 인증 설정
- api: API 키 관리
- security: 보안 설정
- process: 프로세스 관리

## 5. API 엔드포인트

### 5.1 공개 API
- `/api/public-sensor-config`: 센서 설정 조회
- `/api/public-sensor-stream`: 실시간 데이터 스트림
  - API 키 인증 필요
  - CORS 지원

### 5.2 내부 API
- `/api/sensor-stream`: 인증된 SSE 스트림
- `/api/sensor-data`: 폴링 방식 데이터 조회
- `/api/system-status`: 시스템 상태
- `/api/tcp-command`: TCP 명령 전송
- `/api/restart-sensor`: 센서 프로그램 재시작

## 6. 운영 기능

### 6.1 시스템 관리
- Raspberry Pi 네트워크 설정
- 호스트명 변경
- 안전한 재부팅
- 프로세스 모니터링
- CPU/메모리/온도 모니터링

### 6.2 센서 프로그램 제어
- 원격 재시작
- 프로세스 상태 확인
- 로그 관리
- 자동 복구

## 7. 성능 요구사항

### 7.1 응답 시간
- 웹 페이지 로딩: < 2초
- 실시간 데이터 업데이트: < 1초
- API 응답: < 500ms

### 7.2 동시 접속
- SSE 클라이언트: 최대 50개
- 웹 세션: 최대 100개
- TCP 재연결: 5초 이내

### 7.3 데이터 처리
- 센서 데이터 수신: 1000 msg/sec
- DB 쓰기: 100 records/sec
- 쿼리 응답: 1000 records < 3초

## 8. 보안 요구사항

### 8.1 인증 및 권한
- 세션 기반 인증
- 역할 기반 접근 제어 (RBAC)
- 자동 세션 타임아웃
- SQL 인젝션 방지

### 8.2 데이터 보호
- 패스워드 암호화 (Bcrypt)
- HTTPS 지원 준비
- API 키 인증
- 감사 로그

## 9. 배포 및 설치

### 9.1 배포 형태
- Python 스크립트 실행
- PyInstaller 실행파일
- Docker 컨테이너 (향후)

### 9.2 시스템 요구사항
- OS: Raspberry Pi OS / Ubuntu / Windows
- Python: 3.7+
- 메모리: 최소 1GB RAM
- 저장공간: 최소 500MB

### 9.3 설치 프로세스
```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경 설정
cp .env.example .env
# .env 파일 수정

# 3. 실행
python app.py

# 또는 실행파일 빌드
./build_exe.bat
```

## 10. 향후 개발 계획

### Phase 1 (현재)
- ✅ 기본 모니터링 기능
- ✅ 실시간 데이터 스트리밍
- ✅ 사용자 권한 관리
- ✅ SERVER/CLIENT 모드

### Phase 2 (계획)
- 데이터 시각화 대시보드
- 알람 및 경고 시스템
- 모바일 반응형 UI
- 데이터 분석 기능

### Phase 3 (향후)
- 클라우드 연동
- AI 기반 이상 탐지
- 예측 유지보수
- 다중 사이트 관리

## 11. 제약사항 및 가정

### 11.1 제약사항
- Raspberry Pi 하드웨어 성능 한계
- SQLite 동시 쓰기 제한
- 단일 서버 아키텍처

### 11.2 가정
- 안정적인 네트워크 환경
- 센서 서버 가용성
- 정기적인 데이터베이스 백업

## 12. 용어 정의

| 용어 | 설명 |
|------|------|
| SSE | Server-Sent Events, 서버→클라이언트 단방향 실시간 통신 |
| TCP Socket | 센서 서버와의 양방향 통신 프로토콜 |
| EXE_MODE | 실행 모드 설정 (SERVER/CLIENT) |
| Blueprint | Flask의 모듈화된 라우트 구조 |
| ConfigManager | 데이터베이스 기반 설정 관리 클래스 |

---

**문서 버전**: 1.0.0  
**작성일**: 2025-01-04  
**작성자**: IT Log Development Team  
**최종 수정**: 2025-01-04