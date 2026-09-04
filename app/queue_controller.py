"""추출 목록을 소유하고 DownloadWorker를 한 번에 하나만 띄우는 컨트롤러."""

from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

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
    inter_job_delay_ms = 3000

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

        try:
            worker = self.worker_factory(
                url=job.url,
                out_dir=job.out_dir,
                filename=job.filename,
                quality=job.quality,
                ffmpeg_path=self._ffmpeg_path,
            )
            worker.progress.connect(self._on_progress)
            worker.title_resolved.connect(self._on_title)
            worker.finished_ok.connect(self._on_finished_ok)
            worker.failed.connect(self._on_failed)
            worker.cancelled.connect(self._on_cancelled)
            worker.finished.connect(self._on_thread_finished)

            self._queue.mark_running(job.id)
            self._worker = worker
            self._active_id = job.id
            # UI 슬롯(job_changed 등)이 예외를 던져도 스레드는 이미 떠 있도록
            # 알리기 전에 먼저 시작한다.
            worker.start()
        except Exception as exc:  # 워커 생성/시작 실패는 그 작업만 실패로 마감하고 다음으로 간다
            self._worker = None
            self._active_id = None
            job_now = self._queue.get(job.id)
            if job_now is not None:
                if job_now.status is JobStatus.PENDING:
                    self._queue.mark_running(job.id)
                self._queue.mark_failed(job.id, f"작업을 시작하지 못했습니다.\n\n{exc}")
                self.job_changed.emit(job.id)
            self._emit_summary()
            self._start_next()
            return

        self.job_changed.emit(job.id)
        self._emit_summary()

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
        if self.inter_job_delay_ms > 0 and self._queue.next_pending() is not None:
            # 연속 요청은 유튜브 봇 확인을 유발하기 쉬우므로 작업 사이에 잠깐 쉰다.
            QTimer.singleShot(self.inter_job_delay_ms, self._start_next)
        else:
            self._start_next()

    def _emit_summary(self) -> None:
        self.summary_changed.emit(self._queue.summary())
