import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from app.main_window import MainWindow
from conftest import FakeWorker


@pytest.fixture
def window(qapp, monkeypatch):
    captured = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: captured.append(a)))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: captured.append(a)))
    FakeWorker.instances.clear()
    w = MainWindow()
    w._controller.worker_factory = FakeWorker
    w._controller.inter_job_delay_ms = 0
    w.captured = captured
    w.show()
    yield w
    w.close()


def test_initial_state(window):
    assert window.width() == 844
    assert window.action_btn.text() == "추출" and window.action_btn.isEnabled()
    assert window.byline_label.text() == "by ssenu"
    assert window.summary_label.text() == "대기 0 · 추출 중 0 · 완료 0"
    assert window.queue_panel.count() == 0
    assert window.queue_panel.empty_label.isHidden() is False


def test_invalid_url_is_not_enqueued(window):
    window.url_edit.setText("")
    window._enqueue()
    assert window.captured and "URL" in window.captured[-1][2]
    assert window.queue_panel.count() == 0


def test_enqueue_clears_inputs_and_runs_sequentially(window, tmp_path):
    window.dir_edit.setText(str(tmp_path))
    window.url_edit.setText("https://www.youtube.com/watch?v=aaaaaaaaaaa")
    window.name_edit.setText("첫째")
    window._enqueue()
    window.url_edit.setText("https://www.youtube.com/watch?v=bbbbbbbbbbb")
    window._enqueue()
    assert window.url_edit.text() == "" and window.name_edit.text() == ""
    assert window.url_edit.isEnabled() and window.action_btn.text() == "추출"
    assert window.summary_label.text() == "대기 1 · 추출 중 1 · 완료 0"
    first = FakeWorker.instances[0]
    first.progress.emit(45)
    assert window.queue_panel.row(1).percent_label.text() == "45%"
    first.finish_ok(str(tmp_path / "첫째.mp4"))
    assert window.queue_panel.row(1).status_label.text() == "완료"
    assert window.queue_panel.row(2).status_label.text() == "추출 중"


def test_close_while_busy_waits_for_worker(window, tmp_path):
    window.dir_edit.setText(str(tmp_path))
    window.url_edit.setText("https://www.youtube.com/watch?v=aaaaaaaaaaa")
    window._enqueue()
    window.url_edit.setText("https://www.youtube.com/watch?v=bbbbbbbbbbb")
    window._enqueue()
    worker = FakeWorker.instances[0]

    window.close()
    assert window.isVisible(), "워커가 살아 있는 동안 창이 닫히면 안 된다"
    assert window._closing is True
    assert worker.cancel_calls == 1
    assert window.queue_panel.count() == 1, "대기 중 작업은 폐기돼야 한다"
    assert window.summary_label.text() == "종료 중… (다운로드 취소)"

    window.close()  # 두 번째 X — cancel이 두 번 가면 안 된다
    assert worker.cancel_calls == 1

    worker.finish_cancelled()
    assert not window.isVisible()
    assert window._controller.is_busy() is False


def test_quality_box_lists_video_then_separator_then_mp3(window):
    box = window.quality_box
    assert [box.itemText(i) for i in range(box.count())] == [
        "최고화질",
        "1080p",
        "720p",
        "480p",
        "",
        "MP3 320kbps",
        "MP3 192kbps",
        "MP3 128kbps",
    ]
    separator = box.model().item(4)
    assert not (separator.flags() & Qt.ItemFlag.ItemIsSelectable)
    assert box.currentText() == "1080p"
    assert box.width() == 132


def test_enqueue_passes_mp3_quality_to_job(window, tmp_path):
    window.dir_edit.setText(str(tmp_path))
    window.url_edit.setText("https://www.youtube.com/watch?v=aaaaaaaaaaa")
    window.quality_box.setCurrentText("MP3 128kbps")
    window._enqueue()

    assert window._controller.job(1).quality == "MP3 128kbps"
    assert window.quality_box.currentText() == "MP3 128kbps", "화질 선택은 추가 후에도 유지된다"
