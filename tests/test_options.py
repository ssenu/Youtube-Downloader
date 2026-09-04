import os

import pytest

from app.options import (
    DEFAULT_QUALITY,
    QUALITY_FORMATS,
    TITLE_TEMPLATE,
    build_format_string,
    build_ydl_opts,
    resolve_collision,
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


def test_resolve_collision_returns_stem_when_free(tmp_path):
    assert resolve_collision(str(tmp_path), "강의") == "강의"


def test_resolve_collision_appends_counter(tmp_path):
    (tmp_path / "강의.mp4").write_text("")
    assert resolve_collision(str(tmp_path), "강의") == "강의 (1)"

    (tmp_path / "강의 (1).mkv").write_text("")
    assert resolve_collision(str(tmp_path), "강의") == "강의 (2)"


def test_resolve_collision_ignores_extension(tmp_path):
    (tmp_path / "강의.webm").write_text("")
    assert resolve_collision(str(tmp_path), "강의") == "강의 (1)"


def test_resolve_collision_handles_glob_metacharacters(tmp_path):
    (tmp_path / "[LIVE] 강의.mp4").write_text("")
    assert resolve_collision(str(tmp_path), "[LIVE] 강의") == "[LIVE] 강의 (1)"


def test_build_opts_uses_given_filename(tmp_path):
    opts = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="웹프로그래밍(09/03)",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert opts["outtmpl"] == os.path.join(str(tmp_path), "웹프로그래밍(0903).%(ext)s")


def test_build_opts_falls_back_to_title_template(tmp_path):
    opts = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert opts["outtmpl"] == os.path.join(str(tmp_path), TITLE_TEMPLATE)


def test_build_opts_falls_back_when_sanitizing_empties_the_name(tmp_path):
    opts = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="///",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert opts["outtmpl"] == os.path.join(str(tmp_path), TITLE_TEMPLATE)


def test_build_opts_fixed_options(tmp_path):
    opts = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="a",
        quality="480p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert opts["merge_output_format"] == "mp4"
    assert opts["ffmpeg_location"] == r"C:\ffmpeg.exe"
    assert opts["noplaylist"] is True
    assert opts["format"] == QUALITY_FORMATS["480p"]


def test_build_opts_registers_hooks_only_when_given(tmp_path):
    def hook(d):
        return None

    with_hooks = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="a",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
        progress_hook=hook,
        postprocessor_hook=hook,
    )
    assert with_hooks["progress_hooks"] == [hook]
    assert with_hooks["postprocessor_hooks"] == [hook]

    without = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="a",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert "progress_hooks" not in without
    assert "postprocessor_hooks" not in without


def test_build_opts_registers_match_filter_only_when_given(tmp_path):
    def hook(info, *, incomplete=False):
        return None

    with_filter = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="a",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
        match_filter=hook,
    )
    assert with_filter["match_filter"] is hook

    without = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="a",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert "match_filter" not in without


def test_build_opts_escapes_percent_in_filename(tmp_path):
    opts = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="할인 50% 강의",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert opts["outtmpl"] == os.path.join(str(tmp_path), "할인 50%% 강의.%(ext)s")
