from PyQt6.QtCore import QObject, pyqtSignal

from app.queue import JobStatus
from app.queue_controller import QueueController


class FakeWorker(QObject):
    """DownloadWorker와 같은 시그널/메서드만 가진 가짜. 아무것도 다운로드하지 않는다."""

    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    title_resolved = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    finished = pyqtSignal()

    instances: list["FakeWorker"] = []

    def __init__(self, url, out_dir, filename, quality, ffmpeg_path):
        super().__init__()
        self.url = url
        self.started = False
        self.cancel_calls = 0
        FakeWorker.instances.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancel_calls += 1

    def wait(self, *args):
        return True

    # 테스트 편의: 워커가 끝나는 과정을 흉내낸다
    def finish_ok(self, path):
        self.finished_ok.emit(path)
        self.finished.emit()

    def finish_cancelled(self):
        self.cancelled.emit()
        self.finished.emit()

    def finish_failed(self, message):
        self.failed.emit(message)
        self.finished.emit()


def make_controller():
    FakeWorker.instances.clear()
    c = QueueController(ffmpeg_path=r"C:\ffmpeg.exe")
    c.worker_factory = FakeWorker
    return c


def test_first_enqueue_starts_immediately_and_others_wait():
    c = make_controller()
    added, changed = [], []
    c.job_added.connect(added.append)
    c.job_changed.connect(changed.append)

    a = c.enqueue("https://youtu.be/a", r"C:\out", "", "1080p")
    b = c.enqueue("https://youtu.be/b", r"C:\out", "", "1080p")
    d = c.enqueue("https://youtu.be/c", r"C:\out", "", "1080p")

    assert added == [a, b, d]
    assert len(FakeWorker.instances) == 1 and FakeWorker.instances[0].started
    assert c.job(a).status is JobStatus.RUNNING
    assert c.job(b).status is JobStatus.PENDING
    assert c.job(d).status is JobStatus.PENDING
    assert c.is_busy()
    assert a in changed


def test_next_starts_only_after_thread_finished():
    c = make_controller()
    a = c.enqueue("https://youtu.be/a", r"C:\out", "", "1080p")
    b = c.enqueue("https://youtu.be/b", r"C:\out", "", "1080p")

    w1 = FakeWorker.instances[0]
    w1.finished_ok.emit(r"C:\out\a.mp4")          # 아직 스레드는 안 끝남
    assert c.job(a).status is JobStatus.DONE
    assert len(FakeWorker.instances) == 1          # 다음 작업 아직 시작 안 함

    w1.finished.emit()                              # 이제 스레드 종료
    assert len(FakeWorker.instances) == 2
    assert FakeWorker.instances[1].url == "https://youtu.be/b"
    assert c.job(b).status is JobStatus.RUNNING


def test_progress_and_title_update_job():
    c = make_controller()
    a = c.enqueue("https://youtu.be/a", r"C:\out", "", "1080p")
    w = FakeWorker.instances[0]
    changed = []
    c.job_changed.connect(changed.append)

    w.progress.emit(42)
    w.title_resolved.emit("웹프로그래밍(09/03)")

    assert c.job(a).progress == 42
    assert c.job(a).display_title == "웹프로그래밍(09/03)"
    assert changed.count(a) == 2


def test_cancel_running_calls_worker_cancel_and_continues_to_next():
    c = make_controller()
    a = c.enqueue("https://youtu.be/a", r"C:\out", "", "1080p")
    b = c.enqueue("https://youtu.be/b", r"C:\out", "", "1080p")
    w1 = FakeWorker.instances[0]

    c.cancel_or_remove(a)
    assert w1.cancel_calls == 1
    assert c.job(a).status is JobStatus.RUNNING     # 상태는 워커가 cancelled를 보낼 때 바뀐다

    w1.finish_cancelled()
    assert c.job(a).status is JobStatus.CANCELLED
    assert c.job(b).status is JobStatus.RUNNING


def test_remove_pending_never_starts_it():
    c = make_controller()
    a = c.enqueue("https://youtu.be/a", r"C:\out", "", "1080p")
    b = c.enqueue("https://youtu.be/b", r"C:\out", "", "1080p")
    removed = []
    c.job_removed.connect(removed.append)

    c.cancel_or_remove(b)
    assert removed == [b]
    assert [j.id for j in c.jobs()] == [a]

    FakeWorker.instances[0].finish_ok("x")
    assert len(FakeWorker.instances) == 1           # b는 시작되지 않았다
    assert not c.is_busy()


def test_failed_job_does_not_block_queue():
    c = make_controller()
    a = c.enqueue("https://youtu.be/a", r"C:\out", "", "1080p")
    b = c.enqueue("https://youtu.be/b", r"C:\out", "", "1080p")

    FakeWorker.instances[0].finish_failed("비공개 영상입니다.")
    assert c.job(a).status is JobStatus.FAILED
    assert c.job(a).error == "비공개 영상입니다."
    assert c.job(b).status is JobStatus.RUNNING


def test_idle_emitted_when_nothing_left():
    c = make_controller()
    idle_calls = []
    c.idle.connect(lambda: idle_calls.append(True))
    a = c.enqueue("https://youtu.be/a", r"C:\out", "", "1080p")
    FakeWorker.instances[0].finish_ok("x")
    assert idle_calls == [True]


def test_cancel_all_drops_pending_and_cancels_running():
    c = make_controller()
    a = c.enqueue("https://youtu.be/a", r"C:\out", "", "1080p")
    b = c.enqueue("https://youtu.be/b", r"C:\out", "", "1080p")
    d = c.enqueue("https://youtu.be/c", r"C:\out", "", "1080p")
    removed = []
    c.job_removed.connect(removed.append)

    c.cancel_all()
    assert sorted(removed) == [b, d]
    assert FakeWorker.instances[0].cancel_calls == 1
    assert c.is_busy()

    idle_calls = []
    c.idle.connect(lambda: idle_calls.append(True))
    FakeWorker.instances[0].finish_cancelled()
    assert not c.is_busy()
    assert idle_calls == [True]
    assert c.summary() == "대기 0 · 추출 중 0 · 완료 0 · 취소 1"


def test_summary_changed_fires_on_enqueue_and_terminal():
    c = make_controller()
    summaries = []
    c.summary_changed.connect(summaries.append)
    c.enqueue("https://youtu.be/a", r"C:\out", "", "1080p")
    assert summaries[-1] == "대기 0 · 추출 중 1 · 완료 0"
    FakeWorker.instances[0].finish_ok("x")
    assert summaries[-1] == "대기 0 · 추출 중 0 · 완료 1"
