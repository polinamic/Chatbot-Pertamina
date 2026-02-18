@echo off
REM Setup script untuk Chatbot Pertamina - Windows

echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Virtual environment created and dependencies installed!
echo.
echo To activate the environment, run:
echo   venv\Scripts\activate.bat
echo.
echo Then run:
echo   python manage.py migrate
echo   python manage.py createsuperuser
echo   python manage.py runserver
