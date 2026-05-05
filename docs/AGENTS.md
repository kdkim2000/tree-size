# AGENTS — Sub-agent 분업 정의

> **Sub-agent** = 특정 도메인에 특화된 Claude 인스턴스. 메인 컨텍스트와 격리되어 큰 탐색·작업을 위임받는다.
> 본 프로젝트는 5개의 도메인 에이전트를 정의한다.

---

## 1. 분업 원칙

```
                ┌────────────────────────┐
                │   Main Claude Code     │  ← 사용자와 대화, 라우팅
                │   (오케스트레이터)      │
                └───────────┬────────────┘
                            │ Agent(...)
   ┌────────────┬───────────┼───────────┬────────────┐
   ▼            ▼           ▼           ▼            ▼
┌──────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐
│qt-ui-    │ │scanner- │ │persistence│ │ test-    │ │ build-  │
│engineer  │ │engineer │ │-engineer  │ │ engineer │ │ engineer│
└──────────┘ └─────────┘ └──────────┘ └──────────┘ └─────────┘
   UI 위젯     스캐너,      SQLite      pytest      PyInstaller
   레이아웃    fs_probe     스키마       pytest-qt   spec/EXE
   테마        Win32 API    마이그       fixture     스모크
```

### 1.1 분업이 필요한 이유

| 이유 | 효과 |
|------|------|
| **컨텍스트 보호** | 100만 파일 스캐너 코드 분석이 메인 대화창을 잡아먹지 않음 |
| **전문화된 시스템 프롬프트** | 각 에이전트가 자기 도메인 규칙만 깊게 이해 |
| **병렬 처리** | 독립 작업 시 동시 실행 |
| **재현성** | 도메인별 표준 절차를 .md로 고정 |

### 1.2 호출 규칙 (메인 Claude이 따를 것)

* UI 코드 작성/수정 → **반드시** `qt-ui-engineer`에 위임.
* 스캐너/Win32 API → `scanner-engineer`.
* SQLite/마이그레이션 → `persistence-engineer`.
* 테스트 작성 → `test-engineer`.
* 빌드/패키징/릴리스 → `build-engineer`.
* 단순 파일 읽기/grep은 메인이 직접 수행 (위임 오버헤드 회피).

---

## 2. 에이전트별 정의 요약

### 2.1 `qt-ui-engineer`

| 항목 | 내용 |
|------|------|
| **책임** | PySide6 위젯/모델/뷰/다이얼로그 작성, QSS 테마 |
| **소유 디렉토리** | `src/tree_size/ui/**` |
| **금지 영역** | `core/**` 직접 수정, SQL 작성, PyInstaller spec |
| **모델 추천** | sonnet (UI 코드 표현력 ≫ 추론 깊이) |
| **도구** | Read, Edit, Write, Glob, Grep, Bash(pytest-qt만) |

**전문 지식**:
- `QAbstractItemModel` 서브클래싱, lazy fetch
- 시그널/슬롯, `QThreadPool`, `Qt.ConnectionType.QueuedConnection`
- QSS 셀렉터, 다크모드 색상 토큰
- pytest-qt `qtbot` 사용

---

### 2.2 `scanner-engineer`

| 항목 | 내용 |
|------|------|
| **책임** | 파일시스템 스캔 로직, Win32 API 래퍼, 권한·심볼릭 핸들링 |
| **소유 디렉토리** | `src/tree_size/core/scanner.py`, `core/fs_probe.py`, `utils/win32.py`, `workers/scan_worker.py` |
| **금지 영역** | UI, 직접 SQL, PyInstaller spec |
| **모델 추천** | opus (Win32 ctypes 정확성 + 동시성 추론) |
| **도구** | Read, Edit, Write, Glob, Grep, Bash, WebSearch, WebFetch |

**전문 지식**:
- `os.scandir`, `DirEntry.stat(follow_symlinks=False)`
- Win32: `GetCompressedFileSizeW`, `FindFirstFileEx`, reparse point flags
- `\\?\` long path 프리픽스
- 심볼릭 링크 / 정크션 / 하드링크 식별 (NTFS reparse tags)
- `concurrent.futures.ThreadPoolExecutor` vs `QThreadPool` trade-off

---

### 2.3 `persistence-engineer`

| 항목 | 내용 |
|------|------|
| **책임** | SQLite 스키마, 마이그레이션, 쿼리 최적화, WAL/직렬화 |
| **소유 디렉토리** | `src/tree_size/persistence/**` |
| **금지 영역** | UI, 스캐너 워커, 빌드 |
| **모델 추천** | sonnet |
| **도구** | Read, Edit, Write, Bash (sqlite3 CLI) |

**전문 지식**:
- SQLite WAL, `PRAGMA synchronous=NORMAL`, `journal_mode=WAL`
- 인덱스 설계 (size DESC, parent_id)
- 마이그레이션 idempotent 설계
- 증분 스캔 비교 알고리즘 (mtime, size_logical)

---

### 2.4 `test-engineer`

| 항목 | 내용 |
|------|------|
| **책임** | 단위/통합/UI/벤치마크 테스트 작성, fixture |
| **소유 디렉토리** | `tests/**` |
| **금지 영역** | `src/**` 수정 (테스트 작성 후 발견된 버그는 메인에 보고) |
| **모델 추천** | sonnet |
| **도구** | Read, Edit, Write, Glob, Grep, Bash (pytest) |

**전문 지식**:
- `pytest-qt`: `qtbot`, `waitSignal`, `waitUntil`
- `pytest-benchmark`: 회귀 차단
- `tmp_path`로 합성 디렉토리 트리 생성
- 권한 테스트(Windows ACL 설정)

---

### 2.5 `build-engineer`

| 항목 | 내용 |
|------|------|
| **책임** | PyInstaller spec, 단일 EXE 빌드, 스모크 테스트, 매니페스트 |
| **소유 디렉토리** | `build/**`, `resources/**`, GitHub Actions workflow |
| **금지 영역** | 비즈니스 로직 수정 |
| **모델 추천** | sonnet |
| **도구** | Read, Edit, Write, Bash, WebFetch |

**전문 지식**:
- PyInstaller `--onefile` vs `--onedir`, hidden imports
- Windows manifest (`longPathAware`, `dpiAware`, `requestedExecutionLevel`)
- `version_info.txt`
- 코드 사이닝 (선택, 향후)
- Defender 오탐 회피 (UPX off, 정상 entry point)

---

## 3. 호출 패턴 예시

### 3.1 단일 위임

```
사용자: "트리뷰에 우클릭 컨텍스트 메뉴 추가"
메인:  Agent(subagent_type="qt-ui-engineer",
              description="Add context menu",
              prompt="src/tree_size/ui/tree_view.py에 우클릭 메뉴 추가.
                      메뉴 항목: 휴지통 삭제, 영구 삭제, 탐색기 열기, 경로 복사.
                      파일 작업은 controllers/file_ops_controller.py를 통해 위임할 것.
                      ARCHITECTURE.md §4.6 ScanController 패턴 참고.")
```

### 3.2 병렬 위임

```
사용자: "스캐너 + 캐시 + 테스트를 한 번에 추가"
메인:  [3개 Agent 병렬 호출]
       ├─ scanner-engineer: scanner.py 작성
       ├─ persistence-engineer: cache_db.py 작성
       └─ test-engineer: 두 모듈에 대한 테스트 셸 작성

       (test-engineer는 코드가 아직 없으므로 인터페이스 합의 후 시작)
```

### 3.3 순차 위임 (의존성 있을 때)

```
1) persistence-engineer: schema.sql + cache_db.py 인터페이스 확정
2) scanner-engineer:     cache_db 인터페이스에 의존하는 scan_worker 작성
3) test-engineer:        통합 테스트 작성
4) qt-ui-engineer:       UI에 진행률 시그널 연결
```

---

## 4. 에이전트 작성 규칙

### 4.1 파일 위치
`.claude/agents/<name>.md`

### 4.2 표준 frontmatter

```markdown
---
name: qt-ui-engineer
description: PySide6 UI 컴포넌트(위젯/모델/뷰/다이얼로그/QSS) 작성 및 수정 전담.
             "트리뷰", "다이얼로그", "메뉴", "테마" 같은 UI 키워드 시 사용.
tools: Read, Edit, Write, Glob, Grep, Bash
model: sonnet
---

(시스템 프롬프트 본문)
```

### 4.3 시스템 프롬프트에 포함할 것

* 책임 / 비책임 (소유 디렉토리, 금지 영역)
* 자주 참조할 문서 링크 (`docs/ARCHITECTURE.md` §X.Y)
* 도메인 규칙 핵심 (`docs/RULES.md` 발췌)
* 표준 작업 절차 (예: "위젯 생성 → 시그널 정의 → 테스트 작성")
* 출력 형식 (변경 파일 목록 + diff 요약)

### 4.4 시스템 프롬프트에 포함하지 말 것

* 일반적인 Claude 사용 규칙 (이미 시스템 레벨에 있음)
* 모든 PRD를 통째로 — 필요한 섹션만 발췌하거나 링크
* 다른 에이전트의 책임 영역

---

## 5. 메인 ↔ 에이전트 통신 규약

### 5.1 메인이 에이전트에게 줄 것

* **명확한 목표**: "X 기능 추가" 가 아니라 "tree_view.py L120 부근에 우클릭 핸들러 추가, 메뉴 5개"
* **참조**: 문서 링크 + 라인 번호
* **제약**: "파일을 새로 만들지 마", "테스트도 같이 작성"
* **응답 길이**: 간결한 보고는 200단어 이내 명시

### 5.2 에이전트가 메인에게 돌려줄 것

* 변경 파일 목록 (path:line)
* 핵심 변경 요약 (3~5줄)
* 발견된 위험/우려사항
* 후속 작업이 필요하면 명시

### 5.3 신뢰하되 검증 (Trust but verify)

* 에이전트의 보고는 "의도"이고 "결과"가 아닐 수 있음.
* 메인은 **변경된 파일을 직접 확인**(특히 git diff)한 뒤 사용자에게 보고.

---

## 6. 변경 이력

| 버전 | 일자 | 변경 |
|------|------|------|
| 0.1 | 2026-05-06 | 초안 — 5개 도메인 에이전트 정의 |
