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
