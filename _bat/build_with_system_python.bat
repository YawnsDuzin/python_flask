@echo off
chcp 65001 >nul
echo ========================================
echo 시스템 Python으로 직접 빌드
echo ========================================
echo.

set CURRENT_DIR=%cd%

echo 1. 가상환경 비활성화...
call deactivate 2>nul

echo.
echo 2. 필요한 패키지 설치 (시스템 Python)...
echo 주의: 시스템 Python에 패키지를 설치합니다!
set /p CONTINUE="계속하시겠습니까? (Y/N): "
if /i not "%CONTINUE%"=="Y" goto :end

pip install --user flask psutil pyinstaller
pip install --user PyQt5

echo.
echo 3. 빌드 디렉토리 정리...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

echo.
echo ========================================
echo 4. Flask 웹앱 빌드...
echo ========================================
python -m PyInstaller --onefile ^
--add-data "templates;templates" ^
--add-data "config.json;." ^
--add-data "config_sensor.json;." ^
--hidden-import "system_monitor_2" ^
--name "DeviceManager" ^
app.py

if errorlevel 1 (
    echo Flask 빌드 실패!
    pause
    goto :end
)

echo.
echo ========================================
echo 5. PyQt5 GUI 빌드...
echo ========================================
python -m PyInstaller --onefile --windowed ^
--name "SocketServerTest" ^
SocketServer_SensorTest.py

if errorlevel 1 (
    echo PyQt5 빌드 실패! 콘솔 모드로 재시도...
    python -m PyInstaller --onefile ^
    --name "SocketServerTest" ^
    SocketServer_SensorTest.py
)

echo.
echo ========================================
echo 빌드 완료!
echo ========================================
echo.
echo 생성된 실행 파일:
if exist "dist\DeviceManager.exe" echo ✓ dist\DeviceManager.exe
if exist "dist\SocketServerTest.exe" echo ✓ dist\SocketServerTest.exe
echo.

:end
pause