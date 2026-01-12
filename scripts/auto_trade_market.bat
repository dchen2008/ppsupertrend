@echo off
REM
REM Launch Market-Aware Trading Bot with Dynamic Risk/Reward
REM Uses 3H PP SuperTrend for market direction (bull/bear)
REM
REM Usage:
REM   auto_trade_market.bat at=account1 fr=EUR_USD tf=5m
REM   auto_trade_market.bat at=account2 fr=EUR_USD tf=15m
REM
REM Examples:
REM   auto_trade_market.bat at=account1 fr=EUR_USD tf=5m
REM   auto_trade_market.bat at=account1 fr=GBP_USD tf=15m
REM   auto_trade_market.bat at=account2 fr=USD_JPY tf=5m

setlocal enabledelayedexpansion

REM Check if correct number of arguments
if "%~3"=="" (
    echo.
    echo ERROR: Invalid number of arguments
    echo.
    echo Usage: %~nx0 at=^<account^> fr=^<instrument^> tf=^<timeframe^>
    echo.
    echo Examples:
    echo   %~nx0 at=account1 fr=EUR_USD tf=5m
    echo   %~nx0 at=account2 fr=EUR_USD tf=15m
    echo   %~nx0 at=account1 fr=GBP_USD tf=5m
    echo.
    echo Parameters:
    echo   at=account1^|account2^|account3  - Trading account to use
    echo   fr=EUR_USD^|GBP_USD^|USD_JPY...  - Currency pair to trade
    echo   tf=5m^|15m                      - Trading timeframe
    echo.
    echo Note: Account-specific configuration will be loaded from:
    echo       ^<account^>\config.yaml
    exit /b 1
)

REM Parse arguments - store raw values
set "ARG1=%~1"
set "ARG2=%~2"
set "ARG3=%~3"

REM Initialize variables
set "ACCOUNT="
set "INSTRUMENT="
set "TIMEFRAME="

REM Parse each argument (order independent)
for %%A in ("%ARG1%" "%ARG2%" "%ARG3%") do (
    set "ARG=%%~A"
    call :ParseArg
)

REM Validate all required parameters were found
if "%ACCOUNT%"=="" (
    echo ERROR: Account not specified. Use at=account1, at=account2, etc.
    exit /b 1
)
if "%INSTRUMENT%"=="" (
    echo ERROR: Instrument not specified. Use fr=EUR_USD, fr=GBP_USD, etc.
    exit /b 1
)
if "%TIMEFRAME%"=="" (
    echo ERROR: Timeframe not specified. Use tf=5m or tf=15m
    exit /b 1
)

goto :ContinueAfterParse

:ParseArg
if "%ARG:~0,3%"=="at=" set "ACCOUNT=%ARG:~3%"
if "%ARG:~0,3%"=="fr=" set "INSTRUMENT=%ARG:~3%"
if "%ARG:~0,3%"=="tf=" set "TIMEFRAME=%ARG:~3%"
goto :eof

:ContinueAfterParse

REM Validate timeframe value
if not "%TIMEFRAME%"=="5m" if not "%TIMEFRAME%"=="15m" (
    echo ERROR: Timeframe must be 5m or 15m ^(got: %TIMEFRAME%^)
    exit /b 1
)

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
REM Remove trailing backslash and get parent directory
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%i in ("%SCRIPT_DIR%") do set "PROJECT_ROOT=%%~dpi"
set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

REM Check configuration files
set "DEFAULT_CONFIG=%PROJECT_ROOT%\src\config.yaml"
set "ACCOUNT_CONFIG=%PROJECT_ROOT%\%ACCOUNT%\config.yaml"

REM Display configuration
echo.
echo ================================================================================
echo    LAUNCHING MARKET-AWARE TRADING BOT
echo ================================================================================
echo Account:     %ACCOUNT%
echo Instrument:  %INSTRUMENT%
echo Timeframe:   %TIMEFRAME%
echo.

REM Check which config files exist
echo Configuration:
if exist "%DEFAULT_CONFIG%" (
    echo   Default Config: %DEFAULT_CONFIG% [OK]
) else (
    echo   Default Config: Not found ^(using built-in defaults^)
)

if exist "%ACCOUNT_CONFIG%" (
    echo   Account Config: %ACCOUNT_CONFIG% [OK] ^(overrides defaults^)
    set "CONFIG_TO_DISPLAY=%ACCOUNT_CONFIG%"
) else (
    echo   Account Config: Not found ^(using defaults only^)
    set "CONFIG_TO_DISPLAY=%DEFAULT_CONFIG%"
)

echo.
echo Starting bot in 3 seconds...
echo Press Ctrl+C to stop
echo.
timeout /t 3 /nobreak >nul

REM Change to project root directory
cd /d "%PROJECT_ROOT%"

REM Create log and csv directories if they don't exist
if not exist "%ACCOUNT%\logs" mkdir "%ACCOUNT%\logs"
if not exist "%ACCOUNT%\csv" mkdir "%ACCOUNT%\csv"

REM Run the market-aware bot
python -m src.trading_bot_market_aware %ACCOUNT_ARG% %INSTRUMENT_ARG% %TIMEFRAME_ARG%

endlocal
