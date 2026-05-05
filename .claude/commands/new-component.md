---
description: 새 PySide6 위젯/모델/다이얼로그 스캐폴딩 자동 생성
argument-hint: <component-type> <ClassName>
---

새로운 UI 컴포넌트의 보일러플레이트를 자동 생성한다.

## Usage
- `/new-component widget MyTreePanel`
- `/new-component dialog SettingsDialog`
- `/new-component model FileSystemModel`

`$ARGUMENTS`의 첫 토큰은 종류(`widget`/`dialog`/`model`/`view`), 두 번째는 PascalCase 클래스명.

## Steps

1. `$ARGUMENTS` 파싱. 누락이면 사용자에게 질문.

2. **Delegate to `qt-ui-engineer` agent** with this task:
   - 클래스명을 snake_case로 변환 → 파일명 (`my_tree_panel.py`).
   - `src/tree_size/ui/<file>.py` 생성. 종류에 따라 보일러플레이트 다름:
     - **widget**: `QWidget` 상속 + `__init__` + `_setup_ui` + 기본 `Signal` 1개
     - **dialog**: `QDialog` 상속 + `accept`/`reject` + Cancel/OK 버튼 박스
     - **model**: `QAbstractItemModel` 상속 + 5개 필수 메서드 (`index`, `parent`, `rowCount`, `columnCount`, `data`) 시그니처
     - **view**: `QTreeView` 또는 `QTableView` 상속 + 컨텍스트 메뉴 hook
   - `tests/ui/test_<file>.py` 생성. `pytest-qt` 기본 인스턴스화 테스트.
   - `src/tree_size/ui/__init__.py`에 import 추가.
   - QSS hook이 필요하면 `themes/light.qss`/`dark.qss`에 셀렉터 자리만 추가 (`/* TODO: <ClassName> */`).

3. 보고:
   ```
   Created:
   - src/tree_size/ui/<file>.py (NN lines)
   - tests/ui/test_<file>.py (NN lines)
   Updated:
   - src/tree_size/ui/__init__.py
   ```

## Reference
- `docs/RULES.md` R-U1~R-U4
- `.claude/agents/qt-ui-engineer.md`
