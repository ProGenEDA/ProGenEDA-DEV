@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Progen KiCad - Test Groq Connection

echo.
echo ============================================================
echo   Progen KiCad - Groq connection test
echo ============================================================
echo.
echo This only tests one tiny Groq request. It does not generate circuits.
echo It uses Notepad so API-key paste works reliably.
echo.

set "ROOT=%~dp0"
set "KEYFILE=%TEMP%\progen_groq_key_%RANDOM%_%RANDOM%.txt"

echo Paste your Groq API key on the first line.>"%KEYFILE%"
echo Save and close Notepad when done.>>"%KEYFILE%"
start /wait notepad "%KEYFILE%"

set "GROQ_API_KEY="
for /f "usebackq tokens=* delims=" %%A in ("%KEYFILE%") do (
    if not defined GROQ_API_KEY (
        set "LINE=%%A"
        if not "!LINE!"=="Paste your Groq API key on the first line." if not "!LINE!"=="Save and close Notepad when done." (
            set "GROQ_API_KEY=%%A"
        )
    )
)
del /q "%KEYFILE%" >nul 2>nul

if not defined GROQ_API_KEY (
    echo ERROR: No API key was found.
    pause
    exit /b 1
)

set /p "GROQ_MODEL=Groq model [llama-3.3-70b-versatile]: "
if "%GROQ_MODEL%"=="" set "GROQ_MODEL=llama-3.3-70b-versatile"

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    pause
    exit /b 1
)

python "%ROOT%kicad\automation\local_generate_experiments_with_groq.py" --test-groq-only

set "EXITCODE=%ERRORLEVEL%"
set "GROQ_API_KEY="
echo.
if "%EXITCODE%"=="0" (
    echo Groq connection OK.
) else (
    echo Groq connection failed. This is network/account/API access, not KiCad generation.
)
echo.
pause
exit /b %EXITCODE%
