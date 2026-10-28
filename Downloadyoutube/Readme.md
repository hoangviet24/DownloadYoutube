# 🎬 YouTube Downloader Pro & AI Transcriber

Ứng dụng YouTube Arcana tải video/âm thanh bằng yt-dlp và có công cụ trích xuất giọng nói thành văn bản bằng OpenAI Whisper.

---

## ✨ Tính năng nổi bật

### 1. 📥 Tải Video & Âm thanh YouTube
- Chất lượng **Best** chọn luồng cao nhất không vượt quá 1080p. Các mức 720p, 1080p, 2K và 4K là giới hạn tối đa; nguồn thấp hơn được giữ nguyên, không bị upscale.
- Hỗ trợ tải MP3 từ 128 đến 320 kbps.
- Giao diện fantasy lấy cảm hứng từ mái vòm Gothic, kính màu, gradient xanh ngọc chuyển động nhẹ và chi tiết vàng; mở mặc định ở tab tải YouTube. Banner tải video và banner trích xuất văn bản dùng chung hiệu ứng chuyển sắc.
- Dán link để thêm một thẻ video vào danh sách; thẻ hiển thị thumbnail, tên, các độ phân giải có thật và nút MP3. Nhấn trực tiếp độ phân giải muốn tải, không cần chọn trong menu.
- Tùy chọn chuyển đổi và tải chỉ âm thanh định dạng **MP3 chất lượng cao** (128kbps - 320kbps).
- Kiểm tra trùng lặp thông minh: Phát hiện file đã tồn tại và xác nhận trước khi ghi đè.
- Tiện ích thao tác nhanh: Nút **📋 Dán link**, nút **📁 Mở thư mục tải**, hỗ trợ phím **Enter** để tải ngay.

### 2. 🤖 Trích xuất âm thanh thành văn bản (AI Speech-to-Text)
- Tích hợp mô hình AI **OpenAI Whisper**, hỗ trợ tiếng Việt và hơn 90 ngôn ngữ khác.
- Chỉ cho phép chạy Whisper khi PyTorch phát hiện GPU NVIDIA hỗ trợ CUDA; dùng FP16 để tăng tốc. Máy chỉ có đồ họa tích hợp Intel Iris sẽ không chạy nhận dạng.
- Hỗ trợ hầu hết các định dạng media: `.mp4`, `.mkv`, `.mp3`, `.wav`, `.m4a`, `.flac`, `.webm`, v.v.
- Bộ nhớ đệm thông minh (Model Caching): Giữ model đã nạp trên RAM/VRAM để xử lý các file tiếp theo ngay lập tức mà không phải tải lại.
- Tiện ích trích xuất: Sao chép nhanh vào Clipboard, xuất kết quả ra file `.txt`, làm sạch ô kết quả.

---

## 📊 Bảng so sánh các mô hình AI Whisper

| Tên Model | Tham số | Dung lượng (VRAM/RAM) | Tốc độ | Độ chính xác | Khuyến nghị sử dụng |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **tiny** | 39M | ~1 GB | Nhanh gấp ~32x | Cơ bản | Máy yếu, cần xem nhanh nội dung |
| **base** | 74M | ~1 GB | Chuẩn (1x) | Tạm ổn | Cấu hình máy phổ thông, laptop |
| **small** | 244M | ~2 GB | Chậm hơn 2-3x | Khá tốt | Độ chính xác cao, nhận diện tốt |
| **medium** | 769M | ~5 GB | Chậm hơn 6-7x | Rất tốt | Khuyên dùng khi có card GPU rời (NVIDIA) |
| **large** | 1550M | ~10 GB | Chậm | Tối ưu nhất | Dành cho máy trạm, GPU có VRAM ≥ 10GB |

---

## 🚀 Hướng dẫn cài đặt & Chạy ứng dụng

## 🧱 Cấu trúc mã nguồn

- `main.py`: khởi tạo ứng dụng và kiểm tra FFmpeg.
- `gui.py`: giao diện desktop, điều phối sự kiện người dùng.
- `downloader.py`: tích hợp yt-dlp/FFmpeg để đọc thông tin và tải media.
- `app/core/quality.py`: quy tắc chất lượng dùng chung cho giao diện và dịch vụ tải.
- `utils.py`: tìm tài nguyên và FFmpeg của môi trường chạy.

Quy tắc chất lượng được tách khỏi giao diện và dùng chung tại lõi để tránh giao diện và bộ tải hiểu khác nhau về cùng một mức chất lượng.

### 1. Yêu cầu hệ thống
- Hệ điều hành: Windows 10 / Windows 11 (64-bit).
- Python: Phiên bản 3.9 đến 3.12.
- Thư viện FFmpeg (đã có sẵn trong thư mục dự án hoặc tự động phát hiện).

### 2. Cài đặt các thư viện cần thiết
```bash
pip install -r requirements.txt
Whisper cần một bản PyTorch có hỗ trợ CUDA tương thích với GPU NVIDIA và driver đã cài. Hãy cài PyTorch theo hướng dẫn chính thức dành cho CUDA trên máy trước khi chạy tính năng nhận dạng.
```

### 3. Khởi chạy ứng dụng
```bash
python main.py
```

### 4. Đóng gói ứng dụng thành file .exe (PyInstaller)
Dự án đã có sẵn cấu hình tối ưu `main.spec`:
```bash
pyinstaller main.spec
```
Sau khi hoàn tất, file chạy sẽ nằm trong thư mục `dist/YouTubePro/YouTubePro.exe`.
