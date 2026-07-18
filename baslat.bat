@echo off
chcp 65001 > nul
title Spor Istanbul Rezervasyon Botu
echo ===================================
echo Spor Istanbul Botu Baslatiliyor...
echo ===================================
echo.

python gui.py

if errorlevel 1 (
    echo.
    echo ===================================
    echo HATA: Uygulama bir hata ile kapandi.
    echo Hata detaylarini yukarida inceleyebilirsiniz.
    echo ===================================
    pause
)
