import os
import sys
import shutil
import subprocess
import re
import yt_dlp
from utils import get_ffmpeg_path
from app.core.quality import parse_audio_quality, parse_video_quality

class VideoDownloader:
    def __init__(self, progress_hook=None):
        self.progress_hook = progress_hook

    def _get_ydl_opts(self, save_path, quality, only_audio=False, ffmpeg_path=None):
        outtmpl = os.path.join(save_path, '%(title)s.%(ext)s')
        opts = {
            'outtmpl': outtmpl,
            'nocolor': True,
            'quiet': True,
            'no_warnings': True,
            'retries': 5,
            'fragment_retries': 5,
            'windowsfilenames': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android']
                }
            }
        }
        if self.progress_hook:
            opts['progress_hooks'] = [self.progress_hook]

        if ffmpeg_path:
            opts['ffmpeg_location'] = ffmpeg_path

        if only_audio:
            preferred_q = parse_audio_quality(quality)
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': preferred_q,
                }],
            })
        else:
            target_h = parse_video_quality(quality)
            if target_h == "best":
                # Best means up to Full HD; do not silently select 2K/4K.
                format_str = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
            else:
                # Keep the requested cap and never upscale a lower-resolution source.
                format_str = f'bestvideo[height<={target_h}]+bestaudio/best[height<={target_h}]'

            opts.update({
                'format': format_str,
                'merge_output_format': 'mp4',
            })
        return opts

    def get_video_specs(self, file_path, ffmpeg_path=None):
        """
        Lấy thông tin (width, height, duration) của video file bằng FFmpeg.
        """
        if not ffmpeg_path:
            ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg_path or not os.path.isfile(file_path):
            return None, None, None

        cmd = [ffmpeg_path, "-i", file_path]
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                errors="ignore",
                creationflags=creationflags
            )
            out = res.stderr
            m_res = re.search(r'Video:.*?\b(\d{2,5})x(\d{2,5})\b', out)
            m_dur = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', out)

            w, h = (int(m_res.group(1)), int(m_res.group(2))) if m_res else (None, None)
            dur = None
            if m_dur:
                dur = int(m_dur.group(1)) * 3600 + int(m_dur.group(2)) * 60 + float(m_dur.group(3))

            return w, h, dur
        except Exception:
            return None, None, None

    def scale_video(self, file_path, target_height, ffmpeg_path=None, status_callback=None):
        """
        Scale video lên target_height (ví dụ 1440 cho 2K, 2160 cho 4K, 4320 cho 8K).
        Đảm bảo giữ đúng tỉ lệ khung hình (aspect ratio) và âm thanh gốc không suy hao.
        """
        if not ffmpeg_path:
            ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg_path or not os.path.isfile(file_path):
            return False, "Không tìm thấy FFmpeg hoặc file video để scale."

        in_w, in_h, duration_sec = self.get_video_specs(file_path, ffmpeg_path)
        if not in_w or not in_h:
            return False, "Không thể đọc độ phân giải video để tiến hành scale."

        shorter_side = min(in_w, in_h)
        if shorter_side >= target_height:
            # Video đã có độ phân giải >= target_height, không cần scale
            return True, file_path

        # Xác định filter giữ tỉ lệ khung hình
        if in_w >= in_h:
            # Video ngang / vuông: cố định chiều cao là target_height, chiều rộng tự tính chẵn
            scale_filter = f"scale=-2:{target_height}:flags=lanczos"
        else:
            # Video dọc (Shorts): cố định chiều rộng là target_height, chiều cao tự tính chẵn
            scale_filter = f"scale={target_height}:-2:flags=lanczos"

        # Cấu hình encoder tối ưu: crf 18 gần như không suy hao chất lượng
        if target_height >= 4320:
            v_codec_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
        else:
            v_codec_args = ["-c:v", "libx264", "-preset", "fast", "-crf", "18"]

        dir_name = os.path.dirname(file_path)
        base_name, ext = os.path.splitext(file_path)
        temp_output = os.path.join(dir_name, f"temp_scale_{os.getpid()}{ext}")
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except Exception:
                pass

        cmd = [
            ffmpeg_path,
            "-y",
            "-loglevel", "error",
            "-i", file_path,
            "-vf", scale_filter,
            *v_codec_args,
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-nostats",
            temp_output
        ]

        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                creationflags=creationflags
            )

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k == "out_time_us":
                        try:
                            cur_sec = int(v) / 1_000_000
                            if duration_sec and duration_sec > 0:
                                pct = min(1.0, cur_sec / duration_sec)
                                if status_callback:
                                    status_callback(pct, cur_sec, duration_sec)
                        except Exception:
                            pass
                    elif k == "progress" and v == "end":
                        break

            process.wait()

            if process.returncode != 0:
                err_msg = process.stderr.read()
                if os.path.exists(temp_output):
                    try:
                        os.remove(temp_output)
                    except Exception:
                        pass
                return False, f"Lỗi FFmpeg khi scale: {err_msg[:200]}"

            # Thay thế file cũ bằng file đã scale
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                shutil.move(temp_output, file_path)
                return True, file_path
            except Exception as e:
                if os.path.exists(temp_output):
                    return True, temp_output
                return False, f"Không thể lưu file sau khi scale: {e}"

        except Exception as e:
            if os.path.exists(temp_output):
                try:
                    os.remove(temp_output)
                except Exception:
                    pass
            return False, f"Lỗi trong quá trình scale video: {e}"

    def get_info(self, url, save_path, quality, only_audio=False):
        """
        Lấy metadata và dự đoán đường dẫn file chính xác trước khi tải.
        Giúp kiểm tra file trùng lặp mà không cần tải lại 2 lần.
        """
        ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg_path:
            return {"status": "error", "message": "Không tìm thấy FFmpeg trên hệ thống!"}

        opts = self._get_ydl_opts(save_path, quality, only_audio, ffmpeg_path)
        opts_for_info = dict(opts)
        opts_for_info['progress_hooks'] = []

        try:
            with yt_dlp.YoutubeDL(opts_for_info) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return {"status": "error", "message": "Không thể lấy thông tin video từ đường link này!"}
                
                raw_filename = ydl.prepare_filename(info)
                base = os.path.splitext(raw_filename)[0]
                final_ext = ".mp3" if only_audio else ".mp4"
                final_path = base + final_ext
                
                return {
                    "status": "success",
                    "info": info,
                    "title": info.get("title", "Video"),
                    "final_path": final_path,
                    "exists": os.path.exists(final_path)
                }
        except yt_dlp.utils.DownloadError as e:
            err_msg = str(e)
            if "Video unavailable" in err_msg:
                return {"status": "error", "message": "Video không khả dụng hoặc đã bị gỡ bỏ!"}
            elif "Private video" in err_msg:
                return {"status": "error", "message": "Đây là video riêng tư, không có quyền truy cập!"}
            return {"status": "error", "message": f"Lỗi tải thông tin: {err_msg}"}
        except Exception as e:
            return {"status": "error", "message": f"Lỗi kết nối: {e}"}

    def download(self, url, save_path, quality, only_audio=False, pre_info=None, auto_scale=True, scale_callback=None):
        ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg_path:
            return {"status": "error", "message": "Không tìm thấy FFmpeg!"}

        opts = self._get_ydl_opts(save_path, quality, only_audio, ffmpeg_path)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                if pre_info:
                    ydl.process_ie_result(pre_info, download=True)
                    info = pre_info
                else:
                    info = ydl.extract_info(url, download=True)

                filename = ydl.prepare_filename(info)
                base = os.path.splitext(filename)[0]
                final_path = f"{base}.mp3" if only_audio else f"{base}.mp4"
                if not os.path.exists(final_path) and os.path.exists(filename):
                    final_path = filename

                return {"status": "success", "path": final_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}
