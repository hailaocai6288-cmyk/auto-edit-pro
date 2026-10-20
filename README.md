# 🎬 AUTO EDIT PRO V7.5

Tự động ghép nhiều clip ngắn → **video 1080x1920 (hoặc 1920x1080)** có chỉnh màu, fade và **phụ đề tự động (Whisper)**.

Có 2 cách dùng:

| Cách | Dùng khi | Chạy bằng |
|------|----------|-----------|
| 🌐 **Web (Chrome)** | Muốn bấm nút, tải clip lên trình duyệt | `run_web.bat` hoặc Streamlit Cloud |
| 💻 **Dòng lệnh** | Có sẵn thư mục clip trên máy | `run.bat` |

## Cấu trúc

```
app.py                 # Giao diện web (Streamlit)
gemini_smart_cut.py    # Bản chạy dòng lệnh
autoedit_core.py       # Lõi xử lý dùng chung
requirements.txt       # Thư viện Python
packages.txt           # Gói hệ thống cho Streamlit Cloud (ffmpeg)
run.bat / run_web.bat  # Chạy nhanh trên Windows
.streamlit/config.toml # Cấu hình (giới hạn upload 500MB)
```

## Chạy trên máy Windows

Yêu cầu: **Python 3.10+** và **FFmpeg bản full** (có libass) nằm trong PATH.

- **Web:** bấm đúp `run_web.bat` → tự mở Chrome tại `http://localhost:8501`.
- **Dòng lệnh:** copy clip vào cùng thư mục (hoặc kéo-thả thư mục clip lên `run.bat`) → bấm đúp `run.bat`.
  Kết quả: `output_capcut_final_v7.mp4` + `v7_sub.srt`.

Hoặc thủ công:
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Triển khai Streamlit Cloud

1. Đẩy toàn bộ repo này lên GitHub.
2. Vào https://share.streamlit.io → **New app** → chọn repo, branch `main`, file `app.py`.
3. `packages.txt` sẽ tự cài FFmpeg, `requirements.txt` cài thư viện.

> Streamlit Cloud có RAM thấp: dùng model Whisper `tiny`/`base` và clip ngắn. Muốn dùng `small`/`medium` thì chạy trên máy cá nhân.

## Tùy chỉnh

| Thiết lập | Mặc định | Nơi sửa |
|-----------|----------|---------|
| FPS, CRF, Fade, Model Whisper, bật/tắt phụ đề | 30 / 18 / 0.4s / base (web), small (CLI) / bật | Thanh bên (web) hoặc đầu file `gemini_smart_cut.py` |
| Cỡ chữ phụ đề | 22 | `SUB_FONT_SIZE` trong `autoedit_core.py` (giảm số để chữ nhỏ hơn) |

## Lưu ý

- Clip đầu tiên quyết định khung dọc/ngang cho cả video; clip khác tỷ lệ sẽ được thêm viền đen.
- Clip không có tiếng sẽ được chèn âm thanh im lặng; clip nào lỗi sẽ bị bỏ qua (có báo trong log).
- Lần đầu chạy Whisper sẽ tải model (vài phút). Nếu burn phụ đề lỗi, video vẫn được xuất không phụ đề.
