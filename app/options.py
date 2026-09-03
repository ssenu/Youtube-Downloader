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
) -> dict:
    """UI 입력을 yt-dlp 옵션 딕셔너리로 만든다."""
    stem = sanitize_filename(filename or "")

    if stem:
        stem = resolve_collision(out_dir, stem)
        outtmpl = os.path.join(out_dir, stem + ".%(ext)s")
    else:
        # 파일명을 비우면 영상 제목을 쓴다. 제목은 미리 알 수 없으므로
        # 충돌 검사를 건너뛰고 yt-dlp 기본 동작에 맡긴다.
        outtmpl = os.path.join(out_dir, TITLE_TEMPLATE)

    opts: dict = {
        "format": build_format_string(quality),
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }

    if progress_hook is not None:
        opts["progress_hooks"] = [progress_hook]
    if postprocessor_hook is not None:
        opts["postprocessor_hooks"] = [postprocessor_hook]

    return opts
