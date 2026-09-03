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
