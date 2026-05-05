# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Tree-Size**: Windows GUI 애플리케이션 — 폴더별 디스크 사용량 분석 도구 (PySide6 + SQLite).
TreeSize Free / WizTree의 오픈 대체재로 만들며, PyInstaller 단일 EXE로 배포한다.

상세 사양은 다음 문서를 참조한다 (필요 시 직접 읽을 것):
- [`docs/PRD.md`](docs/PRD.md) — 제품 요구사항 (기능, 비기능, 마일스톤)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 아키텍처 (계층, 모듈, 데이터모델)

## Harness (Claude Code 협업 환경)

이 프로젝트는 Claude Code로 개발되며, 하네스가 정의되어 있다:
- [`docs/HARNESS.md`](docs/HARNESS.md) — 하네스 마스터 인덱스
- [`docs/RULES.md`](docs/RULES.md) — **반드시 준수**할 코드/리뷰 규칙 (35개)
- [`docs/AGENTS.md`](docs/AGENTS.md) — Sub-agent 분업 정의
- [`docs/SKILLS.md`](docs/SKILLS.md) — 사용/제작 Skills
- [`docs/MCP.md`](docs/MCP.md) — MCP 서버 설정

## Critical Rules (요약 — 전체는 `docs/RULES.md`)

### 아키텍처
- **R-A1**: `src/tree_size/core/**`에서 PySide6/PyQt6 import 금지 — 코어는 Qt 무의존.
- **R-A2**: 파일 I/O / 스캔 / DB 쓰기를 UI 스레드에서 직접 호출 금지. 항상 `QRunnable` + `Signal`.
- **R-A3**: SQLite 쓰기는 단일 `WriterQueue`에서만. 읽기는 다중 connection 허용 (WAL).
- **R-A4**: 경로는 `pathlib.Path`. `os.path.*` 금지.
- **R-A5**: 사용자 입력 경로는 항상 `utils.win32.to_long_path()` 통과.

### 코드 품질
- 타입 힌트 필수, `mypy --strict` 통과 (코어 우선).
- `Node`, `ProgressEvent` 등 대량 객체는 `@dataclass(slots=True)`.
- `print` 금지 → `logging.getLogger(__name__)`.
- 주석은 "왜"만. "무엇"은 코드가 말한다.

### UI
- 시그널은 클래스 변수, 슬롯은 `@Slot(...)` 메서드.
- 인라인 `setStyleSheet` 금지 → `themes/{light,dark}.qss`만.
- 모든 위젯 생성 시 `parent=` 명시.
- 100만 노드 트리 모델은 `QAbstractItemModel` 직접 구현 (NOT `QStandardItemModel`).

### 테스트
- `core/`/`persistence/`/`exporters/` 커버리지 ≥ 80%.
- 통합 테스트는 `tmp_path` 실제 파일시스템 사용. 모킹 금지.
- UI 테스트는 `pytest-qt`의 `qtbot.waitSignal()`. `time.sleep()` 금지.

### AI 협업
- UI 코드는 **반드시** `qt-ui-engineer` agent에 위임.
- 스캐너/Win32 API는 `scanner-engineer`.
- DB 스키마는 `persistence-engineer`.
- 테스트 작성은 `test-engineer`.
- 빌드/패키징은 `build-engineer`.
- 단순 grep/단일 파일 read는 메인이 직접.

## Sub-agents (자동 사용)

`.claude/agents/`에 정의되어 있으며, 키워드로 자동 매칭된다:
- `qt-ui-engineer` — UI 위젯, QSS, 다이얼로그
- `scanner-engineer` — `os.scandir`, Win32, reparse points, long paths
- `persistence-engineer` — SQLite 스키마, WAL, 마이그레이션
- `test-engineer` — pytest, pytest-qt, benchmark
- `build-engineer` — PyInstaller spec, manifest, EXE smoke

## Slash Commands (사용자 정의)

`.claude/commands/`에 정의:
- `/build-exe` — PyInstaller 단일 EXE 빌드 + 스모크 테스트
- `/scan-perf [count]` — 합성 트리로 스캐너 성능 측정 (회귀 검사)
- `/db-shell [query]` — 캐시 DB 검사 모드 (읽기 전용)
- `/new-component <type> <ClassName>` — Qt 컴포넌트 스캐폴딩

## Development Setup

```bash
# Bash (Git Bash)
source venv/Scripts/activate

# PowerShell
.\venv\Scripts\Activate.ps1
```

```bash
# 의존성 설치 (requirements.txt가 작성되면)
pip install -r requirements.txt -r requirements-dev.txt

# 테스트
pytest                              # 전체
pytest tests/unit -x --tb=short     # 단위 테스트만, 첫 실패에서 중단
pytest tests/ui -k tree_view        # UI 테스트 중 'tree_view' 매칭만
pytest --benchmark-only             # 벤치마크만

# 린트/타입
ruff check .
ruff format .
mypy src/tree_size

# 빌드
pyinstaller build/tree-size.spec --clean --noconfirm
```

## Project Structure

`docs/ARCHITECTURE.md` §3에 전체 구조가 정의되어 있다. 핵심:

```
tree-size/
├── src/tree_size/
│   ├── core/           # 도메인 (Qt 무의존) — Scanner, fs_probe, Node
│   ├── persistence/    # SQLite 캐시 — cache_db, migrations
│   ├── workers/        # QRunnable 워커 + 시그널
│   ├── ui/             # PySide6 위젯, 모델, 테마
│   ├── controllers/    # 애플리케이션 서비스
│   ├── exporters/      # CSV/JSON/HTML
│   └── utils/          # logging, paths, win32
├── tests/{unit,integration,ui,benchmark}/
├── build/tree-size.spec
├── docs/{PRD,ARCHITECTURE,HARNESS,RULES,AGENTS,SKILLS,MCP}.md
└── .claude/{settings.json, agents/, commands/}
```

## 환경 정보

- **OS**: Windows 11
- **Python**: 3.11.0 (venv `venv/`)
- **GUI**: PySide6 (Qt 6, LGPL)
- **DB**: SQLite (표준 라이브러리, WAL 모드)
- **빌드**: PyInstaller `--onefile --windowed`
- **UI 언어**: English only

## 주의사항

- `--no-verify` 플래그 절대 금지 (pre-commit 우회 안 됨).
- main 브랜치 force push 금지.
- 시스템 폴더(`C:\Windows`, `Program Files`) 삭제 작업 시 추가 경고 다이얼로그.
- ctypes/Win32 호출은 PR 시 `/security-review` 필수.
- 비밀 정보(.env, GitHub PAT 등)는 `.claude/settings.local.json` 또는 OS 환경변수만. 절대 커밋 금지.
