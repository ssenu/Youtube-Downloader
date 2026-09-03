"""UI 입력을 yt-dlp 옵션으로 변환한다. Qt 의존성 없음."""

from __future__ import annotations

import re

FORBIDDEN_CHARS = '\\/:*?"<>|'

QUALITY_FORMATS: dict[str, str] = {
    "최고화질": "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b",
    "1080p": (
        "bv*[height<=1080][ext=mp4]+ba[ext=m4a]"
        "/bv*[height<=1080]+ba/b[height<=1080]"
    ),
    "720p": (
        "bv*[height<=720][ext=mp4]+ba[ext=m4a]"
        "/bv*[height<=720]+ba/b[height<=720]"
    ),
    "480p": (
        "bv*[height<=480][ext=mp4]+ba[ext=m4a]"
        "/bv*[height<=480]+ba/b[height<=480]"
    ),
}

DEFAULT_QUALITY = "1080p"
TITLE_TEMPLATE = "%(title)s.%(ext)s"

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_filename(name: str) -> str:
    """Windows에서 쓸 수 없는 문자를 제거한다.

    yt-dlp 기본값은 '/'를 '⧸'(U+29F8) 같은 유사 문자로 바꾸는데,
    일부 프로그램이 이를 제대로 다루지 못하므로 아예 제거한다.
    """
    cleaned = "".join(ch for ch in name if ch not in FORBIDDEN_CHARS)
    cleaned = _CONTROL_CHARS.sub("", cleaned)
    return cleaned.strip().strip(".").strip()


def build_format_string(quality: str) -> str:
    """화질 드롭다운 값을 yt-dlp format 문자열로 바꾼다."""
    try:
        return QUALITY_FORMATS[quality]
    except KeyError:
        raise ValueError(f"알 수 없는 화질입니다: {quality}") from None
