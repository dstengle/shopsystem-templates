"""Regression guard for the shop-templates update-path .fabro/ pour
(request_bugfix lead-1cj1 / plan tmpl-0re).

BLOCKER defect: `shop-templates update --target <bc-repo>` pours `.claude/`
(agents, settings, skills) but emits NOTHING to `.fabro/` — `_pour_fabro` was
wired only into `_cmd_bootstrap` (bootstrap path), never into `_cmd_update`.
bc-container launch's update path therefore left no fabro def and `fabro engage`
crashed. The three ADR-051/ADR-057 fabro scenarios (e7668df3 / 941d1df6 /
eb8e7449) exercised `_pour_fabro` via the BOOTSTRAP pour, masking the
update-path gap.

This test drives the REAL `_cmd_update` entry point against a minimal
already-initialized bc shop and asserts the COMPLETE `.fabro/` def is emitted
by update: the ADR-051 topology skeleton (workflow.fabro, workflow.toml,
project.toml, vaults/default/secrets.json) plus the generated node bodies
under nodes/ — every one present and non-empty. ADR-057 D2: both projections
come "out of the same pour", so update must emit `.fabro/` alongside `.claude/`.
"""
import argparse

from shop_templates.cli import _cmd_update

# The ADR-051 topology-skeleton files the complete .fabro/ def must carry
# (the update path emits these alongside .claude/).
_FABRO_SKELETON_RELS = (
    "workflow.fabro",
    "workflow.toml",
    "project.toml",
    "vaults/default/secrets.json",
)


def _minimal_bc_shop(target, shop_name="shopsystem-templates"):
    """Lay down the minimal bc-shop identity files update reads (the same
    .claude/shop/ identity surface a bootstrapped bc shop carries)."""
    shop_dir = target / ".claude" / "shop"
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "type.md").write_text("bc\n")
    (shop_dir / "name.md").write_text(f"{shop_name}\n")


def test_update_emits_complete_fabro_def(tmp_path):
    """`shop-templates update` against a bc shop emits the COMPLETE `.fabro/`
    def (skeleton + non-empty nodes/) via the real _cmd_update path — not just
    via bootstrap. Fails while _pour_fabro is wired only into _cmd_bootstrap."""
    target = tmp_path / "bc-shop"
    target.mkdir()
    _minimal_bc_shop(target)

    fabro_root = target / ".fabro"
    assert not fabro_root.exists(), "precondition: .fabro/ absent before update"

    rc = _cmd_update(argparse.Namespace(target=str(target), shop_type=None))

    assert rc == 0, "update must exit 0"

    # The topology skeleton must be present and non-empty.
    for rel in _FABRO_SKELETON_RELS:
        f = fabro_root / rel
        assert f.is_file(), (
            f"update did not emit .fabro/{rel} — the update path emits no "
            f"complete fabro def (ADR-057 D2: both projections out of the "
            f"same pour)"
        )
        assert f.stat().st_size > 0, f".fabro/{rel} emitted empty"

    # The generated node bodies must be present and non-empty.
    nodes_dir = fabro_root / "nodes"
    assert nodes_dir.is_dir(), "update did not emit .fabro/nodes/"
    node_files = sorted(nodes_dir.glob("*.md"))
    assert node_files, "update emitted .fabro/nodes/ with no node bodies"
    for nf in node_files:
        assert nf.stat().st_size > 0, f".fabro/nodes/{nf.name} emitted empty"
