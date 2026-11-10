@echo off
set PORT=%1
if "%PORT%"=="" set PORT=COM3

idf.py -p %PORT% flash
if errorlevel 1 exit /b 1

python -m esptool --chip esp32 -p %PORT% -b 460800 write_flash 0x1a7000 cities15000.bin
if errorlevel 1 exit /b 1

echo City database flashed successfully.
