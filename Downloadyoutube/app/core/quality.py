"""Quality selection policy shared by the UI and download service."""

import re


VIDEO_QUALITIES = (
    "Best (tối đa 1080p)",
    "4K (2160p)",
    "2K (1440p)",
    "Full HD (1080p)",
    "HD (720p)",
    "SD (480p)",
    "SD (360p)",
)

AUDIO_QUALITIES = (
    "320 kbps (Tốt nhất)",
    "256 kbps",
    "192 kbps (Chuẩn)",
    "128 kbps",
)


def parse_video_quality(quality):
    """Return `best` or the requested maximum vertical resolution."""
    if not quality:
        return "best"
    value = str(quality).strip()
    if "best" in value.lower() or "gốc" in value.lower():
        return "best"
    match = re.search(r"(\d{3,4})", value)
    return int(match.group(1)) if match else "best"


def parse_audio_quality(quality):
    if not quality:
        return "320"
    match = re.search(r"(\d{2,3})", str(quality))
    return match.group(1) if match else "320"
