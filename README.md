# Tree-Size

Windows 디스크 사용량 분석 도구 — TreeSize Free / WizTree의 오픈 대체재.

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6%20%28Qt%206%29-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey)

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| **빠른 스캔** | 멀티스레드 병렬 스캔, 10만 파일 기준 ~1초 |
| **SQLite 캐시** | 재스캔 시 변경된 항목만 업데이트 (초회 대비 83× 빠름) |
| **계층형 트리뷰** | 이름·크기·할당·파일수·폴더수·비율·수정일 7개 컬럼, 정렬 가능 |
| **Bar Chart** | 선택 폴더의 자식 항목 Top 10 막대 그래프 |
| **실시간 필터** | 파일명(정규식)·확장자·크기 범위 필터, 재스캔 없이 즉시 반영 |
| **파일 작업** | 우클릭 → 휴지통/영구 삭제·탐색기 열기·경로 복사 |
| **내보내기** | CSV · JSON · HTML 3가지 형식 |
| **테마** | 라이트 / 다크 / 시스템 연동 전환 |
| **단일 EXE** | Python 설치 불필요, 더블클릭으로 즉시 실행 |

---

## 설치 및 실행

### 방법 1 — 단일 EXE (권장)

1. `dist/tree-size.exe` 다운로드
2. 더블클릭 — Python 설치 불필요

```
tree-size.exe
```

### 방법 2 — Python 소스 실행

```powershell
# 1. 저장소 클론
git clone https://github.com/<your-org>/tree-size.git
cd tree-size

# 2. 가상환경 생성 및 활성화
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. 의존성 설치
pip install -e .

# 4. 실행
python -m tree_size
```

> **주의**: Bash가 아닌 **PowerShell** 또는 **Windows 명령 프롬프트**에서 실행하세요.  
> GUI 앱은 Windows 그래픽 환경이 필요합니다.

---

## 사용법

### 기본 워크플로우

1. **Open Folder** 버튼 클릭 (또는 `Ctrl+O`) → 분석할 폴더 선택
2. 스캔이 시작되며 상태바에 진행률·ETA 표시
3. 트리뷰에서 폴더 클릭 → 오른쪽 Bar Chart에 자식 항목 시각화
4. 원하는 항목 우클릭 → 파일 작업 메뉴

### 키보드 단축키

| 단축키 | 동작 |
|--------|------|
| `Ctrl+O` | 폴더 열기 |
| `F5` | 재스캔 |
| `Ctrl+F` | 검색/필터 포커스 |
| `Ctrl+E` | 결과 내보내기 |
| `Ctrl+,` | 설정 |
| `Delete` | 선택 항목 삭제 |

### 검색·필터

- 상단 검색바에 파일명 입력 (부분 일치 또는 정규식)
- 확장자 드롭다운: All / Images / Videos / Archives / Custom
- 최소 크기(MB) 지정 가능
- 결과는 재스캔 없이 즉시 트리에 반영

### 설정 (`Ctrl+,`)

| 탭 | 항목 |
|----|------|
| General | 테마 (라이트 / 다크 / 시스템) |
| Scan Options | 심볼릭 링크 추적, 할당 크기 측정 |
| Cache | SQLite 캐시 활성화 여부 |

설정은 `%LOCALAPPDATA%\TreeSize\settings.ini`에 저장됩니다.

---

## 개발 환경 설정

### 요구사항

- Windows 10 / 11 (x64)
- Python 3.11+
- 가상환경 사용 권장

### 개발 의존성 설치

```powershell
pip install -e .
pip install pytest pytest-qt pytest-benchmark ruff mypy pyinstaller
```

### 자주 쓰는 명령

```powershell
# 실행
python -m tree_size

# 테스트
pytest                              # 전체 (303개)
pytest tests/unit -x --tb=short     # 단위 테스트만
pytest tests/ui -k tree_model       # UI 테스트 중 일부

# 코드 품질
ruff check .
ruff format .
mypy src/tree_size

# EXE 빌드
pyinstaller build/tree-size.spec --clean --noconfirm
```

---

## 프로젝트 구조

```
tree-size/
├── src/tree_size/
│   ├── core/           # 도메인 (Qt 무의존): scanner, filter, aggregator
│   ├── persistence/    # SQLite 캐시: schema, migrations, cache_db
│   ├── workers/        # QRunnable 워커 + 시그널
│   ├── ui/             # PySide6 위젯, 모델, 테마
│   ├── controllers/    # 애플리케이션 서비스
│   ├── exporters/      # CSV / JSON / HTML
│   └── utils/          # logging, paths, win32
├── tests/
│   ├── unit/           # 단위 테스트
│   ├── integration/    # 통합 테스트 (실제 파일시스템)
│   ├── ui/             # pytest-qt UI 테스트
│   └── benchmark/      # pytest-benchmark 성능
├── build/
│   ├── tree-size.spec  # PyInstaller 스펙
│   └── version_info.txt
├── resources/
│   └── splash.png
└── dist/
    └── tree-size.exe   # 배포 산출물
```

---

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| GUI 프레임워크 | PySide6 (Qt 6, LGPL) |
| 차트 | PyQtGraph |
| 아이콘 | qtawesome (FontAwesome 5) |
| 캐시 DB | SQLite (표준 라이브러리, WAL 모드) |
| 파일 삭제 | send2trash (Windows 휴지통 API) |
| 패키징 | PyInstaller 6 (`--onefile --windowed`) |
| 타입 검사 | mypy (`--strict`) |
| 린터 | ruff |
| 테스트 | pytest + pytest-qt + pytest-benchmark |

---

## 성능 지표

| 측정 항목 | 결과 |
|-----------|------|
| 10k 파일 전체 스캔 | ~857 ms |
| 10k 파일 증분 재스캔 (미변경) | ~10 ms (83× 빠름) |
| 테스트 통과 수 | 303 / 303 |
| 코드 커버리지 | 97% (core + persistence) |
| EXE 크기 | 82 MB |

---

## 생성 과정

이 프로젝트는 **Claude Code (Anthropic)** AI 코딩 에이전트를 사용하여 개발되었습니다.

### 개발 방식

단일 LLM이 모든 코드를 작성하는 방식 대신, 도메인별로 특화된 **5개의 서브 에이전트** 오케스트레이션 구조를 채택했습니다.

```
메인 Claude Code (오케스트레이터)
├── qt-ui-engineer    ← PySide6 위젯, QSS 테마, 다이얼로그
├── scanner-engineer  ← os.scandir, Win32 API, 증분 스캔
├── persistence-engineer ← SQLite 스키마, WAL, 마이그레이션
├── test-engineer     ← pytest, pytest-qt, 벤치마크
└── build-engineer    ← PyInstaller spec, EXE 빌드
```

### 마일스톤별 구현 이력

| 마일스톤 | 기간 | 주요 산출물 |
|---------|------|-----------|
| **M0** | W1 | pyproject.toml, 디렉토리 골격, PyInstaller 초안 |
| **M1-A** | W2 | Scanner (Qt 무의존), Node 데이터클래스, fs_probe Win32 |
| **M1-B** | W3 | LazyTreeModel (100만 노드 지원), ScanController, UI 연결 |
| **M2-A** | W4 | ETA 계산, Pause/Resume, 파일 작업 컨트롤러 |
| **M2-B** | W5 | FilterEngine, SearchBar, 실시간 필터 |
| **M3** | W6 | Bar Chart (PyQtGraph), CSV/JSON/HTML 내보내기 |
| **M4** | W7 | SQLite 캐시, WriterQueue, 증분 스캔 |
| **M5** | W8 | QSS 테마 완성, SettingsService, 단일 EXE 빌드 |

### 핵심 설계 결정

1. **코어/UI 분리** — `core/`는 Qt 무의존 순수 Python. 테스트 용이성 및 이식성 확보.
2. **이벤트 기반 동시성** — 모든 I/O는 `QRunnable` 워커 스레드. UI는 시그널/슬롯으로만 갱신.
3. **WriterQueue 패턴** — SQLite WAL 모드 + 단일 writer 큐로 다중 워커의 동시 쓰기 충돌 방지.
4. **점진적 트리 갱신** — 스캔 중 100ms 배치로 트리 갱신. UI 60fps 유지.
5. **증분 스캔** — mtime + size_logical 비교로 변경된 노드만 재방문. 미변경 디렉토리 서브트리 전체 스킵.

### 품질 기준

- `mypy --strict` 통과 (전 모듈)
- `ruff check` 오류 0
- 커버리지 ≥ 80% (core, persistence 기준 실제 97% 달성)
- Qt 시그널은 클래스 변수, 슬롯은 `@Slot(...)` 데코레이터 필수
- `QAbstractItemModel` 직접 구현 (100만 노드 성능 확보)

---

## 라이선스

MIT License. PySide6는 LGPL 조건을 따릅니다.  
배포 시 PySide6 LGPL 요건(동적 링크 또는 소스 공개)을 확인하세요.

---

## 기여

버그 리포트나 기능 제안은 Issues로 남겨주세요.  
코드 기여 시 `ruff check .` 및 `mypy src/tree_size` 통과 후 PR을 보내주세요.
