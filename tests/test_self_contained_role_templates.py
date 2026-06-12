"""Acceptance pin for WS-4 Part 2 (ADR-037 D2/D3, work_id lead-0nc8).

A fresh product instance, handed only the role templates (no framework spec
§1-6, no findings-from-prototype-1.md), must carry NO load-bearing external
§x/findings citation: every behavior a template names is executable from the
template alone. Any surviving `§` is a bare provenance footnote (attribution
only), never a "see §x of the spec for what to do" deferral. Situational
guidance (the turn-limited PO<->Architect decomposition exchange) is a
loadable PDR-014 skill, not ambient template prose.
"""
import re

import pytest

from shop_templates.cli import iter_skill_files, _read_template


ROLE_TEMPLATES = ["lead-architect", "lead-po", "bc-reviewer", "bc-implementer"]


def _template(name: str) -> str:
    body = _read_template(name)
    assert body is not None, f"role template {name!r} does not resolve"
    return body


def _skills() -> dict[str, str]:
    return {rel: body.decode() for rel, body in iter_skill_files()}


# --- D2: no load-bearing external citation ---------------------------------


@pytest.mark.parametrize("role", ROLE_TEMPLATES)
def test_no_findings_from_prototype_reference(role: str) -> None:
    """The findings-from-prototype-1.md doc is not shipped to a fresh product;
    no role template may reference it at all (the durable rule it carried must
    be inlined, the prototype-narrative footnote dropped)."""
    assert "findings-from-prototype" not in _template(role), (
        f"{role}.md references findings-from-prototype-1.md, which does not "
        f"resolve in a freshly-instantiated product"
    )


@pytest.mark.parametrize("role", ROLE_TEMPLATES)
def test_no_load_bearing_spec_deferral(role: str) -> None:
    """No template may defer operative doctrine to an external framework spec
    section. 'per §x of the spec' / 'see §x of the spec' / '§x of the spec'
    phrasings are load-bearing deferrals: they tell the reader to go read the
    spec for what to do. A fresh product ships no framework spec §1-6, so any
    such deferral is dangling."""
    body = _template(role)
    lowered = body.lower()
    # Catch "§<n> of the spec" and "section <n> of the spec" deferrals.
    assert "of the spec" not in lowered, (
        f"{role}.md defers to an external spec ('of the spec'); the operative "
        f"doctrine must be stated inline instead"
    )
    # Catch "per §x" / "see §x" deferral lead-ins (a bare provenance footnote
    # in parentheses is fine; a deferral verb in front of a § is not).
    for m in re.finditer(r"(per|see|refer to|defined in)\s+§", lowered):
        raise AssertionError(
            f"{role}.md contains a load-bearing deferral {m.group(0)!r} to an "
            f"external §; inline the doctrine and demote the § to a bare "
            f"provenance footnote"
        )


@pytest.mark.parametrize("role", ROLE_TEMPLATES)
def test_surviving_section_marks_are_bare_provenance(role: str) -> None:
    """Any surviving framework-spec `§x` reference must be a bare provenance
    footnote: it lives inside a parenthetical (attribution form), never as the
    operative subject of a sentence. ADR/PDR section refs (e.g. 'ADR-010 §4')
    are decision-record provenance and are exempt."""
    body = _template(role)
    for m in re.finditer(r"§", body):
        # Window of context around the § occurrence.
        start = max(0, m.start() - 40)
        ctx = body[start : m.end() + 20]
        # Exempt: ADR/PDR decision-record section citations.
        if re.search(r"(ADR|PDR)-\d+\s*§", ctx):
            continue
        # A bare framework-spec § must appear inside a parenthetical.
        assert "(" in body[start : m.start()] and ")" in body[m.end() : m.end() + 40], (
            f"{role}.md carries a framework-spec § that is not a bare "
            f"parenthetical provenance footnote; context: {ctx!r}"
        )


# --- D2: the operative doctrine each citation deferred to is now inline -----


def test_architect_eight_activities_named_inline() -> None:
    """The eight §3.2 Architect activities must be named inline so the
    catalogue is executable from the template alone."""
    body = _template("lead-architect")
    for activity in [
        "Write ADRs",
        "structurizr",
        "decomposition",
        "Assign scenarios",
        "Reconcile scenario register",
    ]:
        assert activity in body, (
            f"lead-architect.md no longer names the activity {activity!r} inline"
        )


def test_architect_work_id_is_lead_beads_issue_id_stated_inline() -> None:
    """The work_id-is-a-lead-beads-issue-ID rule (was deferred to §6) must be
    stated inline, not deferred to the spec."""
    body = _template("lead-architect").lower()
    assert "work_id" in body and "lead beads issue id" in body, (
        "lead-architect.md must state the work_id-is-a-lead-beads-issue-id "
        "rule inline"
    )


def test_architect_pre_state_determines_vehicle_stated_inline() -> None:
    """The durable rule from findings-from-prototype-1.md §5 — the pre-state
    (not the prior-slice pattern) determines the message vehicle — must be
    stated inline."""
    body = _template("lead-architect").lower()
    assert "pre-state" in body and "prior-slice pattern" in body, (
        "lead-architect.md must state the pre-state-determines-vehicle rule "
        "inline (durable rule from the dropped prototype footnote)"
    )


# --- D3: the turn-limited exchange is a loadable PDR-014 skill --------------


def test_turn_limited_exchange_is_a_loadable_skill() -> None:
    """The situational turn-limited PO<->Architect decomposition exchange
    (3-round default cap + one allowed extension) must live in a loadable
    skill under templates/skills/, not as ambient lead-architect prose."""
    skills = _skills()
    skill_path = "po-architect-decomposition-exchange/SKILL.md"
    assert skill_path in skills, (
        f"expected PDR-014 decomposition-exchange skill at {skill_path!r}; "
        f"present skills: {sorted(skills)}"
    )
    body = skills[skill_path].lower()
    assert "3 round" in body or "three round" in body, (
        "decomposition-exchange skill must carry the 3-round default cap"
    )
    assert "extension" in body, (
        "decomposition-exchange skill must carry the one-allowed-extension rule"
    )


def test_architect_no_longer_carries_turn_limited_exchange_as_ambient_prose() -> None:
    """The ambient '3 rounds by default' / 'one allowed extension' situational
    prose must no longer live in the lead-architect template body; the template
    may at most point to the loadable skill."""
    body = _template("lead-architect").lower()
    assert "rounds by default" not in body, (
        "lead-architect.md still carries the turn-limited 'rounds by default' "
        "exchange as ambient prose; extract it to the PDR-014 skill"
    )
    assert "one allowed extension" not in body, (
        "lead-architect.md still carries the 'one allowed extension' situational "
        "prose as ambient text; extract it to the PDR-014 skill"
    )
