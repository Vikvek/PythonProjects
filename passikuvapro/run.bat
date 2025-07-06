@echo off
python -m venv venv
call venv\Scripts\activate
pip install opencv-python pillow
echo Run using: python main.py
pause
