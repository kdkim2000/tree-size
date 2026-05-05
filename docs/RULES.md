# RULES — 프로젝트 가드레일

> 본 문서는 Tree-Size 프로젝트 코드/리뷰/협업의 **반드시 준수할 규칙**을 정의한다.
> 핵심 항목은 [`CLAUDE.md`](../CLAUDE.md)에 요약되어 항상 자동 로드된다.

---

## 1. 아키텍처 규칙

### R-A1. UI/Logic 분리 강제
* `src/tree_size/core/**`에서 `PySide6`, `PyQt6`를 **import 금지**.
  * 검증: `ruff` custom rule 또는 import-linter.
* 도메인 로직은 Qt 없이 단독으로 단위 테스트 가능해야 한다.
* **이유**: 핵심 로직의 재사용성/테스트성 확보, Qt 버전 업그레이드 격리.

### R-A2. 워커는 항상 `QRunnable + Signal`
* UI 스레드에서 직접 파일 I/O / 스캔 / DB 쓰기 호출 금지.
* 결과는 `Signal`을 통해서만 UI로 전달.
* **이유**: 100만 파일 스캔 중에도 UI 60fps 유지.

### R-A3. SQLite 쓰기는 단일 큐로 직렬화
* `persistence/cache_db.py`의 `WriterQueue` 한 곳에서만 INSERT/UPDATE/DELETE.
* 읽기는 다중 connection 허용 (WAL).
* **이유**: WAL이라도 writer 경합은 lock 대기 → 처리량 저하.

### R-A4. 경로는 `pathlib.Path`로 통일
* `os.path.*` 사용 금지(I/O 경계의 어쩔 수 없는 경우 제외).
* 외부 API 호출 시 `str(path)` 변환.
* **이유**: 가독성 + 윈도우 long-path 처리 일관성.

### R-A5. Long path 지원 의무
* 사용자 입력 경로는 항상 `utils.win32.to_long_path()`를 거친 후 사용.
* `\\?\` 프리픽스 자동 부착, manifest의 `longPathAware` 활용.
* **이유**: 깊은 디렉토리(>260자)에서 스캔 누락 방지.

---

## 2. 코드 품질 규칙

### R-C1. 타입 힌트 필수
* 모든 public 함수/메서드에 시그니처 + 반환 타입.
* `mypy --strict` 통과(점진적 적용 — `core/` 먼저).
* **예외**: 테스트 코드의 fixture는 선택.

### R-C2. 데이터 클래스에 `slots=True`
* `Node`, `ProgressEvent` 등 대량 생성 객체는 `@dataclass(slots=True, frozen=...)` 사용.
* **이유**: 100만 객체 시 메모리 30~40% 절감.

### R-C3. 예외는 좁은 범위에서 잡는다
* `except Exception:` 광범위 캐치 금지.
* 스캐너에서는 `OSError`/`PermissionError`/`FileNotFoundError`만 명시적으로 잡는다.
* 잡은 예외는 반드시 로그 + UI에 전달.

### R-C4. Logging — print 금지
* `logging.getLogger(__name__)` 패턴 사용.
* DEBUG: 개발자, INFO: 일반 동작, WARNING: 권한/누락, ERROR: 처리 실패.

### R-C5. 주석은 "왜"만 작성
* `# 자식 노드를 lazy load한다` (X — 코드가 이미 말함)
* `# Windows long-path 호환을 위해 \\?\ 필수` (O — 비자명한 의도)

---

## 3. UI 규칙 (PySide6)

### R-U1. 시그널은 클래스 변수, 슬롯은 메서드
```python
class ScanController(QObject):
    progressUpdated = Signal(ProgressEvent)  # 클래스 변수

    @Slot(Path)
    def start(self, root: Path) -> None: ...
```

### R-U2. QSS는 파일로만 관리
* 인라인 `setStyleSheet("color: red")` 금지.
* `ui/themes/light.qss`, `dark.qss`만 사용.

### R-U3. 부모 명시
* 모든 위젯 생성 시 `parent=` 인자 전달.
* **이유**: Qt 객체 트리 누수 방지.

### R-U4. 모델은 직접 구현
* 100만 노드를 다루므로 `QStandardItemModel` 사용 금지.
* `QAbstractItemModel` 서브클래스 + lazy fetch.

---

## 4. 파일 작업 안전 규칙

### R-F1. 파괴적 작업은 확인 다이얼로그
* 영구 삭제, 이동, 권한 변경 → 사용자 명시적 확인 필수.
* 휴지통 삭제(send2trash)도 다중 선택은 confirm.

### R-F2. 시스템 폴더 보호
* `C:\Windows`, `C:\Program Files`, `C:\Program Files (x86)` → 삭제 비활성화.
* 옵션으로 해제 가능하지만 추가 경고.

### R-F3. 트랜잭션 로그
* 파일 작업(삭제/이동)은 `logs/file_ops.log`에 기록.
* 사용자가 추적 가능해야 함.

---

## 5. 테스트 규칙

### R-T1. 코어 모듈 커버리지 ≥ 80%
* `core/`, `persistence/`, `exporters/` 대상.
* UI 코드는 별도 기준(스모크 테스트로 충분).

### R-T2. 통합 테스트는 `tmp_path` 사용
* 실제 파일시스템 사용. 모킹 금지.
* **이유**: 모킹은 실제 권한 오류, 심볼릭 링크 동작을 잡지 못함.

### R-T3. 성능 회귀 차단
* `pytest-benchmark`로 10만 파일 스캔 ≤ 30초 유지.
* CI에서 회귀 시 fail.

### R-T4. UI 테스트는 `pytest-qt`
* `qtbot.waitSignal()`로 비동기 검증.
* `qtbot.mouseClick()`으로 인터랙션.

---

## 6. 커밋 / PR 규칙

### R-G1. 커밋 메시지: Conventional Commits
* `feat:`, `fix:`, `refactor:`, `perf:`, `test:`, `docs:`, `chore:`, `build:`
* scope 권장: `feat(scanner): handle reparse points`

### R-G2. PR 본문 필수 항목
* `## Summary` — 1~3 bullet
* `## Test plan` — 체크리스트
* (`/pr-description` Skill 사용 권장)

### R-G3. main에 직접 push 금지
* 모든 변경은 PR 통해서만.
* 단 본인 로컬의 `main`에 commit은 무방(아직 origin 없음 → 향후 적용).

### R-G4. 절대 `--no-verify` 사용 금지
* pre-commit hook 실패는 항상 근본 원인 수정.

---

## 7. AI 협업 규칙 (Claude Code 전용)

### R-AI1. 분업 강제
* UI 작업은 `qt-ui-engineer` agent에 위임.
* 스캔/파일시스템은 `scanner-engineer`.
* DB 스키마는 `persistence-engineer`.
* 테스트는 `test-engineer`.
* 빌드/패키징은 `build-engineer`.

### R-AI2. 컨텍스트 절약
* 대용량 검색·탐색은 `Explore` agent에 위임.
* 단일 파일 읽기는 메인이 직접.

### R-AI3. 파괴적 명령 사전 확인
* `git push --force`, `git reset --hard`, `rm -rf` → 사용자 확인 필수.
* 본 프로젝트의 `dist/`, `build/`, `venv/` 외 디렉토리 삭제 금지.

### R-AI4. 생성한 코드는 반드시 검증
* 새 모듈 작성 후 즉시 `pytest -k <모듈명>` 또는 import smoke test.
* TypeError가 잠재된 채 PR 작성 금지.

### R-AI5. Spec-First
* 기능 추가 시 PRD/ARCHITECTURE에 먼저 반영 → 코드 작성.
* 임의 추가 기능은 사용자 확인 필수.

---

## 8. 보안 규칙

### R-S1. 비밀 정보 절대 커밋 금지
* `.env`, `credentials.json`, `*.pem` → `.gitignore` + pre-commit hook으로 차단.
* GitHub PAT는 `settings.local.json` 또는 OS 환경 변수만.

### R-S2. ctypes/Win32 호출 검토
* `core/fs_probe.py`, `utils/win32.py`의 ctypes 호출은 PR 시 `security-review` 필수.
* 버퍼 크기, 핸들 누수 점검.

### R-S3. 외부 입력은 검증
* 파일 경로 입력 → `Path.resolve(strict=False)` 후 사용.
* CSV 내보내기 시 `;`, 줄바꿈 이스케이프.

---

## 9. 규칙 위반 처리

| 위반 유형 | 자동 차단 | 인적 검토 |
|-----------|----------|----------|
| ruff/mypy 오류 | pre-commit hook | — |
| Qt import in core/ | import-linter (CI) | — |
| 보안 정책 위반 | secret-scan hook | code review |
| 테스트 미작성 (P0 모듈) | — | PR review |
| 성능 회귀 | pytest-benchmark CI | PR review |

---

## 10. 변경 이력

| 버전 | 일자 | 변경 |
|------|------|------|
| 0.1 | 2026-05-06 | 초안 — 35개 규칙 정의 |
