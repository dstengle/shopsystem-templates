"""Acceptance pins for the lead-pm main-session PM-mode role template
(PDR-033, work_id lead-kz33 — Behavior 1, 12 scenarios).

Every content scenario asserts against the `shop-templates show lead-pm`
surface, which resolves through ``_read_template("lead-pm")`` — the same
package-data boundary the other role templates use. The role-set-wiring
scenario asserts lead-pm is a member of the canonical ``lead`` role set so
the bootstrap pour includes it and ``show`` / ``list`` resolve it.

Scenario hashes pinned here (lead-kz33 assign_scenarios):
  90090bb7f38b9777  d132172b8d4659ed  38bb3a0ef6905784  16709fc0931d000b
  58381551b5029cb8  ffc4c880440d0ad0  96abd54a2c8dac75  a354959486530d40
  4dbfb0ae8790c776  72ae7fd0e41a01e3  657c435fa34ba18c  4a4ef884012be9dc

A dedicated file (not tests/conftest.py) is used deliberately so the
concurrent PDR-033 waves that share conftest do not collide.
"""
import subprocess
import sys

import pytest

from shop_templates.cli import _read_template, _CANONICAL_ROLE_SETS


def _body() -> str:
    body = _read_template("lead-pm")
    assert body is not None, "role template 'lead-pm' does not resolve"
    return body


def _lower() -> str:
    return _body().lower()


# ---------------------------------------------------------------------------
# Role-set wiring: lead-pm is a canonical member of the lead role set so the
# bootstrap pour writes it and `show` / `list` resolve it.
# ---------------------------------------------------------------------------


def test_lead_pm_in_canonical_lead_role_set() -> None:
    assert "lead-pm" in _CANONICAL_ROLE_SETS["lead"], (
        "lead-pm must be a member of _CANONICAL_ROLE_SETS['lead'] so the "
        "bootstrap pour and update reconciliation include it"
    )
    # The existing back-office roles must remain untouched.
    assert "lead-po" in _CANONICAL_ROLE_SETS["lead"]
    assert "lead-architect" in _CANONICAL_ROLE_SETS["lead"]


def test_show_lead_pm_resolves_via_cli() -> None:
    """`shop-templates show lead-pm` must print the template body (exit 0)."""
    proc = subprocess.run(
        [sys.executable, "-m", "shop_templates", "show", "lead-pm"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"`show lead-pm` exited {proc.returncode}; stderr: {proc.stderr!r}"
    )
    assert proc.stdout.strip(), "`show lead-pm` produced an empty body"
    assert proc.stdout == _read_template("lead-pm"), (
        "`show lead-pm` output must be the byte content of templates/lead-pm.md"
    )


# ---------------------------------------------------------------------------
# 4a4ef884012be9dc — structural section headers + non-empty body.
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = [
    "## Position",
    "## Mode entry and exit",
    "## Session-opening rule",
    "## What you own",
    "## Posture",
    "## Altitude rule",
    "## Boundaries",
    "## Skills",
]


def test_body_is_non_empty() -> None:
    assert _body().strip(), "lead-pm template body is empty"


@pytest.mark.parametrize("header", REQUIRED_SECTIONS)
def test_required_section_header_present(header: str) -> None:
    assert header in _body(), f"lead-pm template missing section header {header!r}"


# ---------------------------------------------------------------------------
# 90090bb7f38b9777 — identity: main-session PM mode, stakeholder front door,
# NOT a subagent, only interactive role; lead-po/lead-architect back-office;
# grounded on interactivity as an execution-topology position.
# ---------------------------------------------------------------------------


def test_identity_main_session_pm_mode_front_door_not_subagent() -> None:
    b = _lower()
    assert "product manager mode of the main session" in b
    assert "stakeholder's front door" in b
    assert "not a subagent" in b


def test_identity_only_interactive_role() -> None:
    b = _lower()
    assert "interactive dialogue with the product authority" in b
    assert "only role that does" in b


def test_identity_others_are_back_office() -> None:
    b = _lower()
    assert "lead-po and lead-architect are back-office" in b
    assert "lead-pm is the interface" in b


def test_identity_grounded_on_execution_topology() -> None:
    b = _lower()
    assert "position in the execution topology that only the main session holds" in b


# ---------------------------------------------------------------------------
# d132172b8d4659ed — scope: discovery+shaping slice of PM + product
# communication; GTM disciplines OUT; PDR-033 amendment-c cited.
# ---------------------------------------------------------------------------


def test_scope_discovery_shaping_plus_product_communication() -> None:
    b = _lower()
    assert "discovery-and-shaping slice of product management" in b
    assert "product communication" in b


def test_scope_gtm_disciplines_out_of_scope() -> None:
    b = _lower()
    for term in [
        "market research",
        "personas",
        "segmentation",
        "positioning",
        "pricing",
        "growth metrics",
    ]:
        assert term in b, f"GTM out-of-scope term {term!r} not named"
    assert "out of scope" in b


def test_scope_cites_pdr_033_amendment_c() -> None:
    b = _lower()
    assert "pdr-033 amendment-c" in b


# ---------------------------------------------------------------------------
# 38bb3a0ef6905784 — mode entered on directional/exploratory/ambiguous/
# multi-option input; committed contract -> lead-po; technical/dispatch ->
# existing routes.
# ---------------------------------------------------------------------------


def test_mode_entry_on_directional_input() -> None:
    b = _lower()
    for term in ["directional", "exploratory", "ambiguous", "multi-option"]:
        assert term in b, f"mode-entry trigger {term!r} not named"
    assert "outcome is direction rather than a contract or a dispatch" in b


def test_mode_entry_distinguishes_contract_and_technical_routes() -> None:
    b = _lower()
    assert "committed contract" in b
    assert "routes to the lead-po" in b
    assert "existing routes" in b


# ---------------------------------------------------------------------------
# 16709fc0931d000b — close-with-artifact gate.
# ---------------------------------------------------------------------------


def test_exit_only_via_session_record_with_artifact() -> None:
    b = _lower()
    assert "produced or revised list names at least one artifact" in b
    assert "no session closes without an artifact" in b


def test_empty_session_recorded_and_routed_not_closed_empty() -> None:
    b = _lower()
    assert "idle chat" in b
    assert "mis-routed po/architect task" in b
    assert "rather than closed empty" in b


# ---------------------------------------------------------------------------
# 58381551b5029cb8 — unconditional session-opening rule.
# ---------------------------------------------------------------------------


def test_session_opening_reads_current_state_and_journal() -> None:
    b = _lower()
    assert "before any substantive turn" in b
    assert "current-state doc" in b
    assert "completion journal" in b


def test_session_opening_problem_statement_cites_current_state() -> None:
    b = _lower()
    assert "cite the current-state entry or gap it addresses" in b
    assert "ungrounded in what exists is fantasy" in b


# ---------------------------------------------------------------------------
# ffc4c880440d0ad0 — altitude rule.
# ---------------------------------------------------------------------------


def test_altitude_problem_space_no_env_schemas_flags() -> None:
    b = _lower()
    assert "problem space" in b
    assert "capability level" in b
    assert "no env var names" in b
    assert "no schemas" in b
    assert "no cli flags" in b


def test_altitude_technical_claim_is_a_verification_request() -> None:
    b = _lower()
    assert "technical claim below that altitude is a request for architect pre-state verification" in b


def test_altitude_bounded_feasibility_probe_links_evidence() -> None:
    b = _lower()
    assert "bounded feasibility probe" in b
    assert "before converging a shape" in b
    assert "evidence section" in b


# ---------------------------------------------------------------------------
# 96abd54a2c8dac75 — vs-PO boundary + block-and-reopen.
# ---------------------------------------------------------------------------


def test_boundary_po_why_vs_commitment() -> None:
    b = _lower()
    assert "owns the why (intent -> candidate)" in b
    assert "lead-po owns the commitment (brief -> scenarios)" in b
    assert "never writes scenarios or briefs" in b


def test_boundary_po_block_and_reopen() -> None:
    b = _lower()
    assert "blocks a brief on a why-problem the candidate reopens with the lead-pm" in b


def test_boundary_po_no_cross_patching() -> None:
    b = _lower()
    assert "never lets the lead-po patch the why inside a brief" in b
    assert "never patches boundaries inside a candidate" in b


# ---------------------------------------------------------------------------
# a354959486530d40 — vs-Architect boundary.
# ---------------------------------------------------------------------------


def test_boundary_architect_problem_vs_solution_space() -> None:
    b = _lower()
    assert "holds the problem space and the architect holds the solution space" in b


def test_boundary_architect_prioritization_orders_verification_gates() -> None:
    b = _lower()
    assert "prioritization records order the dispatch queue" in b
    assert "pre-state verification gates what dispatches" in b


# ---------------------------------------------------------------------------
# 4dbfb0ae8790c776 — vs-product-authority boundary.
# ---------------------------------------------------------------------------


def test_boundary_product_authority_drafts_but_never_ratifies() -> None:
    b = _lower()
    assert "drafts direction pdrs and facilitates the product authority's decision" in b
    assert "ratification belongs to the product authority" in b
    assert "never ratifies" in b


# ---------------------------------------------------------------------------
# 72ae7fd0e41a01e3 — artifacts owned.
# ---------------------------------------------------------------------------


def test_artifacts_append_only_named() -> None:
    b = _lower()
    for term in [
        "intent records",
        "candidates",
        "prioritization records",
        "session records",
        "pdr drafts for converged direction decisions",
    ]:
        assert term in b, f"append-only artifact {term!r} not named"


def test_artifacts_living_docs_stewarded() -> None:
    b = _lower()
    assert "problem-space map" in b
    assert "current-state doc" in b
    assert "readme and site as outward renderings" in b


def test_artifacts_capability_claims_trace_to_current_state() -> None:
    b = _lower()
    assert "every capability claim in the readme or site traces to a current-state entry" in b


# ---------------------------------------------------------------------------
# 657c435fa34ba18c — mode -> skill -> terminal artifact mapping.
# ---------------------------------------------------------------------------


def test_skills_mode_to_skill_to_artifact_mapping() -> None:
    b = _lower()
    assert "discovery" in b and "discovery-dialogue skill" in b and "intent record" in b
    assert "shaping skill" in b and "candidate driven to shaped" in b
    assert "option-tradeoff skill" in b and "pdr draft or candidate fork" in b
    assert "prioritization skill" in b and "prioritization record" in b
    assert "problem-space-mapping skill" in b and "problem-space map revision" in b
    assert "product-narrative skill" in b
    assert "readme, site, or current-state revision" in b


def test_skills_every_session_declares_its_mode() -> None:
    b = _lower()
    assert "every session declares its mode in the session record" in b


# ---------------------------------------------------------------------------
# Zero-product-literal discipline: the template must stay slug-generic.
# ---------------------------------------------------------------------------


def test_no_product_specific_literal() -> None:
    assert "shopsystem" not in _lower(), (
        "lead-pm template must not carry the product-specific 'shopsystem' "
        "literal (templates are slug/dummyco-generic)"
    )
