import re
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from moviepy.video.io.VideoFileClip import VideoFileClip 
import torch
import whisper
from downloader import VideoDownloader
from utils import resource_path
import threading
import PIL.Image
import os

# Cấu hình giao diện
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def get_optimal_model(self):
        # 1. Kiểm tra xem có Card đồ họa NVIDIA (CUDA) không
        has_cuda = torch.cuda.is_available()
        
        if has_cuda:
            # Lấy dung lượng VRAM trống (tính bằng GB)
            vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            
            if vram >= 10: return "large"
            if vram >= 5:  return "medium"
            if vram >= 2:  return "small"
            return "base"
        else:
            # Nếu dùng CPU, mặc định nên là 'base' để Laptop không bị quá tải
            return "base"
    def export_to_txt(self):
        # Lấy nội dung hiện có trong Textbox
        content = self.text_result.get("0.0", "end").strip()
        
        if not content or content.startswith("đang khởi động"):
            messagebox.showwarning("Thông báo", "Chưa có nội dung gì để xuất cả!")
            return

        # Mở hộp thoại chọn nơi lưu file
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="trich_xuat_van_ban.txt"
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("Thành công", f"Đã lưu file tại:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể lưu file: {e}")
    def __init__(self):
        super().__init__()
        self.title(" YouTube Pro - Win11 Style")
        
        # 1. Kích thước cửa sổ
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        app_width = int(screen_width * 0.7) # Tăng lên 70% vì giờ có thêm Tab trích xuất văn bản
        app_height = int(screen_height * 0.7)
        center_x = int((screen_width - app_width) / 2)
        center_y = int((screen_height - app_height) / 2)
        self.geometry(f"{app_width}x{app_height}+{center_x}+{center_y}")

        # 2. Biến điều khiển
        self.save_path = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        self.quality_var = tk.StringVar(value="1080")
        self.audio_only = tk.BooleanVar(value=False)

        # 3. Tạo hệ thống Tab (Chiếm toàn bộ cửa sổ)
        self.tabview = ctk.CTkTabview(self, corner_radius=15)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)

        self.tab_download = self.tabview.add("Tải Video")
        self.tab_transcribe = self.tabview.add("Trích xuất văn bản")

        # Cấu hình grid cho các Tab để căn giữa nội dung bên trong
        self.tab_download.grid_columnconfigure(0, weight=1)
        self.tab_transcribe.grid_columnconfigure(0, weight=1)

        self.init_download_tab()
        self.init_transcribe_tab()

    def init_download_tab(self):
        # Font chữ
        title_font = ("Segoe UI Variable Display", 28, "bold")
        norm_font = ("Segoe UI Variable Text", 16)
        path_font = ("Consolas", 12)

        # --- Logo ---
        try:
            logo_path = resource_path("download-file.png")
            logo_image = ctk.CTkImage(light_image=PIL.Image.open(logo_path),
                                      dark_image=PIL.Image.open(logo_path),
                                      size=(100, 100))
            self.logo_label = ctk.CTkLabel(self.tab_download, image=logo_image, text="")
            self.logo_label.grid(row=0, column=0, pady=(20, 10))
            
            icon_path = resource_path("download-file.ico")
            self.after(200, lambda: self.iconbitmap(icon_path))
        except:
            self.header_label = ctk.CTkLabel(self.tab_download, text="YOUTUBE DOWNLOADER", font=title_font)
            self.header_label.grid(row=0, column=0, pady=(30, 20))

        # --- Input URL (Gắn vào tab_download) ---
        self.url_frame = ctk.CTkFrame(self.tab_download, fg_color="transparent")
        self.url_frame.grid(row=1, column=0, padx=40, pady=10, sticky="ew")
        self.url_frame.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(self.url_frame, placeholder_text="Dán link YouTube vào đây...", 
                                     font=norm_font, height=45, border_width=2)
        self.url_entry.grid(row=0, column=0, sticky="ew")

        # --- Config Frame (Gắn vào tab_download) ---
        self.config_frame = ctk.CTkFrame(self.tab_download, corner_radius=15, border_width=1)
        self.config_frame.grid(row=2, column=0, padx=40, pady=20, sticky="ew")
        self.config_frame.grid_columnconfigure(1, weight=1)

        # Nơi lưu
        ctk.CTkLabel(self.config_frame, text="Nơi lưu:", font=norm_font).grid(row=0, column=0, padx=20, pady=15)
        self.path_entry = ctk.CTkEntry(self.config_frame, textvariable=self.save_path, state="readonly", font=path_font, height=35)
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=10)
        ctk.CTkButton(self.config_frame, text="Thay đổi", command=self.browse_path, width=100).grid(row=0, column=2, padx=20)

        # Chất lượng
        self.opt_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        self.opt_frame.grid(row=1, column=0, columnspan=3, pady=(0, 15))
        
        ctk.CTkLabel(self.opt_frame, text="Chất lượng:", font=norm_font).pack(side="left", padx=10)
        self.q_combo = ctk.CTkComboBox(self.opt_frame, values=["4320", "2160", "1440", "1080", "720", "480"], 
                                      variable=self.quality_var, state="readonly", width=120)
        self.q_combo.pack(side="left", padx=10)
        
        ctk.CTkCheckBox(self.opt_frame, text="Tải MP3", variable=self.audio_only, 
                         command=self.toggle_audio, font=norm_font).pack(side="left", padx=20)

        # --- Progress ---
        self.progress = ctk.CTkProgressBar(self.tab_download, height=12)
        self.progress.grid(row=3, column=0, padx=40, pady=(10, 0), sticky="ew")
        self.progress.set(0)
        
        self.status_label = ctk.CTkLabel(self.tab_download, text="Sẵn sàng...", font=("Segoe UI Variable Text", 12, "italic"))
        self.status_label.grid(row=4, column=0, pady=5)

        # --- Nút tải ---
        self.btn_download = ctk.CTkButton(self.tab_download, text="BẮT ĐẦU TẢI", font=title_font,
                                          height=60, corner_radius=30, fg_color="#28a745", 
                                          command=self.start_download_thread)
        self.btn_download.grid(row=5, column=0, pady=20)
    #Lựa chọn Video
    def select_video_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Media files", "*.mp4 *.mkv *.mp3 *.wav")])
        if file_path:
            self.process_transcription(file_path)

    def process_transcription(self, video_path):
        clip = VideoFileClip(video_path)
        duration = clip.duration 
        
        if duration > 300: 
            messagebox.showwarning("Quá dài", "Video này dài hơn 5 phút rồi!")
            clip.close()
            return
        
        self.text_result.delete("0.0", "end")
        self.text_result.insert("0.0", " đang khởi động bộ não AI... Vui lòng đợi trong giây lát...\n")
        threading.Thread(target=self.run_whisper, args=(video_path, clip), daemon=True).start()

    def run_whisper(self, video_path, clip):
        try:
            # 1. Bắt đầu (Dùng đúng biến trans_progress)
            self.trans_progress.set(0.1)
            self.trans_status.configure(text="Đang tách âm thanh...", text_color="blue")
            
            audio_path = "temp_audio.mp3"
            clip.audio.write_audiofile(audio_path, logger=None)
            
            # 2. Nạp Model
            self.trans_progress.set(0.4)
            selected_model = self.model_var.get()
            self.trans_status.configure(text=f"Đang nạp bộ não AI ({selected_model})...")
            
            model = whisper.load_model(selected_model)

            # 3. Trích xuất
            self.trans_status.configure(text="Đang chuyển thành văn bản (AI đang suy nghĩ)...")
            
            # Chạy AI
            result = model.transcribe(audio_path, fp16=False)

            # 4. Hiển thị kết quả
            full_text = ""
            for segment in result["segments"]:
                full_text += f"{segment['text'].strip()}\n"
            
            self.text_result.delete("0.0", "end")
            self.text_result.insert("0.0", full_text)
            
            # 5. Hoàn tất
            self.trans_progress.set(1.0) # Đầy cây
            self.trans_status.configure(text="Xong rồi Bạn ơi!", text_color="#28a745")
            self.show_transcribe_finish_dialog()

            clip.close()
            if os.path.exists(audio_path): os.remove(audio_path)
            
        except Exception as e:
            self.trans_progress.set(0)
            self.trans_status.configure(text="Lỗi rồi!", text_color="red")
            messagebox.showerror("Lỗi", str(e))
    
    def toggle_audio(self):
        if self.audio_only.get():
            self.q_combo.configure(state="disabled")
        else:
            self.q_combo.configure(state="readonly")

    def browse_path(self):
        path = filedialog.askdirectory()
        if path: 
            self.save_path.set(path)

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            p_str = d.get('_percent_str', '0%')
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            clean_p_str = ansi_escape.sub('', p_str)
            numeric_p = re.sub(r'[^\d.]', '', clean_p_str)
            
            try:
                if numeric_p:
                    p_float = float(numeric_p)
                    speed = d.get('_speed_str', 'Unknown').strip()
                    speed = ansi_escape.sub('', speed)
                    self.progress.set(p_float / 100)
                    self.status_label.configure(text=f"Tốc độ: {speed} | Đang tải: {p_float}%", text_color="#c4302b")
            except: pass
            self.update_idletasks()

    def start_download_thread(self):
        url = self.url_entry.get()
        if not url:
            messagebox.showwarning("Chú ý", "Chưa có link kìa!")
            return
        self.status_label.configure(text="Đang kết nối...", text_color="blue")
        threading.Thread(target=self.run_download, args=(url,), daemon=True).start()

    def run_download(self, url):
        dl = VideoDownloader(self.progress_hook)
        result = dl.download(url, self.save_path.get(), self.quality_var.get(), self.audio_only.get())
        
        if result["status"] == "success":
            self.status_label.configure(text="Xong!", text_color="#28a745")
            self.show_finish_dialog(result["path"])
        else:
            self.status_label.configure(text="Lỗi rồi!", text_color="red")
            messagebox.showerror("Lỗi", result["message"])
    def show_transcribe_finish_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Xử lý xong")
        dialog.geometry("350x150")
        dialog.attributes("-topmost", True)
        
        # Căn giữa
        x = self.winfo_x() + (self.winfo_width() // 2) - 175
        y = self.winfo_y() + (self.winfo_height() // 2) - 75
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(dialog, text="✨ Đã chuyển văn bản thành công!", 
                     font=("Segoe UI Variable Display", 15, "bold")).pack(pady=20)
        
        ctk.CTkButton(dialog, text="Đóng", width=100, 
                      command=dialog.destroy).pack(pady=10)
    def open_file(self, path):
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không mở được: {e}")

    def show_finish_dialog(self, file_path):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Hoàn tất")
        dialog.geometry("400x200")
        dialog.attributes("-topmost", True)
        
        # Căn giữa dialog
        x = self.winfo_x() + (self.winfo_width() // 2) - 200
        y = self.winfo_y() + (self.winfo_height() // 2) - 100
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(dialog, text="🎉 Tải xong rồi!", font=("Segoe UI Variable Display", 18, "bold")).pack(pady=(30, 10))
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20)

        ctk.CTkButton(btn_frame, text="Mở Video", width=120, height=40,
                      command=lambda: [self.open_file(file_path), dialog.destroy()]).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Đóng", width=100, height=40, fg_color="transparent", 
                      border_width=1, command=dialog.destroy).pack(side="left", padx=10)
        
    #xuất file txt
    def init_transcribe_tab(self):
        ctk.CTkLabel(self.tab_transcribe, text="AUDIO TO TEXT", 
                     font=("Segoe UI Variable Display", 24, "bold"), text_color="#1f538d").pack(pady=20)
        
        # Tạo một khung chứa các nút bấm cho gọn
        self.trans_btn_frame = ctk.CTkFrame(self.tab_transcribe, fg_color="transparent")
        self.trans_btn_frame.pack(pady=10)

        self.btn_select_file = ctk.CTkButton(self.trans_btn_frame, text="📁 Chọn Video/Audio", 
                                             height=40, command=self.select_video_file)
        self.btn_select_file.pack(side="left", padx=10)
        self.model_var = ctk.StringVar(value=self.get_optimal_model()) # Tự động chọn cái tốt nhất

        # Khung cấu hình AI
        self.ai_config_frame = ctk.CTkFrame(self.tab_transcribe, fg_color="transparent")
        self.ai_config_frame.pack(pady=10)

        ctk.CTkLabel(self.ai_config_frame, text="Chọn 'Bộ não' AI:", font=("Segoe UI Variable Text", 14)).pack(side="left", padx=10)
        
        self.model_combo = ctk.CTkComboBox(self.ai_config_frame, 
                                            values=["tiny", "base", "small", "medium", "large"],
                                            variable=self.model_var,
                                            state="readonly", width=120)
        self.model_combo.pack(side="left", padx=10)

        # NÚT MỚI: Xuất file Text
        self.btn_export_txt = ctk.CTkButton(self.trans_btn_frame, text="💾 Xuất file .txt", 
                                             height=40, fg_color="#607d8b", hover_color="#455a64",
                                             command=self.export_to_txt)
        self.btn_export_txt.pack(side="left", padx=10)
        # --- THÊM PROGRESS BAR CHO TAB 2 ---
        self.trans_progress = ctk.CTkProgressBar(self.tab_transcribe, height=12)
        self.trans_progress.pack(fill="x", padx=40, pady=(10, 0))
        self.trans_progress.set(0) # Khởi tạo 0%

        self.trans_status = ctk.CTkLabel(self.tab_transcribe, text="Chờ lệnh của Bạn...", 
                                         font=("Segoe UI Variable Text", 12, "italic"))
        self.trans_status.pack(pady=5)

        self.text_result = ctk.CTkTextbox(self.tab_transcribe, font=("Segoe UI Variable Text", 15),
                                         border_width=2, corner_radius=10)
        self.text_result.pack(pady=20, padx=30, fill="both", expand=True)