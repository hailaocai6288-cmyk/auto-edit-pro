# -*- coding: utf-8 -*-
r"""
AUTO EDIT PRO V7.5
- Xuất 1080x1920 (dọc)
- Auto Sub bằng Whisper (model small)
- FontSize=22, màu vàng, viền đen
- Hiệu ứng: scale + pad + eq + unsharp + fade
- Chạy bằng run.bat (double-click)
"""
import os
import subprocess
import sys
import tempfile
import json
import shutil

# ============== CẤU HÌNH ==============
TARGET_DIR = r"E:\EDIT VIDEO AS Skill - Ban Nang Cap"   # Đổi đường dẫn nếu cần
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")
TARGET_FPS = 30
CRF = 18
ENABLE_AUTO_SUB = True
FADE_DURATION = 0.4
WHISPER_MODEL = "small"   # tiny / base / small / medium
# ======================================

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def run(cmd, timeout=None):
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="Timeout")


def probe(path):
    r = run([
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type,width,height,duration:format=duration",
        "-of", "json", path
    ])
    try:
        d = json.loads(r.stdout or "{}")
        streams = d.get("streams", [])
        v = next((s for s in streams if s.get("codec_type") == "video"), {})
        has_a = any(s.get("codec_type") == "audio" for s in streams)
        w = int(v.get("width") or 0)
        h = int(v.get("height") or 0)
        dur = float(v.get("duration") or d.get("format", {}).get("duration") or 0)
        return {"w": w, "h": h, "duration": dur, "has_audio": has_a}
    except Exception:
        return {"w": 720, "h": 1280, "duration": 0.0, "has_audio": True}


def get_all_clips():
    if not os.path.isdir(TARGET_DIR):
        print(f"[LỖI] Không tìm thấy thư mục: {TARGET_DIR}")
        return []
    files = [
        os.path.join(TARGET_DIR, f)
        for f in sorted(os.listdir(TARGET_DIR))
        if f.lower().endswith(VIDEO_EXT)
        and "output_" not in f.lower()
        and "_v7" not in f.lower()
        and "temp_" not in f.lower()
        and "sub_" not in f.lower()
        and "v7_sub" not in f.lower()
    ]
    return files


def check_ffmpeg_subtitles_support():
    r = run(["ffmpeg", "-filters"])
    if "subtitles" in (r.stdout or ""):
        print("[OK] FFmpeg hỗ trợ filter 'subtitles'")
        return True
    print("[CẢNH BÁO] FFmpeg KHÔNG có filter 'subtitles' (cần bản full có libass).")
    return False


def generate_subtitles(video_path, srt_path):
    try:
        import whisper
        print(f"\n[Auto Sub] Đang tải model Whisper '{WHISPER_MODEL}'...")
        model = whisper.load_model(WHISPER_MODEL)
        print("[Auto Sub] Đang nhận diện ngôn ngữ & phiên âm (1–3 phút)...")

        result = model.transcribe(
            video_path, task="transcribe", language=None, verbose=False
        )

        detected_lang = result.get("language", "unknown")
        segments = result.get("segments", [])
        print(f"[Auto Sub] Ngôn ngữ: {detected_lang.upper()} | Số đoạn: {len(segments)}")

        if not segments:
            print("[Auto Sub] Không tìm thấy đoạn thoại.")
            return False

        with open(srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, start=1):
                start_sec = segment["start"]
                end_sec = segment["end"]
                text = segment["text"].strip()
                if not text:
                    continue
                print(f"  ({start_sec:.1f}s → {end_sec:.1f}s): {text}")

                def fmt_time(sec):
                    h = int(sec // 3600)
                    m = int((sec % 3600) // 60)
                    s = int(sec % 60)
                    ms = int(round((sec - int(sec)) * 1000))
                    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

                f.write(f"{i}\n{fmt_time(start_sec)} --> {fmt_time(end_sec)}\n{text}\n\n")

        print(f"[Auto Sub] Đã ghi: {srt_path}")
        return True
    except ImportError:
        print("[LỖI] Chưa cài openai-whisper.")
        print("  → Chạy: python -m pip install openai-whisper")
        return False
    except Exception as e:
        print(f"[LỖI Auto Sub] {type(e).__name__}: {e}")
        return False


def build_vf(W, H, duration, do_scale=True):
    parts = [f"fps={TARGET_FPS}"]
    if do_scale and W > 0 and H > 0:
        parts.append(f"scale={W}:{H}:force_original_aspect_ratio=decrease")
        parts.append(f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black")
    parts.append("eq=contrast=1.06:saturation=1.08:brightness=0.01")
    parts.append("unsharp=3:3:0.4:3:3:0.0")
    if duration > FADE_DURATION * 2.5:
        parts.append(f"fade=t=in:st=0:d={FADE_DURATION}")
        parts.append(f"fade=t=out:st={max(0, duration - FADE_DURATION)}:d={FADE_DURATION}")
    parts.append("format=yuv420p")
    return ",".join(parts)


def process_clip(c, info, i, target_W, target_H, temp_dir):
    out_clip = os.path.join(temp_dir, f"proc_{i:02d}.mp4")
    duration = info["duration"] or 10.0

    attempts = [
        (True, target_W, target_H, f"{target_W}x{target_H}"),
        (False, 0, 0, "gốc"),
    ]

    for do_scale, W, H, label in attempts:
        vf = build_vf(W, H, duration, do_scale=do_scale)

        if info["has_audio"]:
            cmd = [
                "ffmpeg", "-y", "-i", c,
                "-vf", vf,
                "-af", "aresample=44100,aformat=channel_layouts=stereo",
                "-c:v", "libx264", "-crf", str(CRF), "-preset", "medium",
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v:0", "-map", "0:a:0",
                "-shortest", out_clip
            ]
        else:
            print(f"  [!] Clip {i+1} không có tiếng → thêm silent")
            cmd = [
                "ffmpeg", "-y", "-i", c,
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-vf", vf,
                "-c:v", "libx264", "-crf", str(CRF), "-preset", "medium",
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v:0", "-map", "1:a:0",
                "-shortest", out_clip
            ]

        res = run(cmd)
        if res.returncode == 0 and os.path.exists(out_clip) and os.path.getsize(out_clip) > 1000:
            print(f"  → Clip {i+1} OK ({label})")
            return out_clip
        else:
            err = (res.stderr or "")[-400:].replace("\n", " | ")
            print(f"  [!] Clip {i+1} lỗi ({label}): {err[:200]}")

    print(f"  [CẢNH BÁO] Clip {i+1} dùng bản gốc")
    return c


def burn_subtitles(video_path, srt_path, output_path):
    # FontSize=22 (nhỏ gọn)
    sub_style = (
        "FontName=Arial,FontSize=22,"
        "PrimaryColour=&H00FFFF&,"
        "OutlineColour=&H000000&,"
        "BackColour=&H80000000&,"
        "Outline=2,Shadow=1,BorderStyle=1,"
        "Alignment=2,MarginV=40"
    )

    simple_srt = os.path.join(os.path.dirname(video_path) or ".", "sub_temp.srt")
    try:
        shutil.copy2(srt_path, simple_srt)
    except Exception:
        simple_srt = srt_path

    escaped = simple_srt.replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"subtitles='{escaped}':force_style='{sub_style}'",
        "-c:v", "libx264", "-crf", str(CRF), "-preset", "medium",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    print("[Burn Sub] Cách 1...")
    res = run(cmd)
    if res.returncode == 0 and os.path.exists(output_path):
        if simple_srt != srt_path and os.path.exists(simple_srt):
            try: os.remove(simple_srt)
            except: pass
        return True
    print(f"[Burn Sub] Lỗi cách 1: {(res.stderr or '')[-500:]}")

    escaped2 = simple_srt.replace("\\", "/")
    cmd[cmd.index("-vf") + 1] = f"subtitles={escaped2}:force_style='{sub_style}'"
    print("[Burn Sub] Cách 2...")
    res2 = run(cmd)
    if res2.returncode == 0 and os.path.exists(output_path):
        if simple_srt != srt_path and os.path.exists(simple_srt):
            try: os.remove(simple_srt)
            except: pass
        return True
    print(f"[Burn Sub] Lỗi cách 2: {(res2.stderr or '')[-400:]}")
    return False


def main():
    print("=" * 64)
    print("  AUTO EDIT PRO V7.5 - 1080p + font nhỏ")
    print(f"  Thư mục: {TARGET_DIR}")
    print("=" * 64)

    try:
        import whisper
        print("[OK] openai-whisper đã cài")
    except ImportError:
        print("[CẢNH BÁO] Chưa cài openai-whisper")
        print("  → python -m pip install openai-whisper")

    has_sub_filter = check_ffmpeg_subtitles_support()

    clips = get_all_clips()
    if not clips:
        print("\n[LỖI] Không tìm thấy clip nào!")
        input("Nhấn Enter để thoát...")
        return

    print(f"\nTìm thấy {len(clips)} clip:")
    for idx, c in enumerate(clips, 1):
        print(f"  {idx}. {os.path.basename(c)}")

    temp_output = os.path.join(TARGET_DIR, "temp_merged_v7.mp4")
    final_output = os.path.join(TARGET_DIR, "output_capcut_final_v7.mp4")
    srt_local = os.path.join(TARGET_DIR, "v7_sub.srt")

    infos = [probe(c) for c in clips]
    orig_w = infos[0]["w"] or 720
    orig_h = infos[0]["h"] or 1280
    is_vertical = orig_h >= orig_w

    if is_vertical:
        target_W, target_H = 1080, 1920
    else:
        target_W, target_H = 1920, 1080

    print(f"\nGốc: {orig_w}x{orig_h} | Mục tiêu: {target_W}x{target_H}")

    processed_clips = []
    with tempfile.TemporaryDirectory() as temp_dir:
        print("\n[1/3] Đang xử lý từng clip...")
        for i, c in enumerate(clips):
            print(f"  → Clip {i+1}/{len(clips)}: {os.path.basename(c)}")
            out = process_clip(c, infos[i], i, target_W, target_H, temp_dir)
            processed_clips.append(out)

        print("\n[2/3] Đang ghép nối...")
        list_file = os.path.join(temp_dir, "concat_list.txt")
        with open(list_file, "w", encoding="utf-8") as lf:
            for p in processed_clips:
                lf.write(f"file '{p.replace(chr(92), '/')}'\n")

        res_concat = run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", temp_output
        ])
        if res_concat.returncode != 0:
            print(f"[LỖI] Ghép nối: {res_concat.stderr[-600:]}")
            input("Nhấn Enter...")
            return

        info_temp = probe(temp_output)
        if not info_temp["has_audio"]:
            print("[!] Thêm silent audio...")
            fixed = os.path.join(temp_dir, "fixed_audio.mp4")
            if run([
                "ffmpeg", "-y", "-i", temp_output,
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v:0", "-map", "1:a:0", "-shortest", fixed
            ]).returncode == 0:
                os.replace(fixed, temp_output)

    sub_applied = False
    if ENABLE_AUTO_SUB and has_sub_filter:
        print("\n[3/3] Đang tạo & burn phụ đề (FontSize=22)...")
        if generate_subtitles(temp_output, srt_local):
            if burn_subtitles(temp_output, srt_local, final_output):
                sub_applied = True
                print(f"\n🎉 XONG! Có HÌNH + TIẾNG + SUB")
                print(f"   📂 {final_output}")
                print(f"   📄 {srt_local}")
            else:
                print("→ Burn fail. Xuất video không sub.")
        else:
            print("[Auto Sub] Không tạo được .srt")
    else:
        print("\n[!] Bỏ qua bước phụ đề")

    if not sub_applied:
        if os.path.exists(temp_output):
            os.replace(temp_output, final_output)
        print(f"\n🎉 XONG (không sub): {final_output}")
        if os.path.exists(srt_local):
            print(f"   File .srt: {srt_local}")

    if os.path.exists(temp_output):
        try: os.remove(temp_output)
        except: pass

    if os.path.exists(final_output):
        fi = probe(final_output)
        print(f"\n[Kiểm tra cuối]")
        print(f"  Độ dài      : {fi['duration']:.1f}s")
        print(f"  Độ phân giải: {fi['w']}x{fi['h']}")
        print(f"  Có audio    : {'CÓ' if fi['has_audio'] else 'KHÔNG'}")
        print(f"  Có sub      : {'CÓ' if sub_applied else 'KHÔNG'}")

    input("\nNhấn Enter để thoát...")


if __name__ == "__main__":
    main()
