import os

import pytest
from PyQt6.QtCore import QObject, pyqtSignal


@pytest.fixture(scope="session")
def qapp():
    """위젯 테스트용 QApplication. 화면 없이 offscreen으로 돈다."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


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
