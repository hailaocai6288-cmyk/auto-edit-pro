# -*- coding: utf-8 -*-
"""
AUTO EDIT PRO V7.5 - lõi xử lý dùng chung cho:
app.py              (giao diện web Streamlit, chạy trên Chrome)
gemini_smart_cut.py (chạy dòng lệnh / run.bat trên Windows)
Quy trình: chuẩn hóa từng clip (1080p + chỉnh màu + fade) -> ghép -> Whisper tạo phụ đề -> burn phụ đề.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile

# =============================================================================
# WA LỖI soundfile.open() không nhận tham số 'metadata_err'
# (faster-whisper bản mới truyền tham số này, nhưng soundfile<=0.12.1 chưa có)
# =============================================================================
try:
    import soundfile as _sf

    _sf_open_orig = _sf.open

    def _sf_open_patched(path, *args, **kwargs):
        kwargs.pop("metadata_err", None)   # bỏ tham số không tương thích
        return _sf_open_orig(path, *args, **kwargs)

    _sf.open = _sf_open_patched
except Exception:
    pass
# =============================================================================

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")

# Phụ đề: màu vàng, viền đen. Muốn chữ nhỏ hơn thì giảm SUB_FONT_SIZE (mặc định V7.5 = 22).
SUB_FONT_SIZE = 22
SUB_STYLE = (
    f"FontName=Arial,FontSize={SUB_FONT_SIZE}, "
    "PrimaryColour=&H00FFFF&, "
    "OutlineColour=&H000000&, "
    "BackColour=&H80000000&, "
    "Outline=2,Shadow=1,BorderStyle=1, "
    "Alignment=2,MarginV=40 "
)

_MODEL_CACHE = {}


def natural_key(name):
    """Sắp xếp tự nhiên: clip2 đứng trước clip10."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def run(cmd, timeout=None, cwd=None):
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=timeout, cwd=cwd,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, returncode=127, stdout="",
                                           stderr=f"Không tìm thấy lệnh: {cmd[0]}")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="Timeout")


def check_tools():
    """Trả về danh sách lỗi (rỗng = ổn)."""
    problems = []
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            problems.append(f"Chưa cài '{tool}' hoặc chưa thêm vào PATH.")
    return problems


def has_subtitle_filter():
    r = run(["ffmpeg", "-hide_banner", "-filters"])
    return "subtitles" in (r.stdout or "")


def probe(path):
    r = run([
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type,width,height,duration:format=duration",
        "-of", "json", path,
    ])
    try:
        d = json.loads(r.stdout or "{}")
        streams = d.get("streams", [])
        v = next((s for s in streams if s.get("codec_type") == "video"), {})
        has_a = any(s.get("codec_type") == "audio" for s in streams)
        w = int(v.get("width") or 0)
        h = int(v.get("height") or 0)
        dur = float(d.get("format", {}).get("duration") or v.get("duration") or 0)
        return {"w": w, "h": h, "duration": dur, "has_audio": has_a}
    except Exception:
        return {"w": 720, "h": 1280, "duration": 0.0, "has_audio": True}


def build_vf(W, H, duration, fps, fade, do_scale=True):
    parts = [f"fps={fps}"]
    if do_scale and W > 0 and H > 0:
        parts.append(f"scale={W}:{H}:force_original_aspect_ratio=decrease")
        parts.append(f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black")
    parts.append("eq=contrast=1.06:saturation=1.08:brightness=0.01")
    parts.append("unsharp=3:3:0.4:3:3:0.0")
    if fade > 0 and duration > fade * 2.5:
        parts.append(f"fade=t=in:st=0:d={fade}")
        parts.append(f"fade=t=out:st={max(0, duration - fade):.3f}:d={fade}")
    parts.append("format=yuv420p")
    return ", ".join(parts)


def process_clip(src, info, idx, W, H, workdir, fps, crf, fade, log):
    out_clip = os.path.join(workdir, f"proc_{idx:03d}.mp4")
    duration = info["duration"] or 10.0
    attempts = [(True, W, H, f"{W}x{H}"), (False, 0, 0, "giữ độ phân giải gốc")]
    for do_scale, w, h, label in attempts:
        vf = build_vf(w, h, duration, fps, fade, do_scale)
        if info["has_audio"]:
            cmd = [
                "ffmpeg", "-y", "-i", src,
                "-vf", vf,
                "-af", "aresample=44100,aformat=channel_layouts=stereo",
                "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v:0", "-map", "0:a:0",
                "-shortest", out_clip,
            ]
        else:
            # Clip không có tiếng -> thêm âm thanh im lặng để ghép không bị lệch.
            cmd = [
                "ffmpeg", "-y", "-i", src,
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-vf", vf,
                "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v:0", "-map", "1:a:0",
                "-shortest", out_clip,
            ]
        res = run(cmd)
        if res.returncode == 0 and os.path.exists(out_clip) and os.path.getsize(out_clip) > 1000:
            log(f"  ✓ Clip {idx + 1} OK ({label})")
            return out_clip
        err = (res.stderr or "")[-300:].replace("\n", " | ")
        log(f"  ! Clip {idx + 1} lỗi ({label}): {err}")
    return None


def concat_clips(paths, out_path, workdir):
    list_file = os.path.join(workdir, "concat_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for p in paths:
            f.write("file '{}'\n".format(p.replace("\\", "/").replace("'", "'\\''")))
    return run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", out_path,
    ])


def fmt_srt_time(sec):
    total_ms = int(round(max(0.0, sec) * 1000))
    h, rem = divmod(total_ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe(video_path, model_name, log):
    """Nhận diện giọng nói -> [(start, end, text)].
    Ưu tiên faster-whisper (nhẹ), dự phòng openai-whisper."""

    # --- faster-whisper ---
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        WhisperModel = None

    if WhisperModel is not None:
        key = ("fw", model_name)
        if key not in _MODEL_CACHE:
            log(f"[Auto Sub] Đang tải model Whisper '{model_name}' (lần đầu hơi lâu)...")
            try:
                _MODEL_CACHE[key] = WhisperModel(model_name, device="cpu", compute_type="int8")
            except Exception as ex:
                log(f"[Auto Sub] faster-whisper lỗi khi tải model: {ex} -> chuyển sang openai-whisper.")
                WhisperModel = None

        if WhisperModel is not None:
            try:
                log("[Auto Sub] Đang nhận diện giọng nói (faster-whisper)...")
                segs, info = _MODEL_CACHE[key].transcribe(video_path, task="transcribe", vad_filter=True)
                out = [(s.start, s.end, s.text.strip()) for s in segs if s.text.strip()]
                log(f"[Auto Sub] Ngôn ngữ: {info.language.upper()} | Số đoạn: {len(out)}")
                return out
            except Exception as ex:
                log(f"[Auto Sub] faster-whisper lỗi khi transcribe: {ex} -> thử openai-whisper.")

    # --- openai-whisper (dự phòng) ---
    try:
        import whisper
    except ImportError:
        raise RuntimeError("Chưa cài thư viện phụ đề. Chạy: python -m pip install faster-whisper openai-whisper")

    key = ("ow", model_name)
    if key not in _MODEL_CACHE:
        log(f"[Auto Sub] Đang tải model Whisper '{model_name}' (openai-whisper)...")
        _MODEL_CACHE[key] = whisper.load_model(model_name)

    log("[Auto Sub] Đang nhận diện giọng nói (openai-whisper)...")
    res = _MODEL_CACHE[key].transcribe(video_path, task="transcribe", language=None, verbose=False, fp16=False)
    out = [(s["start"], s["end"], s["text"].strip()) for s in res.get("segments", []) if s["text"].strip()]
    log(f"[Auto Sub] Ngôn ngữ: {str(res.get('language', '?')).upper()} | Số đoạn: {len(out)}")
    return out


def write_srt(segments, srt_path):
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, (s, e, text) in enumerate(segments, start=1):
            f.write(f"{i}\n{fmt_srt_time(s)} --> {fmt_srt_time(e)}\n{text}\n\n")


def burn_subtitles(video_path, srt_path, output_path, crf, workdir, log):
    # Chạy ffmpeg trong workdir với tên file ngắn "sub.srt" -> không lo lỗi dấu cách,
    # dấu tiếng Việt, ký tự ':' hay '\' trong đường dẫn Windows.
    local_srt = os.path.join(workdir, "sub.srt")
    if os.path.abspath(srt_path) != os.path.abspath(local_srt):
        shutil.copy2(srt_path, local_srt)
    cmd = [
        "ffmpeg", "-y", "-i", os.path.abspath(video_path),
        "-vf", f"subtitles=sub.srt:force_style='{SUB_STYLE}'",
        "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
        "-c:a", "copy", "-movflags", "+faststart",
        os.path.abspath(output_path),
    ]
    res = run(cmd, cwd=workdir)
    if res.returncode == 0 and os.path.exists(output_path):
        return True
    log(f"[Burn Sub] Lỗi: {(res.stderr or '')[-400:]}")
    return False


def render(clip_paths, output_path, fps=30, crf=18, fade=0.4, enable_sub=True,
           whisper_model="small", log=print, srt_path=None, progress=None):
    """
    Ghép các clip -> output_path. Trả về dict:
    ok, sub_applied, srt_path, info (độ dài/độ phân giải), error
    """
    def step(frac):
        if progress:
            progress(min(max(frac, 0.0), 1.0))

    result = {"ok": False, "sub_applied": False, "srt_path": None, "info": None, "error": None}

    problems = check_tools()
    if problems:
        result["error"] = " ".join(problems)
        return result

    if not clip_paths:
        result["error"] = "Không có clip nào để xử lý."
        return result

    infos = [probe(p) for p in clip_paths]
    first = infos[0]
    vertical = (first["h"] or 1280) >= (first["w"] or 720)
    W, H = (1080, 1920) if vertical else (1920, 1080)
    log(f"Gốc: {first['w']}x{first['h']} → Mục tiêu: {W}x{H}")

    with tempfile.TemporaryDirectory() as workdir:
        log(f"[1/3] Xử lý {len(clip_paths)} clip...")
        processed = []
        for i, (p, info) in enumerate(zip(clip_paths, infos)):
            log(f"  → Clip {i + 1}/{len(clip_paths)}: {os.path.basename(p)}")
            out = process_clip(p, info, i, W, H, workdir, fps, crf, fade, log)
            if out:
                processed.append(out)
            else:
                log(f"  ! Bỏ qua clip {i + 1} (không xử lý được)")
            step(0.05 + 0.55 * (i + 1) / len(clip_paths))

        if not processed:
            result["error"] = "Không clip nào xử lý được. Kiểm tra lại định dạng video."
            return result

        log("[2/3] Ghép nối các clip...")
        merged = os.path.join(workdir, "merged.mp4")
        res = concat_clips(processed, merged, workdir)
        if res.returncode != 0 or not os.path.exists(merged):
            result["error"] = f"Lỗi ghép nối: {(res.stderr or '')[-300:]}"
            return result

        step(0.65)

        sub_ok = False
        if enable_sub:
            log("[3/3] Tạo & burn phụ đề...")
            if not has_subtitle_filter():
                log("  ! FFmpeg không có filter 'subtitles' (cần bản full có libass) → bỏ qua phụ đề.")
            else:
                try:
                    segs = transcribe(merged, whisper_model, log)
                    if not segs:
                        log("  ! Không tìm thấy đoạn thoại → xuất video không phụ đề.")
                    else:
                        srt_tmp = os.path.join(workdir, "sub_src.srt")
                        write_srt(segs, srt_tmp)
                        step(0.85)
                        if burn_subtitles(merged, srt_tmp, output_path, crf, workdir, log):
                            sub_ok = True
                            if srt_path:
                                shutil.copy2(srt_tmp, srt_path)
                                result["srt_path"] = srt_path
                except Exception as ex:  # noqa: BLE001
                    log(f"  ! Lỗi phụ đề: {type(ex).__name__}: {ex} → xuất video không phụ đề.")

        if not sub_ok:
            shutil.copy2(merged, output_path)

    if not os.path.exists(output_path):
        result["error"] = "Không tạo được file đầu ra."
        return result

    result["ok"] = True
    result["sub_applied"] = sub_ok
    result["info"] = probe(output_path)
    step(1.0)
    return result
