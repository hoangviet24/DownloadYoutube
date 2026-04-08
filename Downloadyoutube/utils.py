import os
import subprocess
import shutil
import sys
import urllib.request
import zipfile

def check_ffmpeg():
    """Kiểm tra xem ffmpeg đã có trong PATH chưa."""
    return shutil.which("ffmpeg") is not None

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
            os.environ["PATH"] += os.pathsep + ffmpeg_path
            break
            
    os.remove(zip_path)
    print("Đã thiết lập ffmpeg tạm thời cho phiên làm việc này.")
def resource_path(relative_path):
    """ Lấy đường dẫn tuyệt đối đến tài nguyên, dùng cho cả dev và sau khi đóng gói """
    try:
        # PyInstaller tạo thư mục tạm và lưu đường dẫn trong _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)