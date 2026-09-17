# MP3 음성 추출 설계

작성일: 2026-09-17
선행 스펙: `2026-09-03-youtube-downloader-design.md`(단일 다운로드), `2026-09-04-download-queue-design.md`(추출 목록). 이 문서는 그 위에 덧붙이는 변경만 다룬다.

## 1. 목적

영상 대신 음성만 MP3 파일로 받을 수 있게 한다. 강의·팟캐스트처럼 들을 콘텐츠를 휴대폰이나 플레이어에 넣어 쓰는 용도다. 사용 흐름(주소 붙여넣기 → `추출`)은 바꾸지 않고, `화질` 드롭다운에서 MP3 항목을 고르는 것만으로 동작한다.

## 2. 범위

### 포함
- `화질` 드롭다운에 `MP3 320kbps` / `MP3 192kbps` / `MP3 128kbps` 추가 (영상 항목과 구분선으로 나눔)
- 음성 스트림만 내려받아 선택한 고정 비트레이트(CBR)의 MP3로 변환
- MP3에 제목·아티스트(채널명)·날짜 태그 기록
- 워커 `status` 시그널의 MP3 단계 문구: `음성 다운로드 중…` → `MP3 변환 중…` → `완료` (현재 목록 행은 이 문구를 표시하지 않고 `추출 중`만 보인다. 5.2 참고)
- 영상 작업과 MP3 작업을 한 추출 목록에 섞어 순차 실행
- 변환 직후 취소 시 `.mp3`가 남지 않도록 정리

### 제외 (YAGNI)
- 썸네일 앨범 아트 삽입
- mp3 이외 음성 형식(m4a, opus, wav 등)
- VBR 음질 선택
- 확장자별 파일 이름 충돌 검사 (5.1 참고)

## 3. 핵심 설계 결정

### 3.1 드롭다운 항목 하나 = 작업 설정 하나

MP3 여부와 비트레이트를 별도 필드로 두지 않고, 기존 `quality` 문자열 하나에 담는다. `Job.quality`, `DownloadQueue`, `QueueController`, `QueuePanel`, `DownloadWorker` 생성자, 테스트의 `FakeWorker`는 변경하지 않는다. 문자열이 영상인지 MP3인지는 `options.is_audio_quality()` 하나로 판정한다.

### 3.2 비트레이트는 원본보다 높여도 음질이 좋아지지 않는다

YouTube 원본 음성은 대개 opus 약 130~160kbps 또는 AAC 128kbps다. 320kbps는 원본 이상의 음질을 만들지 못하고 파일만 커진다. 그래도 사용자가 용량/호환성 기준으로 고를 수 있게 세 단계를 둔다.

### 3.3 번들 ffmpeg으로 충분하다 (검증함)

imageio-ffmpeg 번들(`ffmpeg-win-x86_64-v7.1.exe`)에 `libmp3lame` 인코더가 있다. ffprobe가 없어도 yt-dlp의 `FFmpegExtractAudioPP`는 `ffmpeg -i` 출력으로 코덱을 알아내 변환에 성공한다. 3초 opus webm으로 `FFmpegExtractAudioPP(mp3, 192)` → `FFmpegMetadataPP`를 실행해 `.mp3`만 남고, 비트레이트 194kb/s, 한글 제목·아티스트·날짜 태그가 들어가는 것을 확인했다. 새 의존성은 없다.

### 3.4 yt-dlp 후처리 훅은 변환 결과 경로를 늦게 알려준다 (검증함)

yt-dlp(2026.08.19)의 후처리 훅은 `run()` 전에 복사한 `info_dict`를 `started`와 `finished` 모두에 넘긴다. 그래서 `ExtractAudio`의 `finished`에서도 `filepath`는 변환 전 경로(`.webm`)이고, `.mp3` 경로는 다음 단계인 `Metadata`의 `started`에서 처음 보인다. 실제 이벤트 순서:

```
ExtractAudio started   …\probe.webm
ExtractAudio finished  …\probe.webm
Metadata     started   …\probe.mp3
Metadata     finished  …\probe.mp3
```

`ExtractAudio finished` 시점에 취소가 걸리면 워커는 `.mp3`를 기록하지 못한 채 정리하므로 완성된 `.mp3`가 남는다. 영상 병합은 `Merger started`가 이미 최종 `.mp4` 경로를 주므로 이 문제가 없다. 해결은 5.2.

## 4. 레이아웃

창 크기·배치는 그대로다. 드롭다운 내용만 바뀐다.

```
파일 이름                  화질
[                    ]   [ 1080p        ▾ ]
                           최고화질
                           1080p            ← 기본값 유지
                           720p
                           480p
                           ────────────
                           MP3 320kbps
                           MP3 192kbps
                           MP3 128kbps
```

- 라벨은 `화질` 그대로.
- 드롭다운 폭은 기존 132를 유지하되, `MP3 320kbps`가 잘리면 `max(132, quality_box.sizeHint().width())`로 늘린다. 늘어난 만큼 파일 이름 칸이 줄어든다(파일 이름 칸은 stretch 1).
- 목록 행 표시는 바뀌지 않는다(형식 표시 뱃지 없음). 끝난 파일 확장자는 탐색기에서 확인한다.

## 5. 컴포넌트

### 5.1 `app/options.py`

```python
AUDIO_BITRATES: dict[str, str] = {
    "MP3 320kbps": "320",
    "MP3 192kbps": "192",
    "MP3 128kbps": "128",
}
AUDIO_FORMAT = "ba/b"

def is_audio_quality(quality: str) -> bool     # quality in AUDIO_BITRATES
```

- `QUALITY_FORMATS`(영상 4개)와 `DEFAULT_QUALITY = "1080p"`는 변경하지 않는다.
- `build_format_string(quality)`: 영상 항목이면 기존대로, MP3 항목이면 `AUDIO_FORMAT`, 둘 다 아니면 기존처럼 `ValueError`.
- `build_ydl_opts(...)`: 시그니처 변경 없음. `outtmpl`, `ffmpeg_location`, `noplaylist`, `quiet` 등 공통 옵션과 훅 등록은 기존과 같다. 분기:
  - 영상: 기존과 동일(`merge_output_format: "mp4"` 포함).
  - MP3: `merge_output_format` 키를 넣지 않고 다음을 추가한다.
    ```python
    "postprocessors": [
        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
         "preferredquality": AUDIO_BITRATES[quality]},
        {"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": False},
    ]
    ```
- `ba/b`: 음성 전용 스트림을 우선 받고, 없으면 합본을 받아 음성을 추출한다.
- 파일 이름 충돌 검사(`resolve_collision`)는 확장자 무시 방식을 유지한다. 같은 폴더에 `강의.mp4`가 있으면 MP3는 `강의 (1).mp3`가 된다. 확장자별로 검사하면 같은 이름의 `.webm`이 남아 있을 때 yt-dlp가 다운로드를 건너뛰고 그 파일을 변환해 '완료'가 거짓이 될 수 있으므로 택하지 않는다.

### 5.2 `app/download_worker.py`

생성자·시그널 변경 없음. 생성 시 `self._audio = is_audio_quality(quality)`.

**상태 문구**

| 단계 | 영상 | MP3 |
|---|---|---|
| 정보 확인 | `영상 정보 확인 중…` | `영상 정보 확인 중…` |
| 다운로드 (`_on_progress`, downloading) | 첫 스트림 `영상 다운로드 중…`, 이후 `음성 다운로드 중…` | 항상 `음성 다운로드 중…` |
| 후처리 (`_on_postprocessor`, started) | `병합 중…` | `MP3 변환 중…` |
| 끝 | `완료` | `완료` |

이 문구는 `status` 시그널로만 나간다. `QueueController`는 추출 목록 스펙 5.2대로 `status`를 연결하지 않으므로 목록 행에는 `추출 중`과 진행률만 보인다. 행에 단계 문구를 보여주는 것은 이번 범위가 아니다.

MP3 모드의 후처리 문구는 후처리기 종류(`ExtractAudio`, `Metadata`, 그 밖의 Fixup 등)와 무관하게 `MP3 변환 중…` 하나로 표시한다.

**`_on_postprocessor` 순서 변경: 경로 기록 → 취소 확인**

```python
def _on_postprocessor(self, d):
    info = d.get("info_dict") or {}
    path = info.get("filepath")
    if path:
        self._seen_paths.append(path)
        if self._audio and d.get("postprocessor") == "ExtractAudio":
            self._seen_paths.append(os.path.splitext(path)[0] + ".mp3")
    if self._cancelled:
        raise CancelledError()
    if d.get("status") == "started":
        self.status.emit("MP3 변환 중…" if self._audio else "병합 중…")
```

- 기존 코드는 취소 확인 후 경로를 기록했다. 순서를 바꿔도 영상 경로에는 영향이 없다(정리 대상에 같은 경로가 한 번 더 들어갈 뿐이고, `cleanup_partials`는 없는 파일을 무시한다).
- 예상 `.mp3` 경로는 `FFmpegExtractAudioPP`가 `replace_extension(path, "mp3")`로 만드는 경로와 같다.
- 정상 완료 시 `pick_final_path`는 기록 목록을 뒤에서부터 보며 실제로 있는 파일을 고르므로, 원본 `.webm`이 지워진 뒤 남은 `.mp3`가 선택된다. 변경 없음.

### 5.3 `app/main_window.py`

- `from app.options import AUDIO_BITRATES, DEFAULT_QUALITY, QUALITY_FORMATS`
- 드롭다운 채우기:
  ```python
  self.quality_box.addItems(list(QUALITY_FORMATS))
  self.quality_box.insertSeparator(self.quality_box.count())
  self.quality_box.addItems(list(AUDIO_BITRATES))
  self.quality_box.setCurrentText(DEFAULT_QUALITY)
  ```
- 폭 규칙은 4장.
- `_enqueue`는 변경 없음. `quality_box.currentText()`가 그대로 `quality`로 넘어간다(구분선은 선택할 수 없다).

### 5.4 변경하지 않는 것

`app/queue.py`, `app/queue_controller.py`, `app/queue_panel.py`, `app/validation.py`, `app/errors.py`, `app/ffmpeg_locator.py`, `app/theme.py`, `build.spec`, `requirements.txt`, `tests/conftest.py`.

## 6. 데이터 흐름

```
화질 드롭다운 "MP3 192kbps" 선택 → 추출 클릭 → controller.enqueue(quality="MP3 192kbps")
  → (기존 큐 흐름) → DownloadWorker(quality="MP3 192kbps"), _audio=True
  → build_ydl_opts: format "ba/b" + postprocessors [ExtractAudio 192, Metadata]
  → 다운로드 훅: "음성 다운로드 중…", 진행률
  → 후처리 훅: 경로 기록(.webm, 예상 .mp3) → 취소 확인 → "MP3 변환 중…"
  → pick_final_path → …\제목.mp3 → finished_ok → 목록 행 "완료", 더블클릭 시 .mp3 선택
```

## 7. 에러 처리

| 상황 | 처리 |
|---|---|
| 변환 실패(손상된 스트림, ffmpeg 오류) | 워커가 `failed`로 변환, 해당 행만 `실패`(툴팁에 `friendly_error` 문구), 다음 작업 계속 |
| 다운로드 중 취소 | 기존과 동일하게 받던 파일 정리 |
| 변환 직후(`ExtractAudio finished`) 취소 | 예상 `.mp3` 경로가 이미 기록돼 있어 `.webm`과 `.mp3` 모두 정리 |
| 태그 기록 시작 시 취소 | `Metadata started`에서 `.mp3` 기록 후 취소 → 정리. 태그 기록용 `.temp.mp3`는 `run()` 안에서 만들고 끝나기 전에 교체되므로, 훅 시점에는 남아 있지 않다 |
| 음성 전용 스트림 없음 | `ba/b`의 `b`로 합본을 받아 음성 추출 |
| 같은 이름 파일이 이미 있음 | 확장자와 무관하게 ` (n)` 붙임 (5.1) |

## 8. 테스트

**`tests/test_options.py` (Qt 없음)**
- `list(AUDIO_BITRATES) == ["MP3 320kbps", "MP3 192kbps", "MP3 128kbps"]`, 값은 `"320"`, `"192"`, `"128"`
- `is_audio_quality`: MP3 세 항목은 True, 영상 네 항목과 알 수 없는 문자열은 False
- `build_format_string("MP3 192kbps") == "ba/b"`, 알 수 없는 항목은 여전히 `ValueError`
- MP3 옵션: `format == "ba/b"`, `"merge_output_format" not in opts`, `postprocessors`가 `[ExtractAudio(mp3, 해당 비트레이트), Metadata(add_metadata=True, add_chapters=False)]` 순서
- 영상 옵션에는 `postprocessors` 키가 없음
- 기존 영상 테스트(`test_quality_options_are_exactly_four_in_order` 등)는 수정 없이 통과

**`tests/test_download_worker.py` (Qt, 네트워크 없음)** — 훅을 직접 호출하는 기존 방식
- MP3 모드 `_on_progress`(downloading): `status`가 `음성 다운로드 중…`
- MP3 모드 `_on_postprocessor`(started): `status`가 `MP3 변환 중…`; 영상 모드는 `병합 중…`
- MP3 모드에서 취소 플래그를 세운 뒤 `ExtractAudio finished`(`filepath=…\a.webm`) 호출 → `CancelledError`가 나고 `_seen_paths`에 `…\a.webm`과 `…\a.mp3`가 모두 있음
- 영상 모드에서 `ExtractAudio` 이름이 와도 예상 `.mp3`를 추가하지 않음

**`tests/test_main_window.py` (헤드리스)**
- 드롭다운 항목 텍스트 순서: 영상 4개, 구분선 1개(인덱스 4, 텍스트 빈 문자열), MP3 3개
- 기본 선택 `1080p`
- `MP3 320kbps` 텍스트가 드롭다운 폭 안에 들어감(`fontMetrics().horizontalAdvance(...)` + 좌우 여백 ≤ 폭)

**종단 확인 (실제 네트워크, 수동 하네스)**
1. 짧은 공개 영상 하나를 `MP3 192kbps`로 추출 → 저장 폴더에 `.mp3` 하나만 남음, `.webm`/`.part` 없음, ffmpeg으로 title/artist/date 태그와 약 192kb/s 확인, 행 `완료`, 더블클릭 시 `.mp3` 선택
2. 목록에 `1080p` 영상 → `MP3 128kbps` → `MP3 320kbps` 순으로 투입해 모두 순차 완료, 요약 `대기 0 · 추출 중 0 · 완료 3`
3. MP3 작업의 후처리가 시작된 뒤(하네스에서 워커 `status`가 `MP3 변환 중…`을 보낸 순간) 컨트롤러 `cancel_or_remove` → `취소됨`, 폴더에 해당 작업 파일이 남지 않음

## 9. 기존 스펙과의 관계

- 선행 스펙 2장의 제외 목록과 충돌하지 않는다(음성 추출은 명시적으로 제외되지 않았다).
- `DownloadWorker`, `DownloadQueue`, `QueueController`의 공개 계약은 유지된다. 워커 내부의 후처리 훅 처리 순서만 바뀐다(5.2).
- 선행 스펙 4.3의 "단계는 상태 라벨로 표시" 원칙을 MP3 단계 문구에도 그대로 적용한다. 추출 목록 스펙 이후 이 문구는 행에 표시되지 않지만 워커의 `status` 시그널 계약은 유지한다.
