#!/usr/bin/env python3
"""reel.py — let Claude "watch" and "listen" to a short video.

Usage:
  python3 reel.py <video_file_or_url> [--out DIR] [--fps 1] [--lang ar|en|auto]

Produces in DIR:
  info.json         duration, resolution, audio presence
  frames/           one frame every 1/fps seconds (timestamped names)
  sheet_XX.jpg      contact sheets (grid of frames with timestamps) for quick viewing
  transcript.txt    speech-to-text with timestamps (Whisper small, offline)
"""
import argparse, json, os, subprocess, sys, glob, math, shutil, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.environ.get("WHISPER_MODEL", "/opt/whisper-small")
if not os.path.isdir(MODEL_DIR):
    MODEL_DIR = "small"  # downloaded automatically on first run


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def fetch(src, out):
    if os.path.exists(src):
        return src
    # URL: try yt-dlp (works only if the domain is allowed on this network)
    dst = os.path.join(out, "video.%(ext)s")
    try:
        run(["yt-dlp", "-q", "-f", "mp4/best", "-o", dst, src])
    except subprocess.CalledProcessError as e:
        sys.exit("DOWNLOAD_FAILED: " + (e.stderr or "")[-400:])
    return glob.glob(os.path.join(out, "video.*"))[0]


def probe(path):
    p = json.loads(run(["ffprobe", "-v", "quiet", "-print_format", "json",
                        "-show_format", "-show_streams", path]).stdout)
    v = next((s for s in p["streams"] if s["codec_type"] == "video"), {})
    has_audio = any(s["codec_type"] == "audio" for s in p["streams"])
    return {"duration": float(p["format"].get("duration", 0)),
            "width": v.get("width"), "height": v.get("height"),
            "has_audio": has_audio}


_TOK = None


def ocr(img):
    """Read caption-style text: try light-on-dark and dark-on-light, keep the cleaner result."""
    import re
    from PIL import Image
    global _TOK
    _TOK = _TOK or re.compile(r"[A-Za-z؀-ۿ'’.,?!\-]{2,}|[IAa]|\d+[%$]?")
    im = Image.open(img).convert("L")
    im = im.resize((im.width * 2, im.height * 2))
    best = ""
    for fn in (lambda p: 0 if p > 200 else 255, lambda p: 0 if p < 55 else 255):
        tmp = img + ".ocr.png"
        im.point(fn).save(tmp)
        try:
            t = run(["tesseract", tmp, "-", "-l", "eng+ara", "--psm", "6"]).stdout
        except Exception:
            t = ""
        os.remove(tmp)
        good = []
        for line in t.splitlines():
            toks = line.split()
            ok = [w for w in toks if _TOK.fullmatch(w)]
            if toks and len(ok) / len(toks) >= 0.6 and sum(map(len, ok)) >= 6:
                good.append(" ".join(ok))
        cand = " ".join(good)
        if len(cand) > len(best):
            best = cand
    return best


def frames(path, out, fps, info, diff_thr=15.0, max_gap=6.0):
    """Sample at `fps`, OCR every sample (on-screen text as cheap text),
    keep only visually distinct keyframes (new shot / big change, or every max_gap s)."""
    from PIL import Image, ImageDraw
    import numpy as np
    fdir = os.path.join(out, "frames")
    os.makedirs(fdir, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vf",
         f"fps={fps},scale=540:-2", "-q:v", "3", os.path.join(fdir, "f_%04d.jpg")])
    files = sorted(glob.glob(os.path.join(fdir, "f_*.jpg")))
    keep, texts, prev_sig, last_t, last_txt = [], [], None, -99, None
    for i, f in enumerate(files):
        t = i / fps
        sig = np.asarray(Image.open(f).convert("L").resize((64, 112)), dtype=np.float32)
        d = 999 if prev_sig is None else float(np.abs(sig - prev_sig).mean())
        if d > diff_thr or t - last_t >= max_gap:
            keep.append((t, f)); prev_sig = sig; last_t = t
        txt = ocr(f)
        if txt and difflib.SequenceMatcher(None, txt, last_txt or "").ratio() < 0.75:
            texts.append(f"[{t:5.1f}s] {txt}")
            last_txt = txt
    open(os.path.join(out, "onscreen_text.txt"), "w").write(
        "\n".join(texts) if texts else "(no on-screen text)")
    # compact contact sheets: 4x2 grid, 320px frames, timestamp label
    W, per, cols = 320, 8, 4
    for s in range(math.ceil(len(keep) / per)):
        chunk = keep[s*per:(s+1)*per]
        ims = [Image.open(f).convert("RGB") for _, f in chunk]
        ims = [im.resize((W, int(im.height * W / im.width))) for im in ims]
        H = max(im.height for im in ims)
        rows = math.ceil(len(ims) / cols)
        c = min(cols, len(ims))
        sheet = Image.new("RGB", (c*W + (c-1)*4, rows*H + (rows-1)*4), "white")
        for j, ((t, _), im) in enumerate(zip(chunk, ims)):
            x, y = (j % cols) * (W + 4), (j // cols) * (H + 4)
            sheet.paste(im, (x, y))
            dr = ImageDraw.Draw(sheet)
            dr.rectangle([x, y, x + 44, y + 18], fill="black")
            dr.text((x + 4, y + 3), f"{t:.0f}s", fill="yellow")
        sheet.save(os.path.join(out, f"sheet_{s:02d}.jpg"), quality=80)
    return {"sampled": len(files), "keyframes": len(keep), "sheets": math.ceil(len(keep) / per)}


YAMNET_DIR = os.environ.get("YAMNET_DIR", os.path.join(HERE, "yamnet"))
SKIP = {"Silence", "Inside, small room", "Inside, large room or hall", "Outside, urban or manmade",
        "Outside, rural or natural"}


YAMNET_TGZ = "https://registry.npmjs.org/@apocaliss92/scrypted-yamnet/-/scrypted-yamnet-0.0.3.tgz"
YAMNET_SHA = "10c95ea3eb9a7bb4cb8bddf6feb023250381008177ac162ce169694d05c317de"


def ensure_yamnet():
    """Fetch YAMNet (Google, Apache-2.0) once from the npm registry tarball and verify it."""
    model = os.path.join(YAMNET_DIR, "yamnet.tflite")
    if os.path.exists(model):
        return
    import hashlib, io, tarfile, urllib.request
    os.makedirs(YAMNET_DIR, exist_ok=True)
    data = urllib.request.urlopen(YAMNET_TGZ, timeout=120).read()
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        files = {m.name.rsplit("/", 1)[-1]: m for m in tf.getmembers() if "/src/model/" in m.name}
        tfl = tf.extractfile(files["yamnet.tflite"]).read()
        if hashlib.sha256(tfl).hexdigest() != YAMNET_SHA:
            raise RuntimeError("YAMNet checksum mismatch")
        csv_bytes = tf.extractfile(files["yamnet_class_map.csv"]).read()
    open(os.path.join(YAMNET_DIR, "yamnet_class_map.csv"), "wb").write(csv_bytes)
    open(model, "wb").write(tfl)


def sounds(path, out, win_s=1.0):
    """Non-speech audio: music, singing, instruments, animals, objects, ambience (YAMNet, 521 AudioSet classes)."""
    import csv, wave, numpy as np
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        try:
            from tflite_runtime.interpreter import Interpreter
        except ImportError:
            import tensorflow as tf
            Interpreter = tf.lite.Interpreter
    ensure_yamnet()
    wav = os.path.join(out, "audio.wav")
    if not os.path.exists(wav):
        run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", wav])
    names = [r["display_name"] for r in csv.DictReader(open(os.path.join(YAMNET_DIR, "yamnet_class_map.csv")))]
    it = Interpreter(os.path.join(YAMNET_DIR, "yamnet.tflite")); it.allocate_tensors()
    i_in, i_out = it.get_input_details()[0]["index"], it.get_output_details()[0]["index"]
    with wave.open(wav) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
    step = int(16000 * win_s)
    rows, overall = [], []
    for s in range(0, max(1, len(a)), step):
        seg = a[s:s + 15600]
        if len(seg) < 4000:
            break
        seg = np.pad(seg, (0, 15600 - len(seg)))
        it.set_tensor(i_in, seg); it.invoke()
        sc = it.get_tensor(i_out)[0]; overall.append(sc)
        top = [(names[k], float(sc[k])) for k in sc.argsort()[::-1][:4]
               if sc[k] >= 0.15 and names[k] not in SKIP]
        rows.append((s / 16000, ", ".join(f"{n} {v:.2f}" for n, v in top) or "-"))
    # merge consecutive windows with the same leading labels
    lines, prev = [], None
    for t, lab in rows:
        key = ",".join(x.rsplit(" ", 1)[0] for x in lab.split(", ")[:2])
        if key != prev:
            lines.append(f"[{t:5.1f}s] {lab}"); prev = key
    m = np.mean(overall, 0) if overall else None
    summary = "" if m is None else "overall: " + ", ".join(
        f"{names[k]} {m[k]:.2f}" for k in m.argsort()[::-1][:6] if names[k] not in SKIP)
    txt = summary + "\n" + "\n".join(lines)
    open(os.path.join(out, "sounds.txt"), "w").write(txt)
    return txt


def identify_song(path, out, duration):
    """Song title + artist via Shazam (shazamio: free, no API key). Needs amp.shazam.com reachable."""
    import asyncio
    from shazamio import Shazam
    wav = os.path.join(out, "audio.wav")
    if not os.path.exists(wav):
        run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", wav])
    starts = sorted({0.0, max(0.0, duration / 2 - 6)} | ({duration * 0.8 - 6} if duration > 30 else set()))

    async def go():
        sh, found, seen = Shazam(), [], set()
        rec = getattr(sh, "recognize", None) or sh.recognize_song
        for st in starts:
            clip = os.path.join(out, f"_clip{int(st)}.wav")
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{st:.1f}", "-t", "12", "-i", wav, clip])
            try:
                r = await rec(clip)
            finally:
                os.remove(clip)
            tr = (r or {}).get("track")
            if tr and tr.get("key") not in seen:
                seen.add(tr.get("key"))
                found.append(f"[{st:.0f}s] {tr.get('title')} - {tr.get('subtitle')}  {tr.get('url', '')}")
        return found

    found = asyncio.run(go())
    txt = "\n".join(found) if found else "(no song matched)"
    open(os.path.join(out, "songs.txt"), "w").write(txt)
    return txt


def transcribe(path, out, lang):
    from faster_whisper import WhisperModel
    wav = os.path.join(out, "audio.wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", wav])
    model = WhisperModel(MODEL_DIR, device="cpu", compute_type="int8")
    import wave, numpy as np
    with wave.open(wav) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
    segs, inf = model.transcribe(audio, language=None if lang == "auto" else lang,
                                 vad_filter=True, beam_size=5)
    lines = [f"[{s.start:6.1f}s → {s.end:6.1f}s] {s.text.strip()}" for s in segs]
    hdr = f"# language={inf.language} (p={inf.language_probability:.2f})\n"
    txt = hdr + ("\n".join(lines) if lines else "(no speech detected — music/sfx only)")
    open(os.path.join(out, "transcript.txt"), "w").write(txt)
    return txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", default="reel_out")
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--lang", default="auto")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    path = fetch(a.src, a.out)
    info = probe(path)
    # long videos: cap sampling at ~180 frames (keyframes are deduped after)
    fps = a.fps if info["duration"] * a.fps <= 180 else 180 / max(info["duration"], 1)
    info.update(frames(path, a.out, fps, info))
    info["fps_used"] = round(fps, 3)
    json.dump(info, open(os.path.join(a.out, "info.json"), "w"), indent=1)
    print(json.dumps(info))
    if info["has_audio"]:
        print(transcribe(path, a.out, a.lang))
        try:
            print(sounds(path, a.out))
        except Exception as e:
            print(f"(sound tagging unavailable: {e})")
        try:
            print("songs:", identify_song(path, a.out, info["duration"]))
        except Exception as e:
            msg = f"(song ID unavailable: {type(e).__name__}: {str(e)[:150]})"
            open(os.path.join(a.out, "songs.txt"), "w").write(msg)
            print(msg)
    else:
        print("(no audio track)")


if __name__ == "__main__":
    main()
