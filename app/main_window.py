"""메인 창. 입력 수집과 시그널 배선만 담당한다."""

from __future__ import annotations

import os
import subprocess
import sys

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.download_worker import DownloadWorker
from app.ffmpeg_locator import FFmpegNotFoundError, locate_ffmpeg
from app.options import DEFAULT_QUALITY, QUALITY_FORMATS
from app.validation import validate_out_dir, validate_url


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YouTube 다운로더")
        self.setMinimumWidth(580)

        self._worker: DownloadWorker | None = None
        self._ffmpeg_path: str | None = None

        self._build_ui()
        self._check_ffmpeg()

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        form = QFormLayout()

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        form.addRow("URL", self.url_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("비워두면 영상 제목을 사용합니다")
        form.addRow("파일명", self.name_edit)

        self.quality_box = QComboBox()
        self.quality_box.addItems(list(QUALITY_FORMATS))
        self.quality_box.setCurrentText(DEFAULT_QUALITY)
        form.addRow("화질", self.quality_box)

        self.dir_edit = QLineEdit(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DesktopLocation
            )
        )
        self.browse_btn = QPushButton("찾아보기…")
        self.browse_btn.clicked.connect(self._choose_dir)

        dir_row = QHBoxLayout()
        dir_row.setContentsMargins(0, 0, 0, 0)
        dir_row.addWidget(self.dir_edit)
        dir_row.addWidget(self.browse_btn)
        dir_holder = QWidget()
        dir_holder.setLayout(dir_row)
        form.addRow("저장 위치", dir_holder)

        outer.addLayout(form)

        self.action_btn = QPushButton("추출")
        self.action_btn.setMinimumHeight(36)
        self.action_btn.clicked.connect(self._on_action)
        outer.addWidget(self.action_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        outer.addWidget(self.progress)

        self.status_label = QLabel("대기 중")
        outer.addWidget(self.status_label)

        self.setCentralWidget(central)

    def _check_ffmpeg(self) -> None:
        try:
            self._ffmpeg_path = locate_ffmpeg()
        except FFmpegNotFoundError as exc:
            self._ffmpeg_path = None
            self.action_btn.setEnabled(False)
            self.status_label.setText("ffmpeg 없음")
            QMessageBox.critical(self, "ffmpeg을 찾을 수 없습니다", str(exc))

    def _choose_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "저장 위치 선택", self.dir_edit.text()
        )
        if chosen:
            self.dir_edit.setText(chosen)

    def _on_action(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.status_label.setText("취소 중…")
            self.action_btn.setEnabled(False)
            self._worker.cancel()
            return
        self._start()

    def _start(self) -> None:
        url = self.url_edit.text().strip()
        out_dir = self.dir_edit.text().strip()

        for message in (validate_url(url), validate_out_dir(out_dir)):
            if message:
                QMessageBox.warning(self, "입력을 확인해 주세요", message)
                return

        # 지역 변수로 두면 가비지 컬렉션되어 스레드가 죽는다. 반드시 보관한다.
        self._worker = DownloadWorker(
            url=url,
            out_dir=out_dir,
            filename=self.name_edit.text().strip(),
            quality=self.quality_box.currentText(),
            ffmpeg_path=self._ffmpeg_path,
        )
        self._worker.progress.connect(self.progress.setValue)
        self._worker.status.connect(self.status_label.setText)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)

        self.progress.setValue(0)
        self._set_running(True)
        self._worker.start()

    def _set_running(self, running: bool) -> None:
        for widget in (
            self.url_edit,
            self.name_edit,
            self.quality_box,
            self.dir_edit,
            self.browse_btn,
        ):
            widget.setEnabled(not running)

        self.action_btn.setEnabled(True)
        self.action_btn.setText("취소" if running else "추출")

    def _on_finished(self, path: str) -> None:
        self._set_running(False)
        self.status_label.setText("완료")

        box = QMessageBox(self)
        box.setWindowTitle("완료")
        box.setText(f"저장했습니다.\n\n{path}")
        open_btn = box.addButton("폴더 열기", QMessageBox.ButtonRole.ActionRole)
        box.addButton("닫기", QMessageBox.ButtonRole.RejectRole)
        box.exec()

        if box.clickedButton() is open_btn:
            self._reveal(path)

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        self.progress.setValue(0)
        self.status_label.setText("실패")
        QMessageBox.critical(self, "다운로드 실패", message)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self.progress.setValue(0)
        self.status_label.setText("취소됨")

    @staticmethod
    def _reveal(path: str) -> None:
        target = os.path.normpath(path)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", target])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", target])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(target)])

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
