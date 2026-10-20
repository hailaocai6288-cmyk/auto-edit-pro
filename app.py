# -*- coding: utf-8 -*-
import os
import subprocess
import sys
import tempfile
import json
import shutil
import streamlit as st

st.set_page_config(page_title="Auto Edit Pro V7.5", page_icon="🎬", layout="centered")

st.title("🎬 AUTO EDIT PRO V7.5")
st.caption("Tự động ghép clip ngắn → Video 1080p + Phụ đề tự động (Whisper)")

# Sidebar cấu hình
st.sidebar.header("⚙️ Cấu hình Video")
target_fps = st.sidebar.number_input("FPS", value=30, min_value=15, max_value=60)
crf = st.sidebar.slider("Chất lượng CRF (Càng nhỏ càng nét)", 15, 28, 18)
enable_sub = st.sidebar.checkbox("Tự động tạo phụ đề", value=True)
whisper_model = st.sidebar.selectbox("Model Whisper", ["tiny", "base", "small", "medium"], index=2)

uploaded_files = st.file_uploader(
    "Tải các clip ngắn lên đây (.mp4, .mov, .mkv)", 
    type=["mp4", "mov", "mkv", "avi", "webm"], 
    accept_multiple_files=True
)

def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")

def probe_video(path):
    r = run_cmd([
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

def generate_srt(video_path, srt_path, model_name):
    try:
        import whisper
        model = whisper.load_model(model_name)
        result = model.transcribe(video_path, task="transcribe", language=None, verbose=False)
        segments = result.get("segments", [])
        if not segments:
            return False
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, start=1):
                s, e, text = seg["start"], seg["end"], seg["text"].strip()
                if not text: continue
                fmt = lambda sec: f"{int(sec//3600):02d}:{int((sec%3600)//60):02d}:{int(sec%60):02d},{int(round((sec-int(sec))*1000)):03d}"
                f.write(f"{i}\n{fmt(s)} --> {fmt(e)}\n{text}\n\n")
        return True
    except Exception as ex:
        st.error(f"Lỗi Whisper: {ex}")
        return False

def burn_sub(video_path, srt_path, output_path):
    sub_style = "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,Outline=2,Alignment=2,MarginV=40"
    escaped = srt_path.replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"subtitles='{escaped}':force_style='{sub_style}'",
        "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
        "-c:a", "copy", output_path
    ]
    res = run_cmd(cmd)
    return res.returncode == 0 and os.path.exists(output_path)

if uploaded_files and st.button("🚀 Bắt đầu Biên Tập & Ghép Video", type="primary"):
    with st.spinner("Đang xử lý video... Vui lòng đợi trong giây lát."):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_paths = []
            for idx, uploaded_file in enumerate(uploaded_files):
                path = os.path.join(temp_dir, f"in_{idx}_{uploaded_file.name}")
                with open(path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                input_paths.append(path)

            st.info(f"Đã tải lên {len(input_paths)} video. Bắt đầu xử lý...")
            
            # Kiểm tra kích thước video đầu tiên
            info0 = probe_video(input_paths[0])
            is_vert = (info0["h"] or 1280) >= (info0["w"] or 720)
            target_W, target_H = (1080, 1920) if is_vert else (1920, 1080)

            # Process clips
            proc_paths = []
            for i, p in enumerate(input_paths):
                info = probe_video(p)
                dur = info["duration"] or 10.0
                out_clip = os.path.join(temp_dir, f"proc_{i:02d}.mp4")
                vf = f"fps={target_fps},scale={target_W}:{target_H}:force_original_aspect_ratio=decrease,pad={target_W}:{target_H}:(ow-iw)/2:(oh-ih)/2:black,eq=contrast=1.06:saturation=1.08:brightness=0.01,unsharp=3:3:0.4:3:3:0.0,format=yuv420p"
                
                cmd = ["ffmpeg", "-y", "-i", p, "-vf", vf, "-c:v", "libx264", "-crf", str(crf), "-preset", "medium"]
                if info["has_audio"]:
                    cmd += ["-af", "aresample=44100,aformat=channel_layouts=stereo", "-c:a", "aac", "-b:a", "192k", "-map", "0:v:0", "-map", "0:a:0"]
                else:
                    cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-c:a", "aac", "-b:a", "192k", "-map", "0:v:0", "-map", "1:a:0"]
                cmd += ["-shortest", out_clip]
                
                run_cmd(cmd)
                if os.path.exists(out_clip):
                    proc_paths.append(out_clip)

            # Concat
            concat_list = os.path.join(temp_dir, "list.txt")
            with open(concat_list, "w", encoding="utf-8") as f:
                for p in proc_paths:
                    f.write(f"file '{p.replace(chr(92), '/')}'\n")

            temp_merged = os.path.join(temp_dir, "merged.mp4")
            run_cmd(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", temp_merged])

            final_out = os.path.join(temp_dir, "final.mp4")
            srt_out = os.path.join(temp_dir, "sub.srt")

            # Auto sub
            sub_ok = False
            if enable_sub:
                st.text("Đang nhận diện giọng nói và tạo phụ đề...")
                if generate_srt(temp_merged, srt_out, whisper_model):
                    if burn_sub(temp_merged, srt_out, final_out):
                        sub_ok = True

            if not sub_ok and os.path.exists(temp_merged):
                shutil.copy(temp_merged, final_out)

            if os.path.exists(final_out):
                st.success("🎉 Xuất video thành công!")
                st.video(final_out)
                with open(final_out, "rb") as file:
                    st.download_button(
                        label="📥 Tải Video Hoàn Chỉnh Về Máy",
                        data=file,
                        file_name="auto_edit_pro_output.mp4",
                        mime="video/mp4"
                    )
