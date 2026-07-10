@echo off
REM Scraping quotidien BRVM : lance app.ingest et note le resultat dans un log.
REM Ce script est appele par le Planificateur de taches Windows.

cd /d "%~dp0.."

echo. >> ingest_log.txt
echo ===== %date% %time% ===== >> ingest_log.txt
"C:\Users\arthu\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m app.ingest >> ingest_log.txt 2>&1

if %errorlevel% neq 0 (
    echo ERREUR : le scraping a echoue (code %errorlevel%) >> ingest_log.txt
)
