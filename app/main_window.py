"""메인 창. 입력 수집과 시그널 배선만 담당한다."""

from __future__ import annotations

import os
import subprocess
import sys

from PyQt6.QtCore import QStandardPaths, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
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
from app.resources import resource_path
from app.validation import validate_out_dir, validate_url


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "field")
    return label


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YouTube 다운로더")
        self.setWindowIcon(QIcon(resource_path("app.ico")))

        self._worker: DownloadWorker | None = None
        self._closing = False
        self._ffmpeg_path: str | None = None

        self._build_ui()
        self._check_ffmpeg()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("root")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(28, 28, 28, 28)
        outer.setSpacing(18)

        # 헤더: 아이콘 + 제목
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 22 - 18)  # 아래 spacing(18)과 합쳐 22가 되도록 보정
        header.setSpacing(12)
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
        header.addWidget(icon_label)
        header.addWidget(title_label)
        header.addStretch(1)
        outer.addLayout(header)

        # 영상 주소 (히어로)
        url_group = QVBoxLayout()
        url_group.setSpacing(6)
        url_group.addWidget(_field_label("영상 주소"))
        self.url_edit = QLineEdit()
        self.url_edit.setObjectName("urlEdit")
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        url_group.addWidget(self.url_edit)
        outer.addLayout(url_group)

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
        outer.addLayout(name_quality_row)

        # 저장 위치
        dir_group = QVBoxLayout()
        dir_group.setSpacing(6)
        dir_group.addWidget(_field_label("저장 위치"))
        dir_row = QHBoxLayout()
        dir_row.setContentsMargins(0, 0, 0, 0)
        dir_row.setSpacing(8)
        self.dir_edit = QLineEdit(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DesktopLocation
            )
        )
        self.browse_btn = QPushButton("변경…")
        self.browse_btn.setObjectName("browseBtn")
        self.browse_btn.clicked.connect(self._choose_dir)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(self.browse_btn, 0)
        dir_group.addLayout(dir_row)
        outer.addLayout(dir_group)

        # 액션 블록: 버튼 + 진행률 + 상태/퍼센트가 하나의 시그니처 블록
        action_block = QVBoxLayout()
        action_block.setContentsMargins(0, 26 - 18, 0, 0)  # 위 spacing(18)과 합쳐 26이 되도록 보정
        action_block.setSpacing(10)

        self.action_btn = QPushButton("추출")
        self.action_btn.setObjectName("actionBtn")
        self.action_btn.clicked.connect(self._on_action)
        action_block.addWidget(self.action_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        action_block.addWidget(self.progress)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        self.status_label = QLabel("대기 중")
        self.status_label.setObjectName("statusLabel")
        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("percentLabel")
        self.percent_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.percent_label, 0)
        action_block.addLayout(status_row)

        outer.addLayout(action_block)

        self.setCentralWidget(central)

        self.setFixedWidth(520)
        self.adjustSize()
        self.setFixedHeight(self.sizeHint().height())

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
        self._worker.progress.connect(self._on_progress)
        self._worker.status.connect(self.status_label.setText)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.finished.connect(self._on_thread_finished)

        self.progress.setValue(0)
        self.percent_label.setText("0%")
        self._set_running(True)
        self._worker.start()

    def _on_progress(self, value: int) -> None:
        self.progress.setValue(value)
        self.percent_label.setText(f"{value}%")

    def _set_running(self, running: bool) -> None:
        if self._closing:
            return  # 종료 대기 중에는 어떤 입력도 다시 활성화하지 않는다
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
        self.action_btn.setProperty("mode", "cancel" if running else "")
        self.action_btn.style().unpolish(self.action_btn)
        self.action_btn.style().polish(self.action_btn)

    def _on_finished(self, path: str) -> None:
        if self._closing:
            return
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
        if self._closing:
            return
        self._set_running(False)
        self.progress.setValue(0)
        self.percent_label.setText("0%")
        self.status_label.setText("실패")
        QMessageBox.critical(self, "다운로드 실패", message)

    def _on_cancelled(self) -> None:
        if self._closing:
            return
        self._set_running(False)
        self.progress.setValue(0)
        self.percent_label.setText("0%")
        self.status_label.setText("취소됨")

    @staticmethod
    def _reveal(path: str) -> None:
        target = os.path.normpath(path)
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{target}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", target])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(target)])

    def _on_thread_finished(self) -> None:
        """QThread가 완전히 끝난 뒤 호출된다. 종료를 기다리고 있었다면 이제 닫는다."""
        if self._closing and self._worker is not None:
            # finished는 스레드가 끝나기 직전에 발화할 수 있으므로 isRunning()이
            # 확실히 False가 되도록 잠깐 기다린다. 이미 끝났으면 즉시 반환한다.
            self._worker.wait()
            self.close()

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            # 실행 중인 QThread를 파괴하면 종료 시 크래시가 난다.
            # 취소를 요청하고 이벤트를 무시한 뒤, _on_thread_finished가 다시 close()를 부른다.
            if not self._closing:
                self._closing = True
                self.status_label.setText("종료 중… (다운로드 취소)")
                self.action_btn.setEnabled(False)
                self._worker.cancel()
            event.ignore()
            return
        super().closeEvent(event)
