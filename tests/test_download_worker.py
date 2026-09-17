import os

import pytest

from app.download_worker import (
    CancelledError,
    DownloadWorker,
    cleanup_partials,
    pick_final_path,
)


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


def test_probe_title_emits_title_resolved(monkeypatch):
    import yt_dlp

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            assert download is False
            return {"title": "웹프로그래밍(09/03)"}

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)

    worker = DownloadWorker(
        url="https://example.com/v",
        out_dir="C:\\tmp",
        filename="",
        quality="1080p",
        ffmpeg_path="C:\\ffmpeg.exe",
    )
    got: list[str] = []
    worker.title_resolved.connect(got.append)

    assert worker._probe_title() == "웹프로그래밍(09/03)"
    assert got == ["웹프로그래밍(09/03)"]


def test_probe_title_returns_empty_and_does_not_emit_without_title(monkeypatch):
    import yt_dlp

    class FakeYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            return {}

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)

    worker = DownloadWorker(
        url="https://example.com/v",
        out_dir="C:\\tmp",
        filename="",
        quality="1080p",
        ffmpeg_path="C:\\ffmpeg.exe",
    )
    got: list[str] = []
    worker.title_resolved.connect(got.append)

    assert worker._probe_title() == ""
    assert got == []


def _make_worker(quality: str, out_dir: str = "C:\\tmp") -> DownloadWorker:
    return DownloadWorker(
        url="https://example.com/v",
        out_dir=out_dir,
        filename="강의",
        quality=quality,
        ffmpeg_path="C:\\ffmpeg.exe",
    )


def _pp_event(status: str, postprocessor: str, path: str) -> dict:
    return {
        "status": status,
        "postprocessor": postprocessor,
        "info_dict": {"filepath": path},
    }


def test_audio_mode_download_status_is_audio_only():
    worker = _make_worker("MP3 192kbps")
    got: list[str] = []
    worker.status.connect(got.append)

    worker._on_progress(
        {
            "status": "downloading",
            "filename": "C:\\tmp\\강의.webm",
            "downloaded_bytes": 10,
            "total_bytes": 100,
        }
    )

    assert got == ["음성 다운로드 중…"]


def test_video_mode_first_stream_status_is_unchanged():
    worker = _make_worker("1080p")
    got: list[str] = []
    worker.status.connect(got.append)

    worker._on_progress(
        {
            "status": "downloading",
            "filename": "C:\\tmp\\강의.f137.mp4",
            "downloaded_bytes": 10,
            "total_bytes": 100,
        }
    )

    assert got == ["영상 다운로드 중…"]


@pytest.mark.parametrize(
    "quality, postprocessor, expected",
    [
        ("MP3 192kbps", "ExtractAudio", "MP3 변환 중…"),
        ("MP3 192kbps", "Metadata", "MP3 변환 중…"),
        ("1080p", "Merger", "병합 중…"),
    ],
)
def test_postprocessor_status_depends_on_mode(quality, postprocessor, expected):
    worker = _make_worker(quality)
    got: list[str] = []
    worker.status.connect(got.append)

    worker._on_postprocessor(_pp_event("started", postprocessor, "C:\\tmp\\강의.webm"))

    assert got == [expected]


def test_cancel_right_after_audio_conversion_records_mp3_for_cleanup():
    """ExtractAudio finished 훅은 .webm 경로만 준다. .mp3도 정리 대상에 들어가야 한다."""
    worker = _make_worker("MP3 192kbps")
    worker.cancel()

    with pytest.raises(CancelledError):
        worker._on_postprocessor(
            _pp_event("finished", "ExtractAudio", "C:\\tmp\\강의.webm")
        )

    assert "C:\\tmp\\강의.webm" in worker._seen_paths
    assert "C:\\tmp\\강의.mp3" in worker._seen_paths


def test_cancel_at_merge_still_records_merged_path():
    worker = _make_worker("1080p")
    worker.cancel()

    with pytest.raises(CancelledError):
        worker._on_postprocessor(_pp_event("finished", "Merger", "C:\\tmp\\강의.mp4"))

    assert worker._seen_paths == ["C:\\tmp\\강의.mp4"]


def test_video_mode_does_not_guess_mp3_path():
    worker = _make_worker("1080p")

    worker._on_postprocessor(_pp_event("started", "ExtractAudio", "C:\\tmp\\강의.webm"))

    assert worker._seen_paths == ["C:\\tmp\\강의.webm"]


def test_audio_hook_sequence_leads_pick_final_path_to_mp3(tmp_path):
    webm = str(tmp_path / "강의.webm")  # 변환 후 yt-dlp가 지운 상태
    mp3 = tmp_path / "강의.mp3"
    mp3.write_bytes(b"")
    worker = _make_worker("MP3 192kbps", out_dir=str(tmp_path))

    for status, postprocessor, path in [
        ("started", "ExtractAudio", webm),
        ("finished", "ExtractAudio", webm),
        ("started", "Metadata", str(mp3)),
        ("finished", "Metadata", str(mp3)),
    ]:
        worker._on_postprocessor(_pp_event(status, postprocessor, path))

    assert pick_final_path(worker._seen_paths) == str(mp3)
