import yt_dlp
import os
import shutil

class VideoDownloader:
    def __init__(self, progress_hook):
        self.progress_hook = progress_hook

    def download(self, url, save_path, quality, only_audio=False):
        ffmpeg_ext = ".exe" if os.name == 'nt' else ""
        local_ffmpeg = os.path.join(os.getcwd(), f"ffmpeg{ffmpeg_ext}")
        ffmpeg_path = local_ffmpeg if os.path.exists(local_ffmpeg) else shutil.which("ffmpeg")

        if not ffmpeg_path:
            return {"status": "error", "message": "Không tìm thấy FFmpeg!"}

        # Cấu hình cơ bản
        ydl_opts = {
            'outtmpl': f'{save_path}/%(title)s.%(ext)s',
            'progress_hooks': [self.progress_hook],
            'nocolor': True,
            'quiet': True,
            'no_warnings': False,
            'ffmpeg_location': ffmpeg_path,
        }

        # --- CHIA LOGIC TẢI Ở ĐÂY ---
        if only_audio:
            # Cấu hình chuyên dụng để tải MP3
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            # Cấu hình tải Video MP4 như cũ
            ydl_opts.update({
                'format': f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Xử lý hậu kỳ để lấy đúng đuôi file trả về cho GUI
                base = os.path.splitext(filename)[0]
                final_path = f"{base}.mp3" if only_audio else f"{base}.mp4"
                
                return {"status": "success", "path": final_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}