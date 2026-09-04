import os

import pytest


@pytest.fixture(scope="session")
def qapp():
    """위젯 테스트용 QApplication. 화면 없이 offscreen으로 돈다."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
