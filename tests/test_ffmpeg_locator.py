import shutil
import sys

import pytest

from app.ffmpeg_locator import FFmpegNotFoundError, locate_ffmpeg


def test_frozen_uses_meipass(tmp_path, monkeypatch):
    fake = tmp_path / "ffmpeg.exe"
    fake.write_text("")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert locate_ffmpeg() == str(fake)


def test_falls_back_to_system_path(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    monkeypatch.setattr(shutil, "which", lambda name: r"C:\tools\ffmpeg.exe")

    assert locate_ffmpeg() == r"C:\tools\ffmpeg.exe"


def test_raises_when_nothing_found(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    monkeypatch.setattr(shutil, "which", lambda name: None)

    with pytest.raises(FFmpegNotFoundError):
        locate_ffmpeg()
