@echo off
title HealthPro Server Launcher
color 0F

echo ===================================================
echo     HEALTHPRO SERVER SUITE - PORTABLE EDITION
echo ===================================================
echo.

:: Get the directory of this script
set "SUITE_DIR=%~dp0"
:: Remove trailing backslash
set "SUITE_DIR=%SUITE_DIR:~0,-1%"

set "MYSQL_BIN=%SUITE_DIR%\mysql\bin\mysqld.exe"
set "PHP_BIN=%SUITE_DIR%\php\php.exe"
:: Fix: Use standard absolute path for datadir to avoid relative path confusion
set "DATA_DIR=%SUITE_DIR%\mysql\data"
set "DOC_ROOT=%SUITE_DIR%\.."

echo [INFO] Suite Directory: %SUITE_DIR%
echo [INFO] Data Directory: %DATA_DIR%

:: 1. Check for binaries
if not exist "%MYSQL_BIN%" (
    echo [ERROR] MySQL not found at %MYSQL_BIN%
    pause
    exit
)
if not exist "%PHP_BIN%" (
    echo [ERROR] PHP not found at %PHP_BIN%
    pause
    exit
)

:: 2. Terminate existing processes to free locks
echo [INIT] Cleaning up old processes...
taskkill /F /IM mysqld.exe /T 2>nul
taskkill /F /IM php.exe /T 2>nul

:: 3. Start MySQL
echo [BOOT] Starting Database Engine...
:: We pass --datadir explicitly to ensure it finds the data
start "HealthProDB" /B "%MYSQL_BIN%" --defaults-file="%SUITE_DIR%\mysql\bin\my.ini" --datadir="%DATA_DIR%" --console > nul 2>&1

:: 4. Start PHP with Ultra-Fast Router
echo [BOOT] Starting Web Engine (Optimized)...
start "HealthProWeb" /B "%PHP_BIN%" -S localhost:80 -t "%DOC_ROOT%" "%DOC_ROOT%\router.php" > nul 2>&1

:: 5. Wait a moment for startup
timeout /t 3 > nul

echo.
echo [SUCCESS] System is Live!
echo [NOTE] Keep this window open. Closing it will stop the server.
echo.
echo ---------------------------------------------------
echo    Access: http://localhost
echo ---------------------------------------------------

:: 6. Open Browser
start http://localhost

:: 7. Loop to keep window open
echo Press any key to STOP SERVER and EXIT...
pause > nul

:: 8. Shutdown
echo.
echo [SHUTDOWN] Stopping services...
taskkill /F /IM mysqld.exe /T 2>nul
taskkill /F /IM php.exe /T 2>nul
echo [DONE] Goodbye.
timeout /t 2 > nul
