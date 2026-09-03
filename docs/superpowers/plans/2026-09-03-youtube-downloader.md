# YouTube 다운로더 (PyQt6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** YouTube URL을 넣으면 화질·파일명·저장 위치를 지정해 영상을 내려받는 PyQt6 데스크톱 앱을 만들고, 단일 exe로 빌드한다.

**Architecture:** Qt에 의존하지 않는 순수 모듈(`ffmpeg_locator`, `options`, `validation`, `errors`)에 로직을 몰아넣고 pytest로 검증한다. `DownloadWorker(QThread)`가 `yt_dlp.YoutubeDL`을 라이브러리로 직접 구동하며 시그널로만 UI와 통신한다. `MainWindow`는 입력 수집과 시그널 배선만 담당한다.

**Tech Stack:** Python 3.14.5, PyQt6 6.11, yt-dlp, imageio-ffmpeg, pytest, PyInstaller

## Global Constraints

- 프로젝트 루트: `C:\mycode\yt-downloader`
- 스펙 문서: `docs/superpowers/specs/2026-09-03-youtube-downloader-design.md`
- 순수 로직 모듈(`ffmpeg_locator.py`, `options.py`, `validation.py`, `errors.py`)은 **PyQt6를 import 하지 않는다.**
- `merge_output_format`은 항상 `"mp4"`이며, 모든 화질 format 문자열은 mp4/m4a 조합을 먼저 시도한다.
- 화질 드롭다운 항목은 정확히 `최고화질`, `1080p`, `720p`, `480p` 4개이고 기본값은 `1080p`이다.
- Windows 금지문자 `\ / : * ? " < > |` 는 파일명에서 제거한다.
- `QThread`에는 이미 `finished` 시그널이 있으므로 완료 시그널 이름은 `finished_ok`를 쓴다. (스펙 6.3의 `finished`를 이 이름으로 대체한다.)
- 워커 `run()` 밖으로 예외가 새어나가면 안 된다. 모든 예외는 `failed` 또는 `cancelled` 시그널로 변환한다.
- 모든 UI 문구는 한국어로 작성한다.
- 커밋 메시지는 한국어로 작성한다.

## 스펙 대비 변경 사항

구현 계획을 세우면서 스펙에서 세 가지를 조정했다. 스펙 문서를 고치지 않고 여기에 기록한다.

1. **`validation.py`와 `errors.py`를 추가한다.** 스펙 5절 구조에는 없지만, 스펙 8절의 입력 검증과 오류 문구 변환은 Qt 없이 테스트할 수 있는 순수 로직이다. `main_window.py`에 묻으면 검증할 수 없으므로 별도 모듈로 뺀다.
2. **완료 시그널 이름은 `finished`가 아니라 `finished_ok`다.** `QThread`가 이미 `finished` 시그널을 갖고 있어 이름이 충돌한다.
3. **`build_ydl_opts`에서 `url` 인자를 뺀다.** 옵션 딕셔너리에 들어가지 않고 `ydl.download([url])`에만 쓰이는 값이다.

---

### Task 1: 프로젝트 뼈대와 ffmpeg 경로 탐색

**Files:**
- Create: `requirements.txt`
- Create: `conftest.py`
- Create: `app/__init__.py`
- Create: `app/ffmpeg_locator.py`
- Test: `tests/test_ffmpeg_locator.py`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces:
  - `app.ffmpeg_locator.locate_ffmpeg() -> str`
  - `app.ffmpeg_locator.FFmpegNotFoundError(RuntimeError)`

**참고:** 루트의 `conftest.py`는 비어 있어도 반드시 만들어야 한다. pytest는 `conftest.py`가 있는 디렉터리를 `sys.path`에 넣는다. 이게 없으면 `tests/`만 경로에 잡혀서 `from app.xxx import ...`가 전부 실패한다.

- [ ] **Step 1: 의존성 파일 작성**

`requirements.txt`:

```
PyQt6>=6.9
yt-dlp>=2025.1.1
imageio-ffmpeg>=0.5
pytest>=8.0
pyinstaller>=6.0
```

- [ ] **Step 2: 패키지 뼈대 생성**

`conftest.py` — 빈 파일로 생성한다.

`app/__init__.py` — 빈 파일로 생성한다.

- [ ] **Step 3: 실패하는 테스트 작성**

`tests/test_ffmpeg_locator.py`:

```python
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
```

`monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)`은 `import imageio_ffmpeg`가 `ImportError`를 던지게 만드는 표준 기법이다. 실제로 설치돼 있어도 테스트 안에서는 없는 것처럼 동작한다.

- [ ] **Step 4: 테스트 실패 확인**

Run: `python -m pytest tests/test_ffmpeg_locator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ffmpeg_locator'`

- [ ] **Step 5: 구현**

`app/ffmpeg_locator.py`:

```python
"""ffmpeg 실행 파일 경로 탐색. Qt 의존성 없음."""

from __future__ import annotations

import os
import shutil
import sys


class FFmpegNotFoundError(RuntimeError):
    """ffmpeg 실행 파일을 찾지 못했을 때 발생한다."""


def locate_ffmpeg() -> str:
    """ffmpeg 실행 파일의 절대 경로를 반환한다.

    탐색 순서: PyInstaller 번들 → imageio-ffmpeg → 시스템 PATH.
    """
    if getattr(sys, "frozen", False):
        bundled = os.path.join(getattr(sys, "_MEIPASS", ""), "ffmpeg.exe")
        if os.path.isfile(bundled):
            return bundled

    try:
        import imageio_ffmpeg

        path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.isfile(path):
            return path
    except Exception:
        pass

    found = shutil.which("ffmpeg")
    if found:
        return found

    raise FFmpegNotFoundError(
        "ffmpeg을 찾을 수 없습니다.\n\n"
        "pip install imageio-ffmpeg 로 설치하거나 "
        "시스템 PATH에 ffmpeg을 추가해 주세요."
    )
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `python -m pytest tests/test_ffmpeg_locator.py -v`
Expected: PASS — 3 passed

- [ ] **Step 7: 커밋**

```bash
git add requirements.txt conftest.py app/__init__.py app/ffmpeg_locator.py tests/test_ffmpeg_locator.py
git commit -m "ffmpeg 경로 탐색 모듈 추가"
```

---

### Task 2: 파일명 살균과 화질 format 문자열

**Files:**
- Create: `app/options.py`
- Test: `tests/test_options.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `app.options.sanitize_filename(name: str) -> str`
  - `app.options.build_format_string(quality: str) -> str`
  - `app.options.QUALITY_FORMATS: dict[str, str]` — 키 순서가 UI 드롭다운 순서다
  - `app.options.DEFAULT_QUALITY: str` = `"1080p"`
  - `app.options.TITLE_TEMPLATE: str` = `"%(title)s.%(ext)s"`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_options.py`:

```python
import pytest

from app.options import (
    DEFAULT_QUALITY,
    QUALITY_FORMATS,
    build_format_string,
    sanitize_filename,
)


def test_removes_windows_forbidden_characters():
    assert sanitize_filename('웹프로그래밍(09/03)') == "웹프로그래밍(0903)"
    assert sanitize_filename('a\\b:c*d?e"f<g>h|i') == "abcdefghi"


def test_strips_surrounding_whitespace_and_dots():
    assert sanitize_filename("  강의노트.  ") == "강의노트"
    assert sanitize_filename("...") == ""


def test_removes_control_characters():
    assert sanitize_filename("강의\x00\x1f노트") == "강의노트"


def test_quality_options_are_exactly_four_in_order():
    assert list(QUALITY_FORMATS) == ["최고화질", "1080p", "720p", "480p"]
    assert DEFAULT_QUALITY == "1080p"


def test_every_format_string_prefers_mp4_first():
    for quality, fmt in QUALITY_FORMATS.items():
        assert fmt.split("/")[0].endswith("+ba[ext=m4a]"), quality


def test_build_format_string_returns_mapped_value():
    assert build_format_string("720p") == QUALITY_FORMATS["720p"]
    assert "height<=720" in build_format_string("720p")


def test_build_format_string_rejects_unknown_quality():
    with pytest.raises(ValueError):
        build_format_string("1440p")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_options.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.options'`

- [ ] **Step 3: 구현**

`app/options.py`:

```python
"""UI 입력을 yt-dlp 옵션으로 변환한다. Qt 의존성 없음."""

from __future__ import annotations

import re

FORBIDDEN_CHARS = '\\/:*?"<>|'

QUALITY_FORMATS: dict[str, str] = {
    "최고화질": "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b",
    "1080p": (
        "bv*[height<=1080][ext=mp4]+ba[ext=m4a]"
        "/bv*[height<=1080]+ba/b[height<=1080]"
    ),
    "720p": (
        "bv*[height<=720][ext=mp4]+ba[ext=m4a]"
        "/bv*[height<=720]+ba/b[height<=720]"
    ),
    "480p": (
        "bv*[height<=480][ext=mp4]+ba[ext=m4a]"
        "/bv*[height<=480]+ba/b[height<=480]"
    ),
}

DEFAULT_QUALITY = "1080p"
TITLE_TEMPLATE = "%(title)s.%(ext)s"

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_filename(name: str) -> str:
    """Windows에서 쓸 수 없는 문자를 제거한다.

    yt-dlp 기본값은 '/'를 '⧸'(U+29F8) 같은 유사 문자로 바꾸는데,
    일부 프로그램이 이를 제대로 다루지 못하므로 아예 제거한다.
    """
    cleaned = "".join(ch for ch in name if ch not in FORBIDDEN_CHARS)
    cleaned = _CONTROL_CHARS.sub("", cleaned)
    return cleaned.strip().strip(".").strip()


def build_format_string(quality: str) -> str:
    """화질 드롭다운 값을 yt-dlp format 문자열로 바꾼다."""
    try:
        return QUALITY_FORMATS[quality]
    except KeyError:
        raise ValueError(f"알 수 없는 화질입니다: {quality}") from None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_options.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: 커밋**

```bash
git add app/options.py tests/test_options.py
git commit -m "파일명 살균과 화질 format 문자열 구현"
```

---

### Task 3: 파일명 충돌 회피와 yt-dlp 옵션 조립

**Files:**
- Modify: `app/options.py` (Task 2에서 만든 파일에 함수 추가)
- Modify: `tests/test_options.py` (테스트 추가)

**Interfaces:**
- Consumes: `app.options.sanitize_filename`, `app.options.build_format_string`, `app.options.TITLE_TEMPLATE`
- Produces:
  - `app.options.resolve_collision(out_dir: str, stem: str) -> str`
  - `app.options.build_ydl_opts(out_dir: str, filename: str, quality: str, ffmpeg_path: str, progress_hook=None, postprocessor_hook=None) -> dict`

**참고:** 스펙 6.2는 `build_ydl_opts`의 첫 인자로 `url`을 적었으나, URL은 옵션 딕셔너리에 들어가지 않고 `ydl.download([url])`에만 쓰인다. 쓰이지 않는 인자이므로 시그니처에서 뺀다.

**참고:** yt-dlp의 `overwrites=False`는 파일이 있으면 다운로드를 **건너뛸 뿐** 이름을 바꿔주지 않는다. 그래서 충돌 회피를 직접 구현한다.

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_options.py` 맨 아래에 다음을 추가한다. 파일 상단의 import 문도 아래처럼 바꾼다.

```python
import os

import pytest

from app.options import (
    DEFAULT_QUALITY,
    QUALITY_FORMATS,
    TITLE_TEMPLATE,
    build_format_string,
    build_ydl_opts,
    resolve_collision,
    sanitize_filename,
)
```

추가할 테스트:

```python
def test_resolve_collision_returns_stem_when_free(tmp_path):
    assert resolve_collision(str(tmp_path), "강의") == "강의"


def test_resolve_collision_appends_counter(tmp_path):
    (tmp_path / "강의.mp4").write_text("")
    assert resolve_collision(str(tmp_path), "강의") == "강의 (1)"

    (tmp_path / "강의 (1).mkv").write_text("")
    assert resolve_collision(str(tmp_path), "강의") == "강의 (2)"


def test_resolve_collision_ignores_extension(tmp_path):
    (tmp_path / "강의.webm").write_text("")
    assert resolve_collision(str(tmp_path), "강의") == "강의 (1)"


def test_build_opts_uses_given_filename(tmp_path):
    opts = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="웹프로그래밍(09/03)",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert opts["outtmpl"] == os.path.join(str(tmp_path), "웹프로그래밍(0903).%(ext)s")


def test_build_opts_falls_back_to_title_template(tmp_path):
    opts = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert opts["outtmpl"] == os.path.join(str(tmp_path), TITLE_TEMPLATE)


def test_build_opts_falls_back_when_sanitizing_empties_the_name(tmp_path):
    opts = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="///",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert opts["outtmpl"] == os.path.join(str(tmp_path), TITLE_TEMPLATE)


def test_build_opts_fixed_options(tmp_path):
    opts = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="a",
        quality="480p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert opts["merge_output_format"] == "mp4"
    assert opts["ffmpeg_location"] == r"C:\ffmpeg.exe"
    assert opts["noplaylist"] is True
    assert opts["format"] == QUALITY_FORMATS["480p"]


def test_build_opts_registers_hooks_only_when_given(tmp_path):
    def hook(d):
        return None

    with_hooks = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="a",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
        progress_hook=hook,
        postprocessor_hook=hook,
    )
    assert with_hooks["progress_hooks"] == [hook]
    assert with_hooks["postprocessor_hooks"] == [hook]

    without = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="a",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert "progress_hooks" not in without
    assert "postprocessor_hooks" not in without
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_options.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_collision' from 'app.options'`

- [ ] **Step 3: 구현**

`app/options.py` 상단 import에 `glob`과 `os`를 추가한다.

```python
import glob
import os
import re
```

파일 맨 아래에 다음 두 함수를 추가한다.

```python
def resolve_collision(out_dir: str, stem: str) -> str:
    """`out_dir`에 `stem.*`이 이미 있으면 ' (1)', ' (2)'를 붙여 비어 있는 이름을 찾는다.

    다운로드가 끝나기 전에는 확장자를 알 수 없으므로 확장자를 뺀 이름으로 검사한다.
    """
    escaped_dir = glob.escape(out_dir)

    def taken(candidate: str) -> bool:
        pattern = os.path.join(escaped_dir, glob.escape(candidate) + ".*")
        return bool(glob.glob(pattern))

    if not taken(stem):
        return stem

    counter = 1
    while taken(f"{stem} ({counter})"):
        counter += 1
    return f"{stem} ({counter})"


def build_ydl_opts(
    out_dir: str,
    filename: str,
    quality: str,
    ffmpeg_path: str,
    progress_hook=None,
    postprocessor_hook=None,
) -> dict:
    """UI 입력을 yt-dlp 옵션 딕셔너리로 만든다."""
    stem = sanitize_filename(filename or "")

    if stem:
        stem = resolve_collision(out_dir, stem)
        outtmpl = os.path.join(out_dir, stem + ".%(ext)s")
    else:
        # 파일명을 비우면 영상 제목을 쓴다. 제목은 미리 알 수 없으므로
        # 충돌 검사를 건너뛰고 yt-dlp 기본 동작에 맡긴다.
        outtmpl = os.path.join(out_dir, TITLE_TEMPLATE)

    opts: dict = {
        "format": build_format_string(quality),
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }

    if progress_hook is not None:
        opts["progress_hooks"] = [progress_hook]
    if postprocessor_hook is not None:
        opts["postprocessor_hooks"] = [postprocessor_hook]

    return opts
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_options.py -v`
Expected: PASS — 15 passed

- [ ] **Step 5: 커밋**

```bash
git add app/options.py tests/test_options.py
git commit -m "파일명 충돌 회피와 yt-dlp 옵션 조립 구현"
```

---

### Task 4: 입력 검증

**Files:**
- Create: `app/validation.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `app.validation.validate_url(url: str) -> str | None` — 문제가 있으면 한국어 오류 문구, 없으면 `None`
  - `app.validation.validate_out_dir(path: str) -> str | None` — 같은 규약

**참고:** "문제가 없으면 `None`"이라는 규약을 지켜야 한다. 호출부가 `if message:` 한 줄로 분기한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_validation.py`:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_validation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.validation'`

- [ ] **Step 3: 구현**

`app/validation.py`:

```python
"""추출 시작 전 입력값 검증. Qt 의존성 없음.

모든 함수는 문제가 있으면 사용자에게 보여줄 한국어 문구를,
문제가 없으면 None을 반환한다.
"""

from __future__ import annotations

import os


def validate_url(url: str) -> str | None:
    stripped = (url or "").strip()

    if not stripped:
        return "URL을 입력해 주세요."

    if not stripped.startswith(("http://", "https://")):
        return "http:// 또는 https:// 로 시작하는 주소를 입력해 주세요."

    return None


def validate_out_dir(path: str) -> str | None:
    stripped = (path or "").strip()

    if not stripped:
        return "저장 위치를 선택해 주세요."

    if not os.path.isdir(stripped):
        return f"저장 위치를 찾을 수 없습니다.\n\n{stripped}"

    if not os.access(stripped, os.W_OK):
        return f"저장 위치에 쓸 수 없습니다. 다른 폴더를 선택해 주세요.\n\n{stripped}"

    return None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_validation.py -v`
Expected: PASS — 8 passed

- [ ] **Step 5: 커밋**

```bash
git add app/validation.py tests/test_validation.py
git commit -m "URL과 저장 위치 입력 검증 추가"
```

---

### Task 5: 오류 메시지 변환

**Files:**
- Create: `app/errors.py`
- Test: `tests/test_errors.py`

**Interfaces:**
- Consumes: 없음
- Produces: `app.errors.friendly_error(exc: Exception) -> str`

**참고:** yt-dlp의 예외 문구는 영어이고 스택 정보가 섞여 있다. 사용자가 실제로 취할 수 있는 행동이 있는 경우(로그인 필요, 지역 차단 등)를 골라 한국어로 바꾸고, 나머지는 원문을 덧붙여 그대로 보여준다. 원문을 지우면 진단이 불가능해진다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_errors.py`:

```python
from app.errors import friendly_error


def test_private_video():
    message = friendly_error(Exception("ERROR: Private video. Sign in if you've been granted access"))
    assert "비공개" in message


def test_unavailable_video():
    assert "이용할 수 없" in friendly_error(Exception("ERROR: Video unavailable"))


def test_geo_blocked():
    message = friendly_error(Exception("The uploader has not made this video available in your country"))
    assert "지역" in message


def test_network_failure():
    message = friendly_error(Exception("<urlopen error [Errno 11001] getaddrinfo failed>"))
    assert "네트워크" in message


def test_unsupported_url():
    assert "지원하지 않" in friendly_error(Exception("ERROR: Unsupported URL: https://example.com"))


def test_unknown_error_keeps_original_text():
    original = "something completely unexpected happened"
    message = friendly_error(Exception(original))
    assert original in message
    assert "실패" in message
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.errors'`

- [ ] **Step 3: 구현**

`app/errors.py`:

```python
"""yt-dlp 예외를 사용자용 한국어 문구로 바꾼다. Qt 의존성 없음."""

from __future__ import annotations

# (검사할 키워드 묶음, 보여줄 문구) 순서대로 검사한다.
_RULES: list[tuple[tuple[str, ...], str]] = [
    (("private video",), "비공개 영상입니다. 다운로드할 수 없습니다."),
    (("video unavailable", "has been removed"), "삭제되었거나 이용할 수 없는 영상입니다."),
    # yt-dlp 실제 문구는 "has not made this video available in your country"라서
    # "not available in your country"로 검사하면 매칭되지 않는다.
    (("available in your country", "geo restrict", "geo-restrict"), "지역 차단된 영상입니다."),
    (("sign in to confirm your age", "age-restricted"), "연령 확인이 필요한 영상입니다."),
    (("sign in", "login required"), "로그인이 필요한 영상입니다."),
    (("unsupported url", "is not a valid url"), "지원하지 않는 URL입니다. 주소를 확인해 주세요."),
    (
        ("urlopen error", "getaddrinfo failed", "timed out", "connection reset"),
        "네트워크 연결에 문제가 있습니다. 연결을 확인한 뒤 다시 시도해 주세요.",
    ),
    (("ffmpeg",), "영상 병합에 실패했습니다. ffmpeg 설치 상태를 확인해 주세요."),
]


def friendly_error(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()

    for keywords, message in _RULES:
        if any(keyword in lowered for keyword in keywords):
            return message

    return f"다운로드에 실패했습니다.\n\n{text}"
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_errors.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: 커밋**

```bash
git add app/errors.py tests/test_errors.py
git commit -m "yt-dlp 오류를 한국어 안내 문구로 변환"
```

---

### Task 6: 다운로드 워커

**Files:**
- Create: `app/download_worker.py`
- Test: `tests/test_download_worker.py`

**Interfaces:**
- Consumes: `app.options.build_ydl_opts`, `app.errors.friendly_error`
- Produces:
  - `app.download_worker.pick_final_path(paths: list[str]) -> str | None`
  - `app.download_worker.cleanup_partials(paths: list[str]) -> None`
  - `app.download_worker.CancelledError(Exception)`
  - `app.download_worker.DownloadWorker(QThread)` — 생성자 `(url, out_dir, filename, quality, ffmpeg_path, parent=None)`
  - 시그널: `progress(int)`, `status(str)`, `finished_ok(str)`, `failed(str)`, `cancelled()`
  - 메서드: `cancel() -> None`

**참고 (중요):** 경로 선택과 임시 파일 정리는 `DownloadWorker`의 메서드가 아니라 **모듈 수준 순수 함수**로 뺀다. QThread 인스턴스를 만들려면 QApplication이 필요할 수 있어 테스트가 불안정해지기 때문이다. 이렇게 빼면 Qt 없이 검증할 수 있다.

**참고:** yt-dlp는 훅에서 던진 예외를 `DownloadError`로 감싸서 다시 던진다. 그래서 `except CancelledError`만으로는 취소를 못 잡는다. 일반 `except Exception` 안에서도 `self._cancelled` 플래그를 다시 확인해야 한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_download_worker.py`:

```python
import os

from app.download_worker import cleanup_partials, pick_final_path


def test_pick_final_path_returns_last_existing(tmp_path):
    gone = tmp_path / "video.f137.mp4"
    merged = tmp_path / "video.mp4"
    merged.write_text("")

    assert pick_final_path([str(gone), str(merged)]) == str(merged)


def test_pick_final_path_prefers_later_entries(tmp_path):
    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    first.write_text("")
    second.write_text("")

    assert pick_final_path([str(first), str(second)]) == str(second)


def test_pick_final_path_returns_none_when_nothing_exists(tmp_path):
    assert pick_final_path([str(tmp_path / "nope.mp4")]) is None


def test_pick_final_path_handles_empty_list():
    assert pick_final_path([]) is None


def test_cleanup_removes_partials_and_originals(tmp_path):
    target = tmp_path / "video.mp4"
    target.write_text("")
    part = tmp_path / "video.mp4.part"
    part.write_text("")
    ytdl = tmp_path / "video.mp4.ytdl"
    ytdl.write_text("")
    keep = tmp_path / "다른파일.mp4"
    keep.write_text("")

    cleanup_partials([str(target)])

    assert not target.exists()
    assert not part.exists()
    assert not ytdl.exists()
    assert keep.exists(), "훅이 알려준 경로 밖의 파일은 건드리면 안 된다"


def test_cleanup_ignores_missing_files(tmp_path):
    survivor = tmp_path / "무관한파일.mp4"
    survivor.write_text("")

    cleanup_partials([str(tmp_path / "없음.mp4")])

    assert survivor.exists()
    assert list(tmp_path.iterdir()) == [survivor]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_download_worker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.download_worker'`

- [ ] **Step 3: 구현**

`app/download_worker.py`:

```python
"""yt-dlp를 별도 스레드에서 구동하는 워커."""

from __future__ import annotations

import os

from PyQt6.QtCore import QThread, pyqtSignal

from app.errors import friendly_error
from app.options import build_ydl_opts


class CancelledError(Exception):
    """사용자 취소 시 yt-dlp 내부 루프를 빠져나오기 위한 내부 예외."""


def pick_final_path(paths: list[str]) -> str | None:
    """훅이 알려준 경로 중 실제로 남아 있는 마지막 파일을 고른다.

    병합이 끝나면 중간 스트림 파일(.f137.mp4 등)은 삭제되므로
    존재 여부로 최종 산출물을 가려낼 수 있다.
    """
    for path in reversed(paths):
        if path and os.path.isfile(path):
            return path
    return None


def cleanup_partials(paths: list[str]) -> None:
    """취소 시 받다 만 파일을 지운다.

    훅이 알려준 경로만 건드린다. 저장 폴더를 확장자로 훑어 지우면
    다른 프로그램이 만든 파일까지 지울 위험이 있다.
    """
    for path in paths:
        if not path:
            continue
        for junk in (path + ".part", path + ".ytdl", path):
            if os.path.isfile(junk):
                try:
                    os.remove(junk)
                except OSError:
                    pass


class DownloadWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, url, out_dir, filename, quality, ffmpeg_path, parent=None):
        super().__init__(parent)
        self._url = url
        self._out_dir = out_dir
        self._filename = filename
        self._quality = quality
        self._ffmpeg_path = ffmpeg_path
        self._cancelled = False
        self._seen_paths: list[str] = []
        self._stream_index = 0

    def cancel(self) -> None:
        """취소를 요청한다. 훅이 다음에 호출될 때 반영된다."""
        self._cancelled = True

    def _on_progress(self, d: dict) -> None:
        if self._cancelled:
            raise CancelledError()

        state = d.get("status")

        if state == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            if total:
                self.progress.emit(min(100, int(done * 100 / total)))
            self.status.emit(
                "영상 다운로드 중…" if self._stream_index == 0 else "음성 다운로드 중…"
            )

        elif state == "finished":
            path = d.get("filename")
            if path:
                self._seen_paths.append(path)
            self._stream_index += 1
            self.progress.emit(100)

    def _on_postprocessor(self, d: dict) -> None:
        if self._cancelled:
            raise CancelledError()

        if d.get("status") == "started":
            self.status.emit("병합 중…")

        info = d.get("info_dict") or {}
        path = info.get("filepath")
        if path:
            self._seen_paths.append(path)

    def run(self) -> None:
        try:
            from yt_dlp import YoutubeDL

            opts = build_ydl_opts(
                out_dir=self._out_dir,
                filename=self._filename,
                quality=self._quality,
                ffmpeg_path=self._ffmpeg_path,
                progress_hook=self._on_progress,
                postprocessor_hook=self._on_postprocessor,
            )

            self.status.emit("영상 정보 확인 중…")
            with YoutubeDL(opts) as ydl:
                ydl.download([self._url])

        except CancelledError:
            cleanup_partials(self._seen_paths)
            self.cancelled.emit()
            return

        except Exception as exc:
            # yt-dlp는 훅에서 던진 예외를 DownloadError로 감싸므로
            # 여기서 플래그를 한 번 더 확인해야 취소를 취소로 처리할 수 있다.
            if self._cancelled:
                cleanup_partials(self._seen_paths)
                self.cancelled.emit()
            else:
                self.failed.emit(friendly_error(exc))
            return

        final = pick_final_path(self._seen_paths)
        if final is None:
            self.failed.emit("다운로드는 끝났지만 저장된 파일을 찾지 못했습니다.")
            return

        self.progress.emit(100)
        self.status.emit("완료")
        self.finished_ok.emit(final)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_download_worker.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: 전체 테스트 확인**

Run: `python -m pytest -v`
Expected: PASS — 38 passed

- [ ] **Step 6: 커밋**

```bash
git add app/download_worker.py tests/test_download_worker.py
git commit -m "yt-dlp 다운로드 워커 구현"
```

---

### Task 7: 메인 창과 진입점

**Files:**
- Create: `app/main_window.py`
- Create: `main.py`

**Interfaces:**
- Consumes: `app.download_worker.DownloadWorker`, `app.ffmpeg_locator.locate_ffmpeg`, `app.ffmpeg_locator.FFmpegNotFoundError`, `app.options.QUALITY_FORMATS`, `app.options.DEFAULT_QUALITY`, `app.validation.validate_url`, `app.validation.validate_out_dir`
- Produces: `app.main_window.MainWindow(QMainWindow)`, `main.main()`

**참고:** 워커 참조를 `self._worker`에 반드시 보관해야 한다. 지역 변수로 두면 가비지 컬렉션되어 스레드가 중간에 죽는다. PyQt에서 가장 흔한 실수다.

- [ ] **Step 1: 메인 창 구현**

`app/main_window.py`:

```python
"""메인 창. 입력 수집과 시그널 배선만 담당한다."""

from __future__ import annotations

import os
import subprocess
import sys

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.download_worker import DownloadWorker
from app.ffmpeg_locator import FFmpegNotFoundError, locate_ffmpeg
from app.options import DEFAULT_QUALITY, QUALITY_FORMATS
from app.validation import validate_out_dir, validate_url


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YouTube 다운로더")
        self.setMinimumWidth(580)

        self._worker: DownloadWorker | None = None
        self._ffmpeg_path: str | None = None

        self._build_ui()
        self._check_ffmpeg()

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        form = QFormLayout()

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        form.addRow("URL", self.url_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("비워두면 영상 제목을 사용합니다")
        form.addRow("파일명", self.name_edit)

        self.quality_box = QComboBox()
        self.quality_box.addItems(list(QUALITY_FORMATS))
        self.quality_box.setCurrentText(DEFAULT_QUALITY)
        form.addRow("화질", self.quality_box)

        self.dir_edit = QLineEdit(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DesktopLocation
            )
        )
        self.browse_btn = QPushButton("찾아보기…")
        self.browse_btn.clicked.connect(self._choose_dir)

        dir_row = QHBoxLayout()
        dir_row.setContentsMargins(0, 0, 0, 0)
        dir_row.addWidget(self.dir_edit)
        dir_row.addWidget(self.browse_btn)
        dir_holder = QWidget()
        dir_holder.setLayout(dir_row)
        form.addRow("저장 위치", dir_holder)

        outer.addLayout(form)

        self.action_btn = QPushButton("추출")
        self.action_btn.setMinimumHeight(36)
        self.action_btn.clicked.connect(self._on_action)
        outer.addWidget(self.action_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        outer.addWidget(self.progress)

        self.status_label = QLabel("대기 중")
        outer.addWidget(self.status_label)

        self.setCentralWidget(central)

    def _check_ffmpeg(self) -> None:
        try:
            self._ffmpeg_path = locate_ffmpeg()
        except FFmpegNotFoundError as exc:
            self._ffmpeg_path = None
            self.action_btn.setEnabled(False)
            self.status_label.setText("ffmpeg 없음")
            QMessageBox.critical(self, "ffmpeg을 찾을 수 없습니다", str(exc))

    def _choose_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "저장 위치 선택", self.dir_edit.text()
        )
        if chosen:
            self.dir_edit.setText(chosen)

    def _on_action(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.status_label.setText("취소 중…")
            self.action_btn.setEnabled(False)
            self._worker.cancel()
            return
        self._start()

    def _start(self) -> None:
        url = self.url_edit.text().strip()
        out_dir = self.dir_edit.text().strip()

        for message in (validate_url(url), validate_out_dir(out_dir)):
            if message:
                QMessageBox.warning(self, "입력을 확인해 주세요", message)
                return

        # 지역 변수로 두면 가비지 컬렉션되어 스레드가 죽는다. 반드시 보관한다.
        self._worker = DownloadWorker(
            url=url,
            out_dir=out_dir,
            filename=self.name_edit.text().strip(),
            quality=self.quality_box.currentText(),
            ffmpeg_path=self._ffmpeg_path,
        )
        self._worker.progress.connect(self.progress.setValue)
        self._worker.status.connect(self.status_label.setText)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)

        self.progress.setValue(0)
        self._set_running(True)
        self._worker.start()

    def _set_running(self, running: bool) -> None:
        for widget in (
            self.url_edit,
            self.name_edit,
            self.quality_box,
            self.dir_edit,
            self.browse_btn,
        ):
            widget.setEnabled(not running)

        self.action_btn.setEnabled(True)
        self.action_btn.setText("취소" if running else "추출")

    def _on_finished(self, path: str) -> None:
        self._set_running(False)
        self.status_label.setText("완료")

        box = QMessageBox(self)
        box.setWindowTitle("완료")
        box.setText(f"저장했습니다.\n\n{path}")
        open_btn = box.addButton("폴더 열기", QMessageBox.ButtonRole.ActionRole)
        box.addButton("닫기", QMessageBox.ButtonRole.RejectRole)
        box.exec()

        if box.clickedButton() is open_btn:
            self._reveal(path)

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        self.progress.setValue(0)
        self.status_label.setText("실패")
        QMessageBox.critical(self, "다운로드 실패", message)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self.progress.setValue(0)
        self.status_label.setText("취소됨")

    @staticmethod
    def _reveal(path: str) -> None:
        target = os.path.normpath(path)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", target])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", target])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(target)])

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
```

- [ ] **Step 2: 진입점 작성**

`main.py`:

```python
"""YouTube 다운로더 진입점."""

import sys

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 앱이 뜨는지 확인**

Run: `python main.py`

Expected: 창이 뜨고 URL / 파일명 / 화질 / 저장 위치 / 추출 버튼 / 진행바 / "대기 중" 라벨이 보인다. 화질 드롭다운은 `1080p`가 선택돼 있고, 저장 위치에는 바탕화면 경로가 채워져 있다. 콘솔에 예외가 찍히지 않는다. 확인 후 창을 닫는다.

- [ ] **Step 4: 검증 동작 확인**

앱을 다시 실행하고 URL을 비운 채 "추출"을 누른다.

Expected: "URL을 입력해 주세요." 경고 창이 뜨고 다운로드가 시작되지 않는다. 창을 닫는다.

- [ ] **Step 5: 전체 테스트가 여전히 통과하는지 확인**

Run: `python -m pytest -v`
Expected: PASS — 38 passed

- [ ] **Step 6: 커밋**

```bash
git add app/main_window.py main.py
git commit -m "메인 창과 진입점 추가"
```

---

### Task 8: 실제 다운로드 종단 확인

**Files:** 없음 (수동 검증 태스크)

**Interfaces:**
- Consumes: Task 7까지의 전체 앱
- Produces: 없음

**참고:** 이 태스크는 코드를 만들지 않는다. 단위 테스트가 잡지 못하는 것 — 실제 yt-dlp 동작, 진행바 단계 전환, 취소, 병합 결과 — 을 확인하는 관문이다. 여기서 발견한 문제는 고친 뒤 다시 확인한다.

테스트에 쓸 영상: `https://www.youtube.com/live/3l8nOjIzI-A` (42분 강의, 영상·음성 분리 스트림이라 병합 경로를 반드시 지난다)

- [ ] **Step 1: 취소 동작 확인**

앱을 실행하고 위 URL, 화질 `480p`, 저장 위치는 임시 폴더를 지정한 뒤 "추출"을 누른다. 진행바가 움직이기 시작하면 "취소"를 누른다.

Expected:
- 상태 라벨이 `취소 중…` → `취소됨`으로 바뀐다
- 진행바가 0으로 돌아가고 입력 위젯이 다시 활성화된다
- 저장 폴더에 `.part`, `.ytdl`, `.f<숫자>.*` 파일이 남아 있지 않다

- [ ] **Step 2: 파일명 지정 다운로드 확인**

같은 URL, 화질 `480p`, 파일명에 `테스트/영상`을 입력하고 "추출"을 누른 뒤 끝까지 기다린다.

Expected:
- 상태 라벨이 `영상 정보 확인 중…` → `영상 다운로드 중…` → `음성 다운로드 중…` → `병합 중…` → `완료` 순으로 바뀐다
- 진행바가 되감기는 것처럼 보이는 구간은 있어도 최종적으로 100%에서 멈춘다
- 완료 창이 뜨고 "폴더 열기"를 누르면 탐색기가 해당 파일을 선택한 채 열린다
- 저장된 파일 이름이 `테스트영상.mp4`이다 (`/`가 제거됨, `⧸` 같은 유사 문자가 아님)

- [ ] **Step 3: 병합 결과 검증**

Run (경로는 실제 저장 위치로 바꾼다):

```bash
python -c "import imageio_ffmpeg,subprocess,sys; subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-i',sys.argv[1]])" "저장경로\테스트영상.mp4"
```

Expected: 출력에 `Video: h264` 스트림과 `Audio: aac` 스트림이 **둘 다** 보이고, `Duration`이 약 `00:42:2x`이다. 오디오 스트림이 없으면 병합이 실패한 것이므로 format 문자열을 다시 확인해야 한다.

- [ ] **Step 4: 충돌 회피 확인**

같은 파일명 `테스트/영상`으로 한 번 더 다운로드한다.

Expected: 기존 파일을 덮어쓰지 않고 `테스트영상 (1).mp4`가 새로 생긴다.

- [ ] **Step 5: 잘못된 URL 처리 확인**

URL에 `https://www.youtube.com/watch?v=aaaaaaaaaaa`(존재하지 않는 ID)를 넣고 추출한다.

Expected: 앱이 죽지 않고 "다운로드 실패" 창이 뜬다. 상태 라벨이 `실패`가 되고 입력 위젯이 다시 활성화된다.

- [ ] **Step 6: 확인 결과 기록 후 커밋**

Step 1~5에서 고친 내용이 있으면 이 시점에 커밋한다. 고칠 게 없었다면 커밋할 것이 없으므로 건너뛴다.

```bash
git status --short
```

---

### Task 9: exe 패키징

**Files:**
- Create: `build.spec`
- Modify: `.gitignore` (`build/`, `dist/`가 이미 있으면 그대로 둔다)

**Interfaces:**
- Consumes: Task 8까지 동작이 확인된 전체 앱
- Produces: `dist/yt-downloader.exe`

**참고:** imageio-ffmpeg의 바이너리 파일명은 `ffmpeg-win-x86_64-v7.1.exe`처럼 버전이 붙어 있다. 그런데 `ffmpeg_locator`는 번들 안에서 `ffmpeg.exe`를 찾는다. 그래서 spec에서 임시 폴더에 `ffmpeg.exe`라는 이름으로 복사한 뒤 그 파일을 포함시켜야 한다. 이 단계를 빠뜨리면 exe가 ffmpeg을 못 찾는다.

**참고:** yt-dlp는 extractor를 동적으로 import 하므로 PyInstaller의 정적 분석에 잡히지 않는다. `collect_submodules('yt_dlp.extractor')`로 명시해야 한다.

- [ ] **Step 1: PyInstaller 설치 확인**

Run: `python -m pip install --upgrade pyinstaller`
Expected: 설치 완료 (이미 설치돼 있으면 그대로 통과)

- [ ] **Step 2: 빌드 설정 작성**

`build.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import tempfile

import imageio_ffmpeg
from PyInstaller.utils.hooks import collect_submodules

# ffmpeg_locator가 번들 안에서 'ffmpeg.exe'를 찾으므로 그 이름으로 복사해 넣는다.
_staged_ffmpeg = os.path.join(tempfile.gettempdir(), "ffmpeg.exe")
shutil.copyfile(imageio_ffmpeg.get_ffmpeg_exe(), _staged_ffmpeg)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[(_staged_ffmpeg, ".")],
    datas=[],
    # yt-dlp는 extractor를 동적으로 import 하므로 정적 분석에 잡히지 않는다.
    hiddenimports=collect_submodules("yt_dlp.extractor"),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="yt-downloader",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
```

- [ ] **Step 3: 빌드 실행**

Run: `python -m PyInstaller build.spec --noconfirm`
Expected: 오류 없이 끝나고 `dist/yt-downloader.exe`가 생성된다. 빌드에 수 분이 걸리고 exe 용량은 100MB 내외다.

- [ ] **Step 4: exe 실행 확인**

Run: `dist\yt-downloader.exe`

Expected: 창이 뜬다. ffmpeg 관련 오류 창이 **뜨지 않아야** 한다. 뜬다면 Step 2의 ffmpeg 복사가 제대로 되지 않은 것이다.

- [ ] **Step 5: exe로 실제 다운로드 확인**

exe에서 `https://www.youtube.com/live/3l8nOjIzI-A`를 화질 `480p`로 다운로드한다.

Expected: 개발 환경과 동일하게 완료된다. `ModuleNotFoundError`가 나면 해당 모듈을 `build.spec`의 `hiddenimports`에 추가하고 Step 3부터 다시 한다.

- [ ] **Step 6: 커밋**

```bash
git add build.spec .gitignore
git commit -m "PyInstaller exe 빌드 설정 추가"
```

---

## 완료 기준

- `python -m pytest -v` 전체 통과 (38개)
- `python main.py`로 실행해 실제 영상 다운로드·취소·충돌 회피가 모두 동작
- `dist/yt-downloader.exe` 단독 실행으로 다운로드 성공
