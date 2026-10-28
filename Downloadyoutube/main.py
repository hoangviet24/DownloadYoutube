import sys
import os
import tkinter as tk
from tkinter import messagebox
from utils import check_ffmpeg, install_ffmpeg, resource_path
from gui import App

def setup_windows_appid():
    """Thiết lập AppUserModelID để Windows hiển thị đúng icon riêng trên Taskbar."""
    if os.name == 'nt':
        try:
            import ctypes
            myappid = 'viet.youtube.downloader.pro.1.0' 
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

if __name__ == "__main__":
    setup_windows_appid()

    # Bước 1: Kiểm tra FFmpeg
    if not check_ffmpeg():
        root = tk.Tk()
        root.withdraw()
        icon_path = resource_path(os.path.join("assets", "download-file.ico"))
        if os.path.exists(icon_path):
            try:
                root.iconbitmap(icon_path)
            except Exception:
                pass

        confirm = messagebox.askyesno(
            "Thiếu FFmpeg", 
            "Ứng dụng cần thư viện FFmpeg để xử lý video/âm thanh.\nBạn có muốn tự động tải và cài đặt FFmpeg không?"
        )
        if confirm:
            try:
                install_ffmpeg()
                root.destroy()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể cài đặt FFmpeg: {e}")
                root.destroy()
                sys.exit(1)
        else:
            root.destroy()
            sys.exit(0)

    # Bước 2: Khởi chạy ứng dụng chính
    app = App()
    app.mainloop()

