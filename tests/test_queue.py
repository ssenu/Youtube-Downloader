import pytest

from app.queue import DownloadQueue, JobStatus


def make_queue_with(n: int) -> DownloadQueue:
    q = DownloadQueue()
    for i in range(n):
        q.add(f"https://youtu.be/v{i}", r"C:\out", "", "1080p")
    return q


def test_add_assigns_increasing_ids_and_keeps_order():
    q = make_queue_with(3)
    ids = [j.id for j in q.jobs()]
    assert ids == [1, 2, 3]
    assert all(j.status is JobStatus.PENDING for j in q.jobs())


def test_display_title_prefers_title_then_filename_then_url():
    q = DownloadQueue()
    named = q.add("https://youtu.be/a", r"C:\out", "강의 1주차", "720p")
    blank = q.add("https://youtu.be/b", r"C:\out", "", "720p")
    assert named.display_title == "강의 1주차"
    assert blank.display_title == "https://youtu.be/b"
    q.set_title(blank.id, "웹프로그래밍(09/03)")
    assert blank.display_title == "웹프로그래밍(09/03)"


def test_next_pending_is_oldest_pending():
    q = make_queue_with(3)
    q.mark_running(1)
    assert q.running().id == 1
    assert q.next_pending().id == 2


def test_only_one_running_at_a_time():
    q = make_queue_with(2)
    q.mark_running(1)
    with pytest.raises(ValueError):
        q.mark_running(2)


def test_transitions_from_running():
    q = make_queue_with(3)
    q.mark_running(1)
    q.mark_done(1, r"C:\out\a.mp4")
    assert q.get(1).status is JobStatus.DONE
    assert q.get(1).result_path == r"C:\out\a.mp4"
    assert q.get(1).progress == 100

    q.mark_running(2)
    q.mark_failed(2, "비공개 영상입니다.")
    assert q.get(2).status is JobStatus.FAILED
    assert q.get(2).error == "비공개 영상입니다."

    q.mark_running(3)
    q.mark_cancelled(3)
    assert q.get(3).status is JobStatus.CANCELLED
    assert q.running() is None
    assert q.next_pending() is None


def test_invalid_transitions_raise():
    q = make_queue_with(1)
    with pytest.raises(ValueError):
        q.mark_done(1, "x")          # PENDING -> DONE 불가
    q.mark_running(1)
    q.mark_done(1, "x")
    with pytest.raises(ValueError):
        q.mark_running(1)            # DONE -> RUNNING 불가
    with pytest.raises(ValueError):
        q.mark_cancelled(1)          # DONE -> CANCELLED 불가


def test_remove_pending_and_finished_but_not_running():
    q = make_queue_with(3)
    q.remove(3)
    assert [j.id for j in q.jobs()] == [1, 2]
    q.mark_running(1)
    with pytest.raises(ValueError):
        q.remove(1)
    q.mark_done(1, "x")
    q.remove(1)
    assert [j.id for j in q.jobs()] == [2]


def test_unknown_id_raises_key_error():
    q = make_queue_with(1)
    assert q.get(99) is None
    with pytest.raises(KeyError):
        q.mark_running(99)


def test_progress_is_clamped():
    q = make_queue_with(1)
    q.mark_running(1)
    q.set_progress(1, 150)
    assert q.get(1).progress == 100
    q.set_progress(1, -5)
    assert q.get(1).progress == 0


def test_summary_hides_zero_failed_and_cancelled():
    q = make_queue_with(4)
    q.mark_running(1)
    assert q.summary() == "대기 3 · 추출 중 1 · 완료 0"
    q.mark_done(1, "x")
    q.mark_running(2)
    q.mark_failed(2, "e")
    q.mark_running(3)
    q.mark_cancelled(3)
    assert q.summary() == "대기 1 · 추출 중 0 · 완료 1 · 실패 1 · 취소 1"


def test_is_finished():
    q = make_queue_with(2)
    assert q.get(1).is_finished is False
    q.mark_running(1)
    assert q.get(1).is_finished is False
    q.mark_done(1, "x")
    assert q.get(1).is_finished is True
