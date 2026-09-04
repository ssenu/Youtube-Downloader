# 추출 목록(순차 다운로드 큐) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `추출`을 누를 때마다 작업이 오른쪽 목록에 쌓이고, 앱이 한 번에 하나씩 순서대로 내려받으며 행마다 상태·진행률을 보여준다. 제목 옆에 `by ssenu`를 넣는다.

**Architecture:** 큐 상태 기계(`app/queue.py`)는 Qt 없는 순수 파이썬으로 두고 pytest로 검증한다. `QueueController(QObject)`가 그 큐를 들고 기존 `DownloadWorker`를 한 번에 하나만 띄운다. `QueuePanel(QWidget)`은 행 위젯을 그리기만 한다. `MainWindow`는 입력을 캡처해 컨트롤러에 넘기고 시그널로 패널을 갱신한다. `DownloadWorker`는 제목을 알리는 시그널 하나만 추가한다.

**Tech Stack:** Python 3.14, PyQt6 6.11, yt-dlp, pytest (Qt 위젯 테스트는 `QT_QPA_PLATFORM=offscreen`)

## Global Constraints

- 스펙: `docs/superpowers/specs/2026-09-04-download-queue-design.md`. 선행 스펙 6.4의 "추출 중 입력 비활성화 / 버튼 취소 전환 / 완료 QMessageBox"는 이 계획으로 **대체**된다.
- `app/queue.py`는 PyQt6를 import 하지 않는다.
- `추출 중`(RUNNING)은 동시에 최대 하나. 전이는 `PENDING → RUNNING → {DONE, FAILED, CANCELLED}`뿐이며, 허용되지 않는 전이는 `ValueError`.
- 상태 문구는 정확히 `대기 중`, `추출 중`, `완료`, `실패`, `취소됨`. 요약은 `대기 n · 추출 중 n · 완료 n`이고 실패/취소가 0이 아닐 때만 ` · 실패 n`, ` · 취소 n`을 덧붙인다.
- `추출` 버튼은 항상 `추출`이고, 다운로드 중에도 입력 위젯은 활성 상태다.
- 완료 팝업은 없다. 완료 행 더블클릭이 탐색기에서 파일을 선택한다.
- 워커 참조는 컨트롤러의 `self._worker`에 보관한다. 워커의 `QThread.finished`가 오기 전에는 다음 작업을 시작하지 않는다.
- `DownloadWorker`, `options`, `validation`, `errors`, `ffmpeg_locator`의 기존 계약은 유지한다(워커에 `title_resolved` 시그널 추가만).
- 헤드리스 스크립트가 의존하는 이름: `url_edit`, `name_edit`, `quality_box`, `dir_edit`, `browse_btn`, `action_btn`, `summary_label`, `queue_panel`, `_enqueue`, `_controller`.
- 모든 UI 문구와 커밋 메시지는 한국어.
- 새 색/폰트는 만들지 않는다. 기존 토큰(`#D03020`, `#6B6B70`, `#E4E4E7`, `#1A1A1B`, `#FFFFFF`, `#F6F6F7`)만 쓴다.

## 스펙 대비 변경 사항

1. **`Job.display_title` 속성 추가.** 스펙 4절의 "파일명이 있으면 파일명, 없으면 URL, 제목을 알아내면 제목" 규칙을 한 곳에서 계산하기 위해서다. `DownloadQueue.add()`가 `title`을 입력 파일명으로 초기화하고, 워커가 제목을 알려주면 덮어쓴다.
2. **`QueueController.job_added` 시그널 추가.** 스펙 5.2에는 `job_changed`만 있지만, 패널이 "새 행 추가"와 "기존 행 갱신"을 구분해야 하므로 분리한다.
3. **워커의 프로브를 `_probe_title()` 메서드로 뽑는다.** `run()` 안에 인라인이던 빈 파일명 제목 조회를 메서드로 빼야 `yt_dlp.YoutubeDL`을 가짜로 바꿔 시그널 발화를 테스트할 수 있다. 동작은 같다.
4. **창 폭은 900이 아니라 904.** 왼쪽 열 520(여백 포함) + 열 사이 24 + 오른쪽 360 = 904. 스펙의 900은 어림값이었고, 기존 왼쪽 열 치수를 그대로 유지하는 쪽을 택한다.
5. **`tests/conftest.py`에 `qapp` 픽스처 추가.** 패널 위젯 테스트는 `QApplication`이 필요하다. 세션 범위로 하나 만들고 `QT_QPA_PLATFORM=offscreen`을 강제한다. 기존 순수 테스트에는 영향이 없다.

---

### Task 1: 큐 상태 기계

**Files:**
- Create: `app/queue.py`
- Test: `tests/test_queue.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `app.queue.JobStatus(str, Enum)` — `PENDING="대기 중"`, `RUNNING="추출 중"`, `DONE="완료"`, `FAILED="실패"`, `CANCELLED="취소됨"`
  - `app.queue.Job` 데이터클래스 — 필드 `id, url, out_dir, filename, quality, status, progress, title, result_path, error`; 속성 `display_title -> str`, `is_finished -> bool`
  - `app.queue.DownloadQueue` — `add(url, out_dir, filename, quality) -> Job`, `get(job_id) -> Job | None`, `jobs() -> list[Job]`, `running() -> Job | None`, `next_pending() -> Job | None`, `mark_running(job_id)`, `set_progress(job_id, value)`, `set_title(job_id, title)`, `mark_done(job_id, path)`, `mark_failed(job_id, error)`, `mark_cancelled(job_id)`, `remove(job_id)`, `summary() -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_queue.py`:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_queue.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.queue'`

- [ ] **Step 3: 구현**

`app/queue.py`:

```python
"""추출 목록의 상태 기계. Qt 의존성 없음.

불변식:
- RUNNING은 동시에 최대 하나.
- 전이는 PENDING -> RUNNING -> {DONE, FAILED, CANCELLED} 뿐이며 되돌아가지 않는다.
- 허용되지 않는 전이는 ValueError, 없는 id는 KeyError.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "대기 중"
    RUNNING = "추출 중"
    DONE = "완료"
    FAILED = "실패"
    CANCELLED = "취소됨"


@dataclass
class Job:
    id: int
    url: str
    out_dir: str
    filename: str
    quality: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    title: str = ""
    result_path: str = ""
    error: str = ""

    @property
    def display_title(self) -> str:
        """행에 보여줄 이름. 알아낸 제목 > 입력 파일명 > URL."""
        return self.title or self.filename or self.url

    @property
    def is_finished(self) -> bool:
        return self.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED)


class DownloadQueue:
    def __init__(self) -> None:
        self._jobs: list[Job] = []
        self._next_id = 1

    # --- 조회 ---

    def add(self, url: str, out_dir: str, filename: str, quality: str) -> Job:
        job = Job(
            id=self._next_id,
            url=url,
            out_dir=out_dir,
            filename=filename,
            quality=quality,
            title=filename.strip(),
        )
        self._next_id += 1
        self._jobs.append(job)
        return job

    def get(self, job_id: int) -> Job | None:
        return next((j for j in self._jobs if j.id == job_id), None)

    def jobs(self) -> list[Job]:
        return list(self._jobs)

    def running(self) -> Job | None:
        return next((j for j in self._jobs if j.status is JobStatus.RUNNING), None)

    def next_pending(self) -> Job | None:
        return next((j for j in self._jobs if j.status is JobStatus.PENDING), None)

    # --- 전이 ---

    def mark_running(self, job_id: int) -> None:
        job = self._require(job_id)
        if self.running() is not None:
            raise ValueError("이미 추출 중인 작업이 있습니다")
        self._transition(job, JobStatus.PENDING, JobStatus.RUNNING)

    def set_progress(self, job_id: int, value: int) -> None:
        self._require(job_id).progress = max(0, min(100, int(value)))

    def set_title(self, job_id: int, title: str) -> None:
        if title:
            self._require(job_id).title = title

    def mark_done(self, job_id: int, path: str) -> None:
        job = self._require(job_id)
        self._transition(job, JobStatus.RUNNING, JobStatus.DONE)
        job.progress = 100
        job.result_path = path

    def mark_failed(self, job_id: int, error: str) -> None:
        job = self._require(job_id)
        self._transition(job, JobStatus.RUNNING, JobStatus.FAILED)
        job.error = error

    def mark_cancelled(self, job_id: int) -> None:
        job = self._require(job_id)
        self._transition(job, JobStatus.RUNNING, JobStatus.CANCELLED)

    def remove(self, job_id: int) -> None:
        job = self._require(job_id)
        if job.status is JobStatus.RUNNING:
            raise ValueError("추출 중인 작업은 제거할 수 없습니다. 먼저 취소하세요")
        self._jobs.remove(job)

    # --- 요약 ---

    def summary(self) -> str:
        counts = {status: 0 for status in JobStatus}
        for job in self._jobs:
            counts[job.status] += 1
        text = (
            f"대기 {counts[JobStatus.PENDING]} · "
            f"추출 중 {counts[JobStatus.RUNNING]} · "
            f"완료 {counts[JobStatus.DONE]}"
        )
        if counts[JobStatus.FAILED]:
            text += f" · 실패 {counts[JobStatus.FAILED]}"
        if counts[JobStatus.CANCELLED]:
            text += f" · 취소 {counts[JobStatus.CANCELLED]}"
        return text

    # --- 내부 ---

    def _require(self, job_id: int) -> Job:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    @staticmethod
    def _transition(job: Job, expected: JobStatus, new: JobStatus) -> None:
        if job.status is not expected:
            raise ValueError(
                f"{job.status.value} → {new.value} 전이는 허용되지 않습니다 (작업 {job.id})"
            )
        job.status = new
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_queue.py -v`
Expected: PASS — 11 passed

- [ ] **Step 5: 커밋**

```bash
git add app/queue.py tests/test_queue.py
git commit -m "추출 목록 상태 기계 추가"
```

---

### Task 2: 워커에 제목 알림 시그널 추가

**Files:**
- Modify: `app/download_worker.py` (시그널 선언부 `:71-75`, `run()`의 빈 파일명 프로브 블록 `:139-153`)
- Modify: `tests/test_download_worker.py` (테스트 추가)

**Interfaces:**
- Consumes: 없음
- Produces: `DownloadWorker.title_resolved = pyqtSignal(str)`; `DownloadWorker._probe_title() -> str`

**참고:** 현재 `run()` 안에는 파일명이 비었을 때 `YoutubeDL(probe_opts).extract_info(...)`로 제목을 알아내는 블록이 인라인으로 있다. 이 블록을 `_probe_title()` 메서드로 옮기고 거기서 `title_resolved`를 emit 한다. `run()`은 `from yt_dlp import YoutubeDL`을 함수 안에서 import 하므로, 테스트는 `yt_dlp.YoutubeDL`을 몽키패치하면 된다.

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_download_worker.py` 맨 아래에 추가:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_download_worker.py -v`
Expected: FAIL — `AttributeError: 'DownloadWorker' object has no attribute 'title_resolved'`

- [ ] **Step 3: 구현**

`app/download_worker.py` 시그널 선언에 한 줄 추가:

```python
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    title_resolved = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
```

`cancel()` 메서드 바로 아래에 메서드 추가:

```python
    def _probe_title(self) -> str:
        """파일명을 비웠을 때 제목을 먼저 알아낸다.

        그냥 %(title)s 템플릿을 넘기면 yt-dlp가 기존 파일을 발견했을 때
        다운로드를 건너뛰고 그 파일을 결과로 돌려주므로 '완료'가 거짓이 된다.
        알아낸 제목은 title_resolved로 UI에 알린다.
        """
        from yt_dlp import YoutubeDL

        probe_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
        }
        with YoutubeDL(probe_opts) as probe:
            info = probe.extract_info(self._url, download=False)
        title = (info or {}).get("title") or ""
        if title:
            self.title_resolved.emit(title)
        return title
```

`run()`의 빈 파일명 블록을 아래로 교체한다. 기존의 `probe_opts = {` 부터 `info = None` 까지(그리고 그 위의 주석 3줄)를 지우고, `if not filename.strip():` 블록 전체가 정확히 다음이 되게 한다:

```python
            filename = self._filename
            if not filename.strip():
                self.status.emit("영상 정보 확인 중…")
                filename = self._probe_title()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_download_worker.py -v`
Expected: PASS — 12 passed (기존 10 + 2)

Run: `python -m pytest -q`
Expected: 63 passed (50 + 11 + 2)

- [ ] **Step 5: 커밋**

```bash
git add app/download_worker.py tests/test_download_worker.py
git commit -m "워커가 알아낸 제목을 title_resolved 시그널로 알림"
```

---

### Task 3: 큐 컨트롤러

**Files:**
- Create: `app/queue_controller.py`
- Test: `tests/test_queue_controller.py`

**Interfaces:**
- Consumes: `app.queue.DownloadQueue`, `app.queue.Job`, `app.queue.JobStatus`; `app.download_worker.DownloadWorker(url=, out_dir=, filename=, quality=, ffmpeg_path=)`와 시그널 `progress(int)`, `title_resolved(str)`, `finished_ok(str)`, `failed(str)`, `cancelled()`, `finished()`(QThread), 메서드 `start()`, `cancel()`, `wait()`
- Produces:
  - `app.queue_controller.QueueController(QObject)` — 생성자 `(ffmpeg_path: str | None, parent=None)`
  - 시그널 `job_added(int)`, `job_changed(int)`, `job_removed(int)`, `summary_changed(str)`, `idle()`
  - 메서드 `enqueue(url, out_dir, filename, quality) -> int`, `job(job_id) -> Job`, `jobs() -> list[Job]`, `summary() -> str`, `is_busy() -> bool`, `cancel_or_remove(job_id) -> None`, `cancel_all() -> None`
  - 클래스 속성 `worker_factory = DownloadWorker` — 테스트가 가짜 워커로 바꾼다

**참고:** `QObject`와 시그널은 `QApplication` 없이도 동작한다(직접 연결). 이 테스트는 이벤트 루프를 돌리지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_queue_controller.py`:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_queue_controller.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.queue_controller'`

- [ ] **Step 3: 구현**

`app/queue_controller.py`:

```python
"""추출 목록을 소유하고 DownloadWorker를 한 번에 하나만 띄우는 컨트롤러."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from app.download_worker import DownloadWorker
from app.queue import DownloadQueue, Job, JobStatus


class QueueController(QObject):
    job_added = pyqtSignal(int)
    job_changed = pyqtSignal(int)
    job_removed = pyqtSignal(int)
    summary_changed = pyqtSignal(str)
    idle = pyqtSignal()

    # 테스트에서 가짜 워커로 바꾼다.
    worker_factory = DownloadWorker

    def __init__(self, ffmpeg_path: str | None, parent=None) -> None:
        super().__init__(parent)
        self._ffmpeg_path = ffmpeg_path
        self._queue = DownloadQueue()
        # 지역 변수로 두면 가비지 컬렉션되어 스레드가 죽는다. 반드시 보관한다.
        self._worker = None
        self._active_id: int | None = None

    # --- 조회 ---

    def job(self, job_id: int) -> Job:
        job = self._queue.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    def jobs(self) -> list[Job]:
        return self._queue.jobs()

    def summary(self) -> str:
        return self._queue.summary()

    def is_busy(self) -> bool:
        return self._worker is not None

    # --- 명령 ---

    def enqueue(self, url: str, out_dir: str, filename: str, quality: str) -> int:
        job = self._queue.add(url, out_dir, filename, quality)
        self.job_added.emit(job.id)
        self._emit_summary()
        self._start_next()
        return job.id

    def cancel_or_remove(self, job_id: int) -> None:
        """행의 × 동작. 추출 중이면 취소, 아니면 목록에서 제거."""
        job = self._queue.get(job_id)
        if job is None:
            return
        if job.status is JobStatus.RUNNING:
            if self._worker is not None:
                self._worker.cancel()
            return
        self._queue.remove(job_id)
        self.job_removed.emit(job_id)
        self._emit_summary()

    def cancel_all(self) -> None:
        """대기 중은 전부 제거하고, 추출 중이면 취소한다 (창 닫기용)."""
        for job in self._queue.jobs():
            if job.status is JobStatus.PENDING:
                self._queue.remove(job.id)
                self.job_removed.emit(job.id)
        if self._worker is not None:
            self._worker.cancel()
        self._emit_summary()
        if self._worker is None:
            self.idle.emit()

    # --- 내부: 워커 수명 ---

    def _start_next(self) -> None:
        if self._worker is not None or self._queue.running() is not None:
            return
        job = self._queue.next_pending()
        if job is None:
            self.idle.emit()
            return

        worker = self.worker_factory(
            url=job.url,
            out_dir=job.out_dir,
            filename=job.filename,
            quality=job.quality,
            ffmpeg_path=self._ffmpeg_path,
        )
        self._worker = worker
        self._active_id = job.id

        worker.progress.connect(self._on_progress)
        worker.title_resolved.connect(self._on_title)
        worker.finished_ok.connect(self._on_finished_ok)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(self._on_thread_finished)

        self._queue.mark_running(job.id)
        self.job_changed.emit(job.id)
        self._emit_summary()
        worker.start()

    def _on_progress(self, value: int) -> None:
        if self._active_id is None:
            return
        self._queue.set_progress(self._active_id, value)
        self.job_changed.emit(self._active_id)

    def _on_title(self, title: str) -> None:
        if self._active_id is None:
            return
        self._queue.set_title(self._active_id, title)
        self.job_changed.emit(self._active_id)

    def _on_finished_ok(self, path: str) -> None:
        self._finish(lambda job_id: self._queue.mark_done(job_id, path))

    def _on_failed(self, message: str) -> None:
        self._finish(lambda job_id: self._queue.mark_failed(job_id, message))

    def _on_cancelled(self) -> None:
        self._finish(self._queue.mark_cancelled)

    def _finish(self, mark) -> None:
        job_id = self._active_id
        if job_id is None:
            return
        job = self._queue.get(job_id)
        if job is None or job.status is not JobStatus.RUNNING:
            return
        mark(job_id)
        self.job_changed.emit(job_id)
        self._emit_summary()

    def _on_thread_finished(self) -> None:
        """QThread가 완전히 끝난 뒤. 여기서만 다음 작업을 시작한다."""
        worker = self._worker
        if worker is not None:
            worker.wait()
        # 워커가 종료 시그널 없이 끝났다면(있어서는 안 되지만) 실패로 마감한다.
        job_id = self._active_id
        if job_id is not None:
            job = self._queue.get(job_id)
            if job is not None and job.status is JobStatus.RUNNING:
                self._queue.mark_failed(job_id, "작업이 결과 없이 종료되었습니다.")
                self.job_changed.emit(job_id)
                self._emit_summary()
        self._worker = None
        self._active_id = None
        self._start_next()

    def _emit_summary(self) -> None:
        self.summary_changed.emit(self._queue.summary())
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_queue_controller.py -v`
Expected: PASS — 9 passed

Run: `python -m pytest -q`
Expected: 72 passed

- [ ] **Step 5: 커밋**

```bash
git add app/queue_controller.py tests/test_queue_controller.py
git commit -m "큐 컨트롤러 추가: 워커를 한 번에 하나만 순차 실행"
```

---

### Task 4: 목록 패널과 행 위젯

**Files:**
- Create: `app/queue_panel.py`
- Create: `tests/conftest.py`
- Modify: `app/theme.py` (QSS 블록 추가, `[mode="cancel"]` 블록 3줄 제거)
- Test: `tests/test_queue_panel.py`, `tests/test_theme.py`(1개 추가)

**Interfaces:**
- Consumes: `app.queue.Job`, `app.queue.JobStatus`
- Produces:
  - `app.queue_panel.JobRow(QWidget)` — 생성자 `(job: Job)`, 시그널 `cancel_clicked(int)`, 메서드 `refresh(job)`; 자식 위젯 `title_label`, `status_label`, `cancel_btn`, `bar`, `percent_label`
  - `app.queue_panel.QueuePanel(QWidget)` — 시그널 `cancel_requested(int)`, `reveal_requested(int)`; 메서드 `add_row(job)`, `update_row(job)`, `remove_row(job_id)`, `row(job_id) -> JobRow | None`, `count() -> int`; 자식 `list_widget`, `empty_label`

**참고:** 위젯 테스트는 `QApplication`이 필요하다. 루트 `conftest.py`는 비워둔 채 두고(`sys.path` 용), `tests/conftest.py`에 세션 픽스처를 둔다. `QT_QPA_PLATFORM`을 픽스처 안에서 `offscreen`으로 강제해야 헤드리스 환경에서도 돈다.

- [ ] **Step 1: 픽스처와 실패하는 테스트 작성**

`tests/conftest.py`:

```python
import os

import pytest


@pytest.fixture(scope="session")
def qapp():
    """위젯 테스트용 QApplication. 화면 없이 offscreen으로 돈다."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
```

`tests/test_queue_panel.py`:

```python
from app.queue import DownloadQueue, JobStatus
from app.queue_panel import JobRow, QueuePanel


def make_job(filename="", url="https://youtu.be/abc"):
    q = DownloadQueue()
    return q, q.add(url, r"C:\out", filename, "1080p")


def test_row_shows_pending_state(qapp):
    _, job = make_job()
    row = JobRow(job)
    assert row.title_label.text() != ""
    assert row.status_label.text() == "대기 중"
    # show() 전이므로 isVisible()이 아니라 숨김 플래그(isHidden)로 판단한다
    assert row.bar.isHidden() is False
    assert row.percent_label.text() == "0%"


def test_row_refresh_running_and_done(qapp):
    q, job = make_job(filename="강의")
    row = JobRow(job)
    q.mark_running(job.id)
    q.set_progress(job.id, 62)
    row.refresh(job)
    assert row.status_label.text() == "추출 중"
    assert row.bar.value() == 62
    assert row.percent_label.text() == "62%"
    assert row.bar.isHidden() is False

    q.mark_done(job.id, r"C:\out\강의.mp4")
    row.refresh(job)
    assert row.status_label.text() == "완료"
    assert row.bar.isHidden() is True
    assert row.percent_label.isHidden() is True


def test_row_failed_shows_reason_in_tooltip(qapp):
    q, job = make_job()
    row = JobRow(job)
    q.mark_running(job.id)
    q.mark_failed(job.id, "비공개 영상입니다.")
    row.refresh(job)
    assert row.status_label.text() == "실패"
    assert row.status_label.toolTip() == "비공개 영상입니다."
    assert row.status_label.property("failed") == "true"


def test_row_cancel_emits_job_id(qapp):
    _, job = make_job()
    row = JobRow(job)
    got = []
    row.cancel_clicked.connect(got.append)
    row.cancel_btn.click()
    assert got == [job.id]


def test_panel_add_update_remove(qapp):
    panel = QueuePanel()
    assert panel.count() == 0
    assert panel.empty_label.isHidden() is False

    q = DownloadQueue()
    a = q.add("https://youtu.be/a", r"C:\out", "", "1080p")
    b = q.add("https://youtu.be/b", r"C:\out", "둘째", "1080p")
    panel.add_row(a)
    panel.add_row(b)
    assert panel.count() == 2
    assert panel.empty_label.isHidden() is True

    q.mark_running(a.id)
    q.set_title(a.id, "첫째 제목")
    panel.update_row(a)
    assert "첫째" in panel.row(a.id).title_label.text()

    panel.remove_row(a.id)
    assert panel.count() == 1
    assert panel.row(a.id) is None
    panel.remove_row(b.id)
    assert panel.empty_label.isHidden() is False


def test_panel_forwards_cancel(qapp):
    panel = QueuePanel()
    q = DownloadQueue()
    a = q.add("https://youtu.be/a", r"C:\out", "", "1080p")
    panel.add_row(a)
    got = []
    panel.cancel_requested.connect(got.append)
    panel.row(a.id).cancel_btn.click()
    assert got == [a.id]
```

`tests/test_theme.py`에 추가:

```python
def test_stylesheet_has_queue_row_styles():
    assert "QWidget#jobRow" in STYLESHEET
    assert "QLabel#byline" in STYLESHEET
    assert '[mode="cancel"]' not in STYLESHEET
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_queue_panel.py tests/test_theme.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.queue_panel'` 및 `test_stylesheet_has_queue_row_styles` 실패

- [ ] **Step 3: 테마 수정**

`app/theme.py`의 `STYLESHEET`에서 다음 3줄을 **삭제**한다:

```css
QPushButton#actionBtn[mode="cancel"] { background: #FFFFFF; color: #D03020; border: 1.5px solid #D03020; }
QPushButton#actionBtn[mode="cancel"]:hover { background: #FBE9E6; }
QPushButton#actionBtn[mode="cancel"]:disabled { color: #E8A39B; border-color: #E8A39B; background: #FFFFFF; }
```

그리고 `QProgressBar` 두 줄 뒤(문자열 끝)에 다음을 **추가**한다:

```css
QLabel#byline { color: #6B6B70; font-size: 12px; }
QLabel#summaryLabel { color: #6B6B70; font-size: 12px; }

QListWidget#queueList { background: transparent; border: none; outline: 0; }
QListWidget#queueList::item { border: none; padding: 0; }
QListWidget#queueList::item:selected, QListWidget#queueList::item:hover { background: transparent; }
QLabel#queueEmpty { color: #6B6B70; font-size: 12px; }

QWidget#jobRow { background: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 8px; }
QLabel#jobTitle { color: #1A1A1B; font-size: 13px; }
QLabel#jobStatus { color: #6B6B70; font-size: 12px; }
QLabel#jobStatus[failed="true"] { color: #D03020; }
QLabel#jobPercent { color: #1A1A1B; font-size: 12px; font-weight: 600; }
QPushButton#jobCancel {
    background: transparent; color: #9A9AA0; border: none;
    min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px;
    font-size: 16px; padding: 0;
}
QPushButton#jobCancel:hover { color: #D03020; }
QProgressBar#jobBar { background: #E4E4E7; border: none; border-radius: 2px; min-height: 4px; max-height: 4px; }
QProgressBar#jobBar::chunk { background: #D03020; border-radius: 2px; }
```

- [ ] **Step 4: 패널 구현**

`app/queue_panel.py`:

```python
"""오른쪽 추출 목록 패널. 행 위젯을 그리고 사용자 동작을 시그널로 넘길 뿐, 상태를 바꾸지 않는다."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.queue import Job, JobStatus


class JobRow(QWidget):
    cancel_clicked = pyqtSignal(int)

    def __init__(self, job: Job, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("jobRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.job_id = job.id
        self._full_title = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        self.title_label = QLabel()
        self.title_label.setObjectName("jobTitle")
        self.status_label = QLabel()
        self.status_label.setObjectName("jobStatus")
        self.cancel_btn = QPushButton("×")
        self.cancel_btn.setObjectName("jobCancel")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setToolTip("취소 / 목록에서 제거")
        self.cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self.job_id))
        top.addWidget(self.title_label, 1)
        top.addWidget(self.status_label, 0)
        top.addWidget(self.cancel_btn, 0)
        outer.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(8)
        self.bar = QProgressBar()
        self.bar.setObjectName("jobBar")
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("jobPercent")
        self.percent_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.percent_label.setFixedWidth(36)
        bottom.addWidget(self.bar, 1)
        bottom.addWidget(self.percent_label, 0)
        outer.addLayout(bottom)

        self.refresh(job)

    def refresh(self, job: Job) -> None:
        self._full_title = job.display_title
        self._elide_title()

        self.status_label.setText(job.status.value)
        failed = job.status is JobStatus.FAILED
        self.status_label.setProperty("failed", "true" if failed else "false")
        self.status_label.setToolTip(job.error if failed else "")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        active = job.status in (JobStatus.PENDING, JobStatus.RUNNING)
        self.bar.setHidden(not active)
        self.percent_label.setHidden(not active)
        self.bar.setValue(job.progress)
        self.percent_label.setText(f"{job.progress}%")

        # 끝난 행의 ×는 '제거', 나머지는 '취소'
        self.cancel_btn.setToolTip("목록에서 제거" if job.is_finished else "취소")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._elide_title()

    def _elide_title(self) -> None:
        width = max(self.title_label.width(), 120)
        metrics = self.title_label.fontMetrics()
        self.title_label.setText(
            metrics.elidedText(self._full_title, Qt.TextElideMode.ElideRight, width)
        )
        self.title_label.setToolTip(self._full_title)


class QueuePanel(QWidget):
    cancel_requested = pyqtSignal(int)
    reveal_requested = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: dict[int, tuple[QListWidgetItem, JobRow]] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        heading = QLabel("추출 목록")
        heading.setProperty("role", "field")
        outer.addWidget(heading)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("queueList")
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.setSpacing(4)
        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        outer.addWidget(self.list_widget, 1)

        self.empty_label = QLabel("추출을 누르면 여기에 쌓입니다")
        self.empty_label.setObjectName("queueEmpty")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.empty_label, 0)

        self._update_empty()

    # --- 행 관리 ---

    def add_row(self, job: Job) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, job.id)
        row = JobRow(job)
        row.cancel_clicked.connect(self.cancel_requested)
        item.setSizeHint(row.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)
        self._rows[job.id] = (item, row)
        self._update_empty()

    def update_row(self, job: Job) -> None:
        entry = self._rows.get(job.id)
        if entry is None:
            return
        item, row = entry
        row.refresh(job)
        item.setSizeHint(row.sizeHint())

    def remove_row(self, job_id: int) -> None:
        entry = self._rows.pop(job_id, None)
        if entry is None:
            return
        item, _ = entry
        self.list_widget.takeItem(self.list_widget.row(item))
        self._update_empty()

    def row(self, job_id: int) -> JobRow | None:
        entry = self._rows.get(job_id)
        return entry[1] if entry else None

    def count(self) -> int:
        return len(self._rows)

    # --- 내부 ---

    def _on_double_click(self, item: QListWidgetItem) -> None:
        job_id = item.data(Qt.ItemDataRole.UserRole)
        if job_id is not None:
            self.reveal_requested.emit(int(job_id))

    def _update_empty(self) -> None:
        empty = not self._rows
        self.empty_label.setHidden(not empty)
        self.list_widget.setHidden(empty)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_queue_panel.py tests/test_theme.py -v`
Expected: PASS — 6 + 3 passed

Run: `python -m pytest -q`
Expected: 79 passed

- [ ] **Step 6: 커밋**

```bash
git add app/queue_panel.py app/theme.py tests/conftest.py tests/test_queue_panel.py tests/test_theme.py
git commit -m "추출 목록 패널과 행 위젯 추가, 테마에 목록 스타일 반영"
```

---

### Task 5: 메인 창 통합

**Files:**
- Modify: `app/main_window.py` (전체 교체)

**Interfaces:**
- Consumes: `QueueController`, `QueuePanel`, `JobStatus`, 기존 `locate_ffmpeg`/`validate_*`/`QUALITY_FORMATS`/`DEFAULT_QUALITY`/`resource_path`
- Produces: `MainWindow` — 속성 `url_edit`, `name_edit`, `quality_box`, `dir_edit`, `browse_btn`, `action_btn`, `summary_label`, `byline_label`, `queue_panel`, `_controller`; 메서드 `_enqueue()`

**참고:** 이 파일은 통째로 교체한다. 기존의 `_worker`, `_start`, `_on_action`, `_set_running`, `_on_finished`, `_on_failed`, `_on_cancelled`, `_on_thread_finished`, `progress`, `percent_label`, `status_label`은 사라진다. `_reveal`, `_check_ffmpeg`, `_choose_dir`, `_closing`은 유지된다.

- [ ] **Step 1: 메인 창 교체**

`app/main_window.py` 전체:

```python
"""메인 창. 입력을 캡처해 컨트롤러에 넘기고, 시그널로 목록을 갱신한다."""

from __future__ import annotations

import os
import subprocess
import sys

from PyQt6.QtCore import QDir, QStandardPaths, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ffmpeg_locator import FFmpegNotFoundError, locate_ffmpeg
from app.options import DEFAULT_QUALITY, QUALITY_FORMATS
from app.queue import JobStatus
from app.queue_controller import QueueController
from app.queue_panel import QueuePanel
from app.resources import resource_path
from app.validation import validate_out_dir, validate_url

LEFT_WIDTH = 520
RIGHT_WIDTH = 360
GAP = 24


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "field")
    return label


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YouTube 다운로더")
        self.setWindowIcon(QIcon(resource_path("app.ico")))

        self._closing = False
        self._ffmpeg_path: str | None = None
        self._controller: QueueController | None = None

        self._build_ui()
        self._check_ffmpeg()
        self._wire_controller()

    # --- UI ---

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("root")
        columns = QHBoxLayout(central)
        columns.setContentsMargins(28, 28, 28, 28)
        columns.setSpacing(GAP)

        left = QWidget()
        left.setFixedWidth(LEFT_WIDTH - 56)  # 기존 520 창의 좌우 여백 28을 뺀 내용 폭 464
        left_col = QVBoxLayout(left)
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(18)

        # 헤더: 아이콘 + 제목 + by ssenu
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 22 - 18)
        header.setSpacing(8)  # 제목-바이라인 8px. 아이콘-제목은 아래 addSpacing(4)로 12px
        icon_label = QLabel()
        icon_label.setPixmap(
            QPixmap(resource_path("app.ico")).scaled(
                28,
                28,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        title_label = QLabel("YouTube 다운로더")
        title_label.setObjectName("appTitle")
        self.byline_label = QLabel("by ssenu")
        self.byline_label.setObjectName("byline")
        self.byline_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
        )
        header.addWidget(icon_label)
        header.addSpacing(4)
        header.addWidget(title_label)
        header.addWidget(self.byline_label, 0, Qt.AlignmentFlag.AlignBottom)
        header.addStretch(1)
        left_col.addLayout(header)

        # 영상 주소 (히어로)
        url_group = QVBoxLayout()
        url_group.setSpacing(6)
        url_group.addWidget(_field_label("영상 주소"))
        self.url_edit = QLineEdit()
        self.url_edit.setObjectName("urlEdit")
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.url_edit.returnPressed.connect(self._enqueue)
        url_group.addWidget(self.url_edit)
        left_col.addLayout(url_group)

        # 파일 이름 / 화질
        name_quality_row = QHBoxLayout()
        name_quality_row.setSpacing(18)

        name_group = QVBoxLayout()
        name_group.setSpacing(6)
        name_group.addWidget(_field_label("파일 이름"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("비워두면 영상 제목을 사용")
        name_group.addWidget(self.name_edit)

        quality_group = QVBoxLayout()
        quality_group.setSpacing(6)
        quality_group.addWidget(_field_label("화질"))
        self.quality_box = QComboBox()
        self.quality_box.addItems(list(QUALITY_FORMATS))
        self.quality_box.setCurrentText(DEFAULT_QUALITY)
        self.quality_box.setFixedWidth(132)
        quality_group.addWidget(self.quality_box)

        name_quality_row.addLayout(name_group, 1)
        name_quality_row.addLayout(quality_group, 0)
        left_col.addLayout(name_quality_row)

        # 저장 위치
        dir_group = QVBoxLayout()
        dir_group.setSpacing(6)
        dir_group.addWidget(_field_label("저장 위치"))
        dir_row = QHBoxLayout()
        dir_row.setContentsMargins(0, 0, 0, 0)
        dir_row.setSpacing(8)
        self.dir_edit = QLineEdit(
            QDir.toNativeSeparators(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.DesktopLocation
                )
            )
        )
        self.browse_btn = QPushButton("변경…")
        self.browse_btn.setObjectName("browseBtn")
        self.browse_btn.clicked.connect(self._choose_dir)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(self.browse_btn, 0)
        dir_group.addLayout(dir_row)
        left_col.addLayout(dir_group)

        # 액션 블록: 버튼 + 요약 한 줄
        action_block = QVBoxLayout()
        action_block.setContentsMargins(0, 26 - 18, 0, 0)
        action_block.setSpacing(10)
        self.action_btn = QPushButton("추출")
        self.action_btn.setObjectName("actionBtn")
        self.action_btn.clicked.connect(self._enqueue)
        action_block.addWidget(self.action_btn)
        self.summary_label = QLabel("대기 0 · 추출 중 0 · 완료 0")
        self.summary_label.setObjectName("summaryLabel")
        action_block.addWidget(self.summary_label)
        left_col.addLayout(action_block)
        left_col.addStretch(1)

        # 오른쪽: 추출 목록
        self.queue_panel = QueuePanel()
        self.queue_panel.setFixedWidth(RIGHT_WIDTH)
        self.queue_panel.cancel_requested.connect(self._on_cancel_requested)
        self.queue_panel.reveal_requested.connect(self._on_reveal_requested)

        columns.addWidget(left, 0)
        columns.addWidget(self.queue_panel, 0)
        self.setCentralWidget(central)

        self.setFixedWidth(LEFT_WIDTH + GAP + RIGHT_WIDTH)
        self.adjustSize()
        self.setFixedHeight(max(self.sizeHint().height(), 456))

    def _check_ffmpeg(self) -> None:
        try:
            self._ffmpeg_path = locate_ffmpeg()
        except FFmpegNotFoundError as exc:
            self._ffmpeg_path = None
            self.action_btn.setEnabled(False)
            self.summary_label.setText("ffmpeg 없음")
            QMessageBox.critical(self, "ffmpeg을 찾을 수 없습니다", str(exc))

    def _wire_controller(self) -> None:
        self._controller = QueueController(self._ffmpeg_path, parent=self)
        self._controller.job_added.connect(self._on_job_added)
        self._controller.job_changed.connect(self._on_job_changed)
        self._controller.job_removed.connect(self.queue_panel.remove_row)
        self._controller.summary_changed.connect(self.summary_label.setText)
        self._controller.idle.connect(self._on_controller_idle)

    # --- 사용자 동작 ---

    def _choose_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "저장 위치 선택", self.dir_edit.text()
        )
        if chosen:
            self.dir_edit.setText(QDir.toNativeSeparators(chosen))

    def _enqueue(self) -> None:
        if self._controller is None or not self.action_btn.isEnabled():
            return
        url = self.url_edit.text().strip()
        out_dir = self.dir_edit.text().strip()

        for message in (validate_url(url), validate_out_dir(out_dir)):
            if message:
                QMessageBox.warning(self, "입력을 확인해 주세요", message)
                return

        self._controller.enqueue(
            url=url,
            out_dir=out_dir,
            filename=self.name_edit.text().strip(),
            quality=self.quality_box.currentText(),
        )
        # 다음 주소를 바로 붙여넣을 수 있게 비운다. 화질·저장 위치는 그대로 둔다.
        self.url_edit.clear()
        self.name_edit.clear()
        self.url_edit.setFocus()

    def _on_cancel_requested(self, job_id: int) -> None:
        if self._controller is not None:
            self._controller.cancel_or_remove(job_id)

    def _on_reveal_requested(self, job_id: int) -> None:
        if self._controller is None:
            return
        try:
            job = self._controller.job(job_id)
        except KeyError:
            return
        if job.status is JobStatus.DONE and job.result_path:
            self._reveal(job.result_path)

    # --- 컨트롤러 → 패널 ---

    def _on_job_added(self, job_id: int) -> None:
        self.queue_panel.add_row(self._controller.job(job_id))

    def _on_job_changed(self, job_id: int) -> None:
        try:
            job = self._controller.job(job_id)
        except KeyError:
            return
        self.queue_panel.update_row(job)

    def _on_controller_idle(self) -> None:
        if self._closing:
            self.close()

    # --- 기타 ---

    @staticmethod
    def _reveal(path: str) -> None:
        target = os.path.normpath(path)
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{target}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", target])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(target)])

    def closeEvent(self, event):
        if self._controller is not None and self._controller.is_busy():
            # 실행 중인 QThread를 파괴하면 종료 시 크래시가 난다.
            # 대기는 비우고 실행 중은 취소한 뒤, 컨트롤러가 idle을 보내면 다시 close()한다.
            if not self._closing:
                self._closing = True
                self.summary_label.setText("종료 중… (다운로드 취소)")
                self.action_btn.setEnabled(False)
                self._controller.cancel_all()
            event.ignore()
            return
        super().closeEvent(event)
```

- [ ] **Step 2: 전체 테스트 확인**

Run: `python -m pytest -q`
Expected: 79 passed (이 태스크는 테스트를 추가하지 않는다)

- [ ] **Step 3: 헤드리스 스모크**

`C:\Users\cwhap\.claude\jobs\047fa836\tmp\t14\smoke_queue.py`를 만들어 실행한다 (저장소에 커밋하지 않는다):

```python
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
sys.path.insert(0, r"C:\mycode\yt-downloader")

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal
from app.theme import apply_theme
from app.main_window import MainWindow
from app.queue import JobStatus

app = QApplication([])
apply_theme(app)
captured = []
QMessageBox.warning = staticmethod(lambda parent, title, text, *a, **k: captured.append((title, text)))

w = MainWindow()
w.show()

assert w.width() == 904, w.width()
assert w.action_btn.text() == "추출" and w.action_btn.isEnabled()
assert w.byline_label.text() == "by ssenu"
assert w.summary_label.text() == "대기 0 · 추출 중 0 · 완료 0"
assert w.queue_panel.count() == 0 and not w.queue_panel.empty_label.isHidden()

# 검증 실패는 목록에 추가하지 않는다
w.url_edit.setText("")
w._enqueue()
assert captured and "URL" in captured[-1][1]
assert w.queue_panel.count() == 0

# 가짜 워커로 순차 실행을 UI까지 확인
class FakeWorker(QObject):
    progress = pyqtSignal(int); status = pyqtSignal(str); title_resolved = pyqtSignal(str)
    finished_ok = pyqtSignal(str); failed = pyqtSignal(str); cancelled = pyqtSignal(); finished = pyqtSignal()
    instances = []
    def __init__(self, url, out_dir, filename, quality, ffmpeg_path):
        super().__init__(); self.url = url; FakeWorker.instances.append(self)
    def start(self): pass
    def cancel(self): pass
    def wait(self, *a): return True

w._controller.worker_factory = FakeWorker
w.url_edit.setText("https://www.youtube.com/watch?v=aaaaaaaaaaa")
w.name_edit.setText("첫째")
w._enqueue()
w.url_edit.setText("https://www.youtube.com/watch?v=bbbbbbbbbbb")
w._enqueue()
assert w.url_edit.text() == "" and w.name_edit.text() == ""
assert w.url_edit.isEnabled() and w.action_btn.text() == "추출"
assert w.queue_panel.count() == 2
assert w.summary_label.text() == "대기 1 · 추출 중 1 · 완료 0"

first = FakeWorker.instances[0]
first.progress.emit(45)
app.processEvents()
row1 = w.queue_panel.row(1)
assert row1.status_label.text() == "추출 중" and row1.percent_label.text() == "45%"
first.finished_ok.emit(r"C:\tmp\첫째.mp4"); first.finished.emit()
app.processEvents()
assert row1.status_label.text() == "완료" and row1.bar.isHidden()
assert w.queue_panel.row(2).status_label.text() == "추출 중"
assert w.summary_label.text() == "대기 0 · 추출 중 1 · 완료 1"

# 완료 행 더블클릭 → _reveal 호출
revealed = []
w._reveal = lambda p: revealed.append(p)  # 인스턴스 속성이라 self 바인딩 없이 호출된다
w._on_reveal_requested(1)
assert revealed == [r"C:\tmp\첫째.mp4"]

# 스크린샷 (실제 폰트로 보려면 windows 플랫폼에서 따로 찍는다)
w.grab().save(r"C:\Users\cwhap\.claude\jobs\047fa836\tmp\t14\queue_offscreen.png")
print("SMOKE OK")
```

Run: `python C:\Users\cwhap\.claude\jobs\047fa836\tmp\t14\smoke_queue.py`
Expected: `SMOKE OK`, 예외 없음. (`w.width()`가 904가 아니면 `setFixedWidth` 계산을 확인한다: 520 + 24 + 360 = 904.)

- [ ] **Step 4: 실제 폰트 스크린샷**

`C:\Users\cwhap\.claude\jobs\047fa836\tmp\t14\shots.py`를 만들어 실행한다. 위 스모크와 같은 방식으로 창을 만들되 `QT_QPA_PLATFORM`을 설정하지 않고(`windows` 플랫폼), `w.move(-3000, -3000)`으로 화면 밖에 띄운 뒤 `QTimer.singleShot(400, ...)` 안에서 가짜 워커로 행 3개(완료 / 추출 중 62% / 대기 중)를 만들고 `w.grab().save(...)`로 `queue_idle.png`(빈 목록)와 `queue_busy.png`(행 3개)를 저장하고 `app.quit()`한다. 두 PNG를 Read 도구로 직접 열어 본다. 확인 항목: `by ssenu`가 제목 오른쪽 아래 기준선에 회색으로 붙어 있는가, 오른쪽 목록의 행이 흰 카드로 8px 라운드인가, 추출 중 행에만 진행바가 있는가, 완료 행에는 진행바가 없는가, × 버튼이 잘리지 않았는가, 창 폭이 904인가. 어긋나면 이 태스크 안에서 고친다.

- [ ] **Step 5: 커밋**

```bash
git add app/main_window.py
git commit -m "메인 창을 추출 목록 컨트롤러와 연결, 하단을 요약 한 줄로, by ssenu 표기"
```

---

### Task 6: 실제 영상으로 종단 확인

**Files:** 없음 (수정이 필요하면 해당 파일)

**Interfaces:**
- Consumes: Task 5까지의 전체 앱
- Produces: 없음

**참고:** 단위 테스트와 가짜 워커가 못 잡는 것 — 진짜 워커가 순차로 세 번 돌 때 컨트롤러가 다음을 정확히 시작하는지, 취소 도중 다음이 자동 시작되는지, 실제 제목이 행에 반영되는지 — 를 확인한다. 이전 종단 하네스(`C:\Users\cwhap\.claude\jobs\047fa836\tmp\t8\harness.py`)의 `run_until_terminal`·다이얼로그 몽키패치 방식을 재사용한다.

- [ ] **Step 1: 하네스 작성**

`C:\Users\cwhap\.claude\jobs\047fa836\tmp\t14\queue_e2e.py`: `offscreen`, `apply_theme`, `MainWindow`, `QMessageBox.*` 몽키패치, 새 임시 폴더 `dl_queue`. 그 다음:

1. `https://www.youtube.com/live/3l8nOjIzI-A` / 파일명 `큐1` / 480p → `_enqueue()`
2. 같은 URL / 파일명 `큐2` / 480p → `_enqueue()`
3. 같은 URL / 파일명 **비움** / 480p → `_enqueue()`
4. 요약이 `대기 2 · 추출 중 1 · 완료 0`인지 확인.
5. `processEvents` 루프를 돌며 작업 1이 `완료`가 될 때까지 대기(≤ 600 s). 작업 2가 `추출 중`으로 바뀌었는지 확인.
6. 작업 2의 진행률이 `> 0`이 되면 `w.queue_panel.row(2).cancel_btn.click()`. 작업 2가 `취소됨`이 되고 작업 3이 `추출 중`이 될 때까지 대기(≤ 120 s). 폴더에 `큐2`가 들어간 파일이 없는지 확인.
7. 작업 3이 `완료`될 때까지 대기(≤ 600 s). 행 제목이 `웹프로그래밍(09/03)`(알아낸 제목)이고 파일이 `웹프로그래밍(0903).mp4`인지 확인.
8. 요약이 `대기 0 · 추출 중 0 · 완료 2 · 취소 1`인지 확인.
9. `w._reveal`을 가짜로 바꾸고 `w._on_reveal_requested(3)` → 경로가 작업 3의 파일인지 확인.
10. `w.close()` 두 번 → 창이 닫히는지(바쁘지 않으므로 즉시).

각 단계마다 `STEP n OK` 또는 `STEP n FAIL <이유>`를 출력하고, 실패해도 끝까지 진행한다. 로그는 `python -u … > …\t14\queue_e2e.log 2>&1`, 타임아웃 600000 ms(부족하면 백그라운드 + 폴링). 끝나면 mp4를 지운다.

- [ ] **Step 2: 실행 및 판정**

Expected: STEP 1~10 전부 OK. 실패하면 로그로 원인을 가리고, 몇 줄짜리 코드 결함이면 해당 모듈 안에서 고친 뒤(단위 테스트가 가능한 경우 실패 테스트부터) 전체 테스트와 하네스를 다시 돌린다. 설계 변경이 필요하면 고치지 말고 보고한다.

- [ ] **Step 3: 커밋 (수정이 있었을 때만)**

```bash
git status --short
```

---

### Task 7: exe 재빌드

**Files:** 없음 (`build.spec` 변경 없음)

- [ ] **Step 1: 잔존 프로세스 정리 후 빌드**

```powershell
Get-Process -Name yt-downloader -ErrorAction SilentlyContinue | Stop-Process -Force
```

Run: `python -m PyInstaller build.spec --noconfirm` (타임아웃 600000)
Expected: 로그에 `Building EXE from EXE-00.toc completed successfully.`, `dist\yt-downloader.exe`의 수정 시각이 마지막 커밋보다 나중.

- [ ] **Step 2: 번들 확인**

PyInstaller의 `CArchiveReader`/`ZlibArchiveReader`로 PYZ를 열어 `app.queue`, `app.queue_controller`, `app.queue_panel` 모듈이 들어 있는지, `app.main_window`의 코드 오브젝트 이름에 `_enqueue`와 `queue_panel`이 있는지 확인한다. `QT_QPA_PLATFORM=offscreen`으로 exe를 띄워 8초 뒤 살아 있는지, 최신 `%TEMP%\_MEI*`에 `ffmpeg.exe`와 `assets\app.ico`가 있는지 확인한 뒤 `Get-Process -Name yt-downloader | Stop-Process -Force`로 트리 전체를 종료한다.

- [ ] **Step 3: 커밋할 것 없음**

`build/`, `dist/`는 git 추적 대상이 아니다.

---

## 완료 기준

- `python -m pytest -q` 79 passed
- 헤드리스 스모크 `SMOKE OK`, 실제 폰트 스크린샷 2장 검토 통과
- 종단 하네스 STEP 1~10 OK (실제 영상 3개 순차, 도중 취소 1개)
- `dist\yt-downloader.exe` 재빌드 및 번들 확인
