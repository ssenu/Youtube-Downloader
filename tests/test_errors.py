from app.errors import friendly_error


def test_private_video():
    message = friendly_error(Exception("ERROR: Private video. Sign in if you've been granted access"))
    assert "비공개" in message


def test_unavailable_video():
    assert "이용할 수 없" in friendly_error(Exception("ERROR: Video unavailable"))


def test_geo_blocked():
    message = friendly_error(Exception("The uploader has not made this video available in your country"))
    assert "지역" in message


def test_network_failure():
    message = friendly_error(Exception("<urlopen error [Errno 11001] getaddrinfo failed>"))
    assert "네트워크" in message


def test_unsupported_url():
    assert "지원하지 않" in friendly_error(Exception("ERROR: Unsupported URL: https://example.com"))


def test_unknown_error_keeps_original_text():
    original = "something completely unexpected happened"
    message = friendly_error(Exception(original))
    assert original in message
    assert "실패" in message


def test_bot_check_is_not_reported_as_login():
    message = friendly_error(Exception("ERROR: [youtube] abc: Sign in to confirm you're not a bot. Use --cookies-from-browser"))
    assert "잠시 후" in message
    assert "로그인" not in message


def test_age_restricted():
    assert "연령" in friendly_error(Exception("Sign in to confirm your age"))


def test_ffmpeg_failure():
    assert "ffmpeg" in friendly_error(Exception("ERROR: ffmpeg exited with code 1"))
