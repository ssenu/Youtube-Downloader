from app.theme import STYLESHEET


def test_stylesheet_has_accent_color():
    assert "#D03020" in STYLESHEET


def test_stylesheet_has_progress_chunk():
    assert "QProgressBar::chunk" in STYLESHEET
