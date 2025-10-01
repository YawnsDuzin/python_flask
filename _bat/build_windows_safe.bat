@echo off
chcp 65001 >nul
echo ========================================
echo Windows EXE 빌드 스크립트 (안전 모드)
echo ========================================
echo.

REM 빌드 디렉토리 정리
echo 기존 빌드 파일 정리 중...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

echo.
echo ========================================
echo 1. DeviceManager.exe (Flask 웹앱) 빌드
echo ========================================
pyinstaller --onefile ^
--add-data "templates;templates" ^
--add-data "config.json;." ^
--add-data "config_sensor.json;." ^
--hidden-import "system_monitor_2" ^
--name "DeviceManager" ^
app.py

if errorlevel 1 (
    echo Flask 애플리케이션 빌드 실패!
    pause
    exit /b 1
)

echo.
echo ========================================
echo 2. SocketServerTest.exe (PyQt5 GUI) 빌드 - 콘솔 모드
echo ========================================
REM PyQt5 앱을 콘솔 모드로 빌드 (--windowed 제거)
pyinstaller --onefile ^
--name "SocketServerTest" ^
SocketServer_SensorTest.py

if errorlevel 1 (
    echo PyQt5 애플리케이션 빌드 실패!
    echo.
    echo 해결 방법:
    echo 1. 한글이 없는 경로로 프로젝트를 복사
    echo 2. 또는 아래 명령어로 PyQt5 재설치:
    echo    pip uninstall -y PyQt5 PyQt5-Qt5 PyQt5-sip
    echo    pip install PyQt5
    pause
    exit /b 1
)

echo.
echo ========================================
echo 빌드 완료!
echo ========================================
echo.
echo 생성된 실행 파일:
echo - dist\DeviceManager.exe (Flask 웹 서버)
echo - dist\SocketServerTest.exe (센서 테스트)
echo.
pause