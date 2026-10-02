@echo off
rem ============================================================
rem  A-RWMF full pipeline: tests -> capture+score+axe -> report
rem
rem  Usage:
rem    scripts\run_all.cmd                              full run
rem    scripts\run_all.cmd <manifest.csv> <out_dir>     custom set
rem ============================================================
setlocal
cd /d "%~dp0.."
set A11Y_BROWSER_CHANNEL=chrome

set MANIFEST=human_study\pages-manifest.csv
set OUTDIR=page_captures\run1
if not "%~1"=="" set MANIFEST=%~1
if not "%~2"=="" set OUTDIR=%~2

echo === 1/3  tests ===
python -m pytest tests -q
if errorlevel 1 (
    echo *** tests FAILED - aborting ***
    exit /b 1
)

echo === 2/3  benchmark: capture + score + axe  [manifest=%MANIFEST%] ===
python scripts\run_benchmark_captures.py --manifest "%MANIFEST%" --out "%OUTDIR%"

echo === 3/3  correlation report ===
if exist "human_study\ratings.csv" (
    python scripts\report_correlation_and_compute.py --ratings "human_study\ratings.csv" --system "%OUTDIR%\scores_system.csv" --axe "%OUTDIR%\scores_axe.csv"
) else (
    echo SKIPPED: human_study\ratings.csv does not exist yet.
    echo          That file is written by the human study, not by code.
    echo          Template: human_study\templates\ratings-template.csv
)

echo === done ===
endlocal
