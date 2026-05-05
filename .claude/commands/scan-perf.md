---
description: 합성 디렉토리 트리 생성 후 스캐너 성능 측정 (pytest-benchmark)
argument-hint: [file-count]
---

스캐너 성능을 측정한다. 기본 10만 파일, `$ARGUMENTS`로 개수 지정 가능 (예: `/scan-perf 1000000`).

## Steps

1. **Delegate to `test-engineer` agent**:
   - 합성 트리 생성 fixture(`tests/_helpers/synthetic_tree.py`)에서 `$ARGUMENTS` 또는 100,000 파일 트리 생성.
   - `pytest tests/benchmark/test_scan_perf.py --benchmark-only --benchmark-columns=mean,stddev,rounds` 실행.
   - 결과를 `docs/benchmarks/<YYYY-MM-DD>.json`에 기록(존재하지 않으면 생성).

2. **회귀 검사**:
   - 직전 baseline 대비 +20% 이상 느려졌으면 ❌ 경고.
   - 단축되었으면 baseline 갱신 제안.

3. **출력**:
   ```
   File count: NNN,NNN
   Mean: XX.X s   Stddev: X.Xs
   Baseline: XX.X s   Δ: -X.X% (faster) / +X.X% (slower)
   ```

## Pre-conditions
- venv 활성화
- `pytest-benchmark` 설치 (`requirements-dev.txt`)
- 합성 트리 fixture 존재

## Reference
- `docs/RULES.md` R-T3
- `docs/PRD.md` §5 (성능 NFR)
- `.claude/agents/test-engineer.md`
