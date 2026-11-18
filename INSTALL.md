# Install video-watcher (instructions for an AI agent: Claude Code, Cursor, Codex...)

1. Clone: `git clone https://github.com/hajjaj-2/video-watcher.git && cd video-watcher`
2. System tools (Python 3.10+ required):
   - Windows: `winget install -e --id Gyan.FFmpeg` and `winget install -e --id UB-Mannheim.TesseractOCR`
     (then reopen the terminal so they are on PATH)
   - macOS: `brew install ffmpeg tesseract tesseract-lang`
   - Linux: `sudo apt-get install -y ffmpeg tesseract-ocr tesseract-ocr-ara`
3. Python packages: `python -m pip install -r requirements.txt`
4. First run downloads the models automatically: Whisper small (~460 MB) and YAMNet (~4 MB).

## How to watch a video with it
Run `python reel.py "<URL or file>" --out result`, then read:
`result/transcript.txt` (speech), `result/sounds.txt` (music/animals/objects), `result/songs.txt` (song + artist),
`result/onscreen_text.txt` (captions), then every `result/sheet_XX.jpg` (keyframes with timestamps).
Analyze the video from these. Do not read result/frames/ unless a detail is unclear.
Options: `--fps 4` for fast cuts, `--lang ar|en` to force the speech language.

## After installing (agent: do this)
1. Tell the user in their language, briefly, what the tool does: downloads a video from a link, extracts the
   distinct scenes as images, reads on-screen text, transcribes speech, detects sounds (music, animals, objects),
   and identifies the song name and artist, so you can watch and listen to the video and analyze it.
2. Ask the user to send an Instagram reel (or TikTok / YouTube) link as a test, then run the tool on it and give
   a scene-by-scene analysis with the audio.
