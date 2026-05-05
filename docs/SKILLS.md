# SKILLS — 사용/제작 Skills 정의

> Claude Code의 **Skill** = 슬래시 커맨드 또는 자동 트리거로 호출되는 재사용 가능 절차.
> 본 문서는 Tree-Size 프로젝트가 활용할 **내장 Skill**과 **커스텀 Skill**을 정의한다.

---

## 1. 내장 Skill 활용 매핑

| Skill | 사용 시점 | 비고 |
|-------|---------|------|
| `init` | 프로젝트 초기화 시 (이미 사용함) | CLAUDE.md 갱신 시 재실행 가능 |
| `review` | PR 리뷰 시 (`/review`) | 변경 사항 리뷰 자동화 |
| `security-review` | 릴리스 직전 (`/security-review`) | 파일 작업/Win32 ctypes 호출 검토 필수 |
| `simplify` | 리팩터링 후 (`/simplify`) | 변경된 코드의 재사용/품질 점검 |
| `update-config` | settings.json/hooks 변경 시 | 권한, 환경변수, 자동 동작 |
| `fewer-permission-prompts` | 세션 후반부 (`/fewer-permission-prompts`) | 권한 화이트리스트 자동 추가 |
| `pr-description` (my-skills) | PR 본문 작성 시 | git diff → 한글 PR 본문 |
| `loop` | 빌드/테스트 폴링 시 | `/loop 30s pytest -x` |

---

## 2. 본 프로젝트 전용 커스텀 Skill

### 2.1 위치
`.claude/skills/<skill-name>/SKILL.md` 형식.
프로젝트 단위 Skill은 repo에 커밋되어 팀 전체 공유.

### 2.2 정의할 Skills

| 이름 | 트리거 키워드 | 책임 |
|------|--------------|------|
| `pyside6-component` | "Qt 컴포넌트 만들어", "QWidget 추가" | PySide6 위젯/모델 스캐폴딩(파일 생성 + 시그널·슬롯 보일러플레이트) |
| `scan-benchmark` | "스캔 성능 측정", "벤치마크" | 합성 디렉토리 트리 생성 + pytest-benchmark 실행 |
| `db-migration` | "DB 마이그레이션", "스키마 변경" | `persistence/migrations.py`에 마이그레이션 추가 + 테스트 |
| `pyinstaller-build` | "EXE 빌드", "배포" | spec 검증 → 빌드 → 스모크 테스트 → 산출물 보고 |
| `qt-leak-check` | "메모리 누수", "QObject 누수" | `gc.get_objects()` + Qt 부모 트리 추적 스니펫 실행 |

---

## 3. Skill 작성 명세

### 3.1 SKILL.md 표준 구조

```markdown
---
name: pyside6-component
description: PySide6 위젯·모델 스캐폴딩 자동 생성. "Qt 컴포넌트 만들어",
             "QWidget 추가", "새 위젯" 등 Qt 컴포넌트 생성 요청 시 사용.
---

## When to use
- 새로운 QWidget 서브클래스 생성
- QAbstractItemModel 서브클래스 생성
- 다이얼로그/패널 추가

## What it does
1. 클래스명·파일명을 사용자에게 확인 (snake_case 변환)
2. `src/tree_size/ui/<file>.py`에 보일러플레이트 작성
3. 부모 클래스에 따라 시그널/슬롯/오버라이드 메서드 자동 삽입
4. `tests/ui/test_<file>.py`에 pytest-qt 기본 테스트 생성
5. `__init__.py`에 import 추가

## Conventions enforced
- 모든 위젯 클래스는 `parent: QWidget | None = None` 인자 필수
- 시그널은 클래스 변수로 선언 (`updated = Signal(int)`)
- QSS 스타일은 인라인 금지 → `themes/*.qss` 참조

## Templates
... (보일러플레이트 코드 블록)
```

### 3.2 명명 규칙

* **이름**: kebab-case, 동작/도메인을 기술 (`scan-benchmark` 좋음, `tools` 나쁨).
* **description**: 구체적이고 트리거 키워드 포함. 모델이 자동 매칭하는 핵심.
* **Frontmatter only**: `name`, `description`만 필수. 나머지는 본문 마크다운.

### 3.3 작성 시 주의

| 해야 할 일 | 하지 말 것 |
|-----------|-----------|
| 트리거 예시를 description에 포함 | 추상적 설명("Helper for Qt") |
| 파일 경로/템플릿을 본문에 명시 | 외부 URL에 의존 |
| 부작용을 명확히 (어떤 파일이 변경되는지) | "프로젝트를 개선합니다" 같은 모호한 표현 |
| 검증 단계 포함 (pytest 실행 등) | 생성만 하고 검증 누락 |

---

## 4. M0~M2 작성 우선순위

| 단계 | Skill | 사유 |
|------|-------|------|
| M0 | (커스텀 없음) | 내장 Skill로 충분 |
| M1 | `pyside6-component` | UI 코드 빈번 작성 시점 |
| M1 | `pyinstaller-build` | 첫 EXE 산출물 검증 |
| M2 | `scan-benchmark` | 성능 회귀 모니터링 시작 |
| M2 | `db-migration` | 스키마 변경 발생 시 |
| M3+ | `qt-leak-check` | 메모리 이슈 발생 시 |

---

## 5. 참고

* Claude Code Skill 공식 가이드: 사용자 프로필의 `~/.claude/skills/blank-template`을 복사해 사용.
* description은 미래 Claude 인스턴스가 자동으로 매칭하는 키이므로 **트리거 단어**를 풍부하게 포함.
