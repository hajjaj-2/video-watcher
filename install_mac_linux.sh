#!/bin/sh
if command -v brew >/dev/null; then brew install ffmpeg tesseract tesseract-lang;
else sudo apt-get install -y ffmpeg tesseract-ocr tesseract-ocr-ara; fi
python3 -m pip install -r "$(dirname "$0")/requirements.txt"
echo 'Done. Run: python3 reel.py "LINK"'
