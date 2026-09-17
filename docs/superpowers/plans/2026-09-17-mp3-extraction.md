# MP3 음성 추출 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `화질` 드롭다운에서 `MP3 320kbps` / `MP3 192kbps` / `MP3 128kbps`를 고르면 음성만 내려받아 선택한 고정 비트레이트의 MP3로 변환하고 제목·아티스트·날짜 태그를 넣는다.

**Architecture:** 드롭다운 문자열 하나(`quality`)가 영상/MP3를 모두 표현한다. `app/options.py`(Qt 없음)가 `is_audio_quality()`로 판정해 yt-dlp 옵션을 분기하고(`ba/b` + `FFmpegExtractAudio` + `FFmpegMetadata`), `DownloadWorker`는 같은 판정으로 상태 문구와 취소 정리 경로만 바꾼다. 큐·컨트롤러·목록 패널은 건드리지 않는다.

**Tech Stack:** Python 3.14, PyQt6 6.11, yt-dlp 2026.08.19, imageio-ffmpeg 번들 ffmpeg 7.1(libmp3lame 포함), pytest (Qt 위젯 테스트는 `QT_QPA_PLATFORM=offscreen`)

## Global Constraints

- 스펙: `docs/superpowers/specs/2026-09-17-mp3-extraction-design.md`.
- 드롭다운 항목과 순서는 정확히 `최고화질`, `1080p`, `720p`, `480p`, 구분선, `MP3 320kbps`, `MP3 192kbps`, `MP3 128kbps`. 기본 선택은 `1080p`, 라벨은 `화질`.
- 비트레이트 값은 문자열 `"320"`, `"192"`, `"128"`. MP3 format 문자열은 `"ba/b"`.
- MP3 후처리는 정확히 `[{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": <비트레이트>}, {"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": False}]` 순서. MP3 옵션에는 `merge_output_format` 키가 없다. 영상 옵션에는 `postprocessors` 키가 없고 나머지는 기존과 같다.
- 워커 상태 문구: MP3 다운로드는 항상 `음성 다운로드 중…`, MP3 후처리는 `MP3 변환 중…`. 영상 문구(`영상 다운로드 중…`/`음성 다운로드 중…`/`병합 중…`)는 그대로.
- `app/options.py`는 PyQt6를 import 하지 않는다.
- 변경하지 않는 파일: `app/queue.py`, `app/queue_controller.py`, `app/queue_panel.py`, `app/validation.py`, `app/errors.py`, `app/ffmpeg_locator.py`, `app/theme.py`, `build.spec`, `requirements.txt`, `tests/conftest.py`.
- `DownloadWorker`의 생성자·시그널은 바꾸지 않는다.
- 새 의존성 없음. 모든 UI 문구·주석·커밋 메시지는 한국어.
- 테스트 실행은 `python -m pytest`. 시작 기준선은 `91 passed`.

## 스펙 대비 변경 사항

1. **드롭다운 폭은 132 고정 유지.** 스펙 4장은 "잘리면 `max(132, sizeHint)`로 늘린다"고 했다. 실제 Windows 폰트에 테마를 적용해 측정하니 `MP3 320kbps` 글자 폭은 78px이고, 폭 132에서 QSS 좌우 패딩(12 + 28)과 테두리(2)를 뺀 글자 영역은 90px이라 잘리지 않는다. 반면 `sizeHint()`는 148이라 그 규칙을 쓰면 필요 없이 넓어진다. 따라서 `setFixedWidth(132)`는 그대로 두고, Task 3에서 실제 폰트로 다시 측정해 확인한다.
2. **드롭다운 폭 자동 테스트는 넣지 않는다.** 스펙 8장의 "`MP3 320kbps`가 폭 안에 들어감" 테스트는 offscreen 플랫폼의 대체 폰트로는 143px로 측정되어 실제와 다르다. 대신 Task 3 Step 6에서 실제 Windows 폰트로 측정 스크립트를 돌린다.

---

### Task 1: MP3 옵션 생성

**Files:**
- Modify: `app/options.py` (상수 추가, `build_format_string`, `build_ydl_opts`)
- Test: `tests/test_options.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `AUDIO_BITRATES: dict[str, str]` — `{"MP3 320kbps": "320", "MP3 192kbps": "192", "MP3 128kbps": "128"}`
  - `AUDIO_FORMAT: str` — `"ba/b"`
  - `is_audio_quality(quality: str) -> bool`
  - `build_format_string(quality: str) -> str` — MP3 항목이면 `AUDIO_FORMAT`
  - `build_ydl_opts(out_dir, filename, quality, ffmpeg_path, progress_hook=None, postprocessor_hook=None, match_filter=None) -> dict` — 시그니처 불변, MP3면 `postprocessors` 추가

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_options.py` 상단 import 블록을 다음으로 바꾼다.

```python
import os

import pytest

from app.options import (
    AUDIO_BITRATES,
    AUDIO_FORMAT,
    DEFAULT_QUALITY,
    QUALITY_FORMATS,
    TITLE_TEMPLATE,
    build_format_string,
    build_ydl_opts,
    is_audio_quality,
    resolve_collision,
    sanitize_filename,
)
```

파일 끝에 다음 테스트를 추가한다.

```python
def test_audio_bitrates_are_exactly_three_in_order():
    assert list(AUDIO_BITRATES) == ["MP3 320kbps", "MP3 192kbps", "MP3 128kbps"]
    assert list(AUDIO_BITRATES.values()) == ["320", "192", "128"]


def test_is_audio_quality_distinguishes_mp3_from_video():
    for quality in AUDIO_BITRATES:
        assert is_audio_quality(quality) is True, quality
    for quality in QUALITY_FORMATS:
        assert is_audio_quality(quality) is False, quality
    assert is_audio_quality("MP3") is False
    assert is_audio_quality("") is False


def test_build_format_string_for_mp3_prefers_audio_only_stream():
    assert AUDIO_FORMAT == "ba/b"
    for quality in AUDIO_BITRATES:
        assert build_format_string(quality) == "ba/b"


@pytest.mark.parametrize(
    "quality, bitrate",
    [("MP3 320kbps", "320"), ("MP3 192kbps", "192"), ("MP3 128kbps", "128")],
)
def test_build_opts_for_mp3_extracts_audio_and_writes_tags(tmp_path, quality, bitrate):
    opts = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="강의",
        quality=quality,
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert opts["format"] == "ba/b"
    assert "merge_output_format" not in opts
    assert opts["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": bitrate,
        },
        {"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": False},
    ]
    assert opts["outtmpl"] == os.path.join(str(tmp_path), "강의.%(ext)s")
    assert opts["ffmpeg_location"] == r"C:\ffmpeg.exe"
    assert opts["noplaylist"] is True


def test_build_opts_for_video_has_no_postprocessors(tmp_path):
    opts = build_ydl_opts(
        out_dir=str(tmp_path),
        filename="강의",
        quality="1080p",
        ffmpeg_path=r"C:\ffmpeg.exe",
    )
    assert "postprocessors" not in opts
    assert opts["merge_output_format"] == "mp4"
    assert opts["format"] == QUALITY_FORMATS["1080p"]
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_options.py -q`
Expected: 수집 단계에서 `ImportError: cannot import name 'AUDIO_BITRATES' from 'app.options'`

- [ ] **Step 3: 구현**

`app/options.py`에서 `DEFAULT_QUALITY = "1080p"` 줄 바로 아래(빈 줄 포함)에 추가한다.

```python
# MP3 항목. 값은 ffmpeg에 넘길 고정 비트레이트(kbps).
# YouTube 원본 음성은 대개 130~160kbps라 320kbps가 음질을 더 올려주지는 않는다.
AUDIO_BITRATES: dict[str, str] = {
    "MP3 320kbps": "320",
    "MP3 192kbps": "192",
    "MP3 128kbps": "128",
}
# 음성 전용 스트림을 우선 받고, 없으면 합본을 받아 음성만 뽑는다.
AUDIO_FORMAT = "ba/b"
```

`build_format_string`을 다음으로 바꾸고, 그 바로 위에 `is_audio_quality`를 추가한다.

```python
def is_audio_quality(quality: str) -> bool:
    """드롭다운 값이 MP3 항목인지 판정한다."""
    return quality in AUDIO_BITRATES


def build_format_string(quality: str) -> str:
    """화질 드롭다운 값을 yt-dlp format 문자열로 바꾼다."""
    if is_audio_quality(quality):
        return AUDIO_FORMAT
    try:
        return QUALITY_FORMATS[quality]
    except KeyError:
        raise ValueError(f"알 수 없는 화질입니다: {quality}") from None
```

`build_ydl_opts` 안의 `opts` 딕셔너리와 그 바로 뒤를 다음으로 바꾼다(`merge_output_format` 줄을 딕셔너리에서 빼고 분기로 옮긴다).

```python
    opts: dict = {
        "format": build_format_string(quality),
        "outtmpl": outtmpl,
        "ffmpeg_location": ffmpeg_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }

    if is_audio_quality(quality):
        # 받은 음성을 MP3로 바꾼 뒤 제목·아티스트(채널)·날짜 태그를 넣는다.
        # 챕터는 MP3 플레이어 대부분이 쓰지 않으므로 넣지 않는다.
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": AUDIO_BITRATES[quality],
            },
            {"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": False},
        ]
    else:
        opts["merge_output_format"] = "mp4"
```

`if progress_hook is not None:` 이하 훅 등록과 `return opts`는 그대로 둔다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_options.py -q`
Expected: 전부 PASS (기존 `test_quality_options_are_exactly_four_in_order`, `test_build_opts_fixed_options`, `test_build_format_string_rejects_unknown_quality` 포함)

Run: `python -m pytest -q`
Expected: `98 passed`

- [ ] **Step 5: 커밋**

```bash
git add app/options.py tests/test_options.py
git commit -m "옵션: MP3 320/192/128kbps 항목과 음성 추출·태그 후처리 옵션 추가"
```

---

### Task 2: 워커의 MP3 상태 문구와 취소 정리

**Files:**
- Modify: `app/download_worker.py` (import, `__init__`, `_on_progress`, `_on_postprocessor`)
- Test: `tests/test_download_worker.py`

**Interfaces:**
- Consumes: `app.options.is_audio_quality(quality: str) -> bool` (Task 1)
- Produces: 공개 계약 변경 없음. 내부 속성 `DownloadWorker._audio: bool` 추가. `_on_postprocessor`는 경로 기록을 취소 확인보다 먼저 한다.

**배경 (구현자가 알아야 할 yt-dlp 동작):** yt-dlp 2026.08.19의 후처리 훅은 `run()` 전에 복사한 `info_dict`를 `started`와 `finished` 모두에 넘긴다. 실제 이벤트는 다음 순서다.

```
ExtractAudio started   …\강의.webm
ExtractAudio finished  …\강의.webm     ← 이미 강의.mp3가 만들어졌지만 경로는 .webm
Metadata     started   …\강의.mp3
Metadata     finished  …\강의.mp3
```

그래서 `ExtractAudio finished`에서 취소되면 기존 코드는 `.mp3`를 모른 채 정리해 완성된 `.mp3`가 폴더에 남는다. `ExtractAudio` 훅에서 확장자만 `.mp3`로 바꾼 경로를 미리 기록해 둔다. `build_ydl_opts`의 충돌 검사가 시작 전에 같은 이름(확장자 무관)이 없음을 보장하므로, 이 예상 경로를 지워도 사용자의 기존 파일을 지울 일은 없다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_download_worker.py` 상단 import를 다음으로 바꾼다.

```python
import os

import pytest

from app.download_worker import (
    CancelledError,
    DownloadWorker,
    cleanup_partials,
    pick_final_path,
)
```

파일 끝에 다음을 추가한다.

```python
def _make_worker(quality: str, out_dir: str = "C:\\tmp") -> DownloadWorker:
    return DownloadWorker(
        url="https://example.com/v",
        out_dir=out_dir,
        filename="강의",
        quality=quality,
        ffmpeg_path="C:\\ffmpeg.exe",
    )


def _pp_event(status: str, postprocessor: str, path: str) -> dict:
    return {
        "status": status,
        "postprocessor": postprocessor,
        "info_dict": {"filepath": path},
    }


def test_audio_mode_download_status_is_audio_only():
    worker = _make_worker("MP3 192kbps")
    got: list[str] = []
    worker.status.connect(got.append)

    worker._on_progress(
        {
            "status": "downloading",
            "filename": "C:\\tmp\\강의.webm",
            "downloaded_bytes": 10,
            "total_bytes": 100,
        }
    )

    assert got == ["음성 다운로드 중…"]


def test_video_mode_first_stream_status_is_unchanged():
    worker = _make_worker("1080p")
    got: list[str] = []
    worker.status.connect(got.append)

    worker._on_progress(
        {
            "status": "downloading",
            "filename": "C:\\tmp\\강의.f137.mp4",
            "downloaded_bytes": 10,
            "total_bytes": 100,
        }
    )

    assert got == ["영상 다운로드 중…"]


@pytest.mark.parametrize(
    "quality, postprocessor, expected",
    [
        ("MP3 192kbps", "ExtractAudio", "MP3 변환 중…"),
        ("MP3 192kbps", "Metadata", "MP3 변환 중…"),
        ("1080p", "Merger", "병합 중…"),
    ],
)
def test_postprocessor_status_depends_on_mode(quality, postprocessor, expected):
    worker = _make_worker(quality)
    got: list[str] = []
    worker.status.connect(got.append)

    worker._on_postprocessor(_pp_event("started", postprocessor, "C:\\tmp\\강의.webm"))

    assert got == [expected]


def test_cancel_right_after_audio_conversion_records_mp3_for_cleanup():
    """ExtractAudio finished 훅은 .webm 경로만 준다. .mp3도 정리 대상에 들어가야 한다."""
    worker = _make_worker("MP3 192kbps")
    worker.cancel()

    with pytest.raises(CancelledError):
        worker._on_postprocessor(
            _pp_event("finished", "ExtractAudio", "C:\\tmp\\강의.webm")
        )

    assert "C:\\tmp\\강의.webm" in worker._seen_paths
    assert "C:\\tmp\\강의.mp3" in worker._seen_paths


def test_cancel_at_merge_still_records_merged_path():
    worker = _make_worker("1080p")
    worker.cancel()

    with pytest.raises(CancelledError):
        worker._on_postprocessor(_pp_event("finished", "Merger", "C:\\tmp\\강의.mp4"))

    assert worker._seen_paths == ["C:\\tmp\\강의.mp4"]


def test_video_mode_does_not_guess_mp3_path():
    worker = _make_worker("1080p")

    worker._on_postprocessor(_pp_event("started", "ExtractAudio", "C:\\tmp\\강의.webm"))

    assert worker._seen_paths == ["C:\\tmp\\강의.webm"]


def test_audio_hook_sequence_leads_pick_final_path_to_mp3(tmp_path):
    webm = str(tmp_path / "강의.webm")  # 변환 후 yt-dlp가 지운 상태
    mp3 = tmp_path / "강의.mp3"
    mp3.write_bytes(b"")
    worker = _make_worker("MP3 192kbps", out_dir=str(tmp_path))

    for status, postprocessor, path in [
        ("started", "ExtractAudio", webm),
        ("finished", "ExtractAudio", webm),
        ("started", "Metadata", str(mp3)),
        ("finished", "Metadata", str(mp3)),
    ]:
        worker._on_postprocessor(_pp_event(status, postprocessor, path))

    assert pick_final_path(worker._seen_paths) == str(mp3)
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_download_worker.py -q`
Expected: 새 테스트 중 다음이 FAIL
- `test_audio_mode_download_status_is_audio_only` (`['영상 다운로드 중…']`)
- `test_postprocessor_status_depends_on_mode[MP3 192kbps-ExtractAudio-MP3 변환 중…]`, `[MP3 192kbps-Metadata-MP3 변환 중…]` (`['병합 중…']`)
- `test_cancel_right_after_audio_conversion_records_mp3_for_cleanup` (`_seen_paths`가 비어 있음)
- `test_cancel_at_merge_still_records_merged_path` (`_seen_paths`가 비어 있음)

나머지(`video_mode_first_stream`, `Merger` 케이스, `does_not_guess`, `pick_final_path_to_mp3`)는 기존 동작의 회귀 방지용이라 이미 PASS여도 된다.

- [ ] **Step 3: 구현**

`app/download_worker.py` import에 추가한다.

```python
from app.errors import friendly_error
from app.options import build_ydl_opts, is_audio_quality
```

`__init__`에서 `self._quality = quality` 바로 아래에 추가한다.

```python
        self._audio = is_audio_quality(quality)
```

`_on_progress`의 `downloading` 분기에서 상태 emit을 다음으로 바꾼다.

```python
            self.status.emit(
                "영상 다운로드 중…"
                if self._stream_index == 0 and not self._audio
                else "음성 다운로드 중…"
            )
```

`_on_postprocessor` 전체를 다음으로 바꾼다.

```python
    def _on_postprocessor(self, d: dict) -> None:
        # 경로 기록을 취소 확인보다 먼저 한다. 변환 직후 취소돼도 결과 파일을 정리해야 한다.
        info = d.get("info_dict") or {}
        path = info.get("filepath")
        if path:
            self._seen_paths.append(path)
            if self._audio and d.get("postprocessor") == "ExtractAudio":
                # yt-dlp는 ExtractAudio의 finished 훅에도 변환 전 경로(.webm 등)를 넘긴다.
                # 변환 결과 .mp3 경로는 다음 후처리기에서야 보이므로 여기서 미리 기록한다.
                self._seen_paths.append(os.path.splitext(path)[0] + ".mp3")

        if self._cancelled:
            raise CancelledError()

        if d.get("status") == "started":
            self.status.emit("MP3 변환 중…" if self._audio else "병합 중…")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_download_worker.py -q`
Expected: 전부 PASS

Run: `python -m pytest -q`
Expected: `107 passed`

- [ ] **Step 5: 커밋**

```bash
git add app/download_worker.py tests/test_download_worker.py
git commit -m "워커: MP3 상태 문구, 변환 직후 취소 시 .mp3도 정리하도록 경로를 먼저 기록"
```

---

### Task 3: 드롭다운에 MP3 항목 추가

**Files:**
- Modify: `app/main_window.py` (import, `_build_ui`의 `quality_box` 채우기)
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `app.options.AUDIO_BITRATES` (Task 1)
- Produces: `MainWindow.quality_box` 항목 = 영상 4개, 구분선(인덱스 4), MP3 3개. `_enqueue`는 변경 없이 `currentText()`를 `quality`로 넘긴다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_main_window.py` 상단 import를 다음으로 바꾼다.

```python
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from app.main_window import MainWindow
from conftest import FakeWorker
```

파일 끝에 추가한다.

```python
def test_quality_box_lists_video_then_separator_then_mp3(window):
    box = window.quality_box
    assert [box.itemText(i) for i in range(box.count())] == [
        "최고화질",
        "1080p",
        "720p",
        "480p",
        "",
        "MP3 320kbps",
        "MP3 192kbps",
        "MP3 128kbps",
    ]
    separator = box.model().item(4)
    assert not (separator.flags() & Qt.ItemFlag.ItemIsSelectable)
    assert box.currentText() == "1080p"
    assert box.width() == 132


def test_enqueue_passes_mp3_quality_to_job(window, tmp_path):
    window.dir_edit.setText(str(tmp_path))
    window.url_edit.setText("https://www.youtube.com/watch?v=aaaaaaaaaaa")
    window.quality_box.setCurrentText("MP3 128kbps")
    window._enqueue()

    assert window._controller.job(1).quality == "MP3 128kbps"
    assert window.quality_box.currentText() == "MP3 128kbps", "화질 선택은 추가 후에도 유지된다"
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_main_window.py -q`
Expected: `test_quality_box_lists_video_then_separator_then_mp3` FAIL (항목이 4개뿐), `test_enqueue_passes_mp3_quality_to_job` FAIL (`setCurrentText`가 없는 항목이라 `quality`가 `1080p`)

- [ ] **Step 3: 구현**

`app/main_window.py`의 import를 바꾼다.

```python
from app.options import AUDIO_BITRATES, DEFAULT_QUALITY, QUALITY_FORMATS
```

`_build_ui`에서 `quality_box` 부분을 다음으로 바꾼다.

```python
        self.quality_box = QComboBox()
        self.quality_box.addItems(list(QUALITY_FORMATS))
        self.quality_box.insertSeparator(self.quality_box.count())
        self.quality_box.addItems(list(AUDIO_BITRATES))
        self.quality_box.setCurrentText(DEFAULT_QUALITY)
        # 실제 폰트에서 'MP3 320kbps'는 78px, 글자 영역은 132-12-28-2=90px이라 잘리지 않는다.
        self.quality_box.setFixedWidth(132)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_main_window.py -q`
Expected: 전부 PASS

Run: `python -m pytest -q`
Expected: `109 passed`

- [ ] **Step 5: 커밋**

```bash
git add app/main_window.py tests/test_main_window.py
git commit -m "메인 창: 화질 드롭다운에 구분선과 MP3 320/192/128kbps 항목 추가"
```

- [ ] **Step 6: 실제 폰트로 폭 확인 (커밋 없음)**

offscreen이 아닌 실제 Windows 플랫폼에서 측정한다. 창을 띄우지 않고 위젯만 만든다.

`$CLAUDE_JOB_DIR\tmp\mp3\measure_width.py`:

```python
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.theme import apply_theme

app = QApplication([])
apply_theme(app)
w = MainWindow()
box = w.quality_box
box.ensurePolished()
fm = box.fontMetrics()
widest = max(fm.horizontalAdvance(box.itemText(i)) for i in range(box.count()))
text_area = box.width() - 12 - 28 - 2
print(f"width={box.width()} widest={widest} text_area={text_area}")
print("WIDTH OK" if widest <= text_area else "WIDTH FAIL")
```

Run: `python <위 파일 경로>` (작업 폴더 `C:\MyCode\yt-downloader`에서, `QT_QPA_PLATFORM` 설정 없이)
Expected: `width=132 widest=78 text_area=90`, `WIDTH OK`. ffmpeg 경고창이 뜨면 안 된다(개발 환경에는 imageio-ffmpeg가 있다). `WIDTH FAIL`이면 `setFixedWidth(132)`를 `setFixedWidth(max(132, widest + 12 + 28 + 2))`로 바꾸고, Step 1 테스트의 `assert box.width() == 132`를 `assert box.width() >= 132`로 바꾼 뒤 Step 4를 다시 돌려 커밋한다.

---

### Task 4: 실제 영상으로 종단 확인

**Files:** 없음 (결함이 나오면 해당 모듈)

**Interfaces:**
- Consumes: Task 1~3까지의 전체 앱. `MainWindow._enqueue`, `quality_box`, `name_edit`, `url_edit`, `dir_edit`, `summary_label`, `queue_panel.row(id).status_label`, `_controller.job(id)`, `_controller._worker`, `_controller._active_id`, `_reveal`, `_on_reveal_requested`.
- Produces: 없음

**참고:** 단위 테스트가 못 잡는 것을 확인한다. 실제 yt-dlp·ffmpeg로 `.mp3`만 남는지, 태그·비트레이트가 들어가는지, 영상/MP3가 섞여 순차 실행되는지, 그리고 **변환 도중 취소 시 `.mp3`가 남지 않는지**(Task 2의 결함 수정). 취소는 워커의 `status` 시그널에 `DirectConnection`으로 붙여, 워커 스레드가 `MP3 변환 중…`을 보내는 바로 그 순간 `cancel()`을 호출한다. 그러면 다음 취소 확인 지점이 정확히 `ExtractAudio finished` 훅이 된다.

- [ ] **Step 1: 하네스 작성**

`$CLAUDE_JOB_DIR\tmp\mp3\mp3_e2e.py` (`$CLAUDE_JOB_DIR`은 실행 중인 세션의 작업 폴더):

```python
import os
import re
import subprocess
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"C:\MyCode\yt-downloader")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.ffmpeg_locator import locate_ffmpeg
from app.main_window import MainWindow
from app.theme import apply_theme

URL = "https://www.youtube.com/live/3l8nOjIzI-A"
VIDEO_TITLE = "웹프로그래밍(09/03)"

app = QApplication([])
apply_theme(app)
for name in ("warning", "critical", "information"):
    setattr(QMessageBox, name, staticmethod(lambda *a, **k: print("DIALOG", a[1:3])))

out_dir = tempfile.mkdtemp(prefix="dl_mp3_")
print("OUT", out_dir)
w = MainWindow()
w._controller.inter_job_delay_ms = 0
w.show()


def report(n, ok, why=""):
    print(f"STEP {n} {'OK' if ok else 'FAIL ' + why}", flush=True)


def status_of(job_id):
    row = w.queue_panel.row(job_id)
    return row.status_label.text() if row else None


def wait_until(pred, timeout):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if pred():
            return True
        time.sleep(0.05)
    return False


def files_with(prefix):
    return sorted(f for f in os.listdir(out_dir) if f.startswith(prefix))


def probe(path):
    ffmpeg = locate_ffmpeg()
    err = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", path], capture_output=True, text=True, encoding="utf-8"
    ).stderr
    tags = dict(re.findall(r"^\s{4}(title|artist|date)\s*:\s*(.+)$", err, re.M))
    m = re.search(r"bitrate:\s*(\d+)\s*kb/s", err)
    return tags, int(m.group(1)) if m else None


def enqueue(name, quality):
    w.dir_edit.setText(out_dir)
    w.url_edit.setText(URL)
    w.name_edit.setText(name)
    w.quality_box.setCurrentText(quality)
    w._enqueue()


# STEP 1: 세 작업 투입
enqueue("음성1", "MP3 192kbps")
enqueue("영상1", "480p")
enqueue("음성취소", "MP3 128kbps")
report(1, w.summary_label.text() == "대기 2 · 추출 중 1 · 완료 0", w.summary_label.text())

# STEP 2: 작업 1 완료 → .mp3 하나만 남음
done = wait_until(lambda: status_of(1) in ("완료", "실패", "취소됨"), 900)
left = files_with("음성1")
report(2, done and status_of(1) == "완료" and left == ["음성1.mp3"], f"{status_of(1)} {left}")

# STEP 3: 태그와 비트레이트
tags, kbps = probe(os.path.join(out_dir, "음성1.mp3"))
ok = (
    tags.get("title") == VIDEO_TITLE
    and bool(tags.get("artist"))
    and re.fullmatch(r"\d{8}", tags.get("date", "")) is not None
    and kbps is not None
    and 185 <= kbps <= 200
)
report(3, ok, f"{tags} {kbps}kb/s")

# STEP 4: 작업 2(영상) 완료 → .mp4
done = wait_until(lambda: status_of(2) in ("완료", "실패", "취소됨"), 900)
left = files_with("영상1")
report(4, done and status_of(2) == "완료" and left == ["영상1.mp4"], f"{status_of(2)} {left}")

# STEP 5: 작업 3 시작 직후 status에 직접 연결, 변환 시작 순간 취소
started = wait_until(lambda: w._controller._active_id == 3 and w._controller._worker is not None, 60)
worker = w._controller._worker if started else None
if worker is not None:
    worker.status.connect(
        lambda s: worker.cancel() if s == "MP3 변환 중…" else None,
        Qt.ConnectionType.DirectConnection,
    )
done = wait_until(lambda: status_of(3) in ("완료", "실패", "취소됨"), 900)
time.sleep(1)
left = files_with("음성취소")
recorded_mp3 = worker is not None and any(p.endswith("음성취소.mp3") for p in worker._seen_paths)
report(5, done and status_of(3) == "취소됨" and left == [] and recorded_mp3,
       f"{status_of(3)} left={left} recorded_mp3={recorded_mp3} "
       f"seen={worker._seen_paths if worker else None}")

# STEP 6: 요약
wait_until(lambda: not w._controller.is_busy(), 30)
report(6, w.summary_label.text() == "대기 0 · 추출 중 0 · 완료 2 · 취소 1", w.summary_label.text())

# STEP 7: 작업 1 더블클릭 동작 → .mp3 경로
revealed = []
w._reveal = lambda p: revealed.append(p)
w._on_reveal_requested(1)
report(7, len(revealed) == 1 and revealed[0].endswith("음성1.mp3"), str(revealed))

# STEP 8: 창 닫힘
w.close()
app.processEvents()
report(8, not w.isVisible())

for f in os.listdir(out_dir):
    os.remove(os.path.join(out_dir, f))
os.rmdir(out_dir)
print("END")
```

- [ ] **Step 2: 실행 및 판정**

Run (백그라운드, 로그 파일로): `python -u $CLAUDE_JOB_DIR\tmp\mp3\mp3_e2e.py > $CLAUDE_JOB_DIR\tmp\mp3\mp3_e2e.log 2>&1`
완료 알림이 오면 로그를 읽는다.

Expected: `STEP 1 OK` ~ `STEP 8 OK`, `END`, `DIALOG` 줄 없음.

실패 시:
- 로그의 `FAIL` 이유로 원인을 가린다. 몇 줄짜리 코드 결함이면 해당 모듈에서 실패 단위 테스트부터 추가해 고치고, `python -m pytest -q`와 하네스를 다시 돌린다.
- STEP 3의 `artist`가 비었으면 이 영상의 채널 정보(`uploader`)가 없는 경우일 수 있다. 로그의 태그 딕셔너리를 보고 설계 문제인지 판단해 보고한다.
- STEP 5가 `취소됨`인데 `recorded_mp3=False`면, `ExtractAudio`보다 먼저 다른 후처리기(Fixup 등)가 `MP3 변환 중…`을 보내 그 시점에 취소된 것이다. 로그의 `seen=` 목록으로 확인하고, 그 경우 `.mp3`가 만들어지기 전 취소라 정리 대상이 아니므로 결함이 아니다. 판정을 보고에 적는다.
- STEP 5가 `완료`로 끝났으면 `DirectConnection` 연결 전에 변환이 시작된 경쟁 상황이다. 연결 시점을 로그로 확인하고 한 번 재실행한다.
- 설계 변경이 필요한 문제는 고치지 말고 보고한다.

- [ ] **Step 3: 커밋 (수정이 있었을 때만)**

```bash
git status --short
```

수정이 있으면 변경 파일만 `git add` 후 `git commit -m "종단 확인에서 발견한 <내용> 수정"`처럼 실제 내용을 적어 커밋한다.

---

### Task 5: exe 재빌드와 번들 확인

**Files:** 없음 (`build.spec` 변경 없음)

- [ ] **Step 1: 잔존 프로세스 정리 후 빌드**

```powershell
Get-Process -Name yt-downloader -ErrorAction SilentlyContinue | Stop-Process -Force
```

Run: `python -m PyInstaller build.spec --noconfirm` (타임아웃 600000)
Expected: 로그에 `Building EXE from EXE-00.toc completed successfully.`, `dist\yt-downloader.exe`의 수정 시각이 마지막 커밋보다 나중.

- [ ] **Step 2: 번들 확인**

`$CLAUDE_JOB_DIR\tmp\mp3\check_bundle.py`:

```python
import marshal

from PyInstaller.archive.readers import CArchiveReader

EXE = r"C:\MyCode\yt-downloader\dist\yt-downloader.exe"
archive = CArchiveReader(EXE)
pyz = archive.open_embedded_archive("PYZ.pyz")


def names(code):
    found = set(code.co_names) | {code.co_name}
    for const in code.co_consts:
        if hasattr(const, "co_code"):
            found |= names(const)
    return found


options_code = pyz.extract("app.options")
if isinstance(options_code, bytes):
    options_code = marshal.loads(options_code)
consts = set()


def walk(code):
    for const in code.co_consts:
        if hasattr(const, "co_code"):
            walk(const)
        elif isinstance(const, str):
            consts.add(const)


walk(options_code)
print("options has is_audio_quality:", "is_audio_quality" in names(options_code))
print("options has MP3 320kbps:", "MP3 320kbps" in consts)
print("options has FFmpegExtractAudio:", "FFmpegExtractAudio" in consts)
pp = [n for n in pyz.toc if n.startswith("yt_dlp.postprocessor.ffmpeg")]
print("yt_dlp ffmpeg postprocessor bundled:", bool(pp))
```

Run: `python $CLAUDE_JOB_DIR\tmp\mp3\check_bundle.py`
Expected: 네 줄 모두 `True`. `pyz.extract`가 bytes가 아닌 코드 객체를 돌려주는 PyInstaller 버전이면 위 분기가 처리한다. API가 달라 예외가 나면 `dir(archive)`/`dir(pyz)`로 메서드 이름을 확인해 같은 검사를 한다.

그 다음 `QT_QPA_PLATFORM=offscreen`으로 exe를 띄워 8초 뒤 프로세스가 살아 있는지, 최신 `%TEMP%\_MEI*` 폴더에 `ffmpeg.exe`가 있는지 확인하고 종료한다.

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$p = Start-Process -FilePath "C:\MyCode\yt-downloader\dist\yt-downloader.exe" -PassThru
Start-Sleep -Seconds 8
"alive: $(-not $p.HasExited)"
$mei = Get-ChildItem $env:TEMP -Directory -Filter "_MEI*" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
"ffmpeg: $(Test-Path (Join-Path $mei.FullName 'ffmpeg.exe'))"
Get-Process -Name yt-downloader -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item Env:QT_QPA_PLATFORM
```

Expected: `alive: True`, `ffmpeg: True`

- [ ] **Step 3: 커밋할 것 없음**

`build/`, `dist/`는 git 추적 대상이 아니다.

---

## 완료 기준

- `python -m pytest -q` → `109 passed`
- Task 3 Step 6 실제 폰트 측정 `WIDTH OK`
- 종단 하네스 STEP 1~8 OK (MP3 192kbps 완료·태그·비트레이트, 영상 480p 완료, MP3 변환 순간 취소 후 파일 없음)
- `dist\yt-downloader.exe` 재빌드, 번들 검사 전부 `True`, 실행 8초 생존
