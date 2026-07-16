"""Regression guard: the /workspace/.fabro/ fabro-engage projection is a
BC-only artifact — a LEAD shop must NEVER receive it (request_bugfix
lead-npm2w).

BUG: `shop-templates bootstrap --shop-type lead ...` and `shop-templates
update --shop-type lead ...` poured the full BC-style `.fabro/` projection
(workflow.fabro, workflow.toml, dispatcher.*, dispatch_acp_agent.py,
nodes/{bc-implementer,bc-reviewer,bc-router,bc-review,bc-sufficiency-check,
work-done-gate}.md, vaults/default) into a LEAD shop alongside the correct
`.claude/` projection. A lead is the interactive router, not a
workflow.fabro-running BC-work-loop shop — it should never receive `.fabro/`.

FIX (option (b), lead-npm2w): the `_pour_fabro` call-site in both
`_cmd_bootstrap` and `_cmd_update` is gated on `shop_type == "bc"`, mirroring
the existing shop_type branching (`_skill_iterator_for`, the lead ops
scaffolding). The `.claude/` projection still pours for BOTH shop types; only
`.fabro/` becomes bc-only.

The conflicting pin e7668df366a93a60 (features/fabro_projection_pour.feature)
is BC-framed ("the shopsystem-templates BC is installed / a shop-templates
pour is run in a workspace") and still holds: a BC pour still emits `.fabro/`.
That invariant is asserted below alongside the new lead-skips-`.fabro/` guard.
"""
import argparse
import subprocess

from shop_templates.cli import _cmd_bootstrap, _cmd_update

# A representative sample of the BC-style .fabro/ tree the lead must NOT
# receive: the topology skeleton and the BC-role node bodies.
_FABRO_MARKERS = (
    "workflow.fabro",
    "workflow.toml",
    "nodes/bc-router.md",
    "nodes/bc-implementer.md",
    "nodes/bc-reviewer.md",
)


def _prepped_target(tmp_path, name):
    """A bootstrap target with a pre-existing .beads/ so the network-dependent
    bd-init / dolt-push block is skipped, and git initialized for .gitignore."""
    target = tmp_path / name
    target.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(target), check=True)
    (target / ".beads").mkdir()
    return target


def _minimal_shop(target, shop_type, shop_name="probe-shop"):
    """Lay down the .claude/shop/ identity files `update` reads."""
    shop_dir = target / ".claude" / "shop"
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "type.md").write_text(shop_type + "\n")
    (shop_dir / "name.md").write_text(f"{shop_name}\n")


def test_lead_bootstrap_does_not_emit_fabro(tmp_path):
    """A `--shop-type lead` bootstrap emits `.claude/` but NOT `.fabro/`."""
    target = _prepped_target(tmp_path, "lead-shop")

    rc = _cmd_bootstrap(
        argparse.Namespace(
            shop_type="lead",
            shop_name="probe-lead",
            target=str(target),
        )
    )
    assert rc == 0, f"lead bootstrap returned non-zero exit {rc}"

    assert (target / ".claude").is_dir(), (
        "lead bootstrap must still pour the .claude/ projection"
    )

    fabro_root = target / ".fabro"
    assert not fabro_root.exists(), (
        "lead bootstrap poured a /workspace/.fabro/ projection — a lead shop "
        "is the interactive router, not a workflow.fabro BC-work-loop shop, "
        "and must NEVER receive the .fabro/ projection (lead-npm2w)"
    )
    for marker in _FABRO_MARKERS:
        assert not (fabro_root / marker).exists(), (
            f"lead bootstrap emitted .fabro/{marker}"
        )


def test_bc_bootstrap_still_emits_fabro(tmp_path):
    """A `--shop-type bc` bootstrap still emits the `.fabro/` projection —
    the e7668df366a93a60 pin (BC pour emits .fabro/) holds unchanged."""
    target = _prepped_target(tmp_path, "bc-shop")

    rc = _cmd_bootstrap(
        argparse.Namespace(
            shop_type="bc",
            shop_name="probe-bc",
            target=str(target),
        )
    )
    assert rc == 0, f"bc bootstrap returned non-zero exit {rc}"

    fabro_root = target / ".fabro"
    assert fabro_root.is_dir(), (
        "bc bootstrap did not emit .fabro/ — e7668df366a93a60 requires a BC "
        "pour to emit the fabro-engage projection"
    )
    for marker in _FABRO_MARKERS:
        assert (fabro_root / marker).is_file(), (
            f"bc bootstrap did not emit .fabro/{marker}"
        )


def test_lead_update_does_not_emit_fabro(tmp_path):
    """`shop-templates update` against a lead shop emits NO `.fabro/`."""
    target = tmp_path / "lead-update"
    target.mkdir()
    _minimal_shop(target, "lead")

    fabro_root = target / ".fabro"
    assert not fabro_root.exists(), "precondition: .fabro/ absent before update"

    rc = _cmd_update(argparse.Namespace(target=str(target), shop_type=None))
    assert rc == 0, f"lead update returned non-zero exit {rc}"

    assert not fabro_root.exists(), (
        "lead update poured a /workspace/.fabro/ projection — update must skip "
        ".fabro/ entirely for a lead shop (lead-npm2w)"
    )


def test_bc_update_still_emits_fabro(tmp_path):
    """`shop-templates update` against a bc shop still emits `.fabro/` —
    reinforcing the update-path bc invariant alongside the lead skip."""
    target = tmp_path / "bc-update"
    target.mkdir()
    _minimal_shop(target, "bc", shop_name="shopsystem-templates")

    rc = _cmd_update(argparse.Namespace(target=str(target), shop_type=None))
    assert rc == 0, f"bc update returned non-zero exit {rc}"

    fabro_root = target / ".fabro"
    assert (fabro_root / "workflow.fabro").is_file(), (
        "bc update did not emit .fabro/workflow.fabro"
    )
    assert (fabro_root / "nodes" / "bc-router.md").is_file(), (
        "bc update did not emit .fabro/nodes/bc-router.md"
    )
