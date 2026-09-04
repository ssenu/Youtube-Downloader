# 추출 목록(순차 다운로드 큐) 설계

작성일: 2026-09-04
선행 스펙: `2026-09-03-youtube-downloader-design.md` (단일 다운로드 앱). 이 문서는 그 위에 덧붙이는 변경만 다룬다.

## 1. 목적

주소를 여러 개 걸어두고 자리를 비울 수 있게 한다. 사용자는 URL을 붙여넣고 설정한 뒤 `추출`을 누르는 동작을 반복하고, 앱은 오른쪽 목록에 작업을 쌓아 **한 번에 하나씩** 순서대로 내려받는다. 목록은 앱을 끄면 사라진다(저장하지 않는다).

덧붙여 제목 옆에 작성자 표기 `by ssenu`를 넣는다.

## 2. 범위

### 포함
- 오른쪽 세로 패널 "추출 목록": 행마다 제목·상태·작은 진행바·퍼센트·× 버튼
- `추출` 버튼은 현재 입력을 작업으로 캡처해 목록 끝에 추가한다
- 순차 실행: 실행 중인 작업이 없으면 즉시 시작, 있으면 `대기 중`
- 행별 취소/제거(×), 완료 행 더블클릭으로 탐색기에서 파일 선택
- 하단 요약 한 줄: `대기 n · 추출 중 n · 완료 n`
- 제목 옆 `by ssenu`

### 제외 (YAGNI)
- 목록 저장/복원
- 실패 작업 재시도 버튼
- 순서 바꾸기(드래그), 우선순위
- 동시 다운로드
- 재생목록 전개
- 완료/전체 완료 팝업

## 3. 사용자 흐름

1. URL·파일 이름·화질·저장 위치를 입력하고 `추출`을 누른다.
2. 입력 검증(기존 `validate_url`/`validate_out_dir`)에 실패하면 지금과 같은 경고창을 띄우고 아무것도 추가하지 않는다.
3. 통과하면 네 값을 **작업(Job)으로 캡처**해 목록 끝에 추가하고, URL과 파일 이름 칸을 비운다. 화질과 저장 위치는 그대로 둔다.
4. 실행 중인 작업이 없으면 그 작업이 바로 시작한다. 있으면 `대기 중`으로 줄을 선다.
5. 작업이 끝나면(완료·실패·취소 중 무엇이든) 다음 `대기 중` 작업이 자동으로 시작한다.
6. 행의 ×: `대기 중`이면 목록에서 제거, `추출 중`이면 다운로드 취소(→ `취소됨`), 끝난 행이면 목록에서 제거.
7. `완료` 행을 더블클릭하면 탐색기가 그 파일을 선택한 채 열린다.

## 4. 레이아웃

창 폭 520 → **900**. 왼쪽 520은 기존 그대로, 오른쪽 360이 목록. 두 열 사이 24px.

```
[아이콘] YouTube 다운로더  by ssenu     │ 추출 목록
                                       │ ┌──────────────────────────────┐
영상 주소                               │ │ 웹프로그래밍(0903)   완료   × │
[                                    ] │ │                         100% │
파일 이름                  화질          │ ├──────────────────────────────┤
[                    ]   [ 1080p ▾ ]   │ │ 2주차 강의          추출 중 × │
저장 위치                               │ │ ▬▬▬▬▬▬▬▬▬▬▬░░░░░░░░░░░░  62% │
[                        ] [변경…]     │ ├──────────────────────────────┤
                                       │ │ https://youtu.be/…  대기 중 × │
[              추출              ]     │ │ ░░░░░░░░░░░░░░░░░░░░░░░░   0% │
대기 1 · 추출 중 1 · 완료 1              │ └──────────────────────────────┘
```

- `by ssenu`: 제목 오른쪽 8px 간격, 12px, 색 `#6B6B70`(muted), 기준선 정렬.
- 오른쪽 패널 제목 `추출 목록`은 왼쪽 필드 라벨과 같은 스타일(12px muted).
- 행: 흰 배경, 8px 라운드, 행 사이 8px. 첫 줄은 제목(13px, 한 줄, 넘치면 말줄임) · 상태 텍스트(12px) · × 버튼(24px, 회색, 호버 시 빨강). 둘째 줄은 4px 진행바 + 퍼센트(12px).
- `완료`·`실패`·`취소됨` 행은 진행바를 숨기고 상태만 남긴다. `실패` 행은 상태 글자를 빨강으로, 툴팁에 실패 사유.
- 목록은 세로 스크롤(`QListWidget`), 비어 있으면 가운데에 `추출을 누르면 여기에 쌓입니다`(12px muted).
- 하단 요약 라벨은 기존 상태/퍼센트 줄 자리에 한 줄. 큰 진행바와 퍼센트 라벨은 제거한다.

행 제목 규칙: 파일 이름을 지정했으면 그 이름. 비웠으면 URL을 보였다가, 워커가 제목을 알아낸 순간(빈 파일명 프로브 직후) 제목으로 바뀐다.

## 5. 컴포넌트

### 5.1 `app/queue.py` — 순수 파이썬, Qt 없음

```python
class JobStatus(str, Enum): PENDING="대기 중"; RUNNING="추출 중"; DONE="완료"; FAILED="실패"; CANCELLED="취소됨"

@dataclass
class Job:
    id: int
    url: str
    out_dir: str
    filename: str          # 사용자가 입력한 값, 비어 있을 수 있음
    quality: str
    status: JobStatus = PENDING
    progress: int = 0      # 0-100
    title: str = ""        # 표시용 제목 (파일명 또는 알아낸 제목), 비면 url 표시
    result_path: str = ""  # DONE일 때 최종 파일
    error: str = ""        # FAILED일 때 사유

class DownloadQueue:
    def add(self, url, out_dir, filename, quality) -> Job
    def get(self, job_id) -> Job | None
    def jobs(self) -> list[Job]                  # 추가 순서
    def running(self) -> Job | None
    def next_pending(self) -> Job | None         # 가장 오래된 PENDING
    def mark_running(self, job_id) -> None       # PENDING -> RUNNING (다른 RUNNING이 있으면 ValueError)
    def set_progress(self, job_id, value) -> None
    def set_title(self, job_id, title) -> None
    def mark_done(self, job_id, path) -> None
    def mark_failed(self, job_id, error) -> None
    def mark_cancelled(self, job_id) -> None
    def remove(self, job_id) -> None             # RUNNING은 제거 불가(ValueError)
    def summary(self) -> str                     # "대기 n · 추출 중 n · 완료 n" (실패/취소는 완료에 넣지 않고, 0이 아닐 때만 " · 실패 n · 취소 n" 덧붙임)
```

불변식: RUNNING은 동시에 최대 하나. 상태 전이는 PENDING→RUNNING→{DONE, FAILED, CANCELLED}뿐이며 되돌아가지 않는다. `mark_*`가 허용되지 않는 전이를 받으면 `ValueError`.

### 5.2 `app/queue_controller.py` — `QObject`

`DownloadQueue`를 소유하고 `DownloadWorker`를 **한 번에 하나만** 띄운다.

```python
class QueueController(QObject):
    job_changed = pyqtSignal(int)      # 갱신된 job id
    job_removed = pyqtSignal(int)
    summary_changed = pyqtSignal(str)
    idle = pyqtSignal()                # 실행 중도 대기 중도 없어졌을 때 (closeEvent용)

    def __init__(self, ffmpeg_path: str, parent=None)
    def enqueue(self, url, out_dir, filename, quality) -> int   # job id 반환, 필요하면 즉시 시작
    def cancel_or_remove(self, job_id) -> None                   # 행의 × 동작
    def cancel_all(self) -> None                                 # 대기 전부 제거 + 실행 중 취소 (closeEvent)
    def is_busy(self) -> bool                                    # 워커가 살아 있는가
    def job(self, job_id) -> Job
```

동작:
- `_start_next()`: `queue.running()`이 없고 `next_pending()`이 있으면 그 작업으로 `DownloadWorker(url, out_dir, filename, quality, ffmpeg_path)`를 만들고 시그널을 연결한 뒤 `start()`. `mark_running`.
- 워커 `progress(int)` → `set_progress` → `job_changed`.
- 워커 `status(str)` → 무시하되, 제목을 알아내기 위해 워커에 새 시그널 `title_resolved(str)`를 추가한다(아래 5.4). → `set_title` → `job_changed`.
- 워커 `finished_ok(path)` → `mark_done`; `failed(msg)` → `mark_failed`; `cancelled()` → `mark_cancelled`. 세 경우 모두 `job_changed`, `summary_changed`.
- 워커 `QThread.finished` → `_worker = None` 후 `_start_next()`. 대기가 없으면 `idle`.
- `cancel_or_remove`: PENDING/DONE/FAILED/CANCELLED → `queue.remove` + `job_removed`; RUNNING → `worker.cancel()` (상태 변경은 워커의 `cancelled` 시그널이 오면 처리).
- 워커 참조는 `self._worker`에 보관한다(GC 방지). 워커가 끝나기 전에는 다음 작업을 절대 시작하지 않는다.

### 5.3 `app/queue_panel.py` — `QWidget`

오른쪽 패널. `QListWidget` 하나와 행마다 `JobRow(QWidget)`.

```python
class QueuePanel(QWidget):
    cancel_requested = pyqtSignal(int)     # × 클릭
    reveal_requested = pyqtSignal(int)     # 완료 행 더블클릭
    def add_row(self, job: Job) -> None
    def update_row(self, job: Job) -> None
    def remove_row(self, job_id: int) -> None

class JobRow(QWidget):
    def __init__(self, job: Job)
    def refresh(self, job: Job) -> None    # 제목/상태/진행바/× 표시 갱신
```

`JobRow.refresh` 규칙: 상태가 RUNNING/PENDING이면 진행바 보임, 아니면 숨김. FAILED면 상태 라벨 빨강 + `setToolTip(job.error)`. 제목 라벨은 `job.title or job.url`, 말줄임(`QFontMetrics.elidedText`).

### 5.4 `app/download_worker.py` — 최소 변경

새 시그널 `title_resolved = pyqtSignal(str)`. 빈 파일명 프로브가 제목을 알아낸 직후 `emit(title)`. 파일명을 지정한 경우에는 emit하지 않는다(행 제목은 이미 파일명). 그 외 로직은 변경하지 않는다.

### 5.5 `app/main_window.py`

- 헤더: `by ssenu` 라벨 추가(objectName `byline`).
- 하단: `progress`/`percent_label`/`status_label` 블록 → `summary_label` 하나. 초기 문구 `대기 0 · 추출 중 0 · 완료 0`.
- `_start()` → `_enqueue()`: 검증 후 `controller.enqueue(...)`, URL·파일 이름 칸 비움, URL 칸에 포커스.
- `action_btn`은 항상 `추출`이고 항상 활성. `_set_running`과 `[mode="cancel"]` 스타일은 제거한다.
- 입력 위젯은 다운로드 중에도 **비활성화하지 않는다**(다음 작업을 입력해야 하므로).
- `QueuePanel`을 오른쪽에 배치. `cancel_requested` → `controller.cancel_or_remove`; `reveal_requested` → 기존 `_reveal(job.result_path)`.
- `closeEvent`: `controller.is_busy()`면 `controller.cancel_all()` 후 `event.ignore()`, `controller.idle` 시그널에 `close`를 연결(한 번만, `_closing` 가드 유지). 바쁘지 않으면 바로 닫힘.
- 창 `setFixedWidth(900)`. 높이는 왼쪽 열 내용 높이 기준 고정, 오른쪽 목록은 그 높이 안에서 스크롤.
- 워커 참조·`_worker`·`_on_finished`/`_on_failed`/`_on_cancelled`/`_on_thread_finished`는 컨트롤러로 이동하므로 창에서 제거한다.

### 5.6 `app/theme.py`

추가 QSS: `QLabel#byline`(12px muted), `QLabel#summaryLabel`, `QListWidget#queueList`(배경 투명, 테두리 없음, 항목 간격 8px), `QWidget#jobRow`(흰 배경, 8px 라운드), `QLabel#jobTitle`, `QLabel#jobStatus`, `QLabel#jobStatus[failed="true"]`(빨강), `QPushButton#jobCancel`(24px, 테두리 없음, 회색 ×, 호버 빨강), `QProgressBar#jobBar`(4px, 기존 색). `QPushButton#actionBtn[mode="cancel"]` 블록은 제거.

## 6. 데이터 흐름

```
추출 클릭 → validate → controller.enqueue(url, out_dir, filename, quality)
  → queue.add → panel.add_row → summary_changed
  → (실행 중 없음) _start_next → DownloadWorker.start → mark_running → job_changed
워커 progress/title_resolved → queue 갱신 → job_changed → panel.update_row
워커 finished_ok/failed/cancelled → mark_* → job_changed, summary_changed
워커 QThread.finished → _worker=None → _start_next (다음 대기) 또는 idle
× 클릭 → cancel_or_remove → (대기/종료) remove + job_removed → panel.remove_row
                           → (실행 중) worker.cancel → … cancelled 경로
더블클릭(완료) → reveal_requested → _reveal(result_path)
```

## 7. 에러 처리

| 상황 | 처리 |
|---|---|
| 검증 실패 | 경고창, 목록에 추가하지 않음 |
| 작업 실패 | 그 행만 `실패`(툴팁에 사유), **다음 작업은 계속** |
| 같은 파일명을 두 번 추가 | 두 번째가 시작될 때 `build_ydl_opts`가 충돌 검사를 하므로 `(1)`이 붙음 |
| 실행 중 행 × | 워커 취소, `취소됨`, 잔여 파일 정리는 기존 워커 로직 |
| 창 닫기 | 실행 중 취소 + 대기 전부 제거, 워커가 끝나면 닫힘. 완료된 파일은 남음 |
| 워커 예외 | 기존과 같이 워커 안에서 `failed`로 변환됨. 컨트롤러는 예외를 받지 않는다 |

## 8. 테스트

**pytest (Qt 없음)** — `tests/test_queue.py`
- 추가 순서대로 `jobs()`가 나오는지, `next_pending()`이 가장 오래된 대기를 주는지
- RUNNING 둘 만들기 시도 → `ValueError`; RUNNING 제거 시도 → `ValueError`
- 각 `mark_*` 전이와 허용되지 않는 전이(DONE→RUNNING 등)의 `ValueError`
- `summary()` 문구: 실패/취소가 0이면 세 항목만, 아니면 덧붙임
- `set_title`/`set_progress` 반영

**pytest (Qt, 네트워크 없음)** — `tests/test_queue_controller.py`
`DownloadWorker`를 가짜 클래스로 몽키패치(시그널만 있는 `QObject`, `start()`는 아무것도 안 함). `enqueue` 3회 → 첫 작업만 RUNNING; 가짜 워커의 `finished_ok` + `finished`를 수동 emit → 두 번째가 RUNNING; 두 번째에 `cancel_or_remove` → `cancel()` 호출됨; 세 번째 대기 중 `cancel_or_remove` → 제거되고 시작되지 않음.

**헤드리스 스모크** — 기존 스모크 갱신: `action_btn.text()=="추출"`, `summary_label` 초기 문구, `by ssenu` 라벨 존재, 폭 900, 빈 URL로 `_enqueue()` 시 경고 + 목록 비어 있음.

**종단 하네스** — 실제 영상으로 주소 3개 연속 투입: 1번 완료 → 2번 자동 시작, 2번 도중 × → `취소됨` + 3번 자동 시작 → 완료. 요약 문구가 `대기 0 · 추출 중 0 · 완료 2 · 취소 1`. 3번 행 더블클릭 → 탐색기 호출(`_reveal` 몽키패치로 인자 확인).

## 9. 기존 스펙과의 관계

- 선행 스펙 6.4의 "추출 중 입력 위젯 비활성화 / 버튼 취소 전환 / 완료 QMessageBox"는 이 스펙으로 **대체**된다.
- `DownloadWorker`, `options`, `validation`, `errors`, `ffmpeg_locator`의 계약은 유지된다(워커에 시그널 하나 추가만).
- 종단 검증 하네스(`.superpowers/sdd/…`)의 `_start()`/`_worker` 의존은 컨트롤러 기준으로 갱신한다.
