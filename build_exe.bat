@echo off
chcp 65001 >nul
REM Flask Application PyInstaller Build Script
REM Only .py files included in executable, other files copied separately
REM Created: 2025-09-04

echo ================================
echo Flask App PyInstaller Build Script
echo ================================
echo.

REM Check current directory
echo Current working directory: %CD%
echo.

REM Check virtual environment activation
if exist "venv_webapp\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv_webapp\Scripts\activate.bat >nul 2>&1
    echo Virtual environment activated.
) else (
    echo Warning: Virtual environment not found.
    echo Continuing without virtual environment...
    timeout /t 3 >nul
)

echo.
echo Checking required files...

REM Check required files
if not exist "app.py" (
    echo Error: app.py file not found.
    pause
    exit /b
)

if not exist "templates" (
    echo Error: templates folder not found.
    pause
    exit /b
)

@REM if not exist "static" (
@REM     echo Error: static folder not found.
@REM     pause
@REM     exit /b
@REM )

echo All required files found.
echo.

REM Clean existing build files
echo Cleaning existing build files...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "*.spec" del /q *.spec

echo.
echo Starting PyInstaller build...
echo Only Python files will be included in executable...
echo.

REM PyInstaller 명령 실행 (파일들은 별도 복사)
pyinstaller ^
    --onefile ^
    --name="ITLOG_Device_Manager" ^
    --hidden-import="flask" ^
    --hidden-import="psutil" ^
    --hidden-import="bcrypt" ^
    --hidden-import="python-dotenv" ^
    --hidden-import="user_manager" ^
    --hidden-import="config_manager" ^
    --hidden-import="system_monitor" ^
    --hidden-import="blueprints" ^
    --hidden-import="blueprints.auth" ^
    --hidden-import="blueprints.device" ^
    --hidden-import="blueprints.sensor" ^
    --hidden-import="blueprints.system" ^
    --hidden-import="blueprints.client" ^
    --hidden-import="blueprints.user_admin" ^
    --hidden-import="blueprints.config_admin" ^
    --hidden-import="blueprints.api" ^
    --console ^
    app.py

echo.
if %ERRORLEVEL% EQU 0 (
    echo ================================
    echo Build Success!
    echo ================================
    echo.
    
    REM Create release folder and copy files
    echo Preparing release folder...
    if not exist "release" mkdir release
    
    REM Copy executable
    if exist "dist\ITLOG_Device_Manager.exe" (
        echo Copying executable...
        copy "dist\ITLOG_Device_Manager.exe" "release\"
    )
    
    REM Copy templates folder
    echo Copying templates folder...
    if exist "release\templates" rmdir /s /q "release\templates"
    xcopy "templates" "release\templates" /E /I /Y
    
    REM Copy static folder
    echo Copying static folder...
    if exist "release\static" rmdir /s /q "release\static"
    xcopy "static" "release\static" /E /I /Y
    
    REM Copy blueprints templates (if exists)
    if exist "blueprints\templates" (
        echo Copying blueprints templates...
        xcopy "blueprints\templates" "release\templates" /E /Y
    )
    
    REM Copy configuration files
    echo Copying configuration files...
    if exist "config_sensor.json" copy "config_sensor.json" "release\"
    if exist ".env" copy ".env" "release\"
    if exist "requirements.txt" copy "requirements.txt" "release\"
    
    REM Copy database file (if exists)
    if exist "sensor.db" (
        echo Copying database file...
        copy "sensor.db" "release\"
    )
    
    REM Generate README file
    echo Creating deployment guide...
    (
        echo ITLOG Device Manager - Deployment Guide
        echo =====================================
        echo.
        echo How to run:
        echo   ITLOG_Device_Manager.exe
        echo.
        echo Required files:
        echo   - ITLOG_Device_Manager.exe  ^(executable file^)
        echo   - templates/                ^(HTML template folder^)
        echo   - static/                   ^(CSS, JS, image folder^)
        echo   - config_sensor.json        ^(sensor config file^)
        echo   - .env                      ^(environment config file^)
        echo   - sensor.db                 ^(database file, optional^)
        echo.
        echo Configuration check:
        echo   1. Check DATABASE_PATH=./ in .env file
        echo   2. Set EXE_MODE=SERVER or CLIENT in .env file
        echo   3. Allow port 5000 in firewall
        echo.
        echo Access URL:
        echo   http://localhost:5000
        echo   or
        echo   http://^<server-IP^>:5000
        echo.
        echo Troubleshooting:
        echo   - sensor.db file will be created automatically if not exists
        echo   - Change port in config_sensor.json if port conflict occurs
        echo   - Check logs in console window
    ) > "release\README.txt"
    
    echo.
    echo ================================
    echo Deployment Complete!
    echo ================================
    echo.
    echo Release files are ready in release folder:
    echo.
    dir /b "release"
    echo.
    echo Copy all files in release folder to target server.
    
) else (
    echo ================================
    echo Build Failed!
    echo ================================
    echo Error code: %ERRORLEVEL%
    echo Please check the error messages above.
)

echo.
pause