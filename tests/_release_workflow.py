"""Shared helpers for reading the EXECUTABLE body of a YAML workflow with
comment lines stripped — used by the scenario-846e463198ce78 pin
(test_release_no_bc_launcher_dispatch_emit.py and the pytest-bdd step defs
in conftest.py).

The comment-vs-executable distinction is load-bearing: release.yml's header
comment legitimately names the bc-launcher to explain that nothing is
emitted to it, so a naive raw-substring scan would false-positive. These
helpers expose the executable body so the assert-absent legs ignore tokens
that live only in comments.
"""
from __future__ import annotations

from pathlib import Path


def bc_root() -> Path:
    return Path(__file__).resolve().parent.parent


def release_workflow_path() -> Path:
    return bc_root() / ".github" / "workflows" / "release.yml"


def strip_inline_comment(line: str) -> str:
    """Remove a trailing ` # ...` comment from a single line, respecting
    single/double quotes so a `#` inside a quoted scalar is preserved."""
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or line[i - 1].isspace():
                return line[:i].rstrip()
    return line


def executable_body(text: str) -> str:
    """Return the EXECUTABLE body of a YAML workflow with full-line comments
    dropped and inline `#`-comment trailers removed, so a token appearing
    only in a descriptive comment is not seen by an assert-absent scan."""
    out_lines: list[str] = []
    for raw in text.splitlines():
        if raw.lstrip().startswith("#"):
            continue
        out_lines.append(strip_inline_comment(raw))
    return "\n".join(out_lines)
