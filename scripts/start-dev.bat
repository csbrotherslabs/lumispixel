@echo off
setlocal
cd /d "%~dp0\.."

python manage.py migrate --noinput
if errorlevel 1 exit /b %errorlevel%

python manage.py check
if errorlevel 1 exit /b %errorlevel%

python manage.py runserver %*
