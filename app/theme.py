"""앱 전역 테마: 색/타이포/여백 토큰을 담은 QSS와 적용 함수.

모듈을 임포트하는 것만으로 Qt를 건드리지 않는다 (QApplication 없이 테스트 가능).
Qt 관련 동작은 apply_theme() 안에서만 일어난다.
"""
from __future__ import annotations

STYLESHEET = """
QMainWindow, QWidget#root { background: #F6F6F7; }

QLabel { color: #1A1A1B; font-size: 13px; }
QLabel#appTitle {
    font-family: "Segoe UI Variable Display", "Segoe UI Semibold", "Malgun Gothic";
    font-size: 17px; font-weight: 600;
}
QLabel[role="field"] { color: #6B6B70; font-size: 12px; }

QLineEdit, QComboBox {
    background: #FFFFFF; color: #1A1A1B;
    border: 1px solid #E4E4E7; border-radius: 8px;
    padding: 0 12px; min-height: 40px; font-size: 13px;
    selection-background-color: #D03020; selection-color: #FFFFFF;
}
QLineEdit:focus, QComboBox:focus { border: 1.5px solid #D03020; }
QLineEdit:disabled, QComboBox:disabled { color: #9A9AA0; background: #F1F1F3; }
QLineEdit#urlEdit { min-height: 46px; font-size: 14px; }

QComboBox { padding-right: 28px; }
QComboBox::drop-down { border: none; width: 28px; subcontrol-origin: padding; subcontrol-position: center right; }
QComboBox::down-arrow {
    image: url(__CHEVRON_PATH__);
    width: 10px; height: 7px;
    margin-right: 10px;
}
QComboBox QAbstractItemView {
    background: #FFFFFF; color: #1A1A1B; border: 1px solid #E4E4E7;
    selection-background-color: #FBE9E6; selection-color: #1A1A1B; outline: 0; padding: 4px;
}

QPushButton#browseBtn {
    background: #FFFFFF; color: #1A1A1B; border: 1px solid #E4E4E7;
    border-radius: 8px; padding: 0 14px; min-height: 40px; font-size: 13px;
}
QPushButton#browseBtn:hover { background: #F1F1F3; }
QPushButton#browseBtn:disabled { color: #9A9AA0; }

QPushButton#actionBtn {
    background: #D03020; color: #FFFFFF; border: none;
    border-radius: 10px; min-height: 46px; font-size: 14px; font-weight: 600;
}
QPushButton#actionBtn:hover { background: #C42C1D; }
QPushButton#actionBtn:pressed { background: #B0281A; }
QPushButton#actionBtn:disabled { background: #E8A39B; color: #FFFFFF; }

QLabel#byline { color: #6B6B70; font-size: 12px; }
QLabel#summaryLabel { color: #6B6B70; font-size: 12px; }

QListWidget#queueList { background: transparent; border: none; outline: 0; }
QListWidget#queueList::item { border: none; padding: 0; }
QListWidget#queueList::item:selected, QListWidget#queueList::item:hover { background: transparent; }
QLabel#queueEmpty { color: #6B6B70; font-size: 12px; }

QWidget#jobRow { background: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 8px; }
#jobTitle { color: #1A1A1B; font-size: 13px; }
QLabel#jobStatus { color: #6B6B70; font-size: 12px; }
QLabel#jobStatus[failed="true"] { color: #D03020; }
QLabel#jobPercent { color: #1A1A1B; font-size: 12px; font-weight: 600; }
QPushButton#jobCancel {
    background: transparent; color: #9A9AA0; border: none;
    min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px;
    font-size: 16px; padding: 0;
}
QPushButton#jobCancel:hover { color: #D03020; }
QProgressBar#jobBar { background: #E4E4E7; border: none; border-radius: 2px; min-height: 4px; max-height: 4px; }
QProgressBar#jobBar::chunk { background: #D03020; border-radius: 2px; }
"""


def apply_theme(app) -> None:
    """QApplication에 Fusion 스타일, 폰트, 스타일시트를 적용한다."""
    from PyQt6.QtGui import QFont

    from app.resources import resource_path

    app.setStyle("Fusion")
    font = QFont("Segoe UI Variable Text", 10)
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Malgun Gothic"])
    app.setFont(font)

    chevron_path = resource_path("chevron_down.png").replace("\\", "/")
    app.setStyleSheet(STYLESHEET.replace("__CHEVRON_PATH__", chevron_path))
