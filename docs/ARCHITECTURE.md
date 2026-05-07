# ARCHITECTURE — Tree-Size

> **문서 버전**: 0.1 (초안)
> **작성일**: 2026-05-06
> **연관 문서**: [`PRD.md`](./PRD.md)

이 문서는 Tree-Size 애플리케이션의 **소프트웨어 아키텍처**를 정의한다. PRD에서 도출된 요구사항을 충족하기 위한 모듈 구조, 동시성 모델, 데이터 모델, 빌드/배포 전략을 다룬다.

---

## 1. 아키텍처 원칙

1. **UI/Logic 분리** — 비즈니스 로직은 Qt에 의존하지 않는 순수 Python으로 작성하여 테스트 용이성 확보.
2. **이벤트 기반 동시성** — 무거운 작업은 모두 워커 스레드. UI는 시그널/슬롯으로만 갱신.
3. **점진적 결과 반영** — 스캔이 진행됨에 따라 트리에 노드를 점진적으로 추가(스트리밍).
4. **단일 책임 모듈** — 스캐너, 모델, 뷰, 컨트롤러, 영속성 레이어를 분명히 구분.
5. **장애 격리** — 한 폴더의 권한 오류가 전체 스캔을 멈추지 않도록 try/except를 워커 단위로 적용.

---

## 2. 시스템 구성도 (Layered View)

```
┌─────────────────────────────────────────────────────────────────┐
│                          Presentation                           │
│  MainWindow │ TreeView │ BarChartPanel │ Toolbar │ Dialogs      │
│             (PySide6 Widgets, QSS Themes)                       │
└────────────────────▲────────────────────────────────────────────┘
                     │ signals / slots
┌────────────────────┴────────────────────────────────────────────┐
│                       Application Layer                         │
│   ScanController │ ExportController │ FileOpsController         │
│   FilterEngine   │ SearchEngine     │ SettingsService           │
└────────────────────▲────────────────────────────────────────────┘
                     │ method calls (sync) / Qt signals (async)
┌────────────────────┴────────────────────────────────────────────┐
│                         Domain / Core                           │
│   Scanner (worker)  │  TreeModel (Qt model)  │  Node entities   │
│   Aggregator        │  IncrementalScanner    │  SizeFormatter   │
└────────────────────▲────────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────────┐
│                       Infrastructure                            │
│   FsProbe (os.scandir + Win32) │ SqliteCache │ Logger │ Config  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 디렉토리 구조

```
tree-size/
├── src/
│   └── tree_size/
│       ├── __init__.py
│       ├── __main__.py              # python -m tree_size 진입점
│       ├── app.py                   # QApplication 부트스트랩
│       │
│       ├── core/                    # 도메인 (Qt 무의존)
│       │   ├── __init__.py
│       │   ├── node.py              # FileNode / FolderNode 데이터 클래스
│       │   ├── scanner.py           # 동기 스캐너(워커에서 호출)
│       │   ├── aggregator.py        # 누적 크기/카운트 집계
│       │   ├── fs_probe.py          # os.scandir + Win32 메타 (compressed/alloc)
│       │   ├── filter.py            # 검색/필터 엔진
│       │   └── formatter.py         # 사이즈 포맷팅 (KB/MB/GB)
│       │
│       ├── persistence/             # 영속성
│       │   ├── __init__.py
│       │   ├── cache_db.py          # SQLite 래퍼
│       │   ├── schema.sql           # DDL
│       │   └── migrations.py        # 스키마 마이그레이션
│       │
│       ├── workers/                 # Qt 동시성
│       │   ├── __init__.py
│       │   ├── scan_worker.py       # QRunnable: 스캔 워커
│       │   ├── progress.py          # 진행률 집계 (스레드 안전)
│       │   └── signals.py           # 워커 ↔ UI 시그널 정의
│       │
│       ├── ui/                      # PySide6 UI
│       │   ├── __init__.py
│       │   ├── main_window.py
│       │   ├── tree_view.py         # 커스텀 QTreeView + LazyTreeModel
│       │   ├── tree_model.py        # QAbstractItemModel 구현
│       │   ├── bar_chart.py         # PyQtGraph 막대 차트
│       │   ├── toolbar.py
│       │   ├── search_bar.py
│       │   ├── status_bar.py
│       │   ├── dialogs/
│       │   │   ├── confirm_delete.py
│       │   │   ├── export.py
│       │   │   └── settings.py
│       │   └── themes/
│       │       ├── light.qss
│       │       ├── dark.qss
│       │       └── theme_manager.py
│       │
│       ├── controllers/             # 애플리케이션 서비스
│       │   ├── __init__.py
│       │   ├── scan_controller.py
│       │   ├── file_ops_controller.py
│       │   ├── export_controller.py
│       │   └── settings_service.py
│       │
│       ├── exporters/
│       │   ├── csv_exporter.py
│       │   ├── json_exporter.py
│       │   └── html_exporter.py
│       │
│       └── utils/
│           ├── logging_setup.py
│           ├── paths.py             # %LOCALAPPDATA% 등
│           └── win32.py             # ctypes 래퍼
│
├── resources/
│   ├── icons/
│   ├── splash.png
│   └── tree-size.ico
│
├── tests/
│   ├── unit/
│   │   ├── test_scanner.py
│   │   ├── test_aggregator.py
│   │   ├── test_filter.py
│   │   └── test_cache_db.py
│   ├── integration/
│   │   └── test_scan_workflow.py
│   └── ui/
│       └── test_main_window.py      # pytest-qt
│
├── build/
│   ├── tree-size.spec               # PyInstaller 스펙
│   └── version_info.txt             # Windows 파일 메타데이터
│
├── docs/
│   ├── PRD.md
│   └── ARCHITECTURE.md
│
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── CLAUDE.md
```

---

## 4. 주요 컴포넌트 설명

### 4.1 `core.scanner.Scanner`

* **책임**: 한 폴더를 깊이 우선으로 순회하며 자식 노드 목록과 메타를 수집한다.
* **인터페이스**:
  ```python
  class Scanner:
      def scan(self, path: Path, *, follow_symlinks: bool = False,
               cancel_token: CancelToken,
               on_node: Callable[[Node], None],
               on_progress: Callable[[ProgressEvent], None]) -> ScanResult: ...
  ```
* **특징**:
  * `os.scandir`을 우선 사용 → `DirEntry.stat(follow_symlinks=False)`로 1회 syscall.
  * NTFS compressed/alloc 크기는 `core.fs_probe.get_alloc_size(path)`로 별도 조회(옵션).
  * 권한 오류는 `PermissionError`로 잡아 로그 후 자식만 건너뜀.
  * 심볼릭 링크는 `inode + dev_id` 집합으로 순환 탐지(Windows에서는 `nFileIndex` 활용).

### 4.2 `core.fs_probe`

| 함수 | 설명 |
|------|------|
| `iter_entries(path)` | `os.scandir` 기반 yield. 권한 예외를 잡아 `(entry, error)` 튜플로 반환 |
| `get_alloc_size(path)` | Win32 `GetCompressedFileSizeW` 호출로 실제 디스크 할당 크기 |
| `is_reparse_point(entry)` | 심볼릭 링크/정크션 감지 |
| `resolve_shortcut(lnk_path)` | `.lnk` 파일의 타겟 경로 추출 (`pywin32` 또는 `ctypes`) |
| `to_long_path(p)` | `\\?\` 프리픽스 부착 (long path 지원) |

### 4.3 `core.node.Node`

```python
@dataclass(slots=True)
class Node:
    name: str
    path: Path
    is_dir: bool
    size_logical: int           # stat_result.st_size 합산
    size_allocated: int         # NTFS 실제 할당 크기 합산
    file_count: int
    folder_count: int
    mtime: float
    parent: "Node | None" = None
    children: list["Node"] = field(default_factory=list)
```

### 4.4 `workers.ScanWorker`

* `QRunnable`을 상속.
* `run()`에서 `Scanner.scan(...)`을 호출하고 결과를 `WorkerSignals`로 emit.
* **시그널 종류**:
  * `nodeReady(Node)` — 노드 1개 완료 (점진적 트리 추가)
  * `progress(ProgressEvent)` — 누적 카운트/바이트/현재 경로
  * `finished(ScanResult)` — 스캔 완료
  * `error(str, Path)` — 스킵된 경로

### 4.5 `ui.tree_model.LazyTreeModel`

* `QAbstractItemModel`을 직접 구현(QStandardItemModel 미사용 — 100만 노드 시 성능/메모리 이슈 회피).
* 스캔 중 `add_node(node)` 슬롯으로 노드를 누적하고, 100ms 타이머(`flush_pending()`)로 배치 `beginResetModel/endResetModel` 하여 렌더링 비용 최소화.
* **DFS 후위순회(post-order) 중요**: Scanner는 자식을 먼저 emit하고 루트를 마지막에 emit한다. `add_node()`는 `node.parent is None`일 때만 `_root`를 설정하므로, 스캔 완료 전까지는 루트가 None이고 `rowCount()`가 0을 반환(정상 동작).
* 필터 적용 시 평면 리스트 모드로 전환되어 트리 계층 없이 검색 결과만 표시.

### 4.6 `controllers.ScanController`

```python
class ScanController(QObject):
    progressUpdated = Signal(ProgressEvent)
    scanFinished = Signal(ScanResult)
    scanError = Signal(str, Path)

    def start(self, root: Path, options: ScanOptions) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def cancel(self) -> None: ...
```

* UI에서 호출되는 단일 진입점.
* 내부적으로 `QThreadPool`에 `ScanWorker`를 제출하고, 시그널을 UI로 릴레이.

---

## 5. 동시성 모델

```
┌──────────────────────────────┐
│         UI Thread            │ ← QApplication.exec()
│   (Qt event loop, painters)  │
└─────────▲────────────┬───────┘
          │ signals    │ start()
          │            ▼
┌─────────┴────────────────────┐
│       QThreadPool            │
│  ┌─────┐ ┌─────┐ ┌─────┐     │
│  │ W1  │ │ W2  │ │ Wn  │ ... │  ← Scanner workers (BFS partition)
│  └─────┘ └─────┘ └─────┘     │
└──────────────────────────────┘
          │
          ▼ writes
┌──────────────────────────────┐
│   SQLite (WAL mode)          │
│   - one writer queue         │  ← persistence.cache_db
│   - readers concurrent       │
└──────────────────────────────┘
```

* **워커 분할 전략**: 루트의 1단계 자식 폴더를 단위로 워커에 분배(작업 도용 방식 — 빈 워커가 큰 폴더의 하위를 다시 분할).
* **공유 상태**: 진행률은 `QAtomicInt` 대용으로 `threading.Lock` + `int` 카운터.
* **취소**: `CancelToken` (set/cleared, 워커는 매 N개 entry마다 polling).
* **DB 쓰기 직렬화**: 단일 writer 큐 (`queue.Queue`)로 직렬화하여 SQLite WAL에서도 충돌 방지.

---

## 6. 데이터 모델 (SQLite 스키마)

`%LOCALAPPDATA%\TreeSize\cache.db`

```sql
-- 스캔 세션(루트 단위)
CREATE TABLE scans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    root_path     TEXT    NOT NULL,
    started_at    INTEGER NOT NULL,
    finished_at   INTEGER,
    options_json  TEXT,
    total_files   INTEGER,
    total_bytes   INTEGER
);

-- 모든 노드(파일+폴더). 폴더는 size_logical/allocated가 자식 합산값.
CREATE TABLE nodes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    parent_id       INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,
    path            TEXT    NOT NULL,            -- 전체 경로(중복 저장이지만 검색 가속)
    is_dir          INTEGER NOT NULL,            -- 0/1
    size_logical    INTEGER NOT NULL DEFAULT 0,
    size_allocated  INTEGER NOT NULL DEFAULT 0,
    file_count      INTEGER NOT NULL DEFAULT 0,
    folder_count    INTEGER NOT NULL DEFAULT 0,
    mtime           INTEGER NOT NULL,
    flags           INTEGER NOT NULL DEFAULT 0,  -- bit 0: compressed, bit 1: reparse
    UNIQUE (scan_id, path)
);

CREATE INDEX idx_nodes_parent ON nodes(parent_id);
CREATE INDEX idx_nodes_scan_path ON nodes(scan_id, path);
CREATE INDEX idx_nodes_size ON nodes(size_logical DESC);
```

**증분 스캔**: 동일 `root_path`에 이전 `scan_id`가 있으면, mtime + size_logical을 비교하여 변경된 노드만 update/insert/delete. 변경 없는 디렉토리는 자식 재방문 생략.

---

## 7. UI 데이터 흐름

### 7.1 스캔 시작

```
User clicks "Open Folder"
  → MainWindow._on_scan_requested()
  → ScanController.start(path, options)
  → ScanWorker submitted to QThreadPool
  → Scanner.scan() runs (DFS post-order)
      자식 노드 emit → 부모 노드 emit → 루트 emit (마지막)
  → nodeReady Signal (QueuedConnection) → LazyTreeModel.add_node()
      자식/중간: _pending 누적 (root=None → flush skip)
      루트 도착: _root 설정
  → 100ms QTimer → flush_pending() → beginResetModel/endResetModel
  → StatusBar.on_progress()
  → 스캔 완료: scanFinished → stop_scan() → 최종 flush_pending()
```

### 7.2 파일 작업

```
User right-clicks node → "Move to Recycle Bin"
  → ConfirmDialog → user confirms
  → FileOpsController.delete([paths], to_recycle=True)
    → send2trash 라이브러리 사용 (Windows 휴지통 API 래퍼)
  → On success: TreeModel.remove_nodes(...)
  → Cache DB updated
```

---

## 8. 테마 시스템

* `ui.themes.theme_manager`가 QSS 파일을 로드하여 `QApplication.setStyleSheet()` 호출.
* 시작 시 `SettingsService`에서 마지막 테마 로드(`light` / `dark` / `system`).
* `system` 모드는 Windows 레지스트리 `HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize\AppsUseLightTheme`를 폴링(또는 `QStyleHints.colorSchemeChanged` 시그널).
* 아이콘은 qtawesome(FontAwesome 5, 접두어 `fa5s.`)으로 동적 색상 적용.
* **PyInstaller onefile 경로 해결**: `_get_themes_dir()` 함수가 `sys._MEIPASS` 존재 여부를 검사하여 번들 내 QSS 경로를 반환. 소스 실행 시에는 `Path(__file__).parent` 사용.
  ```python
  def _get_themes_dir() -> Path:
      if hasattr(sys, "_MEIPASS"):
          return Path(sys._MEIPASS) / "tree_size" / "ui" / "themes"
      return Path(__file__).parent
  ```

---

## 9. 로깅 & 에러 처리

* `utils.logging_setup.setup_logging()`에서 root logger 설정. `app.py`의 `_bootstrap_logging()`이 `QApplication` 생성 전 가장 먼저 호출한다.
* 핸들러:
  * `RotatingFileHandler` — `%LOCALAPPDATA%\TreeSize\logs\tree-size.log` (5MB × 3)
  * `StreamHandler(sys.stderr)` — WARNING 이상만 (개발 모드 / 콘솔 실행 시)
* 환경 변수 `TREESIZE_LOG_LEVEL` (기본 `INFO`)로 로그 레벨 제어 가능.
* 워커 내 미잡힌 예외는 `WorkerSignals.error.emit(str(e), path)`로 UI에 전달 → 상태바에 비파괴적으로 표시.
* **windowed EXE 주의**: `--windowed`(noconsole) 빌드에서 stderr는 사용자에게 보이지 않으므로 파일 핸들러가 유일한 진단 수단.

---

## 10. 설정 (Settings)

* `QSettings` 백엔드(레지스트리 또는 INI). 기본은 INI: `%LOCALAPPDATA%\TreeSize\settings.ini`
* 항목:
  * `theme` (light/dark/system)
  * `scan/follow_symlinks` (bool)
  * `scan/measure_allocation_size` (bool)
  * `scan/parallel_workers` (int, default = `os.cpu_count()`)
  * `cache/enabled` (bool)
  * `cache/max_size_mb` (int, default 200)
  * `recent_scans` (list of paths)

---

## 11. 패키징 / 빌드

### 11.1 `build/tree-size.spec` (PyInstaller)

* **진입점**: `src/tree_size/__main__.py` — `sys.exit(run())`을 직접 호출. `app.py`를 진입점으로 쓰면 `run()`이 정의만 되고 호출되지 않아 EXE가 임포트 4초 후 exit 0으로 종료된다.
* `--onefile` + `--noconsole` (`--windowed`)
* `--icon resources/tree-size.ico`
* datas: `tree_size/ui/themes/*.qss`, `resources/`, `qtawesome/fonts/`
* Hidden imports: `PySide6.QtCharts`, `pyqtgraph`, `send2trash` 등
* `version_info.txt`로 버전/회사/파일 설명 메타데이터 부착
* UPX 압축은 비활성(Windows Defender 오탐 가능성)
* `build/tree-size.spec`, `build/version_info.txt`, `build/tree-size.manifest`는 git 추적 대상 (`.gitignore`에 `!build/*.spec` 예외 추가)

### 11.2 빌드 명령

```powershell
.\venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
pyinstaller build/tree-size.spec --clean
# 산출물: dist/tree-size.exe
```

### 11.3 manifest

`tree-size.exe.manifest`에 다음 포함:
* `longPathAware = true`
* `dpiAware = PerMonitorV2`
* `requestedExecutionLevel level="asInvoker"` (관리자 권한 비요구, 필요 시 사용자가 수동)

---

## 12. 테스트 전략

| 레벨 | 도구 | 대상 |
|------|------|------|
| Unit | pytest | `core/*`, `persistence/*`, `exporters/*` |
| Integration | pytest + tmp_path | 가짜 디렉토리 트리 생성 → Scanner+Aggregator+CacheDB 결합 |
| UI | pytest-qt | TreeView 모델 갱신, 시그널 emit 검증 |
| 성능 | pytest-benchmark | 10만 파일 스캔 회귀 |
| 스모크 | manual | 빌드된 EXE를 깨끗한 Windows에서 실행 |

CI: GitHub Actions (Windows runner) — push마다 `ruff check`, `mypy`, `pytest`, `pyinstaller` (smoke build).

---

## 13. 의존성 (확정 후보)

```text
# requirements.txt
PySide6>=6.6
pyqtgraph>=0.13
qtawesome>=1.3
send2trash>=1.8
pywin32>=306                # Win32 API 래핑 (선택 — ctypes로 대체 가능)

# requirements-dev.txt
pytest>=8.0
pytest-qt>=4.4
pytest-benchmark>=4.0
ruff>=0.5
mypy>=1.10
pyinstaller>=6.6
```

---

## 14. 향후 확장 (Out of v1.0, 참고)

| 기능 | 영향 모듈 |
|------|----------|
| 트리맵(Treemap) 시각화 | `ui/treemap.py` 신규, `pyqtgraph.GraphicsScene` |
| 파이/도넛 차트 | `ui/pie_chart.py` 신규 |
| 다국어 지원 | `resources/i18n/*.qm`, `QTranslator` |
| 중복 파일 탐지 | `core/duplicate_finder.py` (해시 기반, 별도 워커) |
| 디스크 클린업 추천 | 임시/캐시 폴더 휴리스틱 |
| 네트워크 드라이브 정밀 모드 | `fs_probe`에 SMB 분기 |

---

## 15. 결정 기록 (ADR 요약)

| # | 결정 | 대안 | 이유 |
|---|------|------|------|
| ADR-1 | PySide6 채택 | PyQt6, Tkinter | LGPL 자유, 대용량 위젯 성능, 커뮤니티 |
| ADR-2 | `QAbstractItemModel` 직접 구현 | `QStandardItemModel` | 100만 노드 메모리/성능 |
| ADR-3 | SQLite 캐시 | JSON / 메모리 | 증분 스캔 + 검색 가속 |
| ADR-4 | `os.scandir` + 선택적 Win32 | `pathlib.Path.stat()` | scandir이 1.5~3배 빠름 |
| ADR-5 | PyInstaller `--onefile` | `--onedir`, MSI | 일반 사용자 배포 단순성 |
| ADR-6 | UI 영문 전용 | i18n | v1.0 단순화, 추후 추가 가능 |
| ADR-7 | PyInstaller 진입점: `__main__.py` | `app.py` | `app.py`는 `run()`을 정의만 하고 호출하지 않아 EXE가 즉시 종료됨. `__main__.py`가 `sys.exit(run())` 호출의 유일한 지점. |
| ADR-8 | Scanner DFS 후위순회 emit | 전위순회 | 부모 노드는 모든 자식 합산 후 크기 확정. 자식 먼저 emit → 루트 마지막 emit. `add_node()`는 `node.parent is None`으로 루트 감지. |
| ADR-9 | 테마 경로 `sys._MEIPASS` 분기 | `Path(__file__).parent` 고정 | onefile EXE 내부의 `__file__`은 실제 파일시스템 경로가 아님. `_MEIPASS` 조건부로 QSS 파일 위치 결정. |

---

## 16. 변경 이력

| 버전 | 일자 | 변경 내용 |
|------|------|----------|
| 0.1 | 2026-05-06 | 초안. PRD 0.1과 정합. |
| 0.2 | 2026-05-08 | M5 구현 반영. Node 구조(`children_loaded` → `children` list), LazyTreeModel DFS post-order 동작(ADR-8), 테마 경로 `sys._MEIPASS` 분기(ADR-9), PyInstaller 진입점 `__main__.py`(ADR-7), 로그 파일명 수정(`app.log` → `tree-size.log`, 5MB×3), 스캔 흐름 정확화, ADR-7~9 추가. |
