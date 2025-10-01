@echo off
chcp 65001 >nul
echo ========================================
echo 새로운 가상환경으로 빌드 (한글 경로 문제 해결)
echo ========================================
echo.

set NEW_ENV=C:\temp_venv
set TEMP_BUILD=C:\temp_build
set CURRENT_DIR=%cd%

echo 1. 기존 임시 환경 정리...
if exist %NEW_ENV% rmdir /s /q %NEW_ENV%
if exist %TEMP_BUILD% rmdir /s /q %TEMP_BUILD%

echo.
echo 2. 새로운 가상환경 생성 (영문 경로)...
python -m venv %NEW_ENV%

echo.
echo 3. 가상환경 활성화 및 패키지 설치...
call %NEW_ENV%\Scripts\activate.bat

echo.
echo 4. 필요한 패키지 설치...
pip install --upgrade pip
pip install flask psutil pyinstaller
pip install PyQt5

echo.
echo 5. 빌드용 임시 디렉토리 생성...
mkdir %TEMP_BUILD%

echo.
echo 6. 소스 파일 복사...
xcopy /Y "*.py" %TEMP_BUILD%\
xcopy /E /I /Y "templates" %TEMP_BUILD%\templates\
xcopy /Y "*.json" %TEMP_BUILD%\
if exist "static" xcopy /E /I /Y "static" %TEMP_BUILD%\static\

echo.
echo 7. 빌드 디렉토리로 이동...
cd /d %TEMP_BUILD%

echo.
echo ========================================
echo 8. Flask 웹앱 빌드...
echo ========================================
pyinstaller --onefile ^
--add-data "templates;templates" ^
--add-data "config.json;." ^
--add-data "config_sensor.json;." ^
--hidden-import "system_monitor_2" ^
--name "DeviceManager" ^
app.py

if errorlevel 1 (
    echo Flask 빌드 실패!
    goto :cleanup
)

echo.
echo ========================================
echo 9. PyQt5 GUI 빌드...
echo ========================================
pyinstaller --onefile --windowed ^
--name "SocketServerTest" ^
SocketServer_SensorTest.py

if errorlevel 1 (
    echo PyQt5 빌드 실패! 콘솔 모드로 재시도...
    pyinstaller --onefile ^
    --name "SocketServerTest" ^
    SocketServer_SensorTest.py
)

echo.
echo 10. 실행 파일 복사...
if not exist "%CURRENT_DIR%\dist" mkdir "%CURRENT_DIR%\dist"
copy /Y %TEMP_BUILD%\dist\*.exe "%CURRENT_DIR%\dist\"

:cleanup
echo.
echo 11. 정리 작업...
call %NEW_ENV%\Scripts\deactivate.bat
cd /d "%CURRENT_DIR%"

echo.
echo 12. 임시 파일 삭제 여부 확인...
set /p DELETE_TEMP="임시 환경을 삭제하시겠습니까? (Y/N): "
if /i "%DELETE_TEMP%"=="Y" (
    echo 임시 파일 삭제 중...
    rmdir /s /q %NEW_ENV%
    rmdir /s /q %TEMP_BUILD%
)

echo.
echo ========================================
echo 빌드 완료!
echo ========================================
echo.
if exist "%CURRENT_DIR%\dist\DeviceManager.exe" (
    echo ✓ dist\DeviceManager.exe (Flask 웹 서버)
) else (
    echo ✗ DeviceManager.exe 빌드 실패
)
if exist "%CURRENT_DIR%\dist\SocketServerTest.exe" (
    echo ✓ dist\SocketServerTest.exe (센서 테스트)
) else (
    echo ✗ SocketServerTest.exe 빌드 실패
)
echo.
pause