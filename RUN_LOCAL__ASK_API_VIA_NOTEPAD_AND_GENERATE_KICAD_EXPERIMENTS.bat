@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Progen KiCad Local Generator - Paste Fix

echo.
echo ============================================================
echo   Progen KiCad Local Experiment Generator
echo   V10.1 paste-safe local runner
echo ============================================================
echo.
echo This version avoids terminal paste issues and uses Groq SDK/preflight checks.
echo It will open a temporary text file. Paste your Groq API key
echo into that file, save it, close Notepad, then come back here.
echo.
echo The key will be read into this process and the temp file will
echo be deleted immediately. It is not committed or stored in repo.
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
    echo.
    echo ERROR: No API key was found.
    echo Re-run this BAT and paste the key into Notepad before saving.
    echo.
    pause
    exit /b 1
)

echo.
echo API key loaded into memory only.
echo.

set /p "GROQ_MODEL=Groq model [llama-3.3-70b-versatile]: "
if "%GROQ_MODEL%"=="" set "GROQ_MODEL=llama-3.3-70b-versatile"

set /p "CIRCUIT_COUNT=How many circuits to generate [55]: "
if "%CIRCUIT_COUNT%"=="" set "CIRCUIT_COUNT=55"

set /p "BATCH_SIZE=Circuits per API call [5]: "
if "%BATCH_SIZE%"=="" set "BATCH_SIZE=5"

set /p "RUN_LABEL=Run label [local_test]: "
if "%RUN_LABEL%"=="" set "RUN_LABEL=local_test"

set /p "INCLUDE_SUPPLEMENTAL=Include supplemental supported-component circuits? y/N: "
if /I "%INCLUDE_SUPPLEMENTAL%"=="y" (
    set "SUPPLEMENTAL_FLAG=--include-supplemental"
) else (
    set "SUPPLEMENTAL_FLAG="
)

echo.
echo Starting local generation...
echo Root: %ROOT%
echo Model: %GROQ_MODEL%
echo Circuit count: %CIRCUIT_COUNT%
echo Batch size: %BATCH_SIZE%
echo Run label: %RUN_LABEL%
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    echo Install Python 3, then re-run this BAT.
    pause
    exit /b 1
)

python "%ROOT%kicad\automation\local_generate_experiments_with_groq.py" ^
    --repo-root "%ROOT%" ^
    --model "%GROQ_MODEL%" ^
    --count "%CIRCUIT_COUNT%" ^
    --batch-size "%BATCH_SIZE%" ^
    --run-label "%RUN_LABEL%" ^
    %SUPPLEMENTAL_FLAG%

set "EXITCODE=%ERRORLEVEL%"
set "GROQ_API_KEY="

echo.
if "%EXITCODE%"=="0" (
    echo DONE. Now run:
    echo   RUN_LOCAL__ZIP_LATEST_KICAD_EXPERIMENT.bat
) else (
    echo FAILED with exit code %EXITCODE%.
    echo Check the latest folder in:
    echo   kicad\experiments\runs\
)
echo.
pause
exit /b %EXITCODE%
