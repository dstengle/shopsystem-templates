"""Regression guard for the shop-templates .fabro/ pour emitting the ADR-058
reactive-dispatcher def (request_bugfix lead-5qj1 / plan tmpl-6r0).

BLOCKER defect: `_pour_fabro` (ADR-057, wired into `_cmd_update` by lead-1cj1)
emits the ADR-051 WORKFLOW def (workflow.fabro/workflow.toml/project.toml/
vaults/nodes) but NOT the ADR-058 reactive-DISPATCHER def. After
`shop-templates update`/bootstrap, `/workspace/.fabro/` is MISSING
`dispatcher.toml` + `dispatcher.fabro` + `dispatch_acp_agent.py`. The fabro
engage runs `fabro run dispatcher.toml` (ADR-058 reactive dispatcher) and
crashes with `x workflow not found: /workspace/.fabro/dispatcher.toml`.

These tests drive the REAL `_cmd_update` entry point against a minimal
already-initialized bc shop and assert the COMPLETE `.fabro/` def is emitted:
the three ADR-058 dispatcher files are present, non-empty, and — on the real
`fabro` binary — `dispatcher.toml` RESOLVES the def (no "workflow not found").
Both projections come "out of the same pour" (ADR-057 D2), so update must emit
the dispatcher files alongside the workflow def, just as bootstrap does.
"""
import argparse
import shutil
import subprocess
from pathlib import Path

import pytest

from shop_templates.cli import _cmd_update

# The ADR-058 reactive-dispatcher files the complete .fabro/ def must carry,
# matching what `fabro run dispatcher.toml` (the engage) requires.
_DISPATCHER_RELS = (
    "dispatcher.toml",
    "dispatcher.fabro",
    "dispatch_acp_agent.py",
)
_FAB_BIN = "/usr/local/bin/fabro"


def _minimal_bc_shop(target, shop_name="shopsystem-templates"):
    """Lay down the minimal bc-shop identity files update reads (the same
    .claude/shop/ identity surface a bootstrapped bc shop carries)."""
    shop_dir = target / ".claude" / "shop"
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "type.md").write_text("bc\n")
    (shop_dir / "name.md").write_text(f"{shop_name}\n")


def _run_update(tmp_path) -> Path:
    target = tmp_path / "bc-shop"
    target.mkdir()
    _minimal_bc_shop(target)
    rc = _cmd_update(argparse.Namespace(target=str(target), shop_type=None))
    assert rc == 0, "update must exit 0"
    return target / ".fabro"


def test_update_emits_dispatcher_def(tmp_path):
    """`shop-templates update` emits the ADR-058 dispatcher files
    (dispatcher.toml, dispatcher.fabro, dispatch_acp_agent.py) via the real
    _cmd_update path — non-empty, alongside the workflow def."""
    fabro_root = _run_update(tmp_path)
    for rel in _DISPATCHER_RELS:
        f = fabro_root / rel
        assert f.is_file(), (
            f"update did not emit .fabro/{rel} — the ADR-058 reactive-"
            f"dispatcher def is missing, so `fabro run dispatcher.toml` "
            f"(the engage) crashes with 'workflow not found'"
        )
        assert f.stat().st_size > 0, f".fabro/{rel} emitted empty"


def test_poured_dispatcher_resolves_on_real_fabro(tmp_path):
    """The poured `dispatcher.toml` RESOLVES the def on the REAL fabro binary
    (no 'workflow not found'): `fabro validate dispatcher.toml` reaches and
    validates the dispatcher.fabro graph. This is the exact resolution the
    engage's `fabro run dispatcher.toml -I BC_NAME=x` needs to get past."""
    fabro_root = _run_update(tmp_path)
    fabro_bin = shutil.which("fabro") or (
        _FAB_BIN if Path(_FAB_BIN).exists() else None
    )
    if fabro_bin is None:
        pytest.skip("real fabro binary is not available; SKIP honestly")
    res = subprocess.run(
        [fabro_bin, "validate", "--json", "--no-upgrade-check", "dispatcher.toml"],
        cwd=str(fabro_root),
        capture_output=True,
        text=True,
    )
    combined = res.stdout + res.stderr
    assert "workflow not found" not in combined, (
        f"dispatcher.toml did NOT resolve on the real fabro binary — the "
        f"exact engage crash. output:\n{combined}"
    )
    assert res.returncode == 0, (
        f"`fabro validate dispatcher.toml` failed (rc={res.returncode}):\n"
        f"{combined}"
    )
