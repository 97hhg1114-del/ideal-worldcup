@echo off
REM 이상형월드컵 exe 빌드 — worldcup.py 를 고친 뒤에는 다시 실행하세요.
cd /d "%~dp0"
echo [1/2] 아이콘 생성
if not exist icon.ico python make_icon.py || goto :err
echo [2/2] exe 빌드
python -m PyInstaller --onefile --windowed --name IdealWorldcup --icon icon.ico --add-data "icon.ico;." --clean --noconfirm worldcup.py || goto :err
echo.
echo 완료 : %~dp0dist\IdealWorldcup.exe
pause
exit /b 0

:err
echo.
echo [!] 빌드 실패. PyInstaller 와 Pillow 가 설치되어 있는지 확인하세요:
echo     pip install pyinstaller pillow
pause
exit /b 1
