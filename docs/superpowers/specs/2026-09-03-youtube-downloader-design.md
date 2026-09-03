# YouTube 다운로더 (PyQt6) 설계

작성일: 2026-09-03

## 1. 목적

YouTube URL을 붙여넣고 버튼 한 번으로 영상을 내려받는 데스크톱 GUI 프로그램. 명령줄 도구를 매번 치는 대신, 강의 영상처럼 반복해서 받는 콘텐츠를 클릭 몇 번으로 저장하는 것이 목표다.

## 2. 범위

### 포함하는 기능

- URL 입력창
- 파일명 설정 (비워두면 영상 원본 제목 사용)
- 화질 선택 드롭다운 (기본 1080p)
- 저장 위치 선택 (폴더 찾아보기)
- 추출 버튼 + 진행바 + 상태 표시
- 진행 중 취소

### 제외하는 기능 (YAGNI)

아래 항목은 의도적으로 만들지 않는다. 나중에 필요해지면 그때 별도 사이클로 추가한다.

- 자막 다운로드 및 음성인식(STT) 텍스트 생성
- 영상 길이 단위 분할
- 재생목록 일괄 다운로드
- 다중 URL 큐, 동시 다운로드
- 다운로드 이력 저장

## 3. 실행 환경

| 항목 | 값 |
|---|---|
| OS | Windows 11 |
| Python | 3.14.5 (`C:\Python314`) |
| GUI | PyQt6 6.11.0 |
| 다운로드 | yt-dlp (파이썬 라이브러리로 import) |
| 병합 | ffmpeg (imageio-ffmpeg 번들 바이너리) |
| 배포 | PyInstaller onefile exe |

GPU는 NVIDIA가 아닌 Intel Arc B390이지만, 음성인식을 제외했으므로 이 프로그램에는 영향이 없다.

## 4. 핵심 설계 결정

### 4.1 yt-dlp를 subprocess가 아니라 라이브러리로 import 한다

`yt_dlp.YoutubeDL`을 직접 import하고 `progress_hooks` 콜백으로 진행률을 받는다.

**이유:**
- 진행률을 바이트 단위 숫자로 직접 받으므로 stdout 텍스트를 정규식으로 파싱할 필요가 없다. yt-dlp 출력 형식이 바뀌어도 깨지지 않는다.
- PyInstaller가 yt-dlp를 파이썬 모듈로 통째 포함하므로 exe 안에 `yt-dlp.exe`를 따로 동봉하지 않아도 된다.

**대가:** 다운로드가 앱 프로세스 안에서 돌기 때문에 QThread 분리가 필수다. 워커에서 예외가 새면 앱 전체가 죽는다.

### 4.2 순수 로직과 Qt를 분리한다

`options.py`와 `ffmpeg_locator.py`는 Qt를 import하지 않는 순수 파이썬 모듈로 둔다. GUI 앱에서 가장 틀리기 쉬운 부분(포맷 문자열 조합, 파일명 처리, 경로 탐색)을 UI를 띄우지 않고 pytest로 검증하기 위해서다. UI는 입력을 모아 넘기고 시그널을 받아 그리는 역할만 한다.

### 4.3 진행바는 하나, 단계는 상태 라벨로 표시한다

영상과 음성이 분리된 DASH 스트림인 경우가 많아 yt-dlp 진행률이 0→100%를 두 번 반복한다. 그대로 진행바에 연결하면 되감기는 것처럼 보인다.

**해결:** 진행바는 전체 기준 하나만 두고, 현재 단계는 상태 라벨에 문자열로 표시한다.

```
영상 다운로드 중… → 음성 다운로드 중… → 병합 중… → 완료
```

`progress_hooks`로 다운로드 단계를, `postprocessor_hooks`로 병합 단계를 감지한다.

## 5. 프로젝트 구조

```
C:\mycode\yt-downloader\
├── main.py                  # 진입점, QApplication 부팅
├── app\
│   ├── __init__.py
│   ├── main_window.py       # UI 조립 + 시그널 배선
│   ├── download_worker.py   # QThread 워커, yt_dlp 구동
│   ├── options.py           # UI 입력 → yt-dlp opts 변환 (순수 함수)
│   └── ffmpeg_locator.py    # ffmpeg 경로 탐색 (순수 함수)
├── tests\
│   ├── test_options.py
│   └── test_ffmpeg_locator.py
├── requirements.txt
├── build.spec               # PyInstaller 설정
└── docs\superpowers\specs\
```

## 6. 컴포넌트

### 6.1 `ffmpeg_locator.py`

```python
def locate_ffmpeg() -> str
```

ffmpeg 실행 파일의 절대 경로를 반환한다. 탐색 순서:

1. exe로 빌드된 상태(`sys.frozen`)면 `sys._MEIPASS/ffmpeg.exe`
2. 개발 중이면 `imageio_ffmpeg.get_ffmpeg_exe()`
3. 시스템 PATH의 `ffmpeg`

셋 다 실패하면 `FFmpegNotFoundError`를 던진다.

의존성: `sys`, `shutil`, `imageio_ffmpeg`. Qt 없음.

### 6.2 `options.py`

```python
def sanitize_filename(name: str) -> str
def build_format_string(quality: str) -> str
def resolve_collision(out_dir: str, stem: str) -> str
def build_ydl_opts(url, out_dir, filename, quality, ffmpeg_path, progress_hook, postprocessor_hook) -> dict
```

**화질 → format 문자열 매핑**

| 드롭다운 선택 | format 문자열 |
|---|---|
| 최고화질 | `bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b` |
| 1080p (기본) | `bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]` |
| 720p | `bv*[height<=720][ext=mp4]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]` |
| 480p | `bv*[height<=480][ext=mp4]+ba[ext=m4a]/bv*[height<=480]+ba/b[height<=480]` |

mp4/m4a 조합을 먼저 시도하는 이유는 `merge_output_format`이 mp4이기 때문이다. VP9 영상과 Opus 음성을 mp4 컨테이너에 넣으면 remux가 실패하거나 재생 호환성이 떨어진다. mp4 조합이 없는 영상에 한해 뒤쪽 대체 문자열로 넘어간다.

**파일명 처리**

- 입력이 비어 있으면 `outtmpl`은 `%(title)s.%(ext)s`
- 입력이 있으면 `sanitize_filename()`을 거친 뒤 `<이름>.%(ext)s`
- Windows 금지문자 `\ / : * ? " < > |`는 제거한다. yt-dlp 기본값은 `/`를 `⧸`(U+29F8) 같은 유사 문자로 치환하는데, 일부 프로그램에서 문제가 되므로 직접 정리한다.
- 앞뒤 공백과 마침표를 제거하고, 살균 결과가 빈 문자열이면 원본 제목 템플릿으로 되돌린다.

**고정 옵션**

- `merge_output_format`: `mp4`
- `ffmpeg_location`: `locate_ffmpeg()` 결과
- `noplaylist`: `True` — 재생목록 URL을 넣어도 영상 하나만 받는다

**파일명 충돌 처리**

yt-dlp의 `overwrites=False`는 이미 파일이 있으면 다운로드를 건너뛸 뿐 이름을 바꿔주지 않는다. 따라서 충돌 회피는 직접 구현한다.

```python
def resolve_collision(out_dir: str, stem: str) -> str
```

`build_ydl_opts()`가 `outtmpl`을 만들기 전에 호출한다. `out_dir`에 `<stem>.*`과 일치하는 파일이 이미 있으면 `<stem> (1)`, `<stem> (2)` 순으로 비어 있는 이름을 찾아 반환한다. 확장자는 다운로드가 끝나야 확정되므로 확장자를 뺀 이름(stem) 기준으로 검사한다.

파일명을 비워둬서 원본 제목을 쓰는 경우에는 제목을 미리 알 수 없으므로 이 검사를 건너뛴다. 이때는 yt-dlp 기본 동작에 맡긴다.

### 6.3 `download_worker.py`

```python
class DownloadWorker(QThread):
    progress = pyqtSignal(int)      # 0-100
    status   = pyqtSignal(str)      # 단계 안내 문구
    finished = pyqtSignal(str)      # 저장된 파일 경로
    failed   = pyqtSignal(str)      # 사용자용 오류 메시지
```

`run()`에서 `YoutubeDL(opts).download([url])`을 호출한다.

**예외 처리:** `run()` 전체를 `try/except Exception`으로 감싸 모든 예외를 `failed` 시그널로 변환한다. QThread에서 예외가 밖으로 새면 프로세스가 죽기 때문에, 여기서 새는 예외가 하나도 없어야 한다.

**최종 파일 경로 확보:** `finished` 시그널에 넘길 경로는 훅에서 수집한다. `progress_hooks`가 `status == 'finished'`로 호출될 때의 `d['filename']`, 그리고 병합이 일어난 경우 `postprocessor_hooks`의 `d['info_dict']['filepath']`를 워커 인스턴스 변수에 계속 덮어써 둔다. 다운로드가 정상 종료되면 마지막으로 기록된 값이 최종 산출물 경로다. 병합 단계에서 중간 스트림 파일이 삭제되므로, 훅에서 받은 경로 중 실제로 존재하는 것을 골라 넘긴다.

**취소:** `cancel()`이 `self._cancelled = True`를 설정한다. `progress_hooks` 콜백이 매 호출마다 이 플래그를 확인하고, 설정돼 있으면 `CancelledError`를 던져 yt-dlp 내부 루프를 중단시킨다. 워커는 이 예외를 잡아 `failed` 대신 조용히 종료한다.

정리 대상은 훅에서 수집해 둔 경로를 기준으로 삼는다. 해당 파일과 같은 이름의 `.part`, `.ytdl`, `.f<포맷ID>.*` 중간 파일을 지운다. 저장 폴더 전체를 훑어 확장자로 지우는 방식은 쓰지 않는다. 다른 프로그램이 만든 파일을 지울 위험이 있다.

취소는 훅이 호출되는 시점에만 반응하므로 즉시가 아니라 최대 1초 내외의 지연이 있다. 이 정도는 허용한다.

### 6.4 `main_window.py`

**위젯 구성**

| 위젯 | 내용 |
|---|---|
| QLineEdit | URL |
| QLineEdit | 파일명 (placeholder: "비워두면 영상 제목 사용") |
| QComboBox | 화질 — 최고화질 / 1080p / 720p / 480p |
| QLineEdit + QPushButton | 저장 위치 + 찾아보기 (QFileDialog) |
| QPushButton | 추출 (진행 중에는 "취소"로 전환) |
| QProgressBar | 진행률 |
| QLabel | 상태 문구 |

**상태 전이**

- 대기 → 추출 중: 입력 위젯 전체 비활성화, 버튼 라벨을 "취소"로 변경
- 추출 중 → 완료: 입력 위젯 재활성화, `QMessageBox`로 저장 경로 안내 + "폴더 열기" 버튼
- 추출 중 → 취소/실패: 입력 위젯 재활성화, 진행바 초기화

저장 위치 기본값은 바탕화면(`QStandardPaths.DesktopLocation`)으로 둔다.

## 7. 데이터 흐름

```
사용자 입력
  → 입력 검증 (URL 형식, 폴더 쓰기 가능 여부)
  → build_ydl_opts()
  → DownloadWorker 시작
  → progress/status 시그널 → 진행바·라벨 갱신
  → finished 시그널 → 완료 안내
```

## 8. 에러 처리

| 상황 | 처리 |
|---|---|
| URL이 비었거나 `http`로 시작하지 않음 | 워커 시작 전 경고, 진행 안 함 |
| 저장 폴더가 없거나 쓰기 불가 | 워커 시작 전 경고 |
| ffmpeg을 찾을 수 없음 | 앱 시작 시점에 검사해 미리 안내 |
| 비공개·삭제·지역차단 영상 | yt-dlp `DownloadError`를 사용자 친화 문구로 변환 |
| 네트워크 끊김 | yt-dlp 자체 재시도 후 실패 메시지 |
| 파일명 충돌 | 덮어쓰지 않고 `(1)`, `(2)` 접미사 부여 |
| 워커 내부의 모든 예외 | `failed` 시그널로 변환, 앱은 계속 동작 |

## 9. 테스트

**단위 테스트 (pytest)**

- `test_options.py`
  - 화질 4종 각각이 올바른 format 문자열을 만드는지
  - 금지문자가 포함된 파일명이 제대로 살균되는지
  - 파일명이 비었을 때 `%(title)s.%(ext)s`로 떨어지는지
  - 살균 결과가 빈 문자열일 때 원본 제목 템플릿으로 되돌아가는지
  - `resolve_collision()`이 기존 파일이 있을 때 `(1)`, 둘 다 있을 때 `(2)`를 반환하는지 (tmp_path 사용)
- `test_ffmpeg_locator.py`
  - `sys.frozen`을 monkeypatch 했을 때 `_MEIPASS` 경로를 쓰는지
  - 아무것도 없을 때 `FFmpegNotFoundError`를 던지는지

**수동 확인**

실제 강의 영상 URL로 다운로드 1회를 끝까지 돌려 저장 결과와 진행바 동작을 확인한다. 다운로드 도중 취소 버튼을 눌러 중단과 `.part` 정리도 확인한다.

## 10. 패키징

- PyInstaller `--onefile --windowed`
- `ffmpeg.exe`를 `--add-binary`로 동봉 (약 80MB, 최종 exe는 100MB 내외 예상)
- yt-dlp는 extractor를 동적으로 로딩하므로 `hiddenimports` 보강이 필요할 수 있다. 빌드 후 실제 실행으로 확인한다.
- 빌드 설정은 `build.spec`에 둔다.
