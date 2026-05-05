---
description: 캐시 DB(cache.db)를 sqlite3 CLI로 열어 검사 모드 진입
argument-hint: [query]
---

`%LOCALAPPDATA%\TreeSize\cache.db`를 sqlite3로 열어 스키마/데이터를 검사한다.

## Steps

1. DB 경로 확인: `$env:LOCALAPPDATA\TreeSize\cache.db` (Windows). 없으면 사용자에게 안내 후 종료.

2. **`$ARGUMENTS`가 비어있으면**:
   - `.schema`, `SELECT COUNT(*) FROM nodes;`, `SELECT id, root_path, total_files FROM scans ORDER BY started_at DESC LIMIT 5;` 자동 실행.

3. **`$ARGUMENTS`에 SQL이 있으면**:
   - 읽기 전용 쿼리만 허용 (SELECT, EXPLAIN, PRAGMA로 시작). DDL/DML은 거부.
   - `sqlite3 -readonly $DB "$ARGUMENTS"` 실행.

4. **결과 출력**: 표 형식으로. 행 수가 100을 넘으면 처음 50 + 마지막 5만 표시.

## Pre-conditions
- `sqlite3` CLI 설치 (Windows: scoop/winget으로 설치 필요)
- 캐시 DB가 존재 (앱을 한 번 이상 실행한 적 있어야 함)

## 안전
- 절대 INSERT/UPDATE/DELETE/DROP을 실행하지 않는다.
- 사용자가 명시적으로 요청해도 별도 `--write` 플래그 추가 시에만 허용 (현재 미구현).

## Reference
- `docs/ARCHITECTURE.md` §6 — Schema
- `.claude/agents/persistence-engineer.md`
