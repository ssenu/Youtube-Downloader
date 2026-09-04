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
