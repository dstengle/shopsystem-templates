"""Acceptance pins for the canonical lead primer's PDR-033 re-homing
(work_id lead-kz33 — Behavior-group C, 3 scenarios).

The primer is served through the package's public template-access surface
``read_claude_md_primer("lead")`` (the same boundary the lead_primer_*
feature scenarios read). PDR-033 retires the router-level product-authority
discovery gate and re-homes the product-discovery dialogue and structured
discovery-skill selection into the lead-pm main-session mode; the router's
job at the discovery boundary collapses to a CLASSIFICATION action
(PM-mode entry), holding no product judgment itself.

Scenario hashes pinned here (lead-kz33 assign_scenarios):
  e813a6f3a3b575ea  — PM-mode-entry classification standing rule replaces the
                       retired discovery gate; idle-detection & choice-
                       suppression rules remain unaltered.
  6273ec4a54466f6f  — effectively-empty at session start / idle-detection →
                       router ENTERS lead-pm mode (the only interactive seat),
                       not idle, not a discovery subagent.
  41f7ce92d19ce620  — PM-mode entry opens as a brainstorming conversation
                       first; structured discovery-skill selection re-homed
                       to the lead-pm skill group, not router-level triage.

Supersedes / retires (confirmed by the assigned Then-clauses' explicit
negations): 21c07707c418c6ed (product-authority discovery gate),
32b4fd22cfcf55d2 (proactively-open conducted-at-router-level), and
46afaafc507e7d6f (router-performs-skill-selection). The two-signal detection
(00bdd6985ab94756) and idempotent re-fire (bdba904f4f64f4a2) blocks are
PRESERVED.

A dedicated file (not tests/conftest.py) is used deliberately so the
concurrent PDR-033 waves that share conftest do not collide.
"""
import re

from shop_templates.cli import read_claude_md_primer


def _body() -> str:
    body = read_claude_md_primer("lead")
    assert body, "canonical lead primer body is empty"
    return body


def _L() -> str:
    # Collapse whitespace so phrase assertions survive line-wrapping.
    return re.sub(r"\s+", " ", _body().lower())


_DISCOVERY_SKILLS = (
    "jobs-to-be-done",
    "problem-framing-canvas",
    "opportunity-solution-tree",
    "customer-journey-map",
)


# ---------------------------------------------------------------------------
# e813a6f3a3b575ea — PM-mode-entry classification standing rule replaces the
# retired product-authority discovery gate.
# ---------------------------------------------------------------------------


def test_pm_mode_entry_classifies_directional_exploratory_ambiguous_multioption() -> None:
    L = _L()
    assert "pm-mode entry" in L
    assert re.search(
        r"directional[^.]*exploratory[^.]*ambiguous[^.]*multi-option[^.]*pm-mode entry",
        L,
    ), "the rule must classify directional/exploratory/ambiguous/multi-option input as PM-mode entry"
    assert re.search(
        r"enters the lead-pm main-session mode[^.]*rather than dispatching a discovery subagent",
        L,
    ), "PM-mode entry enters the lead-pm mode rather than dispatching a discovery subagent"


def test_pm_mode_entry_routes_contract_to_po_and_technical_to_existing_routes() -> None:
    L = _L()
    assert re.search(
        r"committed contract[^.]*lead-po", L
    ), "committed-contract input routes to the lead-po"
    assert re.search(
        r"technical[^.]*dispatch[^.]*existing routes", L
    ), "technical or dispatch work routes to the existing routes"


def test_pm_mode_entry_prefers_pm_when_unsure() -> None:
    L = _L()
    assert re.search(
        r"unsure[^.]*(prefer|prefers) pm", L
    ), "when unsure between PM and PO, prefer PM"
    assert "mis-route to pm costs one session" in L
    assert "mis-route to po produces an unanchored brief" in L


def test_pm_mode_entry_requires_session_record_open_and_close_gate() -> None:
    L = _L()
    assert re.search(
        r"pm-mode entry[^.]*session record[^.]*opened", L
    ), "on PM-mode entry the router ensures a session record is opened"
    assert re.search(
        r"(on exit|exit)[^.]*closed[^.]*non-empty produced or revised list[^.]*releasing the turn flow",
        L,
    ), "on exit the router verifies the record is closed with a non-empty produced/revised list before releasing turn flow"


def test_pm_mode_entry_router_holds_no_product_judgment() -> None:
    L = _L()
    assert re.search(
        r"router holds no product judgment[^.]*option framing[^.]*brainstorm[^.]*intent probing[^.]*lead-pm mode",
        L,
    ), "router holds no product judgment; option framing/brainstorm/intent probing live in the lead-pm mode"


def test_retired_product_authority_discovery_gate_is_gone() -> None:
    L = _L()
    assert "product-authority discovery gate" not in L, (
        "the retired router-level product-authority discovery gate must be gone"
    )
    assert "### standing rule: product-authority discovery gate" not in L
    # The retired gate's defining requirement — conduct the dialogue itself OR
    # cite a brief before dispatching a discovery subagent — must not survive.
    assert "cite an existing brief or pdr" not in L
    assert "conduct the product-authority discovery dialogue" not in L


def test_idle_detection_and_choice_suppression_rules_remain_unaltered() -> None:
    body = _body()
    assert "### Standing rule: idle-detection checklist" in body
    assert "Only when all five return empty is \"idle\" the correct posture." in body
    assert "### Standing rule: choice suppression" in body
    assert "DECIDE EVERY OPERATIONAL QUESTION YOURSELF AND ACT ON IT" in body


# ---------------------------------------------------------------------------
# 6273ec4a54466f6f — effectively-empty → ENTER lead-pm mode, not idle, not a
# discovery subagent.
# ---------------------------------------------------------------------------


def test_effectively_empty_enters_lead_pm_mode_rather_than_idle() -> None:
    L = _L()
    assert re.search(
        r"effectively-empty[^.]*session start[^.]*idle-detection[^.]*enters the lead-pm main-session mode[^.]*product-discovery conversation[^.]*product authority[^.]*rather than declaring idle",
        L,
    ) or re.search(
        r"effectively-empty[^.]*idle-detection[^.]*enters the lead-pm main-session mode[^.]*rather than declaring idle",
        L,
    ), "on effectively-empty at session start or idle-detection, the router enters lead-pm mode rather than idle"
    assert "session start" in L and "idle-detection" in L
    assert "product authority" in L


def test_effectively_empty_discovery_held_in_pm_mode_not_delegated() -> None:
    L = _L()
    assert re.search(
        r"held in the lead-pm main-session mode[^.]*only interactive seat", L
    ), "the discovery conversation is held in the lead-pm mode, the only interactive seat"
    assert re.search(
        r"not delegated[^.]*non-interactive discovery subagent", L
    ), "the conversation is not delegated to a non-interactive discovery subagent"


def test_effectively_empty_router_classification_dialogue_belongs_to_pm() -> None:
    L = _L()
    assert re.search(
        r"entering pm mode is the router's classification action", L
    ), "entering PM mode is the router's classification action"
    assert re.search(
        r"discovery dialogue belongs to the lead-pm", L
    ), "the discovery dialogue belongs to the lead-pm mode"


# ---------------------------------------------------------------------------
# 41f7ce92d19ce620 — brainstorming opener; structured discovery-skill
# selection re-homed to the lead-pm skill group, not router-level triage.
# ---------------------------------------------------------------------------


def test_pm_entry_opens_as_brainstorming_conversation_first() -> None:
    L = _L()
    assert re.search(
        r"general brainstorming conversation first[^.]*before committing to any single structured discovery skill",
        L,
    ), "PM-mode entry opens as a general brainstorming conversation first"


def test_structured_skill_selection_rehomed_to_lead_pm_not_router_triage() -> None:
    L = _L()
    assert re.search(
        r"selection of a structured discovery skill[^.]*within the lead-pm main-session mode",
        L,
    ), "structured discovery-skill selection happens within the lead-pm main-session mode"
    assert "lead-pm skill group" in L
    assert re.search(
        r"not a router-level triage", L
    ), "the selection is not a router-level triage step"


def test_router_does_not_enumerate_named_discovery_skill_list() -> None:
    L = _L()
    for skill in _DISCOVERY_SKILLS:
        assert skill not in L, (
            f"the retired named discovery-skill list must be gone from the primer "
            f"(router no longer enumerates {skill!r}); it re-homed to the lead-pm mode"
        )
