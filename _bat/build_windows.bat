@echo off
echo ========================================
echo Windows EXE 빌드 스크립트
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
--icon=NONE ^
--name "DeviceManager" ^
app.py

if errorlevel 1 (
    echo Flask 애플리케이션 빌드 실패!
    pause
    exit /b 1
)

echo.
echo ========================================
echo 2. SocketServerTest.exe (PyQt5 GUI) 빌드
echo ========================================
pyinstaller --onefile --windowed ^
--add-data "config_socket.json;." ^
--icon=NONE ^
--name "SocketServerTest" ^
SocketServer_SensorTest.py

if errorlevel 1 (
    echo PyQt5 애플리케이션 빌드 실패!
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
echo - dist\SocketServerTest.exe (센서 테스트 GUI)
echo.
echo 실행 방법:
echo 1. DeviceManager.exe 실행 후 브라우저에서 http://localhost:5000 접속
echo 2. SocketServerTest.exe 실행하여 센서 테스트
echo.
pause