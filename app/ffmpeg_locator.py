"""ffmpeg 실행 파일 경로 탐색. Qt 의존성 없음."""

from __future__ import annotations

import os
import shutil
import sys


class FFmpegNotFoundError(RuntimeError):
    """ffmpeg 실행 파일을 찾지 못했을 때 발생한다."""


def locate_ffmpeg() -> str:
    """ffmpeg 실행 파일의 절대 경로를 반환한다.

    탐색 순서: PyInstaller 번들 → imageio-ffmpeg → 시스템 PATH.
    """
    if getattr(sys, "frozen", False):
        bundled = os.path.join(getattr(sys, "_MEIPASS", ""), "ffmpeg.exe")
        if os.path.isfile(bundled):
            return bundled

    try:
        import imageio_ffmpeg

        path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.isfile(path):
            return path
    except Exception:
        pass

    found = shutil.which("ffmpeg")
    if found:
        return found

    raise FFmpegNotFoundError(
        "ffmpeg을 찾을 수 없습니다.\n\n"
        "pip install imageio-ffmpeg 로 설치하거나 "
        "시스템 PATH에 ffmpeg을 추가해 주세요."
    )
