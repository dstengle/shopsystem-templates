"""Generic console-script clean-install import-currency guard (lead-q1wy).

PRE-STATE (the gap this closes): the existing packaging-currency guards in
`test_packaging_currency.py` assert only (a) each `[project.scripts]`
declaration is present in the built artifact and (b) the backing module
rides in the sdist/wheel — but NEVER that the installed console-script
actually IMPORTS on a clean install. A module-top-level import of an
undeclared / transitive dependency passes BOTH existing currency assertions
yet dies at first invocation. That is exactly how `tmpl-20n` (bc-emit
dead-on-arrival) escaped to v0.6.0.

`lead-ld7i` (`test_bc_emit_scenarios_dependency.py`) closed it for the
`bc-emit` console-script SPECIFICALLY, but the currency-guard PATTERN stayed
import-blind: any FUTURE package-delivered console-script with the same shape
(a module-top-level import of an undeclared dep) escapes the same way.

THIS guard generalizes the importability check beyond the bc-emit-specific
test: it ENUMERATES every `[project.scripts]` entry and asserts each one's
entry-point module imports AND its `--help` exits 0 in an environment where
only the package's DECLARED dependencies (plus the stdlib) are importable.
Any top-level import of an UNDECLARED / transitive package is masked, so the
entry point fails exactly as it would on a clean `pip install`.

Hermeticity / why it is not flaky:

  * The guard runs each entry point in a SUBPROCESS whose `builtins.__import__`
    is wrapped to block any top-level package that is neither stdlib nor a
    declared `[project.dependencies]` / declared-script-package member. This
    is the "mask declared deps' top-level packages" approach the bugfix names
    — it needs no network, no real venv build, and no published index, so it
    cannot flake on connectivity or timing. (A throwaway-venv install of the
    built wheel is the other approach the message offers; the masking approach
    gives the same clean-install import semantics deterministically and is
    what we use here.)
  * It enumerates `[project.scripts]` from the pyproject the build backend
    actually consumes, so a NEW console-script added tomorrow is covered with
    no test edit — the generic future-proofing this bugfix asks for.

The companion test `test_guard_catches_undeclared_top_level_import_regression`
PROVES the guard is real: it injects a temporary entry-point module whose top
level imports a package that is NOT declared, and asserts the SAME masked-import
check the real guard uses flags it (RED for an injected regression), so a green
result on the real scripts is meaningful rather than vacuous.
"""
from __future__ import annotations

import re
import subprocess
import sys
import sysconfig
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
SRC_DIR = REPO_ROOT / "src"


def _read_table_array(pyproject_text: str, header: str, key: str) -> list[str]:
    """Return the quoted string members of `key = [ ... ]` under `[header]`.

    A lightweight TOML reader scoped to one array key inside one table —
    enough to enumerate `[project].dependencies` without a TOML runtime dep
    (mirrors the reader in test_bc_emit_scenarios_dependency.py)."""
    # Isolate the named table body (up to the next top-level [table] header).
    tbl = re.search(
        rf"^\[{re.escape(header)}\]\s*(.*?)(?=^\[)",
        pyproject_text,
        flags=re.DOTALL | re.MULTILINE,
    )
    body = tbl.group(1) if tbl else pyproject_text
    m = re.search(
        rf"^\s*{re.escape(key)}\s*=\s*\[(.*?)\]",
        body,
        flags=re.DOTALL | re.MULTILINE,
    )
    if not m:
        return []
    return [s.strip().strip('"').strip("'") for s in re.findall(r"\"[^\"]*\"|'[^']*'", m.group(1))]


def _project_scripts(pyproject_text: str) -> dict[str, str]:
    """Return the `[project.scripts]` table as {script_name: 'module:attr'}."""
    tbl = re.search(
        r"^\[project\.scripts\]\s*(.*?)(?=^\[)",
        pyproject_text,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert tbl, "no [project.scripts] table found in pyproject"
    entries: dict[str, str] = {}
    for line in tbl.group(1).splitlines():
        m = re.match(r"\s*([A-Za-z0-9_.-]+)\s*=\s*[\"']([^\"']+)[\"']", line)
        if m:
            entries[m.group(1)] = m.group(2)
    return entries


def _declared_dependency_top_packages(pyproject_text: str) -> set[str]:
    """Top-level package names the package DECLARES as dependencies.

    For a `scenarios @ git+...` VCS pin the distribution name is `scenarios`,
    which is also its top-level import package, so the distribution token is a
    sound proxy for the importable top-level package."""
    deps = _read_table_array(pyproject_text, "project", "dependencies")
    tops: set[str] = set()
    for dep in deps:
        # Strip everything after the first non-name char: `name @ ...`,
        # `name>=1`, `name[extra]`, `name (==1)` all reduce to `name`.
        name = re.split(r"[\s@<>=!~;\[(]", dep, maxsplit=1)[0].strip()
        if name:
            tops.add(name.replace("-", "_"))
    return tops


def _script_own_top_package(target: str) -> str:
    """Top-level import package of an entry-point `module.path:attr` target."""
    module = target.split(":", 1)[0]
    return module.split(".")[0]


def _allowed_top_packages(pyproject_text: str) -> set[str]:
    """Packages the masked-import environment must allow: the package's own
    top-level packages (every script's module root) plus declared deps."""
    scripts = _project_scripts(pyproject_text)
    allowed = {_script_own_top_package(t) for t in scripts.values()}
    allowed |= _declared_dependency_top_packages(pyproject_text)
    return allowed


# A subprocess program that masks every top-level package not in ALLOWED and
# not a stdlib module, then imports the entry-point module and runs `<attr>
# ['--help']`. With an undeclared/transitive top-level import this raises
# ModuleNotFoundError exactly as a clean install would; with a lazy/declared
# import it reaches argparse `--help` and exits 0.
_MASKED_HELP_PROGRAM = textwrap.dedent(
    """
    import builtins, sys

    ALLOWED = set({allowed!r})
    STDLIB = set(sys.stdlib_module_names)

    _real_import = builtins.__import__

    def _masked_import(name, globals=None, locals=None, fromlist=(), level=0):
        # A relative import (`from . import x` / `from ._x import *`, level>0,
        # or an empty name) resolves against an already-imported parent
        # package, never a new top-level package — let it through untouched.
        if level and level > 0 or not name:
            return _real_import(name, globals, locals, fromlist, level)
        top = name.split(".", 1)[0]
        if top in ALLOWED or top in STDLIB or top in sys.builtin_module_names:
            return _real_import(name, globals, locals, fromlist, level)
        raise ModuleNotFoundError(
            "No module named %r (masked: not a declared dependency on a "
            "clean install)" % top
        )

    module_path, _, attr = {target!r}.partition(":")
    # The entry-point's OWN top-level package is the script under test, not a
    # dependency — it must always be importable.
    ALLOWED.add(module_path.split(".", 1)[0])

    builtins.__import__ = _masked_import
    # Drop already-cached non-allowed third-party modules so the mask bites
    # even when this dev env happens to have them installed.
    for mod in list(sys.modules):
        top = mod.split(".", 1)[0]
        if top not in ALLOWED and top not in STDLIB and top not in sys.builtin_module_names:
            del sys.modules[mod]

    mod = __import__(module_path, fromlist=["_"])
    entry = getattr(mod, attr)
    try:
        entry(["--help"])
    except SystemExit as exc:
        sys.exit(exc.code or 0)
    sys.exit(0)
    """
)


def _run_masked_help(target: str, allowed: set[str], extra_pythonpath: str | None = None):
    """Run an entry-point target's `--help` under the declared-deps-only mask.

    Returns the completed subprocess. `target` is `module.path:attr`."""
    import os

    program = _MASKED_HELP_PROGRAM.format(allowed=sorted(allowed), target=target)
    pythonpath = str(SRC_DIR)
    if extra_pythonpath:
        pythonpath = extra_pythonpath + os.pathsep + pythonpath
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": pythonpath}
    # Carry a HOME so any well-behaved lib that reads it does not crash.
    if os.environ.get("HOME"):
        env["HOME"] = os.environ["HOME"]
    return subprocess.run(
        [sys.executable, "-c", program],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def _all_scripts():
    return _project_scripts(PYPROJECT.read_text())


@pytest.mark.parametrize("script_name", sorted(_all_scripts().keys()))
def test_every_console_script_imports_and_help_exits_zero_on_clean_install(script_name):
    """GENERIC currency guard: every `[project.scripts]` console-script must
    import and `--help`-exit-0 with only DECLARED dependencies importable.

    This is the import-currency check the existing sdist/wheel + declaration
    guards never make. It catches an undeclared-dep / non-lazy module-top-level
    import (the tmpl-20n bug class) at build/test time rather than at
    launched-BC runtime — for EVERY current and future console-script, not
    just bc-emit."""
    pyproject_text = PYPROJECT.read_text()
    target = _all_scripts()[script_name]
    allowed = _allowed_top_packages(pyproject_text)
    result = _run_masked_help(target, allowed)
    assert "ModuleNotFoundError" not in result.stderr, (
        f"console-script {script_name!r} ({target}) fails to import on a clean "
        f"install: a module-top-level import of an UNDECLARED/transitive "
        f"package is not masked-safe (the tmpl-20n bug class). Declare the dep "
        f"in [project.dependencies] or make the import lazy.\n"
        f"STDERR:\n{result.stderr}"
    )
    assert result.returncode == 0, (
        f"console-script {script_name!r} ({target}) `--help` did not exit 0 on a "
        f"clean install (rc={result.returncode}).\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_guard_catches_undeclared_top_level_import_regression(tmp_path):
    """The guard is REAL, not vacuous: an entry-point module whose TOP LEVEL
    imports an undeclared package must be flagged by the SAME masked-import
    check the real guard uses.

    We synthesize a throwaway entry-point module that does
    `import an_undeclared_pkg_xyz` at module top level, point the masked-help
    runner at it with the real allow-set, and assert it fails with
    ModuleNotFoundError. If this regression slipped past the check, the green
    result on the real scripts would prove nothing."""
    pkg = tmp_path / "regression_probe.py"
    pkg.write_text(
        "import an_undeclared_pkg_xyz  # module-top-level undeclared import\n"
        "def main(argv=None):\n"
        "    import argparse\n"
        "    argparse.ArgumentParser(prog='probe').parse_args(argv)\n"
    )
    allowed = _allowed_top_packages(PYPROJECT.read_text())
    result = _run_masked_help(
        "regression_probe:main", allowed, extra_pythonpath=str(tmp_path)
    )
    assert result.returncode != 0 and "ModuleNotFoundError" in result.stderr, (
        "the masked-import guard FAILED to flag an injected undeclared "
        "module-top-level import — the guard is vacuous and a green result on "
        f"the real scripts proves nothing.\nrc={result.returncode}\n"
        f"STDERR:\n{result.stderr}"
    )


def test_guard_passes_a_lazy_import_entry_point(tmp_path):
    """Counterpart to the regression probe: an entry point whose undeclared
    import is LAZY (inside the command path, not module top level) must PASS
    the masked-help check — proving the guard pinpoints the non-lazy/undeclared
    shape and does not punish a correctly lazy import (the lead-ld7i fix shape).
    """
    pkg = tmp_path / "lazy_probe.py"
    pkg.write_text(
        "def main(argv=None):\n"
        "    import argparse\n"
        "    p = argparse.ArgumentParser(prog='lazy')\n"
        "    args = p.parse_args(argv)\n"
        "    import an_undeclared_pkg_xyz  # lazy: only on the real work path\n"
        "    return 0\n"
    )
    allowed = _allowed_top_packages(PYPROJECT.read_text())
    result = _run_masked_help(
        "lazy_probe:main", allowed, extra_pythonpath=str(tmp_path)
    )
    assert result.returncode == 0 and "ModuleNotFoundError" not in result.stderr, (
        "an entry point whose undeclared import is LAZY (inside the command "
        "path) must pass `--help` under the mask; the guard wrongly flagged it."
        f"\nrc={result.returncode}\nSTDERR:\n{result.stderr}"
    )


def test_scripts_enumeration_is_nonempty_and_covers_known_scripts():
    """Sanity pin: the enumeration the guard parametrizes over must be
    non-empty and must include the currently-declared console-scripts, so a
    pyproject edit that silently drops `[project.scripts]` (and thus empties
    the parametrization, making the guard vacuously pass) is caught."""
    scripts = _all_scripts()
    assert scripts, "[project.scripts] enumeration is empty; the guard would be vacuous"
    assert "shop-templates" in scripts and "bc-emit" in scripts, (
        f"expected the known console-scripts (shop-templates, bc-emit) in the "
        f"enumeration; got {sorted(scripts)}"
    )
