"""추출 시작 전 입력값 검증. Qt 의존성 없음.

모든 함수는 문제가 있으면 사용자에게 보여줄 한국어 문구를,
문제가 없으면 None을 반환한다.
"""

from __future__ import annotations

import os


def validate_url(url: str) -> str | None:
    stripped = (url or "").strip()

    if not stripped:
        return "URL을 입력해 주세요."

    if not stripped.startswith(("http://", "https://")):
        return "http:// 또는 https:// 로 시작하는 주소를 입력해 주세요."

    return None


def validate_out_dir(path: str) -> str | None:
    stripped = (path or "").strip()

    if not stripped:
        return "저장 위치를 선택해 주세요."

    if not os.path.isdir(stripped):
        return f"저장 위치를 찾을 수 없습니다.\n\n{stripped}"

    if not os.access(stripped, os.W_OK):
        return f"저장 위치에 쓸 수 없습니다. 다른 폴더를 선택해 주세요.\n\n{stripped}"

    return None
