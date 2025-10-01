# Raspberry Pi PyInstaller 빌드 환경 구축 가이드

## 1. 시스템 준비

### OS 확인 및 업데이트
```bash
# Raspberry Pi OS 버전 확인
cat /etc/os-release

# 시스템 업데이트
sudo apt update
sudo apt upgrade -y
```

## 2. Python 3.9+ 설치

### Python 버전 확인
```bash
python3 --version
```

### Python 3.9.2 설치
```bash
# 필요한 빌드 도구 설치
sudo apt install -y build-essential tk-dev libncurses5-dev libncursesw5-dev \
libreadline6-dev libdb5.3-dev libgdbm-dev libsqlite3-dev libssl-dev \
libbz2-dev libexpat1-dev liblzma-dev zlib1g-dev libffi-dev

# Python 3.9.2 소스 다운로드 및 빌드 (약 30분 소요)
cd /tmp
wget https://www.python.org/ftp/python/3.9.2/Python-3.9.2.tgz
tar -xf Python-3.9.2.tgz
cd Python-3.9.2
./configure --enable-optimizations
make -j$(nproc)
sudo make altinstall

# 심볼릭 링크 생성 (옵션)
sudo ln -sf /usr/local/bin/python3.9 /usr/bin/python3.9
```

### pip 업그레이드
```bash
python3.9 -m pip install --upgrade pip
```

## 3. 프로젝트 준비

### 프로젝트 디렉토리 생성
```bash
mkdir -p ~/device_manager
cd ~/device_manager
```

### 소스 코드 복사
```bash
# Git 사용 시
git clone [repository_url] .

# 또는 파일 직접 복사 (SCP/SFTP 사용)
scp -r user@source:/path/to/device_manager/* ~/device_manager/
```

## 4. 가상환경 생성 및 라이브러리 설치

### 가상환경 생성
```bash
python3.9 -m venv venv_webapp
source venv_webapp/bin/activate
```

### pip 업그레이드 (가상환경 내)
```bash
pip install --upgrade pip setuptools wheel
```

### 필수 라이브러리 설치
```bash
# requirements.txt가 있는 경우
pip install -r requirements.txt

# 또는 개별 설치
pip install flask>=2.0.0
pip install python-dotenv>=0.19.0
pip install psutil>=5.9.0
pip install bcrypt>=4.0.0
pip install pyinstaller>=5.0.0
```

### PyQt5 설치 (선택사항 - GUI 테스트 도구용)
```bash
# PyQt5는 ARM 아키텍처에서 설치 문제가 있을 수 있음
# 필요한 경우만 설치
sudo apt install -y python3-pyqt5
# 또는
pip install PyQt5>=5.15.0
```

## 5. PyInstaller 실행파일 빌드

### 기본 빌드 (권장)
```bash
# 가상환경 활성화 확인
source venv_webapp/bin/activate

# 단일 실행파일 생성
pyinstaller --onefile \
  --name ITLOG_Device_Manager \
  --add-data "templates:templates" \
  --add-data "static:static" \
  app.py
```

### 상세 옵션 빌드
```bash
pyinstaller --onefile \
  --name ITLOG_Device_Manager \
  --add-data "templates:templates" \
  --add-data "static:static" \
  --add-data "config_sensor.json:." \
  --hidden-import flask \
  --hidden-import psutil \
  --hidden-import bcrypt \
  --noconsole \
  app.py
```

### spec 파일 사용 (고급)
```python
# ITLOG_Device_Manager.spec 파일 생성
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('config_sensor.json', '.')
    ],
    hiddenimports=['flask', 'psutil', 'bcrypt'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5'],  # GUI 불필요 시 제외
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ITLOG_Device_Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 디버깅용 콘솔 표시
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

```bash
# spec 파일로 빌드
pyinstaller ITLOG_Device_Manager.spec
```

## 6. 빌드 결과 확인

### 실행파일 위치
```bash
# dist 폴더에 생성됨
ls -lh dist/
# -rwxr-xr-x 1 pi pi 25M Nov 25 10:30 ITLOG_Device_Manager
```

### 실행파일 정보 확인
```bash
file dist/ITLOG_Device_Manager
# 출력: ELF 32-bit LSB executable, ARM ... (32비트 ARM)
# 또는: ELF 64-bit LSB executable, ARM aarch64 ... (64비트 ARM)
```

## 7. 배포 준비

### release 폴더 생성
```bash
mkdir -p release
cp dist/ITLOG_Device_Manager release/
cp -r templates release/  # 외부 파일로 관리 시
cp -r static release/     # 외부 파일로 관리 시
cp config_sensor.json release/
cp .env.example release/.env
```

### 실행 권한 설정
```bash
chmod +x release/ITLOG_Device_Manager
```

## 8. 테스트 실행

### 기본 실행
```bash
cd release
./ITLOG_Device_Manager
```

### 서비스로 등록 (선택사항)
```bash
# systemd 서비스 파일 생성
sudo tee /etc/systemd/system/device-manager.service << EOF
[Unit]
Description=ITLOG Device Manager
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/device_manager/release
ExecStart=/home/pi/device_manager/release/ITLOG_Device_Manager
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 서비스 활성화 및 시작
sudo systemctl daemon-reload
sudo systemctl enable device-manager.service
sudo systemctl start device-manager.service
```

## 9. 문제 해결

### 라이브러리 누락 오류
```bash
# ldd로 의존성 확인
ldd dist/ITLOG_Device_Manager | grep "not found"

# 필요한 시스템 라이브러리 설치
sudo apt install -y libatlas-base-dev libopenjp2-7
```

### 메모리 부족 (빌드 중)
```bash
# 스왑 파일 추가 (임시)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 빌드 후 제거
sudo swapoff /swapfile
sudo rm /swapfile
```

### SSL 인증서 오류
```bash
# CA 인증서 업데이트
sudo apt install -y ca-certificates
sudo update-ca-certificates
```

## 10. 최적화 팁

### 실행파일 크기 줄이기
```bash
# UPX 압축 사용 (이미 기본 적용)
sudo apt install -y upx-ucl

# strip 적용
strip dist/ITLOG_Device_Manager
```

### 빌드 시간 단축
```bash
# 병렬 빌드
pyinstaller --onefile --log-level=WARN app.py
```

### 크로스 플랫폼 고려사항
- Raspberry Pi Zero/1: ARMv6 (32-bit)
- Raspberry Pi 2: ARMv7 (32-bit)
- Raspberry Pi 3/4: ARMv8 (64-bit, 32-bit OS 가능)
- 가장 낮은 버전에서 빌드하면 상위 호환 가능

## 배포 체크리스트

- [ ] Python 3.9+ 설치 확인
- [ ] 모든 라이브러리 설치 완료
- [ ] PyInstaller 빌드 성공
- [ ] 실행파일 테스트 완료
- [ ] 필요 파일 복사 (templates, static, config 등)
- [ ] .env 파일 설정
- [ ] 데이터베이스 파일 준비 또는 자동 생성 확인
- [ ] 네트워크 포트 방화벽 설정 (5000, 3000)
- [ ] 서비스 자동 시작 설정 (선택사항)