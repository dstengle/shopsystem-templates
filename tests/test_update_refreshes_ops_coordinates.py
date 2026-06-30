"""Regression guards for the shop-templates update-path bin/ops-coordinates
refresh (lead-k7aq / scenario 228 @scenario_hash:8e5955d5fb5bb9c8).

The corrected scenario 228 (in features/update_ops_scaffolding_coverage.feature)
pins the drifted -> refreshed case end-to-end through the real update entry
point. These focused unit guards lock the two adjacent behaviors the dispatch
asked to keep green alongside it:

  * create-if-absent (scenario 213 @scenario_hash:dd82193e56e52d95): a lead shop
    with bin/ops-coordinates ABSENT gets it CREATED by update, byte-equal to the
    bootstrap render-tokens body — covered by the same single unconditional
    re-render that handles the drifted-refresh case.
  * shop-owned non-touch (scenario 139 @scenario_hash:3c496f8858b6b033): update
    does NOT overwrite the shop-owned bin/shop-shell — the ops-coordinates
    refresh is disjoint from the _LEAD_OPS_FILES shop-owned set.
"""
import argparse

from shop_templates.cli import (
    _cmd_update,
    _ops_slug,
    render_ops_template,
)


def _minimal_lead_shop(target, shop_name="shopsystem-product"):
    """Lay down the minimal lead-shop identity files update reads."""
    shop_dir = target / ".claude" / "shop"
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "type.md").write_text("lead\n")
    (shop_dir / "name.md").write_text(f"{shop_name}\n")


def test_update_creates_ops_coordinates_when_absent(tmp_path):
    """213: update against a lead shop whose bin/ops-coordinates is ABSENT
    creates it byte-equal to the bootstrap render-tokens body."""
    target = tmp_path / "lead-shop"
    target.mkdir()
    _minimal_lead_shop(target)
    coords = target / "bin" / "ops-coordinates"
    assert not coords.exists(), "precondition: ops-coordinates absent"

    rc = _cmd_update(argparse.Namespace(target=str(target), shop_type=None))

    assert rc == 0, "update must exit 0"
    assert coords.is_file(), "update must CREATE bin/ops-coordinates when absent"
    expected = render_ops_template("ops-coordinates", _ops_slug("shopsystem-product"))
    assert coords.read_text() == expected, (
        "created bin/ops-coordinates must be byte-equal to the bootstrap render"
    )


def test_update_does_not_overwrite_shop_owned_shop_shell(tmp_path):
    """139: the ops-coordinates refresh is disjoint from the shop-owned
    bin/shop-shell — update must NOT overwrite a hand-edited bin/shop-shell."""
    target = tmp_path / "lead-shop"
    target.mkdir()
    _minimal_lead_shop(target)
    shell = target / "bin" / "shop-shell"
    shell.parent.mkdir(parents=True, exist_ok=True)
    sentinel = "#!/usr/bin/env bash\n# HAND-EDITED shop-owned shop-shell\n"
    shell.write_text(sentinel)

    rc = _cmd_update(argparse.Namespace(target=str(target), shop_type=None))

    assert rc == 0
    assert shell.read_text() == sentinel, (
        "update must NOT overwrite the shop-owned bin/shop-shell"
    )
