# MCP — Model Context Protocol 서버 정의

> **MCP** = Claude Code가 외부 시스템(GitHub, DB, 검색 엔진 등)에 표준 프로토콜로 접근하는 방법.
> 본 프로젝트는 다음 MCP 서버를 사용한다.

---

## 1. 적용할 MCP 서버

### 우선순위 P0 (즉시 도입)

| 서버 | 트랜스포트 | 용도 |
|------|-----------|------|
| **filesystem** (built-in) | local | 로컬 파일 시스템 — Read/Edit/Write 도구로 충분, 별도 추가 불필요 |
| **github** | stdio (npx) | PR 생성/조회, 이슈 관리, CI 상태 확인 |
| **sequential-thinking** | stdio (npx) | 복잡한 디버깅·아키텍처 의사결정 시 단계적 사고 |

### 우선순위 P1 (M1~M2 도입)

| 서버 | 트랜스포트 | 용도 |
|------|-----------|------|
| **sqlite** | stdio | 캐시 DB(`cache.db`) 직접 조회/검사 — 개발 시 디버깅용 |
| **context7** (또는 ref) | http | PySide6/Qt 6 공식 문서 조회 (학습 데이터 cutoff 보완) |

### 우선순위 P2 (필요 시)

| 서버 | 트랜스포트 | 용도 |
|------|-----------|------|
| **memory** (built-in) | local | 사용자/프로젝트 메모리 — 이미 구성되어 있음 |
| **playwright** | stdio | (해당 없음 — 데스크톱 앱) |

---

## 2. `.mcp.json` (팀 공유, repo root)

> 본 파일은 **repo에 커밋**된다. 토큰 같은 비밀 값은 환경 변수 참조로만 작성.

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PAT}"
      }
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    },
    "sqlite": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-sqlite",
        "${LOCALAPPDATA}\\TreeSize\\cache.db"
      ]
    }
  }
}
```

### 환경 변수 설정 (`.claude/settings.local.json` 또는 OS)

```json
{
  "env": {
    "GITHUB_PAT": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }
}
```

> ⚠️ `settings.local.json`은 `.gitignore`에 포함. 토큰을 절대 커밋하지 말 것.

---

## 3. 서버별 사용 가이드

### 3.1 GitHub MCP

**언제 사용**:
- PR 생성, 이슈 조회, 리뷰 코멘트 확인
- CI 상태 체크 (Actions)
- 릴리스 노트 작성 시 커밋 히스토리 추출

**도구 예시**:
- `mcp__github__create_pull_request`
- `mcp__github__list_issues`
- `mcp__github__get_workflow_run`

**권한**: 본 프로젝트는 read+write 모두 필요(PR 생성). PAT scope: `repo`, `workflow`.

### 3.2 Sequential Thinking MCP

**언제 사용**:
- 동시성 버그 추적 (워커 스레드 ↔ UI 시그널 경합)
- 성능 회귀 원인 분석 (스캔이 왜 느려졌는가?)
- 아키텍처 변경 영향 평가

**비용 주의**: 토큰을 많이 쓰므로 단순한 작업에는 사용 금지.

### 3.3 SQLite MCP (P1)

**언제 사용**:
- 캐시 DB 스키마 검증
- 증분 스캔 결과 디버깅 (어떤 노드가 누락되었나?)
- 성능 쿼리 점검 (인덱스 사용 여부)

**개발 전용**: 사용자 환경에서는 활성화 불요. 개발자 PC의 `.claude/settings.local.json`에서만 활성.

### 3.4 Context7 / Ref MCP (P1)

**언제 사용**:
- PySide6 6.6+ 신규 API 사용 시 (학습 cutoff 이후)
- Win32 API 함수 시그니처 확인
- pytest-qt fixture 사용법 검색

**도입 시점**: M2(테마 시스템 + 차트) 단계에서 가치가 커짐.

---

## 4. MCP 도입 결정 트리

```
질문: "이 작업에 MCP가 필요한가?"
  │
  ├─ 외부 시스템(GitHub, DB)을 호출하는가?
  │   ├─ 예 ─► 해당 MCP 사용
  │   └─ 아니오 ─► 내장 도구(Bash/Read/Edit)로 충분
  │
  ├─ 학습 cutoff 이후 정보가 필요한가?
  │   ├─ 예 ─► WebSearch 또는 context7
  │   └─ 아니오 ─► 모델 지식 활용
  │
  └─ 한 작업에서 여러 단계 사고가 필요한가?
      ├─ 매우 복잡 ─► sequential-thinking
      └─ 보통 ─► 기본 reasoning
```

---

## 5. 보안 고려사항

| 위험 | 대응 |
|------|------|
| GitHub PAT 유출 | `settings.local.json`(gitignore) 또는 OS 환경 변수 사용 |
| MCP 서버가 임의 명령 실행 | 신뢰된 npm 패키지(`@modelcontextprotocol/*`)만 사용 |
| SQLite 경로 노출 | `${LOCALAPPDATA}` 환경 변수 사용 (사용자별로 다름) |
| 프롬프트 인젝션 (이슈 본문 등) | 외부 데이터를 받을 때 시스템 reminder 활성화 |

---

## 6. 트러블슈팅

| 증상 | 원인 | 조치 |
|------|------|------|
| `MCP server not responding` | npx 미설치 또는 네트워크 | Node.js 18+ 설치 확인 |
| `403 from GitHub` | PAT scope 부족 | `repo`, `workflow` 권한 추가 |
| `Database is locked` | SQLite WAL 모드 미설정 | 앱 시작 시 `PRAGMA journal_mode=WAL` 실행 |

---

## 7. 변경 이력

| 버전 | 일자 | 변경 |
|------|------|------|
| 0.1 | 2026-05-06 | 초안 — github, sequential-thinking, sqlite 정의 |
