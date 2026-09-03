"""yt-dlp를 별도 스레드에서 구동하는 워커."""

from __future__ import annotations

import glob
import os
import time

from PyQt6.QtCore import QThread, pyqtSignal

from app.errors import friendly_error
from app.options import build_ydl_opts


class CancelledError(Exception):
    """사용자 취소 시 yt-dlp 내부 루프를 빠져나오기 위한 내부 예외."""


def pick_final_path(paths: list[str]) -> str | None:
    """훅이 알려준 경로 중 실제로 남아 있는 마지막 파일을 고른다.

    병합이 끝나면 중간 스트림 파일(.f137.mp4 등)은 삭제되므로
    존재 여부로 최종 산출물을 가려낼 수 있다.
    """
    for path in reversed(paths):
        if path and os.path.isfile(path):
            return path
    return None


def cleanup_partials(paths: list[str]) -> None:
    """취소 시 받다 만 파일을 지운다.

    훅이 알려준 경로만 건드린다. 저장 폴더를 확장자로 훑어 지우면
    다른 프로그램이 만든 파일까지 지울 위험이 있다.

    DASH/HLS로 조각 다운로드된 스트림은 `video.mp4.part` 외에도
    `video.mp4.part-Frag2.part` 같은 조각별 임시 파일을 남기므로
    `path.part`로 시작하는 파일은 glob으로 함께 찾아 지운다.
    """
    for path in paths:
        if not path:
            continue
        junk_files = [path + ".part", path + ".ytdl", path]
        junk_files.extend(glob.glob(glob.escape(path + ".part") + "*"))
        for junk in junk_files:
            _remove_with_retry(junk)


def _remove_with_retry(path: str, attempts: int = 10, delay: float = 0.1) -> None:
    """다운로드 스레드가 파일 핸들을 놓기 전이면 삭제가 실패할 수 있다.

    특히 윈도우에서는 조각(fragment) 다운로드를 취소한 직후 핸들이
    바로 풀리지 않는 경우가 있었다 (Task 8 실제 취소 테스트에서 확인).
    바로 지워지지 않으면 잠깐 대기했다가 다시 시도한다.
    """
    for attempt in range(attempts):
        if not os.path.isfile(path):
            return
        try:
            os.remove(path)
            return
        except OSError:
            if attempt == attempts - 1:
                return
            time.sleep(delay)


class DownloadWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, url, out_dir, filename, quality, ffmpeg_path, parent=None):
        super().__init__(parent)
        self._url = url
        self._out_dir = out_dir
        self._filename = filename
        self._quality = quality
        self._ffmpeg_path = ffmpeg_path
        self._cancelled = False
        self._seen_paths: list[str] = []
        self._stream_index = 0

    def cancel(self) -> None:
        """취소를 요청한다. 훅이 다음에 호출될 때 반영된다."""
        self._cancelled = True

    def _on_progress(self, d: dict) -> None:
        if self._cancelled:
            raise CancelledError()

        state = d.get("status")

        if state == "downloading":
            path = d.get("filename")
            if path and path not in self._seen_paths:
                self._seen_paths.append(path)

            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            if total:
                self.progress.emit(min(100, int(done * 100 / total)))
            self.status.emit(
                "영상 다운로드 중…" if self._stream_index == 0 else "음성 다운로드 중…"
            )

        elif state == "finished":
            path = d.get("filename")
            if path:
                self._seen_paths.append(path)
            self._stream_index += 1
            self.progress.emit(100)

    def _on_postprocessor(self, d: dict) -> None:
        if self._cancelled:
            raise CancelledError()

        if d.get("status") == "started":
            self.status.emit("병합 중…")

        info = d.get("info_dict") or {}
        path = info.get("filepath")
        if path:
            self._seen_paths.append(path)

    def run(self) -> None:
        try:
            from yt_dlp import YoutubeDL

            opts = build_ydl_opts(
                out_dir=self._out_dir,
                filename=self._filename,
                quality=self._quality,
                ffmpeg_path=self._ffmpeg_path,
                progress_hook=self._on_progress,
                postprocessor_hook=self._on_postprocessor,
            )

            self.status.emit("영상 정보 확인 중…")
            with YoutubeDL(opts) as ydl:
                ydl.download([self._url])

        except CancelledError:
            cleanup_partials(self._seen_paths)
            self.cancelled.emit()
            return

        except Exception as exc:
            # yt-dlp는 훅에서 던진 예외를 DownloadError로 감싸므로
            # 여기서 플래그를 한 번 더 확인해야 취소를 취소로 처리할 수 있다.
            if self._cancelled:
                cleanup_partials(self._seen_paths)
                self.cancelled.emit()
            else:
                self.failed.emit(friendly_error(exc))
            return

        final = pick_final_path(self._seen_paths)
        if final is None:
            self.failed.emit("다운로드는 끝났지만 저장된 파일을 찾지 못했습니다.")
            return

        self.progress.emit(100)
        self.status.emit("완료")
        self.finished_ok.emit(final)
