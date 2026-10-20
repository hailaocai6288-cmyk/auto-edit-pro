# AUTO EDIT PRO V7.5

Script tự động ghép nhiều clip ngắn → video dọc 1080x1920 có hiệu ứng + phụ đề (Whisper).

## Yêu cầu

- Windows
- Python 3.10+
- FFmpeg (bản full có libass)
- `pip install openai-whisper`

## Cài đặt nhanh

```bash
python -m pip install openai-whisper
```

Đảm bảo `ffmpeg` và `ffprobe` nằm trong PATH.

## Cách dùng

1. Mở file `gemini_smart_cut.py`, sửa dòng:
   ```python
   TARGET_DIR = r"E:\EDIT VIDEO AS Skill - Ban Nang Cap"
   ```
   thành đường dẫn thư mục chứa các clip của bạn.

2. Copy toàn bộ file trong repo vào thư mục đó (hoặc chỉ copy 2 file chính).

3. Double-click **`run.bat`**

Hoặc chạy bằng CMD:
```cmd
python gemini_smart_cut.py
```

## Kết quả

- File đầu ra: `output_capcut_final_v7.mp4`
- File phụ đề: `v7_sub.srt` (giữ lại để chỉnh tay nếu cần)

## Tùy chỉnh

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `TARGET_DIR` | ... | Thư mục chứa clip |
| `WHISPER_MODEL` | `small` | tiny / base / small / medium |
| `CRF` | 18 | Chất lượng (thấp = đẹp hơn, file nặng hơn) |
| `ENABLE_AUTO_SUB` | True | Bật/tắt phụ đề |
| FontSize | 22 | Sửa trong hàm `burn_subtitles` |

## Lưu ý

- Clip đầu vào nên cùng tỷ lệ (dọc hoặc ngang).
- Lần đầu chạy Whisper sẽ tải model (có thể mất vài phút).
- Nếu burn sub lỗi, script vẫn xuất video + file `.srt` để bạn nhúng bằng CapCut.
