@echo off
title Kunyu Wanguo Quantu - Interaktive Karte
echo.
echo   ========================================
echo     Kunyu Wanguo Quantu - Kartenviewer
echo   ========================================
echo.
echo   Browser oeffnet sich automatisch...
echo   Zum Beenden: Dieses Fenster schliessen.
echo.
start "" http://localhost:8081
python server.py
