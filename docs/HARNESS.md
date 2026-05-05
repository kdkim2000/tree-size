# HARNESS — Claude Code 하네스 엔지니어링 가이드

> **문서 버전**: 0.1
> **작성일**: 2026-05-06
> **목적**: Tree-Size 프로젝트를 Claude Code로 효율적으로 개발하기 위한 환경(하네스) 정의

---

## 1. 하네스 엔지니어링이란?

**하네스(harness)** = Claude(언어 모델)가 실제 작업을 수행하는 **실행 환경**.
모델 자체보다 모델 주변의 **도구·규칙·컨텍스트**가 결과 품질을 좌우한다.

이 프로젝트의 하네스는 5개 축으로 구성된다.

```
         ┌─────────────────────────────────────────────┐
         │              Claude Code                    │
         │           (Sonnet/Opus/Haiku)               │
         └─────────────────┬───────────────────────────┘
                           │
   ┌───────────┬───────────┼──────────┬──────────────┐
   ▼           ▼           ▼          ▼              ▼
┌──────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌──────────┐
│Skills│  │  MCP   │  │ Rules  │  │ Agents │  │ Commands │
│      │  │servers │  │CLAUDE  │  │.claude │  │ /slash   │
│ /md  │  │.json   │  │  .md   │  │/agents │  │  /md     │
└──────┘  └────────┘  └────────┘  └────────┘  └──────────┘
```

| 축 | 정의 | 본 프로젝트의 역할 |
|----|------|------------------|
| **Skills** | 재사용 가능한 작업 절차(슬래시 커맨드) | EXE 빌드, 스캔 프로파일링, DB 마이그레이션 자동화 |
| **MCP** | 외부 도구와의 표준화된 연결 | GitHub PR/이슈, SQLite 검사, 라이브러리 문서 조회 |
| **Rules** | 코드/아키텍처 가드레일 | Qt/Core 분리, 타입 힌트 필수, 워커 스레드 패턴 강제 |
| **Sub-agents** | 도메인 전문 에이전트 | qt-ui, scanner, persistence, test, build 별 분업 |
| **Commands** | 사용자 정의 슬래시 커맨드 | `/scan-perf`, `/build-exe`, `/db-shell` 등 |

---

## 2. 본 프로젝트가 정의하는 하네스 산출물

### 2.1 문서 (`docs/`)

| 파일 | 내용 |
|------|------|
| [`HARNESS.md`](./HARNESS.md) | 본 문서 — 마스터 인덱스 |
| [`SKILLS.md`](./SKILLS.md) | 사용/제작할 Skills 정의 |
| [`MCP.md`](./MCP.md) | MCP 서버 목록 및 설정 |
| [`RULES.md`](./RULES.md) | 프로젝트 코딩/리뷰 규칙 |
| [`AGENTS.md`](./AGENTS.md) | Sub-agent 분업 정의 |

### 2.2 실제 설정 (`.claude/`, repo root)

| 경로 | 역할 |
|------|------|
| `.claude/settings.json` | 프로젝트 설정(권한, 환경변수, hooks) — 팀 공유 |
| `.claude/settings.local.json` | 개인 설정 — `.gitignore` |
| `.claude/agents/*.md` | Sub-agent 정의 파일 |
| `.claude/commands/*.md` | 사용자 정의 슬래시 커맨드 |
| `.claude/skills/*/SKILL.md` | 프로젝트 전용 Skill |
| `.mcp.json` | MCP 서버 설정 (팀 공유, repo root) |
| `CLAUDE.md` | 항상 자동 로드되는 컨텍스트 — 규칙 요약 + 포인터 |

### 2.3 파일 디렉토리 구조

```
tree-size/
├── CLAUDE.md                          # 항상 로드 (요약 + 링크)
├── .mcp.json                          # MCP 서버
├── .claude/
│   ├── settings.json                  # 팀 공유 설정
│   ├── settings.local.json            # 개인 (gitignore)
│   ├── agents/
│   │   ├── qt-ui-engineer.md
│   │   ├── scanner-engineer.md
│   │   ├── persistence-engineer.md
│   │   ├── test-engineer.md
│   │   └── build-engineer.md
│   ├── commands/
│   │   ├── build-exe.md
│   │   ├── scan-perf.md
│   │   ├── db-shell.md
│   │   └── new-component.md
│   └── skills/
│       └── pyside6-component/
│           └── SKILL.md
└── docs/
    ├── PRD.md
    ├── ARCHITECTURE.md
    ├── HARNESS.md      ← 본 문서
    ├── SKILLS.md
    ├── MCP.md
    ├── RULES.md
    └── AGENTS.md
```

---

## 3. 적용 흐름 (Workflow)

### 3.1 신규 기능 개발

```
사용자: "TreeView에 파일 작업 컨텍스트 메뉴 추가해줘"
        │
        ▼
[1] CLAUDE.md → 자동 로드 → 규칙 인식
[2] 메인 Claude → 작업 분류
        │
        ├─ UI 작업 ─────► Agent(qt-ui-engineer)
        ├─ 파일 삭제 ───► Agent(scanner-engineer 또는 직접)
        └─ 테스트 ──────► Agent(test-engineer)
        │
        ▼
[3] Sub-agent → /skills/* 또는 /commands/* 활용
[4] MCP(github) → PR 생성 시 활용
[5] Rules 위반 → 사전 차단 (hooks)
```

### 3.2 EXE 빌드 → 배포

```
사용자: "/build-exe"
        │
        ▼
[1] .claude/commands/build-exe.md 로드
[2] Agent(build-engineer)에 위임
[3] Skill: pyinstaller-build 호출
[4] PyInstaller 실행 → dist/tree-size.exe
[5] 스모크 테스트 자동 실행
```

---

## 4. 우선순위 및 도입 단계

| 단계 | 산출물 | 가치 | 시점 |
|------|-------|------|------|
| **P0** | CLAUDE.md, RULES.md, settings.json | 즉시 영향 — 모든 작업에 적용 | M0 (지금) |
| **P0** | Sub-agents (qt-ui, scanner, persistence) | 분업으로 컨텍스트 효율↑ | M0 |
| **P1** | 슬래시 커맨드(`/build-exe`, `/scan-perf`) | 반복 작업 자동화 | M1 |
| **P1** | MCP (GitHub, SQLite) | PR·DB 검사 자동화 | M1 |
| **P2** | 커스텀 Skill (`pyside6-component`) | 컴포넌트 스캐폴딩 표준화 | M2 |
| **P2** | Hooks (pre-commit ruff/mypy) | 자동 검증 | M2 |

---

## 5. 측정 지표 (하네스가 잘 작동하는가?)

| 지표 | 목표 |
|------|------|
| **컨텍스트 사용률** | 메인 컨텍스트의 70% 이하 유지 (sub-agent로 격리) |
| **권한 프롬프트 횟수** | 세션당 5회 이하 (settings.json 화이트리스트) |
| **재작업률** | rules 위반으로 인한 재작업 < 10% |
| **빌드 성공률** | `/build-exe` 단일 명령으로 성공 100% |
| **테스트 자동화** | PR 생성 전 ruff/mypy/pytest 자동 통과 |

---

## 6. 다음 단계

1. **본 문서를 통독**한 뒤 [`SKILLS.md`](./SKILLS.md), [`MCP.md`](./MCP.md), [`RULES.md`](./RULES.md), [`AGENTS.md`](./AGENTS.md)를 차례로 읽는다.
2. `.claude/settings.json`과 `.claude/agents/*.md`를 검토하고 팀에 맞게 조정한다.
3. `.mcp.json`은 팀 표준 토큰/설정에 따라 수정한다.
4. M1부터 슬래시 커맨드를 추가하며 점진적으로 강화한다.

---

## 7. 변경 이력

| 버전 | 일자 | 변경 |
|------|------|------|
| 0.1 | 2026-05-06 | 초안 |
