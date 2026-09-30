@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem ---------- Preparation du venv (premiere fois seulement) ----------
if exist venv\Scripts\python.exe goto menu

echo Creation de l'environnement, premiere fois seulement...
set PY=
where py >nul 2>nul && set PY=py
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY (
  echo Python introuvable. Installe Python 3.12 depuis python.org
  pause
  exit /b 1
)

%PY% -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 venv\Scripts\python.exe -m pip install PyQt6 matplotlib

rem ---------- Menu ----------
:menu
cls
echo ==============================
echo            OzdAka
echo ==============================
echo.
echo   1. Lancer la carte (simulation)
echo   2. Editeur de cartes
echo   3. Quitter
echo.
set /p choix=Ton choix (1, 2 ou 3) : 

if "%choix%"=="1" goto carte
if "%choix%"=="2" goto editeur
if "%choix%"=="3" exit /b 0
goto menu

:carte
venv\Scripts\python.exe -m client.carte_ville
goto menu

:editeur
venv\Scripts\python.exe -m client.editeur
goto menu