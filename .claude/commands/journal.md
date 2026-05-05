---
description: 현재 세션의 대화·결정·산출물을 구조화된 저널로 기록 (docs/journal/YYYY-MM-DD-NNN.md)
argument-hint: [session-type]
---

현재 대화 세션을 저널로 기록한다.

## Steps

1. **Session type 결정**: `$ARGUMENTS`가 있으면 그것을 사용. 없으면 대화 흐름으로 추론:
   - `Planning` — PRD/아키텍처/설계 논의
   - `Harness` — CLAUDE.md/agents/rules/MCP 작업
   - `Coding` — 소스 코드 작성/수정
   - `Review` — 코드 리뷰, `/review`, `/security-review`
   - `Debug` — 오류 추적/수정
   - `Docs` — 문서 작성만

2. **Delegate to `journal-engineer` agent** with this task:
   - 오늘 날짜의 시퀀스 번호를 계산해 파일 경로를 결정한다.
   - 이번 세션에서 이루어진 결정, 작성/수정된 파일, 규칙 적용 내역, 미해결 사항을 추출한다.
   - `docs/journal/YYYY-MM-DD-NNN.md`를 **표준 형식**으로 작성한다.
   - `docs/journal/INDEX.md`에 한 줄 요약을 추가한다.
   - git diff를 활용해 실제로 변경된 파일 목록을 확인한다.

3. **완료 후** 파일 경로만 출력. 저널 내용을 대화창에 반복 출력하지 않는다.

## 호출 예시
- `/journal` — 세션 타입 자동 추론
- `/journal Harness` — 하네스 작업 세션으로 명시
- `/journal Coding` — 코딩 세션으로 명시

## 참고
- 저널 파일: `docs/journal/YYYY-MM-DD-NNN.md`
- 인덱스 파일: `docs/journal/INDEX.md`
- 에이전트: `.claude/agents/journal-engineer.md`
