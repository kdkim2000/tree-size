"""
Stop hook: 세션 종료 시 docs/journal/activity.log에 타임스탬프 + 요약 1줄을 기록.
전체 구조화 저널은 사용자가 /journal 커맨드로 명시적으로 생성한다.

Claude Code Stop hook 형식:
  stdin: JSON { "stop_hook_active": bool, "transcript_path": str, ... }
  exit 0 → 정상 (아무 출력 없으면 Claude에 보이지 않음)
  exit 2 → 훅 자체를 Claude가 재처리하도록 요청 (사용 안 함)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {}

    # Claude Code가 stop_hook_active=True 로 전달할 때만 기록
    # (무한 루프 방지: 훅 자체가 Claude를 다시 깨우지 않음)
    if data.get("stop_hook_active"):
        return

    project_root = Path(__file__).parent.parent
    journal_dir = project_root / "docs" / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)

    log_file = journal_dir / "activity.log"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    transcript_path = data.get("transcript_path", "")
    num_messages = _count_messages(transcript_path)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{now} | messages={num_messages} | branch={_git_branch(project_root)}\n")


def _count_messages(transcript_path: str) -> int:
    if not transcript_path:
        return 0
    try:
        with open(transcript_path, encoding="utf-8") as f:
            data = json.load(f)
        return len(data.get("messages", []))
    except Exception:
        return 0


def _git_branch(root: Path) -> str:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=3
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
