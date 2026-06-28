@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Zip Latest KiCad Experiment Run

echo.
echo Finding latest folder in kicad\experiments\runs ...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$root = Split-Path -Parent '%~f0';" ^
  "$runs = Join-Path $root 'kicad\experiments\runs';" ^
  "if(!(Test-Path $runs)){ throw 'No kicad\experiments\runs folder found.' };" ^
  "$latest = Get-ChildItem $runs -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1;" ^
  "if(!$latest){ throw 'No experiment run folders found.' };" ^
  "$zip = Join-Path $runs ($latest.Name + '.zip');" ^
  "if(Test-Path $zip){ Remove-Item $zip -Force };" ^
  "Compress-Archive -Path (Join-Path $latest.FullName '*') -DestinationPath $zip -Force;" ^
  "Write-Host ('Zipped: ' + $zip);" ^
  "Start-Process explorer.exe $runs;"

echo.
pause
