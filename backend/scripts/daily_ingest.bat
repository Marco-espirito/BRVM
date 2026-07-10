@echo off
REM Scraping quotidien BRVM : lance app.ingest et note le resultat dans un log.
REM Ce script est appele par le Planificateur de taches Windows.

cd /d "%~dp0.."

echo. >> ingest_log.txt
echo ===== %date% %time% ===== >> ingest_log.txt
if defined BRVM_PYTHON (
    "%BRVM_PYTHON%" -m app.ingest >> ingest_log.txt 2>&1
) else (
    py -3 -m app.ingest >> ingest_log.txt 2>&1
)

if %errorlevel% neq 0 (
    echo ERREUR : le scraping a echoue (code %errorlevel%) >> ingest_log.txt
)
