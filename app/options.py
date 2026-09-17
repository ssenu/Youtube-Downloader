"""UI 입력을 yt-dlp 옵션으로 변환한다. Qt 의존성 없음."""

from __future__ import annotations

import glob
import os
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

# MP3 항목. 값은 ffmpeg에 넘길 고정 비트레이트(kbps).
# YouTube 원본 음성은 대개 130~160kbps라 320kbps가 음질을 더 올려주지는 않는다.
AUDIO_BITRATES: dict[str, str] = {
    "MP3 320kbps": "320",
    "MP3 192kbps": "192",
    "MP3 128kbps": "128",
}
# 음성 전용 스트림을 우선 받고, 없으면 합본을 받아 음성만 뽑는다.
AUDIO_FORMAT = "ba/b"

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


def is_audio_quality(quality: str) -> bool:
    """드롭다운 값이 MP3 항목인지 판정한다."""
    return quality in AUDIO_BITRATES


def build_format_string(quality: str) -> str:
    """화질 드롭다운 값을 yt-dlp format 문자열로 바꾼다."""
    if is_audio_quality(quality):
        return AUDIO_FORMAT
    try:
        return QUALITY_FORMATS[quality]
    except KeyError:
        raise ValueError(f"알 수 없는 화질입니다: {quality}") from None


def resolve_collision(out_dir: str, stem: str) -> str:
    """`out_dir`에 `stem.*`이 이미 있으면 ' (1)', ' (2)'를 붙여 비어 있는 이름을 찾는다.

    다운로드가 끝나기 전에는 확장자를 알 수 없으므로 확장자를 뺀 이름으로 검사한다.
    """
    escaped_dir = glob.escape(out_dir)

    def taken(candidate: str) -> bool:
        pattern = os.path.join(escaped_dir, glob.escape(candidate) + ".*")
        return bool(glob.glob(pattern))

    if not taken(stem):
        return stem

    counter = 1
    while taken(f"{stem} ({counter})"):
        counter += 1
    return f"{stem} ({counter})"


def build_ydl_opts(
    out_dir: str,
    filename: str,
    quality: str,
    ffmpeg_path: str,
    progress_hook=None,
    postprocessor_hook=None,
    match_filter=None,
) -> dict:
    """UI 입력을 yt-dlp 옵션 딕셔너리로 만든다."""
    stem = sanitize_filename(filename or "")

    if stem:
        stem = resolve_collision(out_dir, stem)
        # yt-dlp는 outtmpl을 %-템플릿으로 해석하므로 사용자 파일명의 %는 %%로 이스케이프한다.
        outtmpl = os.path.join(out_dir, stem.replace("%", "%%") + ".%(ext)s")
    else:
        # 파일명을 비우면 영상 제목을 쓴다. 제목은 미리 알 수 없으므로
        # 충돌 검사를 건너뛰고 yt-dlp 기본 동작에 맡긴다.
        outtmpl = os.path.join(out_dir, TITLE_TEMPLATE)

    opts: dict = {
        "format": build_format_string(quality),
        "outtmpl": outtmpl,
        "ffmpeg_location": ffmpeg_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }

    if is_audio_quality(quality):
        # 받은 음성을 MP3로 바꾼 뒤 제목·아티스트(채널)·날짜 태그를 넣는다.
        # 챕터는 MP3 플레이어 대부분이 쓰지 않으므로 넣지 않는다.
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": AUDIO_BITRATES[quality],
            },
            {"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": False},
        ]
    else:
        opts["merge_output_format"] = "mp4"

    if progress_hook is not None:
        opts["progress_hooks"] = [progress_hook]
    if postprocessor_hook is not None:
        opts["postprocessor_hooks"] = [postprocessor_hook]
    if match_filter is not None:
        opts["match_filter"] = match_filter

    return opts
