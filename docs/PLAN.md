# PLAN — Tree-Size 구현 계획

> **문서 버전**: 1.0
> **작성일**: 2026-05-06
> **기반 문서**: PRD.md v0.1, ARCHITECTURE.md v0.1, AGENTS.md v0.1
> **상태**: 승인 대기

---

## 1. 마일스톤 개요

```
주차    M0        M1-A      M1-B      M2-A      M2-B      M3        M4        M5
       [셋업]    [코어]    [UI연결]  [UX]      [검색]    [차트/출력] [캐시]   [배포]
──────────────────────────────────────────────────────────────────────────────
W1      ████
W2                ████
W3                          ████
W4                                    ████
W5                                              ████
W6                                                        ████
W7                                                                  ████
W8                                                                            ████
```

| 마일스톤 | 목표 (한 줄) | 검수 게이트 |
|---------|------------|-----------|
| **M0** | `python -m tree_size` 실행 + 빈 창 열림 + EXE 산출 | `dist/tree-size.exe` 기동 확인 |
| **M1** | 폴더 선택 → 스캔 → TreeView 표시 (UI 무응답 없음) | 10만 파일 30초 이내, UI 60fps |
| **M2** | 진행률·일시정지·파일 작업·검색/필터 완성 | 권한 오류 경로 포함 스캔 크래시 없음 |
| **M3** | Bar Chart + CSV/JSON 내보내기 | Excel에서 CSV 정상 파싱 |
| **M4** | SQLite 캐시 + 증분 스캔 | 2회차 스캔이 1회차보다 ≥50% 빠름 |
| **M5** | 라이트/다크 테마 + 설정 + 단일 EXE | Python 미설치 PC에서 기동 |

---

## 2. 선행 작업 (M0 전에 수동 실행)

```bash
source venv/Scripts/activate

# 런타임 의존성
pip install PySide6 pyqtgraph qtawesome send2trash

# 개발 의존성
pip install pytest pytest-qt pytest-benchmark ruff mypy pyinstaller

# 검증
python -c "import PySide6; print(PySide6.__version__)"
python -c "import pyqtgraph; print(pyqtgraph.__version__)"
pyinstaller --version
```

---

## 3. M0 — 프로젝트 셋업 (W1)

**목표**: 소스 골격 완성, 패키징 파이프라인 검증.

### 3.1 태스크 목록

| # | 태스크 | 담당 agent | 산출 파일 |
|---|-------|-----------|---------|
| M0-1 | pyproject.toml + requirements*.txt 작성 | **build-engineer** | `pyproject.toml`, `requirements.txt`, `requirements-dev.txt` |
| M0-2 | 디렉토리 골격 생성 + 빈 `__init__.py` | **build-engineer** | `src/tree_size/**/__init__.py` 전체 |
| M0-3 | 로깅·경로 유틸 스텁 | **scanner-engineer** | `utils/logging_setup.py`, `utils/paths.py`, `utils/win32.py` |
| M0-4 | 최소 `app.py` + `__main__.py` + `MainWindow` 뼈대 | **qt-ui-engineer** | `app.py`, `__main__.py`, `ui/main_window.py` |
| M0-5 | PyInstaller spec + manifest 초안 | **build-engineer** | `build/tree-size.spec`, `build/tree-size.manifest`, `build/version_info.txt` |
| M0-6 | ruff + mypy pyproject.toml 설정 | **build-engineer** | `pyproject.toml` (갱신) |
| M0-7 | 빈 EXE 빌드 + 기동 스모크 | **build-engineer** | `dist/tree-size.exe` |

### 3.2 M0 상세 명세

#### M0-1 `pyproject.toml`
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "tree-size"
version = "0.1.0"
requires-python = ">=3.11"

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "W", "I", "UP", "B", "SIM"]

[tool.mypy]
strict = true
python_version = "3.11"
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]

[tool.pytest-benchmark]
max_time = 30.0
```

#### M0-3 `utils/paths.py` 인터페이스
```python
from pathlib import Path

def app_data_dir() -> Path: ...       # %LOCALAPPDATA%\TreeSize
def log_dir() -> Path: ...            # app_data_dir() / "logs"
def cache_db_path() -> Path: ...      # app_data_dir() / "cache.db"
def settings_ini_path() -> Path: ... # app_data_dir() / "settings.ini"
```

#### M0-4 `app.py` 인터페이스
```python
def run() -> int:
    app = QApplication(sys.argv)
    # 테마 초기 로드 (light 고정)
    window = MainWindow()
    window.show()
    return app.exec()
```

### 3.3 M0 완료 기준
- `python -m tree_size` → 빈 창 열림, 콘솔 오류 없음
- `ruff check . && mypy src/tree_size` → 오류 0
- `dist/tree-size.exe` 존재, 더블클릭 기동 확인

---

## 4. M1-A — 코어 스캐너 (W2)

**목표**: Qt 없이 단독으로 테스트 가능한 스캔 도메인 완성.
**담당 agent**: `scanner-engineer` (전담), `test-engineer` (병행)

### 4.1 태스크 목록

| # | 태스크 | 산출 파일 |
|---|-------|---------|
| M1A-1 | `core/node.py` — `Node`, `CancelToken`, `ProgressEvent`, `ScanResult`, `ScanOptions` | `core/node.py` |
| M1A-2 | `core/fs_probe.py` — `iter_entries`, `get_alloc_size`, `is_reparse_point`, `to_long_path` | `core/fs_probe.py` |
| M1A-3 | `utils/win32.py` — `GetCompressedFileSizeW` ctypes 래퍼 | `utils/win32.py` |
| M1A-4 | `core/scanner.py` — `Scanner.scan()` (DFS, symlink guard, cancel) | `core/scanner.py` |
| M1A-5 | `core/aggregator.py` — bottom-up 크기 집계 | `core/aggregator.py` |
| M1A-6 | `core/formatter.py` — 사이즈 포맷 (B/KB/MB/GB, 툴팁용 bytes) | `core/formatter.py` |
| M1A-7 | **테스트**: `tests/unit/test_node.py`, `test_scanner.py`, `test_aggregator.py`, `test_formatter.py`, `test_fs_probe.py` | `tests/unit/**` |
| M1A-8 | **통합테스트**: `tests/integration/test_scan_workflow.py` (tmp_path 합성 트리) | `tests/integration/**` |

### 4.2 핵심 인터페이스 (scanner-engineer 구현 기준)

```python
# core/node.py
@dataclass(slots=True)
class Node:
    name: str
    path: Path
    is_dir: bool
    size_logical: int
    size_allocated: int
    file_count: int
    folder_count: int
    mtime: float
    flags: int = 0       # bit0=compressed, bit1=reparse
    parent: "Node | None" = field(default=None, repr=False)

@dataclass(slots=True)
class ProgressEvent:
    current_path: Path
    total_files: int
    total_bytes: int
    elapsed_sec: float

@dataclass
class ScanOptions:
    follow_symlinks: bool = False
    measure_alloc_size: bool = True
    max_workers: int = field(default_factory=os.cpu_count)

class CancelToken:
    def cancel(self) -> None: ...
    def is_cancelled(self) -> bool: ...

# core/scanner.py
class Scanner:
    def scan(
        self, path: Path, options: ScanOptions,
        cancel_token: CancelToken,
        on_node: Callable[[Node], None],
        on_progress: Callable[[ProgressEvent], None],
    ) -> ScanResult: ...
```

### 4.3 Worker 시그널 (workers/ — scanner-engineer 구현)

```python
# workers/signals.py
class WorkerSignals(QObject):
    nodeReady    = Signal(object)   # Node
    progress     = Signal(object)   # ProgressEvent
    finished     = Signal(object)   # ScanResult
    error        = Signal(str, object)  # message, Path

# workers/scan_worker.py
class ScanWorker(QRunnable):
    def __init__(self, root: Path, options: ScanOptions) -> None: ...
    def run(self) -> None: ...  # calls Scanner.scan(), emits via signals
    def pause(self) -> None: ...
    def resume(self) -> None: ...
```

### 4.4 M1-A 완료 기준
- `pytest tests/unit tests/integration -x` → PASS
- `coverage run -m pytest tests/unit; coverage report` → `core/` 커버리지 ≥ 80%
- 심볼릭 링크 순환 → 무한루프 없음 (integration test 확인)
- 권한 거부 폴더 포함 경로 → 스킵 후 계속

---

## 5. M1-B — UI 연결 (W3)

**목표**: ScanWorker → LazyTreeModel → TreeView 경로 완성, 스캔 결과가 화면에 점진적 표시.
**담당 agent**: `qt-ui-engineer` (전담)

### 5.1 태스크 목록

| # | 태스크 | 산출 파일 |
|---|-------|---------|
| M1B-1 | `controllers/scan_controller.py` — `ScanController(QObject)` | `controllers/scan_controller.py` |
| M1B-2 | `ui/tree_model.py` — `LazyTreeModel(QAbstractItemModel)`, 7개 컬럼 | `ui/tree_model.py` |
| M1B-3 | `ui/tree_view.py` — `QTreeView` 래퍼, 컬럼 설정, 100ms 배치 갱신 | `ui/tree_view.py` |
| M1B-4 | `ui/toolbar.py` — Open, Refresh 버튼 + Ctrl+O/F5 단축키 | `ui/toolbar.py` |
| M1B-5 | `ui/status_bar.py` — 파일수, 용량, 경로 표시 | `ui/status_bar.py` |
| M1B-6 | `ui/themes/light.qss` + `dark.qss` (기본 골격) | `ui/themes/*.qss` |
| M1B-7 | `ui/themes/theme_manager.py` | `ui/themes/theme_manager.py` |
| M1B-8 | `ui/main_window.py` — Toolbar + TreeView + StatusBar 레이아웃 연결 | `ui/main_window.py` |
| M1B-9 | **UI 테스트**: 시그널 emit 검증, 모델 row count 검증 | `tests/ui/test_tree_model.py` |

### 5.2 LazyTreeModel 컬럼 정의

| idx | 헤더 | 데이터 소스 |
|-----|------|-----------|
| 0 | Name | `node.name` + 아이콘 |
| 1 | Size | `node.size_logical` (포맷팅) |
| 2 | Allocated | `node.size_allocated` |
| 3 | Files | `node.file_count` |
| 4 | Folders | `node.folder_count` |
| 5 | % of Parent | `node.size_logical / parent.size_logical * 100` |
| 6 | Last Modified | `node.mtime` (datetime 포맷) |

### 5.3 ScanController 인터페이스

```python
class ScanController(QObject):
    progressUpdated = Signal(object)   # ProgressEvent
    nodeReady       = Signal(object)   # Node
    scanFinished    = Signal(object)   # ScanResult
    scanError       = Signal(str, object)  # msg, Path

    def start(self, root: Path, options: ScanOptions) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def cancel(self) -> None: ...
    @property
    def is_running(self) -> bool: ...
```

### 5.4 M1-B 완료 기준
- `C:\Windows\System32` 스캔 → 진행 중 TreeView에 노드 점진적 추가 확인
- 스캔 중 창 이동/스크롤 → UI 60fps 유지 (Task Manager CPU 별도 확인)
- UI 테스트 PASS

---

## 6. M2-A — 스캔 UX + 파일 작업 (W4)

**목표**: 진행률 실시간 표시, Pause/Stop, 우클릭 파일 작업.

### 6.1 태스크 목록

| # | 태스크 | 담당 | 산출 파일 |
|---|-------|------|---------|
| M2A-1 | ETA 계산 (`workers/progress.py` 확장) | **scanner-engineer** | `workers/progress.py` |
| M2A-2 | StatusBar에 ETA + 현재 경로 표시 | **qt-ui-engineer** | `ui/status_bar.py` |
| M2A-3 | Toolbar에 Pause/Resume/Stop 버튼 | **qt-ui-engineer** | `ui/toolbar.py` |
| M2A-4 | `controllers/file_ops_controller.py` | **qt-ui-engineer** | `controllers/file_ops_controller.py` |
| M2A-5 | `ui/dialogs/confirm_delete.py` — 일반/영구삭제 구분 경고 | **qt-ui-engineer** | `ui/dialogs/confirm_delete.py` |
| M2A-6 | TreeView 우클릭 컨텍스트 메뉴 (F-20) | **qt-ui-engineer** | `ui/tree_view.py` (갱신) |
| M2A-7 | 파일 작업 후 TreeModel 갱신 (F-22) | **qt-ui-engineer** | `ui/tree_model.py` (갱신) |
| M2A-8 | **테스트**: 파일 작업 시그널 + 트리 갱신 | **test-engineer** | `tests/ui/test_file_ops.py` |

### 6.2 FileOpsController 인터페이스

```python
class FileOpsController(QObject):
    deletionCompleted = Signal(list)   # [Path] 삭제된 경로들
    operationFailed   = Signal(str, object)  # 에러 메시지, Path

    def delete_to_recycle(self, paths: list[Path]) -> None: ...
    def delete_permanently(self, paths: list[Path]) -> None: ...
    def open_in_explorer(self, path: Path) -> None: ...
    def copy_path(self, path: Path) -> None: ...
```

### 6.3 보호 경로 목록 (하드코드)
```python
PROTECTED_ROOTS = {
    Path("C:/Windows"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
}
```
보호 경로 삭제 시도 → `ProtectedPathError` 발생 + 추가 경고 다이얼로그.

---

## 7. M2-B — 검색 & 필터 (W5)

**목표**: 파일명/확장자/크기 필터, 재스캔 없이 즉시 반영.

### 7.1 태스크 목록

| # | 태스크 | 담당 | 산출 파일 |
|---|-------|------|---------|
| M2B-1 | `core/filter.py` — `FilterSpec`, `FilterEngine.apply(nodes)` | **scanner-engineer** | `core/filter.py` |
| M2B-2 | `ui/search_bar.py` — 검색 입력 위젯 + 필터 옵션 드롭다운 | **qt-ui-engineer** | `ui/search_bar.py` |
| M2B-3 | TreeModel에 FilterEngine 연결 (F-34) | **qt-ui-engineer** | `ui/tree_model.py` (갱신) |
| M2B-4 | 단축키 Ctrl+F → SearchBar 포커스 | **qt-ui-engineer** | `ui/main_window.py` (갱신) |
| M2B-5 | **테스트**: filter 엔진 단위 테스트 | **test-engineer** | `tests/unit/test_filter.py` |
| M2B-6 | **테스트**: SearchBar UI 통합 테스트 | **test-engineer** | `tests/ui/test_search.py` |

### 7.2 FilterSpec 인터페이스

```python
@dataclass
class FilterSpec:
    name_pattern: str = ""         # 부분일치 / 와일드카드 / regex
    use_regex: bool = False
    extensions: list[str] = field(default_factory=list)  # [".mp4", ".iso"]
    min_size: int = 0              # bytes
    max_size: int = 0              # 0 = unlimited
    modified_after: float = 0.0   # unix timestamp; 0 = no filter
    modified_before: float = 0.0

class FilterEngine:
    def apply(self, nodes: Iterable[Node], spec: FilterSpec) -> list[Node]: ...
    def matches(self, node: Node, spec: FilterSpec) -> bool: ...
```

---

## 8. M3 — 시각화 & 내보내기 (W6)

**목표**: Bar Chart 패널 + CSV/JSON/HTML 내보내기.

### 8.1 태스크 목록

| # | 태스크 | 담당 | 산출 파일 |
|---|-------|------|---------|
| M3-1 | `ui/bar_chart.py` — PyQtGraph 막대 그래프, 선택 노드 Top 10 자식 | **qt-ui-engineer** | `ui/bar_chart.py` |
| M3-2 | MainWindow 우측 패널에 BarChart 배치 (PRD §7.1 레이아웃) | **qt-ui-engineer** | `ui/main_window.py` (갱신) |
| M3-3 | `exporters/csv_exporter.py` — 평면화 / 현재 뷰 | 메인 or **scanner-engineer** | `exporters/csv_exporter.py` |
| M3-4 | `exporters/json_exporter.py` — 트리 구조 보존 | 메인 or **scanner-engineer** | `exporters/json_exporter.py` |
| M3-5 | `exporters/html_exporter.py` — 단일 파일 보고서 (P2) | 메인 or **scanner-engineer** | `exporters/html_exporter.py` |
| M3-6 | `controllers/export_controller.py` + `ui/dialogs/export.py` | **qt-ui-engineer** | `controllers/export_controller.py`, `ui/dialogs/export.py` |
| M3-7 | Toolbar에 Export 버튼 + Ctrl+E 단축키 | **qt-ui-engineer** | `ui/toolbar.py` (갱신) |
| M3-8 | **테스트**: 각 exporter 단위 테스트 | **test-engineer** | `tests/unit/test_*_exporter.py` |

### 8.2 Exporter 인터페이스

```python
class CsvExporter:
    def export(self, nodes: list[Node], dest: Path, *, visible_only: bool = False) -> None: ...

class JsonExporter:
    def export(self, root: Node, dest: Path) -> None: ...

class HtmlExporter:
    def export(self, root: Node, dest: Path) -> None: ...
```

---

## 9. M4 — SQLite 캐시 (W7)

**목표**: 스캔 결과 영속화, 재스캔 시 증분 업데이트.

### 9.1 태스크 목록

| # | 태스크 | 담당 | 산출 파일 |
|---|-------|------|---------|
| M4-1 | `persistence/schema.sql` — DDL (ARCHITECTURE §6 기준) | **persistence-engineer** | `persistence/schema.sql` |
| M4-2 | `persistence/migrations.py` — 버전 관리, `001_initial.sql` | **persistence-engineer** | `persistence/migrations.py`, `persistence/001_initial.sql` |
| M4-3 | `persistence/cache_db.py` — `CacheDb`, `WriterQueue`, WAL PRAGMA | **persistence-engineer** | `persistence/cache_db.py` |
| M4-4 | `ScanWorker`에 캐시 쓰기 통합 | **scanner-engineer** | `workers/scan_worker.py` (갱신) |
| M4-5 | 증분 스캔 로직 — mtime/size diff 후 delta 업데이트 | **scanner-engineer** | `core/scanner.py` (갱신) |
| M4-6 | **테스트**: DB CRUD, WAL 동시성, 마이그레이션 | **test-engineer** | `tests/unit/test_cache_db.py` |
| M4-7 | **통합테스트**: 전체 스캔 → DB 저장 → 증분 재스캔 | **test-engineer** | `tests/integration/test_incremental_scan.py` |

### 9.2 CacheDb 인터페이스

```python
class CacheDb:
    def __init__(self, db_path: Path) -> None: ...
    def close(self) -> None: ...

    # 스캔 세션
    def begin_scan(self, root_path: Path, options_json: str) -> int: ...     # → scan_id
    def finish_scan(self, scan_id: int, total_files: int, total_bytes: int) -> None: ...
    def get_last_scan(self, root_path: Path) -> int | None: ...              # → scan_id

    # 노드 (Writer Queue 통해서만)
    def enqueue_insert(self, scan_id: int, nodes: list[Node]) -> None: ...
    def enqueue_update(self, scan_id: int, node: Node) -> None: ...
    def enqueue_delete(self, scan_id: int, path: Path) -> None: ...

    # 읽기 (멀티스레드 가능)
    def get_children(self, scan_id: int, parent_path: Path) -> list[Node]: ...
    def get_node(self, scan_id: int, path: Path) -> Node | None: ...
```

### 9.3 M4 완료 기준
- 동일 경로 2회차 스캔이 1회차보다 ≥50% 빠름 (내용 변경 없는 경우)
- DB 크기: 10만 노드 ≤ 50MB

---

## 10. M5 — 다듬기 & 배포 (W8)

**목표**: 테마·설정 완성, 단일 EXE 최종 빌드.

### 10.1 태스크 목록

| # | 태스크 | 담당 | 산출 파일 |
|---|-------|------|---------|
| M5-1 | `controllers/settings_service.py` — QSettings INI 래퍼 | **qt-ui-engineer** | `controllers/settings_service.py` |
| M5-2 | `ui/dialogs/settings.py` — 설정 다이얼로그 (테마/스캔옵션/캐시) | **qt-ui-engineer** | `ui/dialogs/settings.py` |
| M5-3 | 라이트/다크/시스템 테마 완성 — 모든 위젯 QSS 커버 | **qt-ui-engineer** | `ui/themes/light.qss`, `dark.qss` |
| M5-4 | 아이콘 교체 — qtawesome으로 Toolbar·TreeView 아이콘 | **qt-ui-engineer** | `ui/toolbar.py`, `ui/tree_view.py` |
| M5-5 | 스플래시 스크린 (`resources/splash.png`) | **build-engineer** | `resources/splash.png`, `app.py` |
| M5-6 | PyInstaller spec 최종화 (hidden imports, UPX off) | **build-engineer** | `build/tree-size.spec` |
| M5-7 | `build/version_info.txt` — 버전·회사 메타 | **build-engineer** | `build/version_info.txt` |
| M5-8 | 최종 EXE 빌드 + 스모크 테스트 | **build-engineer** | `dist/tree-size.exe` |
| M5-9 | 전체 회귀 테스트 + 커버리지 보고 | **test-engineer** | CI 리포트 |
| M5-10 | 벤치마크: 10만 파일 스캔 ≤ 30초 확인 | **test-engineer** | `tests/benchmark/` |

### 10.2 최종 EXE 검수 체크리스트

```
□ Python 미설치 PC에서 더블클릭 → 기동
□ C:\ 전체 스캔 5분 이내 (100만 파일 미만 기준)
□ 스캔 중 스크롤/창 이동 → UI 응답
□ 권한 거부 폴더 포함 경로 → 스킵 후 완료 (크래시 없음)
□ 휴지통 삭제 → 트리에서 즉시 제거
□ CSV 내보내기 → Excel에서 정상 파싱
□ 라이트/다크 테마 전환 → 모든 위젯 즉시 갱신
□ Ctrl+O, F5, Ctrl+F, Delete, Ctrl+E 단축키 작동
```

---

## 11. 에이전트 호출 원칙

### 11.1 호출 전 메인이 제공해야 할 것

```
Agent(
  subagent_type="<agent-name>",
  description="<5단어 이내>",
  prompt="""
  [목표] 무엇을 만들어야 하는가 (파일명, 함수명 포함)
  [참조] 이 계획 §X.Y + ARCHITECTURE.md §Y.Z
  [인터페이스] 이미 결정된 함수 시그니처 (위의 코드블록 복붙)
  [제약] 건드리지 말 것, 새로 만들지 말 것 (경계 명시)
  [테스트] 어떤 테스트를 함께 작성할 것인가
  [응답 형식] 변경 파일 목록 + 핵심 결정 + 우려사항 (200단어 이내)
  """
)
```

### 11.2 병렬 호출 가능한 쌍

| 단계 | 병렬 가능 이유 |
|------|-------------|
| M1A-1~6 (scanner) + M0-4 (qt-ui) | 인터페이스 합의 후 독립 구현 |
| M3-3~5 (exporters) + M3-1~2 (bar chart) | 의존 없음 |
| M4-1~3 (persistence) + M4-4~5 (scanner) | 인터페이스가 M4-3 완료 후 확정 → 순차 |

### 11.3 순차 호출이 필요한 경우

```
M1A → M1B : scanner 인터페이스 확정 후 UI 연결
M4-3 → M4-4 : CacheDb API 확정 후 ScanWorker 통합
M5-9 → M5-10 : 회귀 통과 후 벤치마크
```

---

## 12. 위험 및 대응 (PRD §10 기반)

| 위험 | 탐지 시점 | 대응 |
|------|---------|------|
| 메모리 폭증 (100만 노드) | M1-B 통합 테스트 | LazyTreeModel 청크 사이즈 줄이기, SQLite 페이징 |
| PyInstaller hidden import 누락 | M0, M5 | `--collect-all PySide6` 추가 또는 수동 import hook |
| Win32 ctypes 버퍼 오류 | M1-A 리뷰 | `/security-review` 필수, `ctypes.WinError()` 검증 추가 |
| Defender 오탐 EXE | M5 | UPX 비활성 유지, 코드 사이닝 (향후) |
| ETA 계산 부정확 | M2-A | exponential moving average 사용, 빠른 폴더는 clamping |

---

## 13. 변경 이력

| 버전 | 일자 | 변경 |
|------|------|------|
| 1.0 | 2026-05-06 | 초안 — PRD v0.1 + ARCHITECTURE v0.1 기준 전체 계획 |
