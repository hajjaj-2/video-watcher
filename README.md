# video-watcher

Lets Claude (or any AI agent) **watch and listen** to a video from a link or file:
keyframes + on-screen text + speech transcript + sound events (music, animals, objects) + song name & artist.

Works with Instagram, TikTok, YouTube, X, Reddit, Facebook, Pinterest, Google Drive (shared "Anyone with the link"), and local files.

## Easiest install
Paste this to Claude Code / your AI agent:

```
Install this tool for me: https://github.com/hajjaj-2/video-watcher/blob/main/INSTALL.md
```

## Manual install
- Windows: double-click `install_windows.bat`
- Mac/Linux: `sh install_mac_linux.sh`

## Use
```
python reel.py "https://www.instagram.com/reel/..." --out result
```
Outputs in `result/`: `sheet_XX.jpg`, `transcript.txt`, `sounds.txt`, `songs.txt`, `onscreen_text.txt`, `info.json`.

Private posts can't be downloaded. Song ID uses Shazam (free, unofficial).
Credits: Whisper (OpenAI, via faster-whisper), YAMNet (Google, Apache-2.0), yt-dlp, Tesseract.
