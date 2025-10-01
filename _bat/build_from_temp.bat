@echo off
chcp 65001 >nul
echo ========================================
echo 임시 경로에서 빌드 (한글 경로 문제 해결)
echo ========================================
echo.

set TEMP_DIR=C:\temp_build
set CURRENT_DIR=%cd%

echo 1. 임시 디렉토리 생성...
if exist %TEMP_DIR% rmdir /s /q %TEMP_DIR%
mkdir %TEMP_DIR%

echo.
echo 2. 필요한 파일 복사...
xcopy /E /I /Y "*.py" %TEMP_DIR%\
xcopy /E /I /Y "templates" %TEMP_DIR%\templates\
xcopy /E /I /Y "*.json" %TEMP_DIR%\
if exist "static" xcopy /E /I /Y "static" %TEMP_DIR%\static\

echo.
echo 3. 임시 디렉토리로 이동...
cd /d %TEMP_DIR%

echo.
echo 4. PyQt5 GUI 빌드...
pyinstaller --onefile --name "SocketServerTest" SocketServer_SensorTest.py

if errorlevel 1 (
    echo 빌드 실패!
    cd /d "%CURRENT_DIR%"
    pause
    exit /b 1
)

echo.
echo 5. Flask 앱 빌드...
pyinstaller --onefile ^
--add-data "templates;templates" ^
--add-data "config.json;." ^
--add-data "config_sensor.json;." ^
--hidden-import "system_monitor_2" ^
--name "DeviceManager" ^
app.py

if errorlevel 1 (
    echo 빌드 실패!
    cd /d "%CURRENT_DIR%"
    pause
    exit /b 1
)

echo.
echo 6. 실행 파일 복사...
if not exist "%CURRENT_DIR%\dist" mkdir "%CURRENT_DIR%\dist"
copy /Y %TEMP_DIR%\dist\*.exe "%CURRENT_DIR%\dist\"

echo.
echo 7. 원래 디렉토리로 복귀...
cd /d "%CURRENT_DIR%"

echo.
echo 8. 임시 디렉토리 정리...
rmdir /s /q %TEMP_DIR%

echo.
echo ========================================
echo 빌드 완료!
echo ========================================
echo.
echo 생성된 실행 파일:
echo - dist\DeviceManager.exe
echo - dist\SocketServerTest.exe
echo.
pause