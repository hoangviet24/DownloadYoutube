from utils import check_ffmpeg, install_ffmpeg
from gui import App
import tkinter as tk
from tkinter import messagebox
import ctypes
myappid = 'viet.youtube.downloader.pro.1.0' 
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
if __name__ == "__main__":
    # Bước 1: Kiểm tra FFmpeg
    if not check_ffmpeg():
        # Hiển thị thông báo nhỏ cho người dùng biết
        root = tk.Tk()
        root.withdraw()
        confirm = messagebox.askyesno("Thiếu FFmpeg", "Ứng dụng cần FFmpeg để hoạt động. Bạn có muốn tự động cài đặt không?")
        if confirm:
            try:
                install_ffmpeg()
                root.destroy()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể cài đặt FFmpeg: {e}")
                exit()
        else:
            exit()

    # Bước 2: Vào App
    app = App()
    app.mainloop()
