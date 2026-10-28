import os
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets')]
if os.path.exists('ffmpeg.exe'):
    datas.append(('ffmpeg.exe', '.'))

binaries = []
hiddenimports = []

# Gom toan bo du lieu, module an cua CustomTkinter, Whisper, yt-dlp, tiktoken va moviepy
for pkg in ['customtkinter', 'whisper', 'yt_dlp', 'tiktoken', 'moviepy']:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# --- CẤU HÌNH DẠNG THƯ MỤC (ONEDIR - KHUYÊN DÙNG CHO APP CÓ AI/PYTORCH) ---
# Giúp ứng dụng khởi động tức thì, không bị lag giải nén file 1-2GB vào %TEMP%
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='YouTubePro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/download-file.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YouTubePro',
)
