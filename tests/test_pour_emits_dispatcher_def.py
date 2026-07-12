"""Regression guard for the ADR-058 dispatcher-half of the `.fabro/` def pour
(request_bugfix lead-9enm / plan tmpl-8rh; resolves the lead-5qj1 clarify).

The ADR-057 ownership migration moved the fabro def from bc-launcher's asset
mirror into shop-templates' `templates/fabro/` package asset. lead-7a8v migrated
the ADR-051 WORKFLOW half (workflow.fabro / workflow.toml / project.toml /
vaults/default/secrets.json). This test pins the DISPATCHER half (ADR-058): the
reactive-persistent cyclic poll-loop def — dispatcher.toml + dispatcher.fabro +
dispatch_acp_agent.py — must be captured VERBATIM into the same asset and poured
so `shop-templates update` / bootstrap emit the FULL def.

Two properties:

1. Both the direct `_pour_fabro` path AND the real `_cmd_update` entry point
   emit all three dispatcher files, byte-EQUAL to the `templates/fabro/`
   package asset (captured verbatim, not generated).

2. The poured def RESOLVES under fabro: `fabro run dispatcher.toml -I BC_NAME=x`
   parses the entrypoint and its `dispatcher.fabro` graph with NO
   "workflow not found" (the exact failure a missing dispatcher.toml causes),
   and `fabro validate dispatcher.fabro` exits 0. The live run needs a
   server/OAuth infeasible in this env, so this asserts DEF-RESOLUTION only.

Fails while the three dispatcher files are absent from the pour (the pre-fix
state: only the workflow half rode the asset).
"""
import argparse
import shutil
import subprocess
from importlib.resources import files

import pytest

from shop_templates.cli import _pour_fabro, _FABRO_PKG

_DISPATCHER_RELS = (
    "dispatcher.toml",
    "dispatcher.fabro",
    "dispatch_acp_agent.py",
)


def _asset_bytes(rel):
    """The bytes of a `templates/fabro/` package-asset file (the verbatim
    source the pour must emit byte-for-byte)."""
    return (files(_FABRO_PKG) / rel).read_bytes()


def _minimal_bc_shop(target, shop_name="shopsystem-templates"):
    shop_dir = target / ".claude" / "shop"
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "type.md").write_text("bc\n")
    (shop_dir / "name.md").write_text(f"{shop_name}\n")


def test_pour_fabro_emits_dispatcher_def_byte_equal(tmp_path):
    """Direct `_pour_fabro` emits all three ADR-058 dispatcher files, each
    byte-equal to the `templates/fabro/` package asset."""
    target = tmp_path / "bc-shop"
    target.mkdir()

    _pour_fabro(target)

    fabro_root = target / ".fabro"
    for rel in _DISPATCHER_RELS:
        poured = fabro_root / rel
        assert poured.is_file(), (
            f"pour did not emit .fabro/{rel} — the ADR-058 dispatcher half is "
            f"absent from the fabro def pour (only the ADR-051 workflow half "
            f"rides the asset)"
        )
        assert poured.read_bytes() == _asset_bytes(rel), (
            f".fabro/{rel} was not poured byte-verbatim from the "
            f"templates/fabro/ asset"
        )


def test_update_path_emits_dispatcher_def_byte_equal(tmp_path):
    """The REAL `_cmd_update` entry point (not just bootstrap) emits the three
    dispatcher files byte-equal to the asset — the full def out of the update
    pour (ADR-057 D2)."""
    from shop_templates.cli import _cmd_update

    target = tmp_path / "bc-shop"
    target.mkdir()
    _minimal_bc_shop(target)

    rc = _cmd_update(argparse.Namespace(target=str(target), shop_type=None))
    assert rc == 0, "update must exit 0"

    fabro_root = target / ".fabro"
    for rel in _DISPATCHER_RELS:
        poured = fabro_root / rel
        assert poured.is_file(), f"update did not emit .fabro/{rel}"
        assert poured.read_bytes() == _asset_bytes(rel), (
            f"update did not pour .fabro/{rel} byte-verbatim from the asset"
        )


@pytest.mark.skipif(
    shutil.which("fabro") is None, reason="fabro CLI not on PATH"
)
def test_poured_dispatcher_def_resolves_under_fabro(tmp_path):
    """The poured dispatcher def RESOLVES under fabro: `fabro run
    dispatcher.toml -I BC_NAME=x --dry-run` parses the entrypoint + its
    dispatcher.fabro graph with NO "workflow not found", and `fabro validate
    dispatcher.fabro` exits 0. (A live run needs a server/OAuth infeasible
    here; this pins DEF-RESOLUTION, the exact property a missing dispatcher.toml
    breaks.)"""
    target = tmp_path / "bc-shop"
    target.mkdir()
    _pour_fabro(target)
    fabro_dir = target / ".fabro"

    # `fabro run <entrypoint> --dry-run` must RESOLVE the def. It later fails on
    # the (infeasible) server, but resolution is proven by the graph banner and
    # the ABSENCE of the "workflow not found" the missing-toml case produces.
    run = subprocess.run(
        [
            "fabro", "run", "dispatcher.toml",
            "-I", "BC_NAME=x", "--dry-run", "--no-upgrade-check",
        ],
        cwd=fabro_dir, capture_output=True, text=True,
    )
    combined = run.stdout + run.stderr
    assert "workflow not found" not in combined, (
        f"fabro could not RESOLVE dispatcher.toml (workflow not found):\n{combined}"
    )
    assert "BcShopDispatcher" in combined, (
        f"fabro did not resolve the dispatcher.fabro graph from dispatcher.toml:"
        f"\n{combined}"
    )

    # `fabro validate` on the graph resolves server-free and exits 0.
    val = subprocess.run(
        ["fabro", "validate", "dispatcher.fabro", "--no-upgrade-check"],
        cwd=fabro_dir, capture_output=True, text=True,
    )
    assert val.returncode == 0, (
        f"fabro validate dispatcher.fabro did not exit 0:\n{val.stdout}{val.stderr}"
    )
