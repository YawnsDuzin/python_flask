@echo off
chcp 65001 >nul
echo ========================================
echo Flask 웹앱만 빌드 (PyQt5 제외)
echo ========================================
echo.

echo 빌드 디렉토리 정리 중...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

echo.
echo Flask DeviceManager.exe 빌드 중...
pyinstaller --onefile ^
--add-data "templates;templates" ^
--add-data "config.json;." ^
--add-data "config_sensor.json;." ^
--hidden-import "system_monitor_2" ^
--name "DeviceManager" ^
app.py

if errorlevel 1 (
    echo 빌드 실패!
    echo.
    echo 다음을 확인하세요:
    echo 1. templates 폴더가 있는지
    echo 2. config.json, config_sensor.json 파일이 있는지
    echo 3. system_monitor_2.py 파일이 있는지
    pause
    exit /b 1
)

echo.
echo ========================================
echo 빌드 성공!
echo ========================================
echo.
echo 생성된 파일: dist\DeviceManager.exe
echo.
echo 실행 방법:
echo 1. dist\DeviceManager.exe 실행
echo 2. 브라우저에서 http://localhost:5000 접속
echo.
echo PyQt5 GUI는 별도로 Python 스크립트로 실행하세요:
echo python SocketServer_SensorTest.py
echo.
pause