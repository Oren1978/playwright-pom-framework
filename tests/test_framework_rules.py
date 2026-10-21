"""
Framework rules, enforced by tests instead of by code review.

A convention that is only written in a README erodes. These checks fail
the build the moment someone adds a sleep or puts a selector in a test.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRAMEWORK_DIRS = ["tests", "pages", "api", "data", "support"]
SELECTOR_CALLS = {
    "locator",
    "get_by_role",
    "get_by_text",
    "get_by_label",
    "get_by_test_id",
    "get_by_placeholder",
    "query_selector",
}


def python_files(*dirs: str) -> list[Path]:
    """Every non-empty Python file in the given folders."""
    return sorted(
        p for d in dirs for p in (ROOT / d).rglob("*.py") if p.read_text(encoding="utf-8").strip()
    )


def calls_in(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            out.append((node.func.attr, node.lineno))
    return out


@pytest.mark.parametrize(
    "path", python_files(*FRAMEWORK_DIRS), ids=lambda p: str(p.relative_to(ROOT))
)
def test_no_fixed_waits(path: Path):
    """Fixed waits hide timing bugs and slow the suite. Use web-first assertions."""
    offenders = [line for name, line in calls_in(path) if name == "wait_for_timeout"]
    assert not offenders, f"{path.name}: wait_for_timeout on lines {offenders}"
    # time.sleep is additionally banned for the whole repo by ruff (TID251).


TEST_FILES = [p for p in python_files("tests") if p.name != Path(__file__).name]


@pytest.mark.parametrize("path", TEST_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_selectors_live_only_in_page_objects(path: Path):
    """One owner per selector: when the UI changes, only pages/ changes."""
    offenders = [f"{name}() line {line}" for name, line in calls_in(path) if name in SELECTOR_CALLS]
    assert not offenders, f"{path.name} uses selectors directly: {offenders}"
