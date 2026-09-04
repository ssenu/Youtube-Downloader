import os, sys
from app.resources import resource_path

def test_dev_path_points_at_repo_assets():
    p = resource_path("app.ico")
    assert p.endswith(os.path.join("assets", "app.ico"))
    assert os.path.isfile(p)

def test_frozen_path_uses_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resource_path("app.ico") == os.path.join(str(tmp_path), "assets", "app.ico")
