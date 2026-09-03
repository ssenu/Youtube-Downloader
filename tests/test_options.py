import pytest

from app.options import (
    DEFAULT_QUALITY,
    QUALITY_FORMATS,
    build_format_string,
    sanitize_filename,
)


def test_removes_windows_forbidden_characters():
    assert sanitize_filename('웹프로그래밍(09/03)') == "웹프로그래밍(0903)"
    assert sanitize_filename('a\\b:c*d?e"f<g>h|i') == "abcdefghi"


def test_strips_surrounding_whitespace_and_dots():
    assert sanitize_filename("  강의노트.  ") == "강의노트"
    assert sanitize_filename("...") == ""


def test_removes_control_characters():
    assert sanitize_filename("강의\x00\x1f노트") == "강의노트"


def test_quality_options_are_exactly_four_in_order():
    assert list(QUALITY_FORMATS) == ["최고화질", "1080p", "720p", "480p"]
    assert DEFAULT_QUALITY == "1080p"


def test_every_format_string_prefers_mp4_first():
    for quality, fmt in QUALITY_FORMATS.items():
        assert fmt.split("/")[0].endswith("+ba[ext=m4a]"), quality


def test_build_format_string_returns_mapped_value():
    assert build_format_string("720p") == QUALITY_FORMATS["720p"]
    assert "height<=720" in build_format_string("720p")


def test_build_format_string_rejects_unknown_quality():
    with pytest.raises(ValueError):
        build_format_string("1440p")
