"""번들/개발 환경 양쪽에서 assets 파일 경로를 찾는다. Qt 의존성 없음."""
from __future__ import annotations
import os
import sys


def resource_path(name: str) -> str:
    """assets/<name>의 절대 경로. exe로 빌드된 상태면 _MEIPASS 아래에서 찾는다."""
    if getattr(sys, "frozen", False):
        base = os.path.join(getattr(sys, "_MEIPASS", ""), "assets")
    else:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    return os.path.join(base, name)
