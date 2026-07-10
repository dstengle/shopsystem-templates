"""Acceptance pins for the lead-architect template's PDR-033 additions
(work_id lead-kz33 — Behavior-group A, 2 scenarios).

Both scenarios assert against the `shop-templates show lead-architect`
surface, which resolves through ``_read_template("lead-architect")`` — the
same package-data boundary the other role templates use.

Scenario hashes pinned here (lead-kz33 assign_scenarios):
  aae38de4789bdbcd  — dispatch ordering answers to the latest RATIFIED
                       lead-pm prioritization record; deviations recorded in
                       the dispatch bead with a reason; until superseded.
  079dcd64367f5b61  — architect accepts a bounded pre-shape feasibility probe
                       from the lead-pm mode; output is a FINDING through the
                       existing pre-state verification machinery (not BC-code
                       execution); linked to the candidate's Evidence section;
                       time-boxed by the candidate's appetite, not spike-sized.

A dedicated file (not tests/conftest.py) is used deliberately so the
concurrent PDR-033 waves that share conftest do not collide.
"""
import re

from shop_templates.cli import _read_template


def _body() -> str:
    body = _read_template("lead-architect")
    assert body is not None, "role template 'lead-architect' does not resolve"
    return body


def _lower() -> str:
    # Collapse whitespace so phrase assertions survive line-wrapping.
    return re.sub(r"\s+", " ", _body().lower())


# ---------------------------------------------------------------------------
# aae38de4789bdbcd — dispatch order answers to the latest RATIFIED lead-pm
# prioritization record; deviations recorded in the dispatch bead; until
# superseded.
# ---------------------------------------------------------------------------


def test_dispatch_order_answers_to_ratified_prioritization_record() -> None:
    body = _lower()
    assert "ratified" in body, "template must name the ratified record"
    assert "prioritization record" in body
    assert "lead-pm" in body, "the ratified record is produced by the lead-pm mode"
    # Order dispatches according to the latest ratified record.
    assert re.search(
        r"order dispatch[^.]*latest[^.]*ratified[^.]*prioritization record", body
    ) or re.search(
        r"latest[^.]*ratified[^.]*prioritization record[^.]*order[^.]*dispatch",
        body,
    ), "template must direct ordering dispatches by the latest ratified record"


def test_dispatch_order_deviation_recorded_in_bead_with_reason() -> None:
    body = _lower()
    assert "deviation" in body
    assert "dispatch bead" in body
    assert re.search(
        r"deviation[^.]*ratified[^.]*order[^.]*dispatch bead[^.]*reason", body
    ), "a deviation from the ratified order is recorded in the dispatch bead with a reason"


def test_ratified_record_governs_until_superseded() -> None:
    body = _lower()
    assert "superseded" in body
    assert re.search(
        r"ratified prioritization record[^.]*(dispatch order|order)[^.]*answers to",
        body,
    ) or re.search(
        r"(dispatch order|order)[^.]*answers to[^.]*ratified prioritization record",
        body,
    ), "the ratified record is what dispatch order answers to"
    assert re.search(
        r"answers to[^.]*until[^.]*superseded", body
    ), "the ratified record governs until it is superseded"


# ---------------------------------------------------------------------------
# 079dcd64367f5b61 — bounded pre-shape feasibility probe from the lead-pm
# mode; a FINDING through pre-state verification machinery (not BC-code
# execution); linked to the candidate's Evidence section; time-boxed by the
# candidate's appetite, not spike-sized.
# ---------------------------------------------------------------------------


def test_architect_accepts_bounded_preshape_feasibility_probe_from_lead_pm() -> None:
    body = _lower()
    assert "feasibility probe" in body
    assert "pre-shape" in body
    assert "bounded" in body
    assert re.search(
        r"lead-pm[^.]*(request|may request)[^.]*bounded[^.]*pre-shape[^.]*feasibility probe",
        body,
    ), "the lead-pm mode may request a bounded pre-shape feasibility probe"


def test_probe_output_is_a_finding_through_pre_state_machinery_not_bc_code() -> None:
    body = _lower()
    assert "finding" in body
    assert "pre-state verification" in body
    assert re.search(
        r"finding[^.]*pre-state verification", body
    ), "the probe output is a finding produced through pre-state verification machinery"
    assert re.search(
        r"not[^.]*bc[- ]code execution", body
    ), "the finding is not BC-code execution"


def test_probe_finding_linked_to_candidate_evidence_section() -> None:
    body = _lower()
    assert "evidence" in body
    assert re.search(
        r"link[^.]*finding[^.]*candidate[^.]*evidence section", body
    ), "the architect links the finding back to the candidate's Evidence section"


def test_probe_is_appetite_time_boxed_not_a_spike() -> None:
    body = _lower()
    assert "appetite" in body
    assert "time-boxed" in body
    assert re.search(
        r"time-boxed[^.]*(candidate|appetite)", body
    ), "the probe is time-boxed by the candidate's appetite framing"
    assert re.search(
        r"not[^.]*spike", body
    ), "the probe is not a spike-sized implementation"
