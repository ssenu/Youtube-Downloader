"""yt-dlp 예외를 사용자용 한국어 문구로 바꾼다. Qt 의존성 없음."""

from __future__ import annotations

# (검사할 키워드 묶음, 보여줄 문구) 순서대로 검사한다.
_RULES: list[tuple[tuple[str, ...], str]] = [
    (("private video",), "비공개 영상입니다. 다운로드할 수 없습니다."),
    (("video unavailable", "has been removed"), "삭제되었거나 이용할 수 없는 영상입니다."),
    # yt-dlp 실제 문구는 "has not made this video available in your country"라서
    # "not available in your country"로 검사하면 매칭되지 않는다.
    (("available in your country", "geo restrict", "geo-restrict"), "지역 차단된 영상입니다."),
    (("sign in to confirm your age", "age-restricted"), "연령 확인이 필요한 영상입니다."),
    (("sign in", "login required"), "로그인이 필요한 영상입니다."),
    (("unsupported url", "is not a valid url"), "지원하지 않는 URL입니다. 주소를 확인해 주세요."),
    (
        ("urlopen error", "getaddrinfo failed", "timed out", "connection reset"),
        "네트워크 연결에 문제가 있습니다. 연결을 확인한 뒤 다시 시도해 주세요.",
    ),
    (("ffmpeg",), "영상 병합에 실패했습니다. ffmpeg 설치 상태를 확인해 주세요."),
]


def friendly_error(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()

    for keywords, message in _RULES:
        if any(keyword in lowered for keyword in keywords):
            return message

    return f"다운로드에 실패했습니다.\n\n{text}"
