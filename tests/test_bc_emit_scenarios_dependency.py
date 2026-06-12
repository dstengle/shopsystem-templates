"""bc-emit scenarios-dependency + lazy-import guard (lead-ld7i, fixes tmpl-20n).

PRE-STATE (the defect): `src/shop_templates/bc_emit.py` does
`from scenarios.hash import compute_scenario_hash` at MODULE TOP LEVEL, and
`pyproject [project].dependencies = []` does not declare `scenarios`. A clean
`pip install shop-templates` into a launched BC does NOT pull `scenarios`, so
importing the module (and therefore `bc-emit --help`) raises
`ModuleNotFoundError: scenarios` — the console-script is dead-on-arrival.

The two-part fix (both required):

  (a) declare `scenarios` (VCS-pinned per the ADR-018 install convention) in
      shop-templates `[project].dependencies`, so any env installing
      shop-templates resolves it; and
  (b) make the `scenarios` import LAZY — move it out of module top level and
      into the work-done hash-check code path — so importing `bc_emit` and
      running other subcommands (`bc-emit --help`) does NOT touch the
      `scenarios` import and cannot fail on it even when scenarios is absent.

These tests pin all three acceptance criteria:

  pin 1 — the delivered/declared pyproject `[project].dependencies` declares
          a VCS-pinned `scenarios` dependency.
  pin 2 — `bc_emit.py` carries NO module-top-level `scenarios` import
          (verified by parsing the module AST, not a substring grep).
  pin 3 — importing `shop_templates.bc_emit` and running `bc-emit --help`
          SUCCEEDS with `scenarios` unavailable (no
          `ModuleNotFoundError: scenarios`), proving the import is lazy.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BC_EMIT_SRC = REPO_ROOT / "src" / "shop_templates" / "bc_emit.py"
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _project_dependencies(pyproject_text: str) -> list[str]:
    """Extract the string members of the `[project].dependencies` array.

    A lightweight TOML-array reader scoped to the `dependencies = [ ... ]`
    table key — good enough to assert membership without a TOML dependency in
    the test runtime.
    """
    m = re.search(
        r"^\s*dependencies\s*=\s*\[(.*?)\]",
        pyproject_text,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert m, "no [project].dependencies array found in pyproject"
    body = m.group(1)
    return [s.strip().strip('"').strip("'") for s in re.findall(r"\"[^\"]*\"|'[^']*'", body)]


def test_pyproject_declares_vcs_pinned_scenarios_dependency():
    """pin 1 — `[project].dependencies` declares a VCS-pinned `scenarios`.

    Without this, a clean `pip install shop-templates` into a launched BC
    never resolves `scenarios`, so the bc-emit work-done hash path has no
    package to import.
    """
    deps = _project_dependencies(PYPROJECT.read_text())
    scenarios_deps = [d for d in deps if re.match(r"^scenarios\b", d)]
    assert scenarios_deps, (
        f"[project].dependencies does not declare a `scenarios` dependency; "
        f"a clean install of shop-templates would not resolve scenarios for "
        f"the bc-emit work-done hash path. dependencies = {deps!r}"
    )
    # VCS-pinned per the ADR-018 install convention (the same form
    # shopsystem-messaging declares: `scenarios @ git+https://.../@vX.Y.Z`).
    assert any("git+" in d and "@" in d for d in scenarios_deps), (
        f"`scenarios` dependency is not VCS-pinned per the install convention "
        f"(expected `scenarios @ git+https://.../<repo>@<tag>`); got "
        f"{scenarios_deps!r}"
    )


def test_bc_emit_has_no_module_top_level_scenarios_import():
    """pin 2 — no module-top-level `scenarios` import in bc_emit.py.

    Parse the module AST and assert that no top-level (module-body) Import or
    ImportFrom statement references the `scenarios` package. An import nested
    inside a function body is fine (that is the lazy form pin 3 relies on); a
    top-level one is the defect.
    """
    tree = ast.parse(BC_EMIT_SRC.read_text())
    offenders: list[str] = []
    for node in tree.body:  # MODULE-TOP-LEVEL statements only
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "scenarios":
                offenders.append(f"line {node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "scenarios":
                    offenders.append(f"line {node.lineno}: import {alias.name}")
    assert not offenders, (
        "bc_emit.py carries module-top-level `scenarios` import(s); they must "
        "be lazy (inside the work-done hash-check path) so `bc-emit --help` "
        f"works without scenarios installed. Offenders: {offenders}"
    )


def test_bc_emit_help_succeeds_with_scenarios_absent():
    """pin 3 — `bc-emit --help` (and importing the module) succeeds with
    `scenarios` made unavailable, proving the import is lazy.

    We run a subprocess whose `sys.modules['scenarios']` is poisoned to raise
    `ModuleNotFoundError` on any access of the package, then import
    `shop_templates.bc_emit` and invoke its parser's `--help`. With a
    module-top-level import this raises `ModuleNotFoundError: scenarios` at
    import time; with the lazy import it succeeds (argparse `--help` exits 0).
    """
    program = textwrap.dedent(
        """
        import builtins
        import sys

        # Poison the `scenarios` package so ANY import of it (or its
        # submodules) fails as it would on a clean install that never pulled
        # it — even though this dev env happens to have scenarios installed.
        _real_import = builtins.__import__

        def _blocked_import(name, *args, **kwargs):
            if name == "scenarios" or name.startswith("scenarios."):
                raise ModuleNotFoundError("No module named 'scenarios'")
            return _real_import(name, *args, **kwargs)

        builtins.__import__ = _blocked_import
        for mod in list(sys.modules):
            if mod == "scenarios" or mod.startswith("scenarios."):
                del sys.modules[mod]

        # Importing the module must NOT touch the scenarios import.
        import shop_templates.bc_emit as bc_emit

        # `--help` exits 0 via SystemExit; that path must not import scenarios.
        try:
            bc_emit.main(["--help"])
        except SystemExit as exc:
            sys.exit(exc.code or 0)
        sys.exit(0)
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO_ROOT / "src"), **_clean_env()},
    )
    assert "ModuleNotFoundError" not in result.stderr and "scenarios" not in result.stderr, (
        "importing bc_emit / running `bc-emit --help` failed with scenarios "
        f"absent — the scenarios import is not lazy.\nSTDERR:\n{result.stderr}"
    )
    assert result.returncode == 0, (
        f"`bc-emit --help` did not exit 0 with scenarios absent "
        f"(rc={result.returncode}).\nSTDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


def test_scenarios_import_still_present_in_hash_check_path():
    """The fix MOVES the import (lazy), it does not DELETE it: the work-done
    hash-check path must still import `scenarios.hash.compute_scenario_hash`.

    Assert that the module source still references the scenarios.hash import
    somewhere (inside a function body), so a future edit that simply removes
    the import — breaking the actual hash check — is caught.
    """
    src = BC_EMIT_SRC.read_text()
    assert "compute_scenario_hash" in src and "scenarios.hash" in src, (
        "bc_emit.py no longer references scenarios.hash.compute_scenario_hash; "
        "the lazy-import fix must MOVE the import into the work-done hash path, "
        "not delete it (the hash recompute still needs it)."
    )


def _clean_env() -> dict[str, str]:
    """A minimal env carrying PATH so the subprocess can find python."""
    import os

    return {"PATH": os.environ.get("PATH", "")}
