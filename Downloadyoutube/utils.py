import os
import subprocess
import shutil
import sys
import urllib.request
import zipfile

def resource_path(relative_path):
    """
    Lấy đường dẫn tuyệt đối đến tài nguyên.
    Hoạt động chính xác cho cả lúc phát triển (dev) và sau khi đóng gói bằng PyInstaller.
    """
    try:
        # PyInstaller tạo thư mục tạm và lưu đường dẫn trong _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Khi chạy source code, lấy thư mục chứa file utils.py làm gốc
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

def get_ffmpeg_path():
    """
    Tìm đường dẫn ffmpeg và tự động đưa thư mục chứa ffmpeg vào PATH môi trường
    để các thư viện (như yt-dlp, whisper) sử dụng trực tiếp mà không bị lỗi.
    """
    # 1. Kiểm tra trong PATH hệ thống trước
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        return ffmpeg_in_path

    # 2. Kiểm tra các thư mục dự án và đóng gói
    ffmpeg_ext = ".exe" if os.name == 'nt' else ""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(sys.executable)
    
    candidates = [
        resource_path(f"ffmpeg{ffmpeg_ext}"),
        os.path.join(script_dir, f"ffmpeg{ffmpeg_ext}"),
        os.path.join(os.getcwd(), f"ffmpeg{ffmpeg_ext}"),
        os.path.join(app_dir, f"ffmpeg{ffmpeg_ext}"),
    ]

    for p in candidates:
        if os.path.isfile(p):
            ffmpeg_dir = os.path.dirname(os.path.abspath(p))
            # Đảm bảo thư mục chứa ffmpeg nằm trong PATH
            current_path = os.environ.get("PATH", "")
            if ffmpeg_dir not in current_path:
                os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path
            return os.path.abspath(p)

    return None

def check_ffmpeg():
    """Kiểm tra xem ffmpeg đã có trong PATH hoặc thư mục ứng dụng chưa."""
    return get_ffmpeg_path() is not None

def install_ffmpeg():
    """Tự động tải và giải nén ffmpeg cho Windows."""
    print("Đang tải ffmpeg... Vui lòng đợi trong giây lát.")
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    zip_path = "ffmpeg.zip"
    
    # Tải file
    urllib.request.urlretrieve(url, zip_path)
    
    # Giải nén
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("ffmpeg_bin")
    
    # Tìm đường dẫn bin và thêm vào môi trường tạm thời
    for root, dirs, files in os.walk("ffmpeg_bin"):
        if "ffmpeg.exe" in files:
            ffmpeg_path = root
            os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")
            # Copy ffmpeg.exe ra thư mục hiện tại để tiện dùng
            try:
                shutil.copy(os.path.join(ffmpeg_path, "ffmpeg.exe"), "ffmpeg.exe")
            except Exception:
                pass
            break
            
    if os.path.exists(zip_path):
        os.remove(zip_path)
    print("Đã thiết lập ffmpeg thành công.")