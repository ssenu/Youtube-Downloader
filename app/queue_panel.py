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
