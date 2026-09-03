from app.validation import validate_out_dir, validate_url


def test_valid_url_returns_none():
    assert validate_url("https://www.youtube.com/watch?v=abc") is None
    assert validate_url("http://youtu.be/abc") is None


def test_empty_url_is_rejected():
    assert validate_url("") is not None
    assert validate_url("   ") is not None


def test_non_http_url_is_rejected():
    assert validate_url("youtube.com/watch?v=abc") is not None
    assert validate_url("ftp://example.com/a.mp4") is not None


def test_existing_writable_dir_returns_none(tmp_path):
    assert validate_out_dir(str(tmp_path)) is None


def test_missing_dir_is_rejected(tmp_path):
    assert validate_out_dir(str(tmp_path / "없는폴더")) is not None


def test_empty_dir_is_rejected():
    assert validate_out_dir("") is not None


def test_file_path_is_rejected(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("")
    assert validate_out_dir(str(target)) is not None


def test_unwritable_dir_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr("os.access", lambda path, mode: False)
    assert validate_out_dir(str(tmp_path)) is not None
