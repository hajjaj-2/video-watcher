@echo off
winget install -e --id Python.Python.3.12
winget install -e --id Gyan.FFmpeg
winget install -e --id UB-Mannheim.TesseractOCR
python -m pip install -r "%~dp0requirements.txt"
echo Done. Close and reopen the terminal, then: python reel.py "LINK"
pause
