@echo off
title Daraz Price Tracker & Real-Time Scraper Dashboard
cls
echo ========================================================
echo        DARAZ REAL-TIME PRICE SCRAPER & DASHBOARD
echo ========================================================
echo.
echo Select an option:
echo [1] Run Scraper (Scrape daily item data to database)
echo [2] Launch Dashboard Server (http://localhost:5000)
echo [3] Run BOTH (Scrape first, then launch Dashboard)
echo.
set /p choice="Enter your choice (1, 2, or 3): "

if "%choice%"=="1" goto scrape
if "%choice%"=="2" goto dashboard
if "%choice%"=="3" goto both
goto invalid

:scrape
echo.
echo Starting Daraz Scraper...
python scraper.py
echo Scrape complete!
pause
exit

:dashboard
echo.
echo Starting Dashboard Server...
python app.py
pause
exit

:both
echo.
echo [Step 1/2] Running Scraper...
python scraper.py
echo [Step 2/2] Starting Dashboard Server...
python app.py
pause
exit

:invalid
echo Invalid option selected. Exiting.
pause
exit
