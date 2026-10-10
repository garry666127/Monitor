@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_EXIT=1"
set "ERROR_LOG=%~dp0last_error.log"
if "%~1"=="" goto usage
if not exist "%~1" goto missing_video
if not exist "%~dp0.venv\Scripts\python.exe" goto missing_python
if not exist "%~dp0detect_person_yolo.py" goto missing_script
echo Starting MOG2 + YOLO11s hybrid detection. Loading the model may take a moment.
echo Keep this window open until analysis finishes.
"%~dp0.venv\Scripts\python.exe" -u "%~dp0detect_person_yolo.py" "%~1" --debug 2>"%ERROR_LOG%"
set "RUN_EXIT=%ERRORLEVEL%"
if not "%RUN_EXIT%"=="0" goto analysis_failed
echo.
echo Analysis completed. Results are in the results folder.
goto finish
:usage
echo Drag a video file onto run_yolo.bat to analyze the full video.
goto finish
:missing_video
echo Video file not found.
echo Video file not found.>"%ERROR_LOG%"
goto finish
:missing_python
echo Python environment not found. Run setup.ps1 in this project folder first.
echo Python environment not found.>"%ERROR_LOG%"
goto finish
:missing_script
echo detect_person_yolo.py not found beside this launcher.
echo detect_person_yolo.py not found.>"%ERROR_LOG%"
goto finish
:analysis_failed
echo.
echo Analysis failed. Error details:
type "%ERROR_LOG%"
echo.
echo Error log: "%ERROR_LOG%"
:finish
echo.
pause
exit /b %RUN_EXIT%
