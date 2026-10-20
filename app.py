# -*- coding: utf-8 -*-
"""AUTO EDIT PRO V7.5 - giao diện web (Streamlit). Chạy trên Chrome / mọi trình duyệt."""
import os
import tempfile

import streamlit as st

import autoedit_core as core

st.set_page_config(page_title="Auto Edit Pro V7.5", page_icon="🎬", layout="centered")

st.title("🎬 AUTO EDIT PRO V7.5")
st.caption("Tự động ghép clip ngắn → video 1080p + phụ đề tự động (Whisper)")

problems = core.check_tools()
if problems:
    st.error("Thiếu FFmpeg: " + " ".join(problems))
    st.info("Trên Streamlit Cloud: file `packages.txt` phải chứa dòng `ffmpeg`. "
            "Trên máy: cài FFmpeg bản full và thêm vào PATH.")
    st.stop()

# ---------- Sidebar ----------
st.sidebar.header("⚙️ Cấu hình Video")
target_fps = st.sidebar.number_input("FPS", value=30, min_value=15, max_value=60)
crf = st.sidebar.slider("Chất lượng CRF (càng nhỏ càng nét)", 15, 28, 18)
fade = st.sidebar.slider("Fade vào/ra mỗi clip (giây)", 0.0, 1.0, 0.4, 0.1)
sort_names = st.sidebar.checkbox("Sắp xếp clip theo tên file", value=True,
                                 help="Bỏ chọn để giữ đúng thứ tự tải lên.")
enable_sub = st.sidebar.checkbox("Tự động tạo phụ đề", value=True)
whisper_model = st.sidebar.selectbox(
    "Model Whisper", ["tiny", "base", "small", "medium"], index=1,
    help="Trên Streamlit Cloud (RAM thấp) nên dùng tiny/base. Chạy máy cá nhân có thể dùng small/medium.",
)

uploaded = st.file_uploader(
    "Tải các clip ngắn lên đây (.mp4, .mov, .mkv, .avi, .webm, .m4v)",
    type=[e.lstrip(".") for e in core.VIDEO_EXT],
    accept_multiple_files=True,
)

if uploaded:
    files = sorted(uploaded, key=lambda f: core.natural_key(f.name)) if sort_names else list(uploaded)
    st.write("**Thứ tự ghép:** " + " → ".join(f.name for f in files))

    if st.button("🚀 Bắt đầu Biên Tập & Ghép Video", type="primary"):
        st.session_state.pop("result", None)
        log_box = st.empty()
        bar = st.progress(0.0)
        lines = []

        def log(msg):
            lines.append(str(msg))
            log_box.code("\n".join(lines[-12:]), language=None)

        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i, f in enumerate(files):
                safe = f"in_{i:03d}{os.path.splitext(f.name)[1].lower()}"
                p = os.path.join(tmp, safe)
                with open(p, "wb") as out:
                    out.write(f.getbuffer())
                paths.append(p)

            out_path = os.path.join(tmp, "final.mp4")
            srt_path = os.path.join(tmp, "final.srt")
            res = core.render(
                paths, out_path, fps=int(target_fps), crf=int(crf), fade=float(fade),
                enable_sub=enable_sub, whisper_model=whisper_model,
                log=log, srt_path=srt_path, progress=bar.progress,
            )
            if res["ok"]:
                with open(out_path, "rb") as fh:
                    video_bytes = fh.read()
                srt_bytes = None
                if res["srt_path"] and os.path.exists(res["srt_path"]):
                    with open(res["srt_path"], "rb") as fh:
                        srt_bytes = fh.read()
                st.session_state["result"] = {
                    "video": video_bytes, "srt": srt_bytes,
                    "sub": res["sub_applied"], "info": res["info"],
                }
            else:
                st.error(f"❌ {res['error']}")

# Kết quả lưu trong session_state -> bấm nút tải về không làm mất video
result = st.session_state.get("result")
if result:
    st.success("🎉 Xuất video thành công!" + ("" if result["sub"] else " (không có phụ đề)"))
    info = result["info"]
    st.caption(f"{info['w']}x{info['h']} • {info['duration']:.1f}s • "
               f"{'có' if info['has_audio'] else 'không có'} âm thanh")
    st.video(result["video"])
    st.download_button("📥 Tải video hoàn chỉnh", data=result["video"],
                       file_name="auto_edit_pro_output.mp4", mime="video/mp4")
    if result["srt"]:
        st.download_button("📄 Tải file phụ đề (.srt)", data=result["srt"],
                           file_name="auto_edit_pro_output.srt", mime="text/plain")
