import os

from app.download_worker import DownloadWorker, cleanup_partials, pick_final_path


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


def test_cleanup_removes_fragmented_part_files(tmp_path):
    """DASH/HLS 조각 다운로드는 `video.mp4.part-Frag2.part` 같은 이름을 남긴다.

    실제 취소 종단 테스트(Task 8)에서 이런 조각 파일이 지워지지 않고
    남는 것을 확인했다. cleanup_partials가 이 패턴도 지워야 한다.
    """
    target = tmp_path / "video.f135.mp4"
    part = tmp_path / "video.f135.mp4.part"
    part.write_text("")
    frag = tmp_path / "video.f135.mp4.part-Frag2.part"
    frag.write_text("")
    keep = tmp_path / "다른파일.mp4"
    keep.write_text("")

    cleanup_partials([str(target)])

    assert not part.exists()
    assert not frag.exists()
    assert keep.exists(), "훅이 알려준 경로 밖의 파일은 건드리면 안 된다"


def test_cleanup_retries_when_file_briefly_locked(tmp_path, monkeypatch):
    """윈도우에서는 다운로더 스레드가 핸들을 늦게 놓아 첫 삭제 시도가 실패할 수 있다.

    Task 8 실제 취소 테스트에서 .part 파일이 지워지지 않고 남는 것을 확인했다.
    바로 실패해도 포기하지 말고 잠깐 대기한 뒤 재시도해야 한다.
    """
    target = tmp_path / "video.mp4"
    part = tmp_path / "video.mp4.part"
    part.write_text("")

    real_remove = os.remove
    calls = {"count": 0}

    def flaky_remove(path):
        calls["count"] += 1
        if calls["count"] < 3:
            raise PermissionError("locked")
        real_remove(path)

    monkeypatch.setattr("app.download_worker.os.remove", flaky_remove)
    monkeypatch.setattr("app.download_worker.time.sleep", lambda seconds: None)

    cleanup_partials([str(target)])

    assert not part.exists()
    assert calls["count"] == 3


def test_cleanup_gives_up_after_max_attempts_without_raising(tmp_path, monkeypatch):
    part = tmp_path / "video.mp4.part"
    part.write_text("")

    monkeypatch.setattr(
        "app.download_worker.os.remove",
        lambda path: (_ for _ in ()).throw(PermissionError("locked")),
    )
    monkeypatch.setattr("app.download_worker.time.sleep", lambda seconds: None)

    cleanup_partials([str(tmp_path / "video.mp4")])

    assert part.exists(), "포기한 뒤에도 파일은 남아있어야 하고 예외는 밖으로 나오면 안 된다"


def test_cleanup_ignores_missing_files(tmp_path):
    survivor = tmp_path / "무관한파일.mp4"
    survivor.write_text("")

    cleanup_partials([str(tmp_path / "없음.mp4")])

    assert survivor.exists()
    assert list(tmp_path.iterdir()) == [survivor]


def test_downloading_hook_records_filename_for_cleanup():
    worker = DownloadWorker(
        url="https://example.com/v",
        out_dir="C:\\tmp",
        filename="",
        quality="1080p",
        ffmpeg_path="C:\\ffmpeg.exe",
    )

    worker._on_progress(
        {
            "status": "downloading",
            "filename": "C:\\tmp\\video.f137.mp4",
            "downloaded_bytes": 10,
            "total_bytes": 100,
        }
    )

    assert "C:\\tmp\\video.f137.mp4" in worker._seen_paths
