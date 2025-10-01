# ITLog Device Manager

산업용 IoT 센서 모니터링 플랫폼 - 라즈베리 파이 엣지 컴퓨팅 환경을 위한 Flask 기반 실시간 모니터링 시스템

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Flask](https://img.shields.io/badge/flask-2.0%2B-green)
![License](https://img.shields.io/badge/license-MIT-yellow)
![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%20%7C%20Windows-orange)

## 🚀 주요 기능

- **실시간 센서 모니터링**: Server-Sent Events(SSE)를 통한 실시간 데이터 스트리밍
- **다중 센서 지원**: 미세먼지(PM), 산소(O2), 가스(MQ), 질소산화물(NOx), 가스, 풍향/풍속, 진동, 균열, 기울기, 소음 센서
- **장치 관리**: 센서, 통신 설정, LED 디스플레이 CRUD 작업
- **사용자 관리**: 3단계 권한 시스템 (관리자, 운영자, 뷰어)
- **듀얼 모드 운영**:
  - SERVER 모드: TCP 소켓 연결을 통한 전체 기능
  - CLIENT 모드: 원격 접속을 위한 제한된 모니터링
- **시스템 모니터링**: 실시간 CPU, 메모리, 디스크, 네트워크 상태
- **반응형 웹 인터페이스**: 데스크톱 및 모바일 장치 지원
- **API 접근**: 외부 연동을 위한 키 인증 기반 RESTful API

## 📋 시스템 요구사항

- Python 3.8 이상
- 라즈베리 파이(권장) 또는 Windows
- 2GB 이상 RAM
- 센서 데이터 수집을 위한 네트워크 연결

## 🛠️ 설치 방법

### 1. 저장소 클론
```bash
git clone https://github.com/your-username/itlog-device-manager.git
cd itlog-device-manager
```

### 2. 가상환경 설정
```bash
# 가상환경 생성
python -m venv venv_webapp

# 활성화 (Windows)
venv_webapp\Scripts\activate

# 활성화 (Linux/Mac)
source venv_webapp/bin/activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 환경 설정
프로젝트 루트 디렉토리에 `.env` 파일 생성:
```ini
DATABASE_PATH=./
DATABASE_DB=sensor.db
EXE_MODE=SERVER  # 또는 CLIENT
```

### 5. 데이터베이스 초기화
데이터베이스는 첫 실행 시 자동으로 생성됩니다. 기본 관리자 계정:
- 사용자명: `admin`
- 비밀번호: `admin123` (즉시 변경 필수!)

## 🚀 빠른 시작

### 애플리케이션 실행
```bash
python app.py
```
서버는 `http://0.0.0.0:5000`에서 시작됩니다 (데이터베이스 설정을 통해 변경 가능)

### Windows 실행파일 빌드
```bash
# 제공된 빌드 스크립트 사용
build_exe.bat
```
실행파일과 필요한 모든 파일이 `release/` 폴더에 생성됩니다.

## 🏗️ 시스템 구조

### 실행 모드

| 모드 | 기능 | 사용 사례 |
|------|------|-----------|
| **SERVER** | • 전체 기능<br>• TCP 소켓 연결<br>• 실시간 SSE 스트리밍<br>• 모든 관리 기능<br>• 전체 API 접근 | 엣지 장치에서의 주요 배포 |
| **CLIENT** | • TCP 연결 없음<br>• SSE API 비활성화<br>• 읽기 전용 접근<br>• 뷰어로 자동 로그인 | 원격 모니터링 스테이션 |

### 핵심 구성요소

```
device_manager/
├── app.py                  # 메인 Flask 애플리케이션
├── blueprints/            # 모듈화된 라우트 핸들러
│   ├── api.py            # REST API 엔드포인트
│   ├── auth.py           # 인증
│   ├── device.py         # 장치 관리
│   ├── sensor.py         # 센서 대시보드
│   ├── system.py         # 시스템 모니터링
│   └── user_admin.py     # 사용자 관리
├── templates/             # HTML 템플릿
├── static/               # CSS, JS, 이미지
├── config_sensor.json    # 센서 설정
├── sensor.db            # SQLite 데이터베이스
└── .env                 # 환경 설정
```

## 📊 데이터베이스 스키마

### 핵심 테이블
- `device` - 센서 장치 설정
- `cs` - 통신 설정
- `setting` - 시스템 설정
- `led` - LED 디스플레이 설정
- `users` - 권한을 가진 사용자 계정
- `config` - 키-값 설정 저장소
- `client` - 모니터링용 클라이언트 장치

### 센서 데이터 테이블
- `data_pm`, `data_o2`, `data_mq`, `data_nox`, `data_gasm`
- `data_wind`, `data_vibro`, `data_crack`, `data_tilt`, `data_sound`

## 🔌 API 문서

### 인증
API 엔드포인트는 키 인증이 필요합니다:
```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/sensor-stream
```

### 공개 엔드포인트
- `GET /api/public-sensor-stream` - 실시간 센서 데이터 스트림 (SSE)
- `GET /api/sensor-dashboard/cs` - 통신 설정
- `GET /api/sensor-dashboard/font` - 폰트 설정

### 예제: 센서 데이터 가져오기
```python
import requests
import json

# 최신 센서 데이터 가져오기
response = requests.get(
    'http://localhost:5000/api/sensor-dashboard/cs',
    headers={'X-API-Key': 'your-api-key'}
)
data = response.json()
```

## 🧪 테스트

### 센서 데이터 시뮬레이션
```bash
python Extend/SocketServer_SensorTest.py
```

### API 엔드포인트 테스트
```bash
# 기본 서버
python test_sensor_dashboard_api.py

# 커스텀 서버
python test_sensor_dashboard_api.py http://192.168.1.100:5000 your-api-key
```

## ⚙️ 설정

### 웹 인터페이스
`/admin/config/list`에서 설정 패널 접근 (관리자만)

### 데이터베이스 설정
`config` 테이블은 모드별 설정을 사용:
- `DEFAULT` - 모든 모드에서 사용 가능
- `SERVER` - SERVER 모드에서만
- `CLIENT` - CLIENT 모드에서만

### 센서 설정
`config_sensor.json`을 편집하여 커스터마이즈:
- 표시 필드와 단위
- 상태 표시기
- 색상 스킴
- 아이콘 할당

## 🔒 보안

### 권장사항
1. **기본 자격 증명을 즉시 변경**
2. **Flask 시크릿 키 업데이트** (`app.py`)
3. **데이터베이스에서 고유한 API 키 설정**
4. **프로덕션에서 HTTPS 활성화**
5. **`sensor.db`에 적절한 파일 권한 설정**
6. **민감한 데이터는 환경 변수 사용**

### 권한 레벨
| 레벨 | 접근 권한 |
|------|-----------|
| 관리자 | 전체 시스템 접근 |
| 운영자 | 장치 관리, 사용자 관리 제외 |
| 뷰어 | 읽기 전용 모니터링 |

## 🐛 문제 해결

### 센서 데이터가 나타나지 않음
- `.env`에서 `EXE_MODE=SERVER` 확인
- 설정된 호스트:포트에서 TCP 서버 연결 확인
- 방화벽에서 포트 3000이 차단되지 않았는지 확인

### API가 403 Forbidden 반환
- CLIENT 모드는 SSE API를 비활성화
- 스트리밍이 필요한 경우 SERVER 모드로 전환
- API 키 설정 확인

### 템플릿을 찾을 수 없음 오류
- `templates/` 폴더가 있는지 확인
- 템플릿 경로가 슬래시(/)를 사용하는지 확인
- 파일 권한 확인

### 설정 변경이 나타나지 않음
- `gb` 필드가 현재 EXE_MODE와 일치하는지 확인
- `?refresh=true` 매개변수로 캐시 지우기
- 애플리케이션 재시작

## 📦 배포

### 프로덕션 체크리스트
- [ ] 모든 기본 비밀번호 변경
- [ ] HTTPS/SSL 설정
- [ ] 적절한 로깅 설정
- [ ] 백업 전략 구성
- [ ] 리소스 제한 설정
- [ ] 모니터링 알림 구성

### 배포를 위한 파일 구조
```
release/
├── ITLOG_Device_Manager.exe
├── templates/
├── static/
├── config_sensor.json
├── .env
└── sensor.db
```

## 🤝 기여 방법

1. 저장소 포크
2. 기능 브랜치 생성 (`git checkout -b feature/AmazingFeature`)
3. 변경사항 커밋 (`git commit -m 'Add some AmazingFeature'`)
4. 브랜치에 푸시 (`git push origin feature/AmazingFeature`)
5. Pull Request 열기

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다 - 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 🙏 감사의 말

- 우수한 웹 프레임워크를 제공한 Flask 커뮤니티
- 하드웨어 플랫폼을 제공한 라즈베리 파이 재단
- 모든 기여자와 테스터

## 📞 지원

문제 및 질문 사항:
- GitHub에 이슈 생성
- [Wiki](https://github.com/your-username/itlog-device-manager/wiki) 확인
- [FAQ](docs/FAQ.md) 검토

## 🗺️ 로드맵

- [ ] Docker 컨테이너화
- [ ] PostgreSQL/MySQL 지원
- [ ] 향상된 데이터 시각화
- [ ] 모바일 네이티브 앱
- [ ] 클라우드 동기화
- [ ] 이상 감지를 위한 머신러닝
- [ ] 다국어 지원

---

산업용 IoT 모니터링을 위해 ❤️로 만들었습니다