import os
import sys
import re
import threading
import io
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import PIL.Image
from PIL import ImageTk

from utils import resource_path, get_ffmpeg_path
from downloader import VideoDownloader

# Cấu hình giao diện CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- 1. Thiết lập Cửa sổ & Icon ---
        self.title("YouTube Arcana · Tải video và âm thanh")
        self.configure(fg_color="#071426")
        self.icon_path = resource_path(os.path.join("assets", "download-file.ico"))
        self.icon_png_path = resource_path(os.path.join("assets", "download-file.png"))
        self._app_icon_photo = None
        self._setup_app_icons()

        # Kích thước cửa sổ chuẩn (70% màn hình, căn giữa như bản gốc)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        app_width = int(screen_width * 0.7)
        app_height = int(screen_height * 0.72)
        center_x = int((screen_width - app_width) / 2)
        center_y = int((screen_height - app_height) / 2)
        self.geometry(f"{app_width}x{app_height}+{center_x}+{center_y}")
        self.minsize(800, 600)

        # --- 2. Biến điều khiển ---
        default_download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        self.save_path = tk.StringVar(value=default_download_dir)
        self.quality_var = tk.StringVar(value="Best (tối đa 1080p)")
        self.audio_only = tk.BooleanVar(value=False)
        self.model_var = ctk.StringVar(value="base")
        
        self.selected_transcribe_path = None
        self.is_downloading = False
        self.video_queue = []
        self.selected_queue_item = None
        self.is_transcribing = False

        # Cache cho mô hình Whisper để không tốn thời gian tải lại mỗi lần trích xuất
        self.cached_whisper_model = None
        self.cached_model_name = None
        self.discrete_gpu_available = False
        self._gradient_phase = 0.0

        # --- 3. Hệ thống Tab (Chiếm toàn bộ cửa sổ) ---
        self.tabview = ctk.CTkTabview(
            self, corner_radius=16, fg_color="#0b1830",
            segmented_button_fg_color="#10213a",
            segmented_button_selected_color="#347e9b",
            segmented_button_selected_hover_color="#469ab3",
            segmented_button_unselected_color="#152846",
            segmented_button_unselected_hover_color="#203b60",
            text_color="#e7f8ff"
        )
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)

        self.tab_download = self.tabview.add("Tải Video")
        self.tab_transcribe = self.tabview.add("Trích xuất văn bản")
        self.tab_download.configure(fg_color="#0b1830")
        self.tab_transcribe.configure(fg_color="#0b1830")

        # Cấu hình grid cho các Tab để căn giữa nội dung bên trong
        self.tab_download.grid_columnconfigure(0, weight=1)
        self.tab_download.grid_rowconfigure(3, weight=1)
        self.tab_transcribe.grid_columnconfigure(0, weight=1)

        self.init_download_tab()
        self.init_transcribe_tab()
        self.after(100, self._animate_interface)

        # Tự động phát hiện model tối ưu trong nền mà không làm đơ giao diện khi mở app
        threading.Thread(target=self._detect_optimal_model_async, daemon=True).start()

    def _setup_app_icons(self):
        """Thiết lập icon an toàn cho CustomTkinter trên Windows."""
        try:
            if os.path.exists(self.icon_path):
                # Gọi sau 200ms khi cửa sổ đã sẵn sàng để không xung đột với titlebar CustomTkinter
                self.after(200, lambda: self._apply_icon(self))
        except Exception:
            pass

        try:
            if os.path.exists(self.icon_png_path):
                img = PIL.Image.open(self.icon_png_path)
                self._app_icon_photo = ImageTk.PhotoImage(img)
                self.wm_iconphoto(True, self._app_icon_photo)
        except Exception:
            pass

    def _apply_icon(self, window):
        """Áp dụng iconbitmap một cách an toàn."""
        try:
            if os.path.exists(self.icon_path):
                window.iconbitmap(self.icon_path)
        except Exception:
            pass

    def apply_icon_to_window(self, win):
        """Gán icon cho các cửa sổ con Toplevel hoặc Dialog."""
        win.after(100, lambda: self._apply_icon(win))
        if self._app_icon_photo:
            try:
                win.wm_iconphoto(False, self._app_icon_photo)
            except Exception:
                pass

    def _detect_optimal_model_async(self):
        """Chỉ bật nhận dạng khi CUDA phát hiện GPU rời tương thích."""
        try:
            import torch
            if torch.cuda.is_available():
                vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                self.discrete_gpu_available = True
                if vram >= 10:
                    best = "large"
                elif vram >= 5:
                    best = "medium"
                elif vram >= 2:
                    best = "small"
                else:
                    best = "base"
            else:
                best = None
            if best:
                self.after(0, lambda: self.model_var.set(best))
            self.after(0, self._apply_transcription_hardware_state)
        except Exception:
            self.after(0, self._apply_transcription_hardware_state)

    def _apply_transcription_hardware_state(self):
        if not self.discrete_gpu_available:
            self.btn_start_transcribe.configure(state="disabled", fg_color="#263c52")
            self.trans_status.configure(
                text="Nhận dạng văn bản cần GPU rời NVIDIA hỗ trợ CUDA.",
                text_color="#92e5ec"
            )

    # =========================================================================
    # TAB 1: TẢI VIDEO & AUDIO
    # =========================================================================
    def init_download_tab(self):
        title_font = ("Segoe UI Variable Display", 28, "bold")
        norm_font = ("Segoe UI Variable Text", 16)
        path_font = ("Consolas", 12)

        self.banner = tk.Canvas(
            self.tab_download, height=176, bg="#0a1a31", bd=0,
            highlightthickness=1, highlightbackground="#254c68"
        )
        self.banner.grid(row=0, column=0, padx=40, pady=(10, 2), sticky="ew")
        self.banner.bind("<Configure>", self._draw_arcana_banner)

        # --- Input URL & Nút Dán nhanh gọn gàng ---
        self.url_frame = ctk.CTkFrame(self.tab_download, fg_color="transparent")
        self.url_frame.grid(row=1, column=0, padx=40, pady=10, sticky="ew")
        self.url_frame.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            self.url_frame,
            placeholder_text="Dán link YouTube để bắt đầu tải video hoặc âm thanh…",
            font=norm_font,
            height=45,
            border_width=1,
            fg_color="#0d2038",
            border_color="#367d92",
            text_color="#e5f2f7",
            placeholder_text_color="#8aabba"
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.url_entry.bind("<Return>", lambda event: self.add_video_to_queue())

        self.btn_paste = ctk.CTkButton(
            self.url_frame,
            text="📋 Dán",
            width=80,
            height=45,
            font=("Segoe UI Variable Text", 14, "bold"),
            command=self.paste_from_clipboard
        )
        self.btn_paste.grid(row=0, column=1)

        self.btn_add_video = ctk.CTkButton(
            self.url_frame, text="✦ Tìm video", width=120, height=45,
            fg_color="#277d99", hover_color="#379bb1",
            command=self.add_video_to_queue
        )
        self.btn_add_video.grid(row=0, column=2, padx=(10, 0))

        ctk.CTkLabel(
            self.tab_download, text="Video của bạn · chọn chất lượng ngay trên từng thẻ",
            font=("Segoe UI Variable Display", 17, "bold"), text_color="#92e5ec"
        ).grid(row=2, column=0, padx=40, pady=(4, 0), sticky="w")
        self.queue_frame = ctk.CTkScrollableFrame(
            self.tab_download, height=190, corner_radius=14,
            fg_color="#0d2038", border_width=1, border_color="#28516a"
        )
        self.queue_frame.grid(row=3, column=0, padx=40, pady=(5, 12), sticky="nsew")
        self.queue_frame.grid_columnconfigure(0, weight=1)

        # --- Khung cấu hình Nơi lưu & Chất lượng ---
        self.config_frame = ctk.CTkFrame(
            self.tab_download, corner_radius=15, border_width=1,
            fg_color="#10243c", border_color="#28516a"
        )
        self.config_frame.grid(row=4, column=0, padx=40, pady=(0, 8), sticky="ew")
        self.config_frame.grid_columnconfigure(1, weight=1)

        # Hàng 0: Nơi lưu
        ctk.CTkLabel(self.config_frame, text="✧ Lưu vào", font=norm_font, text_color="#92e5ec").grid(
            row=0, column=0, padx=20, pady=15
        )
        self.path_entry = ctk.CTkEntry(
            self.config_frame,
            textvariable=self.save_path,
            
            state="readonly",
            font=path_font,
            height=35,
            fg_color="#0a192d",
            border_color="#2a596f",
            text_color="#d5eaf0"
        )
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=10)

        ctk.CTkButton(
            self.config_frame,
            text="Thay đổi",
            command=self.browse_path,
            width=100
        ).grid(row=0, column=2, padx=20)

        # Hàng 1: Chất lượng & Tùy chọn (Căn giữa cân đối)
        self.opt_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        self.opt_frame.grid(row=1, column=0, columnspan=3, pady=(0, 15))

        self.chk_audio = ctk.CTkCheckBox(
            self.opt_frame,
            text="Tải MP3",
            variable=self.audio_only,
            command=self.toggle_audio,
            font=norm_font
        )
        self.chk_audio.pack(side="left", padx=10)

        # --- Tiến trình tải ---
        self.progress = ctk.CTkProgressBar(self.tab_download, height=12)
        self.progress.grid(row=5, column=0, padx=40, pady=(3, 0), sticky="ew")
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(
            self.tab_download,
            text="Sẵn sàng...",
            font=("Segoe UI Variable Text", 12, "italic"),
            text_color="gray"
        )
        self.status_label.grid(row=6, column=0, pady=3)

        # --- Nút tải ---
        self.btn_download = ctk.CTkButton(
            self.tab_download,
            text="CHỌN THUMBNAIL ĐỂ TẢI",
            font=title_font,
            height=60,
            corner_radius=30,
            fg_color="#277d99",
            hover_color="#379bb1",
            state="disabled",
            command=self.download_selected_queue_item
        )
        self.btn_download.grid(row=7, column=0, pady=8)

    def _draw_arcana_banner(self, event):
        """Draw a responsive cathedral header over the animated gradient."""
        canvas = self.banner
        width, height = max(canvas.winfo_width(), 600), max(canvas.winfo_height(), 150)
        canvas.delete("all")
        self._paint_moving_gradient(canvas, width, height)
        canvas.create_rectangle(1, 1, width - 2, height - 2, outline="#4a94a3", width=1)

        def arch(cx, arch_width, top, base, palette):
            half = arch_width / 2
            shoulder = top + arch_width * 0.33
            outline = [cx - half, base, cx - half, shoulder, cx, top, cx + half, shoulder, cx + half, base]
            canvas.create_polygon(outline, fill="#153d5b", outline="#79d9e4", width=2)
            inner = arch_width * 0.39
            canvas.create_polygon(
                cx - inner, base - 3, cx - inner, shoulder + 10, cx, top + 16,
                cx + inner, shoulder + 10, cx + inner, base - 3,
                fill=palette[0], outline="#c4f4ed", width=1
            )
            canvas.create_line(cx, top + 16, cx, base - 4, fill=palette[1], width=2)
            canvas.create_line(cx - inner, shoulder + 18, cx + inner, shoulder + 18, fill=palette[2], width=2)
            canvas.create_oval(cx - 10, top + 28, cx + 10, top + 48, fill=palette[2], outline="#e5d48c")
            for offset in (-0.55, 0.55):
                x = cx + half * offset
                canvas.create_line(x, shoulder + 5, x, base, fill="#a8eaf0", width=2)
            canvas.create_line(cx - half - 8, base, cx + half + 8, base, fill="#d9c47e", width=3)

        arch(width * 0.72, height * 0.92, 8, height - 9, ("#55b9d0", "#d6efce", "#e1c66f"))
        arch(width * 0.88, height * 0.72, 21, height - 9, ("#4293c0", "#87e0dc", "#e5c96f"))
        arch(width * 1.02, height * 0.58, 31, height - 9, ("#38a0ad", "#a8e4da", "#d9c477"))
        # Pillars and warm light shafts give the glass windows a cathedral setting.
        for x in (width * 0.57, width * 0.82, width * 0.96):
            canvas.create_line(x, 9, x, height - 4, fill="#87b9c2", width=3)
            canvas.create_line(x + 5, 20, x + 5, height - 4, fill="#355a70", width=2)
        canvas.create_line(width * 0.56, height - 7, width, height - 7, fill="#d9c47e", width=2)
        canvas.create_text(
            35, height * 0.43, anchor="w", text="✦  YOUTUBE ARCANA",
            fill="#f1dfaa", font=("Segoe UI Variable Display", 25, "bold")
        )
        canvas.create_text(
            39, height * 0.69, anchor="w", text="Một cánh cổng nhỏ dẫn đến khoảnh khắc bạn muốn lưu giữ",
            fill="#c4e8ed", font=("Segoe UI Variable Text", 11)
        )

    def paste_from_clipboard(self):
        """Dán link từ Clipboard vào ô nhập."""
        try:
            clipboard_text = self.clipboard_get().strip()
            if clipboard_text:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, clipboard_text)
        except Exception:
            pass

    def toggle_audio(self):
        """Set the selected card's output mode to MP3 or MP4."""
        if self.audio_only.get():
            self.quality_var.set("320 kbps (Tốt nhất)")
        else:
            self.quality_var.set("Best (tối đa 1080p)")

    def add_video_to_queue(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Thiếu đường dẫn", "Dán link YouTube trước nhé.")
            return
        self.btn_add_video.configure(state="disabled", text="Đang tìm…")
        self.btn_download.configure(state="disabled", text="ĐANG LẤY THÔNG TIN…")
        threading.Thread(target=self._load_queue_item, args=(url,), daemon=True).start()

    def _load_queue_item(self, url):
        result = VideoDownloader().get_video_choices(url)
        if result.get("status") == "success" and result.get("thumbnail"):
            try:
                request = urllib.request.Request(
                    result["thumbnail"], headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(request, timeout=10) as response:
                    result["thumbnail_bytes"] = response.read()
            except Exception:
                result["thumbnail_bytes"] = None
        self.after(0, lambda: self._finish_adding_queue_item(result))

    def _finish_adding_queue_item(self, item):
        self.btn_add_video.configure(state="normal", text="✦ Tìm video")
        self.btn_download.configure(
            state="disabled" if self.is_downloading else ("normal" if self.selected_queue_item else "disabled"),
            text="TẢI VIDEO ĐANG CHỌN" if self.selected_queue_item else "CHỌN THUMBNAIL ĐỂ TẢI"
        )
        if item.get("status") != "success":
            messagebox.showerror("Không lấy được video", item.get("message", "Lỗi đọc thông tin YouTube."))
            return
        if any(existing["url"] == item["url"] for existing in self.video_queue):
            self.status_label.configure(text="Video này đã có trong danh sách.", text_color="#92e5ec")
            return

        card = ctk.CTkFrame(self.queue_frame, corner_radius=12, fg_color="#122a43", border_width=1, border_color="#28516a")
        card.pack(fill="x", padx=5, pady=5)
        card.grid_columnconfigure(1, weight=1)
        image = None
        if item.get("thumbnail_bytes"):
            try:
                thumb = PIL.Image.open(io.BytesIO(item["thumbnail_bytes"])).convert("RGB")
                image = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=(112, 64))
            except Exception:
                image = None
        thumb_label = ctk.CTkLabel(card, text="▶", image=image, width=112, height=64)
        thumb_label.grid(row=0, column=0, rowspan=2, padx=10, pady=8)
        thumb_label.image = image
        title_label = ctk.CTkLabel(
            card, text=item["title"], anchor="w", justify="left",
            font=("Segoe UI Variable Text", 14, "bold"), text_color="#f2eaff"
        )
        title_label.grid(row=0, column=1, sticky="ew", padx=8, pady=(8, 1))
        choices = ctk.CTkFrame(card, fg_color="transparent")
        choices.grid(row=1, column=1, sticky="w", padx=5, pady=(0, 8))
        heights = item.get("heights", [])
        offered = [height for height in heights if height <= 4320]
        quality_choices = [("Best", "best")] + [(f"{height}p", height) for height in reversed(offered)]
        for label, quality in quality_choices:
            quality_label = ctk.CTkLabel(
                choices, text=label, corner_radius=8, padx=9, pady=5,
                fg_color="#1e405a", text_color="#d3f4f1", cursor="hand2"
            )
            quality_label.pack(side="left", padx=3)
            quality_label.bind(
                "<Button-1>",
                lambda _event, q=quality, source=item: self._select_queue_item(source, q)
            )
            item.setdefault("quality_labels", []).append((quality, quality_label))
        item["card"] = card
        item["thumb_label"] = thumb_label
        item["quality"] = "best"
        item["title_label"] = title_label
        for selectable in (card, thumb_label, item["title_label"]):
            selectable.bind("<Button-1>", lambda _event, source=item: self._select_queue_item(source))
        self.video_queue.append(item)
        self.url_entry.delete(0, "end")
        available = ", ".join(f"{height}p" for height in reversed(offered)) or "chưa đọc được độ phân giải"
        self.status_label.configure(text=f"Đã thêm · chất lượng nguồn: {available}", text_color="#92e5ec")

    def _select_queue_item(self, item, quality=None):
        self.selected_queue_item = item
        if quality is not None:
            item["quality"] = quality
        for queued in self.video_queue:
            queued["card"].configure(
                border_width=2 if queued is item else 1,
                border_color="#e2ca83" if queued is item else "#28516a"
            )
            for candidate_quality, label in queued.get("quality_labels", []):
                active = queued is item and candidate_quality == queued.get("quality", "best")
                label.configure(
                    fg_color="#258da1" if active else "#1e405a",
                    text_color="#ffffff" if active else "#d3f4f1"
                )
        self.btn_download.configure(
            state="disabled" if self.is_downloading else "normal",
            text="ĐANG TẢI VIDEO..." if self.is_downloading else "TẢI VIDEO ĐANG CHỌN"
        )
        self.status_label.configure(
            text=f"Đã chọn: {item['title']} · chất lượng {item.get('quality', 'best')}",
            text_color="#92e5ec"
        )

    def download_selected_queue_item(self):
        item = self.selected_queue_item
        if not item:
            messagebox.showinfo("Chọn video", "Nhấn vào thumbnail video bạn muốn tải trước nhé.")
            return
        self._download_queue_item(item, item.get("quality", "best"), audio=self.audio_only.get())

    def _download_queue_item(self, item, quality, audio=False):
        if self.is_downloading:
            messagebox.showinfo("Đang tải", "Đợi lượt tải hiện tại hoàn tất rồi chọn video tiếp theo nhé.")
            return
        self.selected_queue_item = item
        self.audio_only.set(audio)
        self.quality_var.set(quality if audio else ("Best (tối đa 1080p)" if quality == "best" else str(quality)))
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, item["url"])
        self.start_download_thread()

    def browse_path(self):
        path = filedialog.askdirectory(initialdir=self.save_path.get())
        if path:
            self.save_path.set(path)

    def progress_hook(self, d):
        """Cập nhật tiến trình download an toàn thread-safe."""
        if d.get('status') == 'downloading':
            p_str = d.get('_percent_str', '0%')
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            clean_p_str = ansi_escape.sub('', p_str)
            numeric_p = re.sub(r'[^\d.]', '', clean_p_str)

            try:
                if numeric_p:
                    p_float = float(numeric_p)
                    speed = d.get('_speed_str', 'Đang tính...').strip()
                    speed = ansi_escape.sub('', speed)
                    self.after(0, lambda: self._update_download_progress(p_float, speed))
            except Exception:
                pass

    def _update_download_progress(self, p_float, speed):
        self.progress.set(p_float / 100)
        self.status_label.configure(
            text=f"Tốc độ: {speed} | Đang tải: {p_float:.1f}%",
            text_color="#c4302b"
        )

    def start_download_thread(self):
        """Bắt đầu luồng kiểm tra và tải video."""
        if self.is_downloading:
            messagebox.showwarning("Chú ý", "Hiện đang có một tiến trình tải đang chạy. Vui lòng đợi!")
            return

        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Chú ý", "Chưa có link kìa!")
            return

        # Khóa nút bấm và chuyển trạng thái UI
        self.is_downloading = True
        self.btn_download.configure(state="disabled", text="⏳ ĐANG TẢI VIDEO...", fg_color="#6c757d")
        self.status_label.configure(text="Đang check Metadata...", text_color="blue")
        self.progress.set(0)

        threading.Thread(target=self._process_download, args=(url,), daemon=True).start()

    def _process_download(self, url):
        downloader = VideoDownloader(self.progress_hook)
        save_dir = self.save_path.get()
        quality = self.quality_var.get()
        is_audio = self.audio_only.get()

        try:
            # Bước 1: Lấy info và kiểm tra trùng lặp
            check_res = downloader.get_info(url, save_dir, quality, is_audio)

            if check_res["status"] != "success":
                err_msg = check_res.get("message", "Lỗi lấy thông tin!")
                self.after(0, lambda: self._on_download_error(err_msg))
                return

            final_path = check_res["final_path"]
            info = check_res["info"]

            # Bước 2: Kiểm tra nếu file đã tồn tại
            if check_res.get("exists", False):
                file_name = os.path.basename(final_path)
                user_choice = [False]
                prompt_done = threading.Event()

                def ask_user():
                    ans = messagebox.askyesno(
                        "Xác nhận",
                        f"File '{file_name}' đã tồn tại.\nBạn có muốn tải và ghi đè không?"
                    )
                    user_choice[0] = ans
                    prompt_done.set()

                self.after(0, ask_user)
                prompt_done.wait()

                if not user_choice[0]:
                    self.after(0, self._on_download_cancelled)
                    return
                else:
                    try:
                        os.remove(final_path)
                    except Exception:
                        pass

            # Bước 3: Tải video trực tiếp từ info đã trích xuất (tối ưu, không tải lại metadata)
            self.after(0, lambda: self.status_label.configure(text="Đang kết nối server...", text_color="blue"))

            def scale_callback(pct, cur_sec, tot_sec, q_label):
                pct_str = f"{pct * 100:.1f}%"
                time_str = f"{int(cur_sec)}s/{int(tot_sec)}s" if tot_sec else f"{int(cur_sec)}s"
                text = f"Đang scale video lên {q_label}: {pct_str} ({time_str})"
                self.after(0, lambda: self._update_scale_progress(pct, text))

            dl_res = downloader.download(
                url,
                save_dir,
                quality,
                is_audio,
                pre_info=info,
                auto_scale=False,
                scale_callback=scale_callback
            )

            if dl_res["status"] == "success":
                self.after(0, lambda: self._on_download_success(dl_res["path"]))
            else:
                self.after(0, lambda: self._on_download_error(dl_res.get("message", "Lỗi rồi!")))

        except Exception as e:
            self.after(0, lambda: self._on_download_error(f"Lỗi: {e}"))

    def _update_scale_progress(self, p_float, text):
        """Cập nhật tiến trình khi đang thực hiện scale video."""
        self.progress.set(p_float)
        self.status_label.configure(
            text=text,
            text_color="#6f42c1"
        )

    def _on_download_success(self, file_path):
        self.is_downloading = False
        self.progress.set(1.0)
        self.status_label.configure(text="Xong!", text_color="#28a745")
        self.btn_download.configure(
            state="disabled" if self.is_downloading else ("normal" if self.selected_queue_item else "disabled"),
            text="TẢI VIDEO ĐANG CHỌN" if self.selected_queue_item else "CHỌN THUMBNAIL ĐỂ TẢI",
            fg_color="#277d99"
        )
        self.show_finish_dialog(file_path)

    def _on_download_error(self, message):
        self.is_downloading = False
        self.progress.set(0)
        self.status_label.configure(text="Lỗi rồi!", text_color="red")
        self.btn_download.configure(
            state="disabled" if self.is_downloading else ("normal" if self.selected_queue_item else "disabled"),
            text="TẢI VIDEO ĐANG CHỌN" if self.selected_queue_item else "CHỌN THUMBNAIL ĐỂ TẢI",
            fg_color="#277d99"
        )
        messagebox.showerror("Lỗi", message)

    def _on_download_cancelled(self):
        self.is_downloading = False
        self.status_label.configure(text="Đã hủy tải.", text_color="orange")
        self.btn_download.configure(
            state="disabled" if self.is_downloading else ("normal" if self.selected_queue_item else "disabled"),
            text="TẢI VIDEO ĐANG CHỌN" if self.selected_queue_item else "CHỌN THUMBNAIL ĐỂ TẢI",
            fg_color="#277d99"
        )

    def show_finish_dialog(self, file_path):
        """Hộp thoại thông báo khi tải xong."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Hoàn tất")
        dialog.geometry("400x200")
        dialog.attributes("-topmost", True)
        self.apply_icon_to_window(dialog)

        # Căn giữa dialog
        x = self.winfo_x() + (self.winfo_width() // 2) - 200
        y = self.winfo_y() + (self.winfo_height() // 2) - 100
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(dialog, text="🎉 Tải xong rồi!", font=("Segoe UI Variable Display", 18, "bold")).pack(pady=(30, 10))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20)

        btn_label = "Mở MP3" if file_path.lower().endswith(".mp3") else "Mở Video"
        ctk.CTkButton(
            btn_frame,
            text=btn_label,
            width=120,
            height=40,
            command=lambda: [self.open_file(file_path), dialog.destroy()]
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="Đóng",
            width=100,
            height=40,
            fg_color="transparent",
            border_width=1,
            command=dialog.destroy
        ).pack(side="left", padx=10)

    def open_file(self, path):
        """Mở trực tiếp file bằng ứng dụng mặc định."""
        try:
            if os.path.exists(path):
                os.startfile(path)
            else:
                messagebox.showerror("Lỗi", "File không tồn tại!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không mở được: {e}")

    # =========================================================================
    # TAB 2: TRÍCH XUẤT VĂN BẢN (AUDIO TO TEXT)
    # =========================================================================
    def init_transcribe_tab(self):
        title_font = ("Segoe UI Variable Display", 24, "bold")
        norm_font = ("Segoe UI Variable Text", 14)

        hero = ctk.CTkFrame(self.tab_transcribe, fg_color="transparent")
        hero.pack(fill="x", padx=34, pady=(12, 8))
        self.transcribe_banner = tk.Canvas(
            hero, height=112, bg="#0b1830", bd=0,
            highlightthickness=1, highlightbackground="#2b6174"
        )
        self.transcribe_banner.pack(fill="x")
        self.transcribe_banner.bind("<Configure>", self._draw_transcribe_gradient)

        # --- Khu vực chọn file ---
        self.file_select_frame = ctk.CTkFrame(self.tab_transcribe, fg_color="transparent")
        self.file_select_frame.pack(pady=10)

        self.btn_select_file = ctk.CTkButton(
            self.file_select_frame,
            text="📁 1. Chọn Video/Audio",
            height=40,
            command=self.select_video_file
        )
        self.btn_select_file.pack(side="left", padx=10)

        # Label hiển thị tên file đã chọn
        self.file_info_label = ctk.CTkLabel(
            self.tab_transcribe,
            text="Chưa có file nào được chọn",
            font=("Segoe UI Variable Text", 13, "italic")
        )
        self.file_info_label.pack(pady=5)

        # --- Khu vực cấu hình và thực hiện (Hàng 1: Chọn Model + Nút Bắt đầu trích xuất) ---
        self.action_frame = ctk.CTkFrame(self.tab_transcribe, fg_color="transparent")
        self.action_frame.pack(pady=5)

        ctk.CTkLabel(self.action_frame, text="Bộ não AI:", font=norm_font).pack(side="left", padx=5)
        self.model_combo = ctk.CTkComboBox(
            self.action_frame,
            values=["tiny", "base", "small", "medium", "large"],
            variable=self.model_var,
            state="readonly",
            width=100,
            fg_color="#10243c",
            border_color="#367d92",
            button_color="#277d99",
            button_hover_color="#379bb1",
            text_color="#e5f2f7",
            dropdown_fg_color="#10243c",
            dropdown_text_color="#e5f2f7",
            dropdown_hover_color="#24516a"
        )
        self.model_combo.pack(side="left", padx=10)

        self.btn_start_transcribe = ctk.CTkButton(
            self.action_frame,
            text="⚡ 2. Bắt đầu trích xuất",
            height=40,
            fg_color="gray",
            state="disabled",
            command=self.trigger_transcription
        )
        self.btn_start_transcribe.pack(side="left", padx=10)

        # --- Hàng 2: Thanh công cụ quản lý kết quả (Xuất .txt, Sao chép, Xóa) ---
        self.tools_frame = ctk.CTkFrame(self.tab_transcribe, fg_color="transparent")
        self.tools_frame.pack(pady=(0, 10))

        self.btn_copy_txt = ctk.CTkButton(
            self.tools_frame,
            text="📋 Sao chép",
            height=35,
            width=100,
            fg_color="#455a64",
            hover_color="#37474f",
            command=self.copy_transcribed_text
        )
        self.btn_copy_txt.pack(side="left", padx=6)

        self.btn_export_txt = ctk.CTkButton(
            self.tools_frame,
            text="💾 Xuất .txt",
            height=35,
            width=100,
            fg_color="#607d8b",
            hover_color="#455a64",
            command=self.export_to_txt
        )
        self.btn_export_txt.pack(side="left", padx=6)

        self.btn_clear_txt = ctk.CTkButton(
            self.tools_frame,
            text="🧹 Xóa",
            height=35,
            width=80,
            fg_color="#78909c",
            hover_color="#546e7a",
            command=self.clear_transcribed_text
        )
        self.btn_clear_txt.pack(side="left", padx=6)

        # --- Progress & Textbox ---
        self.trans_progress = ctk.CTkProgressBar(self.tab_transcribe, height=12)
        self.trans_progress.pack(fill="x", padx=40, pady=(5, 0))
        self.trans_progress.set(0)

        self.trans_status = ctk.CTkLabel(
            self.tab_transcribe,
            text="Sẵn sàng phục vụ Việt!",
            font=("Segoe UI Variable Text", 12, "italic")
        )
        self.trans_status.pack(pady=5)

        self.result_panel = ctk.CTkFrame(
            self.tab_transcribe, fg_color="#0e223a", corner_radius=14,
            border_width=1, border_color="#2a596f"
        )
        self.result_panel.pack(pady=(7, 14), padx=30, fill="both", expand=True)
        result_heading = ctk.CTkFrame(self.result_panel, fg_color="transparent")
        result_heading.pack(fill="x", padx=15, pady=(11, 4))
        ctk.CTkLabel(
            result_heading, text="✦ BẢN CHÉP ✦", anchor="w",
            font=("Segoe UI Variable Display", 12, "bold"), text_color="#e0ce91"
        ).pack(side="left")
        ctk.CTkLabel(
            result_heading, text="Văn bản đã nhận dạng", anchor="e",
            font=("Segoe UI Variable Text", 11), text_color="#85abbc"
        ).pack(side="right")
        self.text_result = ctk.CTkTextbox(
            self.result_panel,
            font=("Segoe UI Variable Text", 15),
            fg_color="#0a192d", text_color="#e5f2f7",
            border_width=0, corner_radius=10,
            scrollbar_button_color="#2c7187",
            scrollbar_button_hover_color="#46a4b4"
        )
        self.text_result.pack(pady=(2, 12), padx=12, fill="both", expand=True)

    def _paint_moving_gradient(self, canvas, width, height):
        palette = ((7, 20, 42), (20, 93, 117), (24, 51, 94), (7, 20, 42))
        phase = self._gradient_phase % 1.0
        for x in range(0, width, 14):
            position = ((x / max(width, 1)) + phase) % 1.0
            scaled = position * (len(palette) - 1)
            segment = min(int(scaled), len(palette) - 2)
            blend = scaled - segment
            rgb = tuple(
                round(palette[segment][i] * (1 - blend) + palette[segment + 1][i] * blend)
                for i in range(3)
            )
            color = "#" + "".join(f"{channel:02x}" for channel in rgb)
            canvas.create_rectangle(x, 0, x + 14, height, fill=color, outline=color)

    def _draw_transcribe_gradient(self, _event=None):
        canvas = self.transcribe_banner
        width, height = max(canvas.winfo_width(), 500), max(canvas.winfo_height(), 100)
        canvas.delete("all")
        self._paint_moving_gradient(canvas, width, height)
        canvas.create_rectangle(1, 1, width - 2, height - 2, outline="#315b72", width=1)
        canvas.create_line(24, height - 7, width - 24, height - 7, fill="#cdbb7d", width=1)
        canvas.create_text(
            30, height * 0.40, anchor="w", text="SCRIPTORIUM · TRÍCH XUẤT VĂN BẢN",
            fill="#f0dfa8", font=("Segoe UI Variable Display", 21, "bold")
        )
        canvas.create_text(
            33, height * 0.68, anchor="w", text="Lắng nghe âm thanh, lưu lại lời nói thành văn bản",
            fill="#d0e8ed", font=("Segoe UI Variable Text", 12)
        )
        center_x, mid_y = width - 150, height * 0.51
        import math
        for index, amplitude in enumerate((11, 19, 29, 17, 35, 22, 13, 26, 17, 10)):
            x = center_x + index * 15
            pulse = 0.78 + 0.22 * math.sin(self._gradient_phase * 6.28 + index * 0.55)
            radius = amplitude * pulse
            canvas.create_line(x, mid_y - radius, x, mid_y + radius, fill="#a7e8e5", width=3, capstyle="round")

    def _animate_interface(self):
        self._gradient_phase = (self._gradient_phase + 0.008) % 1.0
        self._draw_arcana_banner(None)
        self._draw_transcribe_gradient()
        self.after(100, self._animate_interface)

    def select_video_file(self):
        """Mở hộp thoại chọn file Video/Audio."""
        file_path = filedialog.askopenfilename(
            filetypes=[("Media files", "*.mp4 *.mkv *.mp3 *.wav *.m4a *.flac *.webm")]
        )
        if file_path:
            self.selected_transcribe_path = file_path
            file_name = os.path.basename(file_path)
            self.file_info_label.configure(text=f"📁 Đã chọn: {file_name}", text_color="#5bc8d1")
            self.btn_start_transcribe.configure(
                state="normal" if self.discrete_gpu_available else "disabled",
                fg_color="#277d99" if self.discrete_gpu_available else "#263c52"
            )

    def trigger_transcription(self):
        """Kiểm tra và kích hoạt trích xuất văn bản."""
        if not self.discrete_gpu_available:
            messagebox.showinfo(
                "Cần GPU rời",
                "Tính năng trích xuất văn bản chỉ hoạt động khi máy có GPU NVIDIA hỗ trợ CUDA."
            )
            return
        if not self.selected_transcribe_path:
            messagebox.showwarning("Chú ý", "Việt chưa chọn file nào mà!")
            return

        if self.is_transcribing:
            messagebox.showwarning("Chú ý", "Đang có tiến trình trích xuất đang chạy!")
            return

        video_path = self.selected_transcribe_path
        ext = os.path.splitext(video_path)[1].lower()

        try:
            self.is_transcribing = True
            self.btn_start_transcribe.configure(state="disabled", fg_color="gray")

            # Kiểm tra thời lượng file
            duration = None
            try:
                from moviepy.video.io.VideoFileClip import VideoFileClip
                from moviepy.audio.io.AudioFileClip import AudioFileClip
                clip = AudioFileClip(video_path) if ext in ['.mp3', '.wav', '.m4a', '.flac'] else VideoFileClip(video_path)
                duration = clip.duration
                clip.close()
            except Exception:
                duration = None

            if duration and duration > 300:
                user_choice = [False]
                done_event = threading.Event()

                def ask():
                    ans = messagebox.askyesno(
                        "Quá dài",
                        f"File này dài hơn 5 phút ({int(duration // 60)} phút {int(duration % 60)} giây).\n"
                        "Việc trích xuất AI có thể mất thời gian. Bạn có muốn tiếp tục không?"
                    )
                    user_choice[0] = ans
                    done_event.set()

                self.after(0, ask)
                done_event.wait()

                if not user_choice[0]:
                    self.is_transcribing = False
                    self.btn_start_transcribe.configure(state="normal", fg_color="#277d99")
                    return

            self.text_result.delete("0.0", "end")
            self.text_result.insert("0.0", "🤖 Đang khởi động bộ não AI... Vui lòng đợi...\n")
            selected_model = self.model_var.get()
            threading.Thread(
                target=self._run_whisper_worker,
                args=(video_path, selected_model),
                daemon=True
            ).start()

        except Exception as e:
            self.is_transcribing = False
            messagebox.showerror("Lỗi file", f"Không thể đọc file: {e}")
            self.btn_start_transcribe.configure(state="normal", fg_color="#277d99")

    def _run_whisper_worker(self, video_path, selected_model):
        try:
            # 1. Bắt đầu
            self.after(0, lambda: self._update_trans_ui(0.1, "Đang xử lý âm thanh...", "blue"))

            # 2. Nạp Model (Tối ưu: dùng lại model đã nạp nếu cùng tên)
            self.after(0, lambda: self._update_trans_ui(0.4, f"Đang nạp bộ não AI ({selected_model})...", "blue"))

            import whisper
            import torch

            if not torch.cuda.is_available():
                raise RuntimeError("Không tìm thấy GPU NVIDIA/CUDA. Nhận dạng văn bản không chạy trên CPU.")
            device = "cuda"
            use_fp16 = True

            if self.cached_whisper_model is not None and self.cached_model_name == selected_model:
                model = self.cached_whisper_model
            else:
                model = whisper.load_model(selected_model, device=device)
                self.cached_whisper_model = model
                self.cached_model_name = selected_model

            # 3. Trích xuất văn bản
            self.after(0, lambda: self._update_trans_ui(0.6, "Đang chuyển thành văn bản (AI đang suy nghĩ)...", "blue"))

            # Whisper nhận trực tiếp video/audio qua ffmpeg (đã có trong PATH)
            result = model.transcribe(video_path, fp16=use_fp16)

            full_text = ""
            for segment in result.get("segments", []):
                full_text += f"{segment['text'].strip()}\n"

            if not full_text.strip():
                full_text = result.get("text", "").strip()

            # 4. Hiển thị kết quả & Hoàn tất
            self.after(0, lambda: self._on_transcribe_done(full_text))

        except Exception as e:
            self.after(0, lambda: self._on_transcribe_error(str(e)))
        finally:
            self.is_transcribing = False

    def _update_trans_ui(self, progress_val, text, color):
        self.trans_progress.set(progress_val)
        self.trans_status.configure(text=text, text_color=color)

    def _on_transcribe_done(self, full_text):
        self.trans_progress.set(1.0)
        self.trans_status.configure(text="Xong rồi Bạn ơi!", text_color="#92e5ec")
        self.text_result.delete("0.0", "end")
        self.text_result.insert("0.0", full_text)
        self.btn_start_transcribe.configure(state="normal", fg_color="#277d99")
        self.show_transcribe_finish_dialog()

    def _on_transcribe_error(self, err_msg):
        self.trans_progress.set(0)
        self.trans_status.configure(text="Lỗi rồi!", text_color="red")
        self.btn_start_transcribe.configure(state="normal", fg_color="#277d99")
        messagebox.showerror("Lỗi", err_msg)

    def show_transcribe_finish_dialog(self):
        """Hộp thoại thông báo khi trích xuất xong."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Xử lý xong")
        dialog.geometry("350x150")
        dialog.attributes("-topmost", True)
        self.apply_icon_to_window(dialog)

        # Căn giữa
        x = self.winfo_x() + (self.winfo_width() // 2) - 175
        y = self.winfo_y() + (self.winfo_height() // 2) - 75
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            dialog,
            text="✨ Đã chuyển văn bản thành công!",
            font=("Segoe UI Variable Display", 15, "bold")
        ).pack(pady=20)

        ctk.CTkButton(
            dialog,
            text="Đóng",
            width=100,
            command=dialog.destroy
        ).pack(pady=10)

    def copy_transcribed_text(self):
        """Sao chép nội dung vào Clipboard."""
        content = self.text_result.get("0.0", "end").strip()
        if not content or content.startswith("🤖 Đang khởi động"):
            messagebox.showwarning("Thông báo", "Chưa có nội dung gì để sao chép!")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(content)
            self.update()
            messagebox.showinfo("Thành công", "Đã sao chép vào Clipboard!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể sao chép: {e}")

    def clear_transcribed_text(self):
        """Xóa trắng ô kết quả."""
        self.text_result.delete("0.0", "end")
        self.trans_progress.set(0)
        self.trans_status.configure(text="Sẵn sàng phục vụ Việt!", text_color="gray")

    def export_to_txt(self):
        """Xuất file .txt."""
        content = self.text_result.get("0.0", "end").strip()
        if not content or content.startswith("🤖 Đang khởi động"):
            messagebox.showwarning("Thông báo", "Chưa có nội dung gì để xuất cả!")
            return

        initial_name = "trich_xuat_van_ban.txt"
        if self.selected_transcribe_path:
            base = os.path.splitext(os.path.basename(self.selected_transcribe_path))[0]
            initial_name = f"{base}.txt"

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile=initial_name
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("Thành công", f"Đã lưu file tại:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể lưu file: {e}")
