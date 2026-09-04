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
