from app.theme import STYLESHEET


def test_stylesheet_has_accent_color():
    assert "#D03020" in STYLESHEET


def test_stylesheet_has_progress_chunk():
    assert "QProgressBar::chunk" in STYLESHEET


def test_stylesheet_has_queue_row_styles():
    assert "QWidget#jobRow" in STYLESHEET
    assert "QLabel#byline" in STYLESHEET
    assert '[mode="cancel"]' not in STYLESHEET
