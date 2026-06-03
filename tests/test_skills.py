"""Pins the skills package-data surface and its content guardrails."""
import pytest
from shop_templates.cli import iter_skill_files


def test_iter_skill_files_yields_relative_paths_and_bytes():
    files = dict(iter_skill_files())
    assert "test-driven-development/SKILL.md" in files
    for rel, body in files.items():
        assert not rel.startswith("/")
        assert "\\" not in rel
        assert isinstance(body, bytes) and len(body) > 0


def _skill(name):
    files = dict(iter_skill_files())
    return files[f"{name}/SKILL.md"].decode()


# bc-router classifies all three message types and names the gate paths
ROUTER_PINS = ["assign_scenarios", "request_maintenance", "request_bugfix",
               "shop-msg", "watch", "clarify", "reviewer"]


@pytest.mark.parametrize("needle", ROUTER_PINS)
def test_bc_router_pins(needle):
    assert needle.lower() in _skill("bc-router").lower()


def test_tdd_is_mandatory_and_clarify_only_exception():
    body = _skill("test-driven-development").lower()
    assert "mandatory" in body
    assert "clarify" in body  # the only exception path routes to the lead


def test_work_done_gate_carries_three_checks():
    body = _skill("work-done-gate").lower()
    assert "git status --porcelain" in body
    assert "origin/main" in body
    assert "scenario_hash" in body or "scenarios hash" in body


def test_writing_plans_is_beads_backed_no_doc():
    body = _skill("writing-plans-bdd").lower()
    assert "bd " in body or "beads" in body
    assert "no plan document" in body or "no doc" in body


def test_implementer_not_the_gate_reviewer_sole_emitter():
    # subagent-driven-development must tell the implementer it never emits
    # work_done for scenario work:
    sdd = _skill("subagent-driven-development").lower()
    assert "never emits `work_done`" in sdd or "never emits work_done" in sdd
    # bc-review must name the reviewer as the SOLE emitter for scenario work:
    assert "sole" in _skill("bc-review").lower()


def test_work_done_uses_repeatable_scenario_hash_flag_not_comma_joined():
    """Guard against the invalid `--scenario-hashes "<a>,<b>"` spelling.
    The CLI takes a repeatable singular `--scenario-hash` flag."""
    for name in ("bc-review", "work-done-gate"):
        assert "--scenario-hashes" not in _skill(name), (
            f"{name} uses the invalid plural flag"
        )
    assert "--scenario-hash" in _skill("bc-review")
