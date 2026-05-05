---
description: PyInstaller로 tree-size.exe 단일 실행 파일 빌드 + 스모크 테스트
argument-hint: [--clean]
---

PyInstaller를 사용해 `dist/tree-size.exe`를 빌드하고 스모크 테스트까지 수행한다.

## Steps

1. **Delegate to `build-engineer` agent** with this task:
   - Verify `pyinstaller` and PySide6 versions match `requirements.txt`.
   - If `$ARGUMENTS` contains `--clean`, ask user to confirm `Remove-Item -Recurse build,dist` then proceed.
   - Run: `pyinstaller build/tree-size.spec --clean --noconfirm` from venv.
   - After build, run smoke test (launch EXE, verify it doesn't immediately exit).
   - Report artifact path, size, warnings.

2. **On success**, output:
   ```
   ✅ dist/tree-size.exe ready (XX MB)
   ```

3. **On failure**, surface the PyInstaller log tail and stop. Do not retry blindly.

## Pre-conditions
- venv activated: `source venv/Scripts/activate` (Bash) or `.\venv\Scripts\Activate.ps1` (PS)
- `requirements.txt` installed
- `build/tree-size.spec` exists

## Reference
- `docs/ARCHITECTURE.md` §11
- `.claude/agents/build-engineer.md`
