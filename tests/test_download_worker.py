import os

from app.download_worker import cleanup_partials, pick_final_path


def test_pick_final_path_returns_last_existing(tmp_path):
    gone = tmp_path / "video.f137.mp4"
    merged = tmp_path / "video.mp4"
    merged.write_text("")

    assert pick_final_path([str(gone), str(merged)]) == str(merged)


def test_pick_final_path_prefers_later_entries(tmp_path):
    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    first.write_text("")
    second.write_text("")

    assert pick_final_path([str(first), str(second)]) == str(second)


def test_pick_final_path_returns_none_when_nothing_exists(tmp_path):
    assert pick_final_path([str(tmp_path / "nope.mp4")]) is None


def test_pick_final_path_handles_empty_list():
    assert pick_final_path([]) is None


def test_cleanup_removes_partials_and_originals(tmp_path):
    target = tmp_path / "video.mp4"
    target.write_text("")
    part = tmp_path / "video.mp4.part"
    part.write_text("")
    ytdl = tmp_path / "video.mp4.ytdl"
    ytdl.write_text("")
    keep = tmp_path / "다른파일.mp4"
    keep.write_text("")

    cleanup_partials([str(target)])

    assert not target.exists()
    assert not part.exists()
    assert not ytdl.exists()
    assert keep.exists(), "훅이 알려준 경로 밖의 파일은 건드리면 안 된다"


def test_cleanup_ignores_missing_files(tmp_path):
    survivor = tmp_path / "무관한파일.mp4"
    survivor.write_text("")

    cleanup_partials([str(tmp_path / "없음.mp4")])

    assert survivor.exists()
    assert list(tmp_path.iterdir()) == [survivor]
