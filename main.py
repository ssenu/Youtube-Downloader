"""YouTube 다운로더 진입점."""

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    try:
        window = MainWindow()
        window.show()
    except Exception as exc:
        # console=False exe에서는 예외가 조용히 사라지므로 최소한 대화상자로 알린다.
        QMessageBox.critical(None, "시작 오류", f"프로그램을 시작하지 못했습니다.\n\n{exc}")
        sys.exit(1)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
