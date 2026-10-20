# -*- coding: utf-8 -*-
r"""
AUTO EDIT PRO V7.5 - bản chạy dòng lệnh (Windows)

Cách dùng:
  - Copy các clip vào CÙNG thư mục với file này rồi bấm đúp run.bat
  - Hoặc kéo-thả 1 thư mục chứa clip lên run.bat
  - Hoặc: python gemini_smart_cut.py "D:\thu-muc-clip"
Kết quả: output_capcut_final_v7.mp4 (+ v7_sub.srt) nằm trong thư mục clip.
"""
import os
import sys

import autoedit_core as core

# ============== CẤU HÌNH ==============
TARGET_FPS = 30
CRF = 18
ENABLE_AUTO_SUB = True
FADE_DURATION = 0.4
WHISPER_MODEL = "small"   # tiny / base / small / medium
# ======================================

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKIP_PREFIXES = ("output_", "temp_", "proc_")


def get_clips(folder):
    names = [
        f for f in os.listdir(folder)
        if f.lower().endswith(core.VIDEO_EXT) and not f.lower().startswith(SKIP_PREFIXES)
    ]
    names.sort(key=core.natural_key)
    return [os.path.join(folder, f) for f in names]


def pause():
    if sys.stdin and sys.stdin.isatty():
        input("\nNhấn Enter để thoát...")


def main():
    folder = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))

    print("=" * 64)
    print("  AUTO EDIT PRO V7.5 - 1080p + phụ đề tự động")
    print(f"  Thư mục: {folder}")
    print("=" * 64)

    if not os.path.isdir(folder):
        print(f"[LỖI] Không tìm thấy thư mục: {folder}")
        return pause()

    problems = core.check_tools()
    if problems:
        for p in problems:
            print(f"[LỖI] {p}")
        print("  → Cài FFmpeg bản full: https://www.gyan.dev/ffmpeg/builds/ và thêm vào PATH.")
        return pause()

    clips = get_clips(folder)
    if not clips:
        print("[LỖI] Không tìm thấy clip nào trong thư mục!")
        return pause()

    print(f"Tìm thấy {len(clips)} clip:")
    for i, c in enumerate(clips, 1):
        print(f"  {i}. {os.path.basename(c)}")
    print()

    final_output = os.path.join(folder, "output_capcut_final_v7.mp4")
    srt_out = os.path.join(folder, "v7_sub.srt")

    res = core.render(
        clips, final_output,
        fps=TARGET_FPS, crf=CRF, fade=FADE_DURATION,
        enable_sub=ENABLE_AUTO_SUB, whisper_model=WHISPER_MODEL,
        log=print, srt_path=srt_out,
    )

    if not res["ok"]:
        print(f"\n[LỖI] {res['error']}")
        return pause()

    fi = res["info"]
    print("\n🎉 XONG!")
    print(f"   📂 {final_output}")
    if res["srt_path"]:
        print(f"   📄 {res['srt_path']}")
    print("\n[Kiểm tra cuối]")
    print(f"  Độ dài      : {fi['duration']:.1f}s")
    print(f"  Độ phân giải: {fi['w']}x{fi['h']}")
    print(f"  Có audio    : {'CÓ' if fi['has_audio'] else 'KHÔNG'}")
    print(f"  Có sub      : {'CÓ' if res['sub_applied'] else 'KHÔNG'}")
    pause()


if __name__ == "__main__":
    main()
