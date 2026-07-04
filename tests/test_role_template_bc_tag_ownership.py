"""ADR-056 D11 role-template ownership repoint (work_id lead-vzxd.10, tmpl-8ut).

Post-cutover, the AUTHORITATIVE source for scenario ownership / assignment is
the `@bc:<name>` TAG in the scenario file — NOT beads. Beads is DEAUTHORIZED as
the ownership/assignment oracle (ADR-056 D11) but STAYS the work-tracking
registry and the source of the inbound `work_id`; only ownership/assignment
moves to the @bc tag.

These pins assert the rendered bc-reviewer / bc-implementer / lead-architect
role templates name the @bc tag (not beads) for scenario ownership and the
pre-state @scenario_hash enumeration, while preserving beads for work-tracking
+ the work_id. The templates are read through the package's template-access
surface (`_read_template`), the same surface `shop-templates show <role>`
renders.
"""
from __future__ import annotations

import pytest

from shop_templates.cli import _read_template


ROLE_TEMPLATES = ["bc-reviewer", "bc-implementer", "lead-architect"]


def _template(name: str) -> str:
    body = _read_template(name)
    assert body is not None, f"role template {name!r} does not resolve"
    return body


@pytest.mark.parametrize("role", ROLE_TEMPLATES)
def test_names_bc_tag_for_scenario_ownership(role: str) -> None:
    """The template names the `@bc` tag as the ownership/assignment source."""
    body = _template(role)
    assert "@bc" in body, (
        f"{role}.md must name the @bc tag as the scenario-ownership source "
        "(ADR-056 D11), but no @bc reference is present"
    )
    lowered = body.lower()
    # The @bc tag must be tied to OWNERSHIP / ASSIGNMENT (not merely mentioned).
    assert ("@bc tag" in lowered) or ("@bc:" in body and "own" in lowered), (
        f"{role}.md must tie the @bc tag to scenario ownership/assignment"
    )


@pytest.mark.parametrize("role", ROLE_TEMPLATES)
def test_deauthorizes_beads_as_ownership_oracle(role: str) -> None:
    """The template states beads is NOT the ownership/assignment oracle."""
    body = _template(role).lower()
    assert "adr-056" in body, f"{role}.md must cite ADR-056 for the cutover repoint"
    # A deauthorization statement: beads/bead is NOT the ownership/assignment
    # authority; the @bc tag is.
    deauth_markers = (
        "deauthorized",
        "not the ownership",
        "not consult beads",
        "not beads",
        "not from beads",
        "not the assignment oracle",
        "not the ownership/assignment oracle",
    )
    assert any(m in body for m in deauth_markers), (
        f"{role}.md must explicitly deauthorize beads as the ownership/"
        f"assignment oracle (ADR-056 D11). None of {deauth_markers!r} found"
    )


@pytest.mark.parametrize("role", ROLE_TEMPLATES)
def test_retains_beads_for_work_tracking_and_work_id(role: str) -> None:
    """Beads stays the work-tracking registry and the work_id source — only
    ownership/assignment moved to the @bc tag."""
    body = _template(role).lower()
    assert "work_id" in body, f"{role}.md must retain the work_id (beads-sourced)"
    assert "work-tracking" in body or "work tracking" in body, (
        f"{role}.md must state beads remains the work-tracking registry"
    )


@pytest.mark.parametrize("role", ROLE_TEMPLATES)
def test_scenario_hash_enumeration_reads_the_bc_tag(role: str) -> None:
    """The pre-state @scenario_hash enumeration / ownership determination reads
    the @bc tag in the scenario files (not beads)."""
    body = _template(role)
    lowered = body.lower()
    assert "@scenario_hash" in body, (
        f"{role}.md must reference the @scenario_hash enumeration"
    )
    # The enumeration/ownership determination is tied to the @bc tag in the
    # scenario file — assert both concepts co-occur in the template.
    assert "@bc" in body and "scenario file" in lowered, (
        f"{role}.md must name the @bc tag in the scenario file as the "
        "ownership/enumeration source"
    )
