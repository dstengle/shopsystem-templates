"""Regression tests for shop-templates package data and CLI.

These pin the package's public surface — what templates exist, that
they can be read via the package-data boundary (importlib.resources),
that the CLI exposes them, and that each template has the structural
sections that callers depend on. The Markdown CONTENT inside templates
is allowed to evolve; the section headers are the load-bearing pins.
"""
import subprocess

import pytest

from shop_templates.cli import _list_template_names, _read_template


EXPECTED_TEMPLATES = ["bc-implementer", "bc-reviewer", "lead-architect", "lead-po"]

BC_IMPLEMENTER_REQUIRED_SECTIONS = [
    "## Your default posture: SEEK CLARITY",
    "## Your job",
    "## Sufficiency check — `request_maintenance`",
    "## Sufficiency check — `assign_scenarios`",
    "## Sufficiency check — `request_bugfix`",
    "## Hand-off to the Reviewer",
    "## Anti-rationalization",
    "## Constraints",
    "## Reporting back",
]

BC_REVIEWER_REQUIRED_SECTIONS = [
    "## What you read",
    "## What you do",
    "## Outcomes",
    "## Anti-rationalization",
    "## Reporting back",
]

LEAD_PO_REQUIRED_SECTIONS = [
    "## Your default posture: COMMIT TO SPECIFICS",
    "## Your job",
    "## Sufficiency check — authoring a scenario",
    "## Sufficiency check — responding to a `clarify`",
    "## Anti-rationalization",
    "## Constraints",
    "## Reporting back",
]

LEAD_ARCHITECT_REQUIRED_SECTIONS = [
    "## Your default posture: PRE-STATE DETERMINES VEHICLE — VERIFIED EMPIRICALLY",
    "## Your job",
    "## Sufficiency check — message-type selection",
    "## Sufficiency check — `assign_scenarios`",
    "## Sufficiency check — `request_bugfix`",
    "## Sufficiency check — `request_maintenance`",
    "## Anti-rationalization",
    "## Constraints",
    "## Reporting back",
]


def test_expected_templates_are_listed():
    assert _list_template_names() == EXPECTED_TEMPLATES


def test_each_expected_template_can_be_read():
    for name in EXPECTED_TEMPLATES:
        content = _read_template(name)
        assert content is not None
        assert len(content) > 0


def test_unknown_template_returns_none():
    assert _read_template("does-not-exist") is None


@pytest.mark.parametrize("section", BC_IMPLEMENTER_REQUIRED_SECTIONS)
def test_bc_implementer_has_required_section(section):
    content = _read_template("bc-implementer")
    assert section in content, f"missing section in bc-implementer: {section!r}"


@pytest.mark.parametrize("section", BC_REVIEWER_REQUIRED_SECTIONS)
def test_bc_reviewer_has_required_section(section):
    content = _read_template("bc-reviewer")
    assert section in content, f"missing section in bc-reviewer: {section!r}"


@pytest.mark.parametrize("section", LEAD_PO_REQUIRED_SECTIONS)
def test_lead_po_has_required_section(section):
    content = _read_template("lead-po")
    assert section in content, f"missing section in lead-po: {section!r}"


@pytest.mark.parametrize("section", LEAD_ARCHITECT_REQUIRED_SECTIONS)
def test_lead_architect_has_required_section(section):
    content = _read_template("lead-architect")
    assert section in content, f"missing section in lead-architect: {section!r}"


def test_lead_architect_requires_empirical_pre_state_verification():
    """Pin Finding 17 (slice 16): the lead-architect template must require
    EMPIRICAL pre-state verification, not just assertion from reading code.

    The S16 dispatch claimed today's shop-msg send payloads were
    "internally consistent" by reading the CLI code — and was wrong (CLI
    computed hash from body, but gherkin field was wrapped → different
    canonical inputs). The Implementer caught the mismatch and adapted.
    Finding 17 named the failure mode; the template iteration after S16
    introduced an empirical-verification requirement to Q1 of the
    sufficiency check. This test pins that requirement so a future
    template refactor that removed it would fail here.
    """
    content = _read_template("lead-architect").lower()
    assert "empirical" in content, (
        "lead-architect must require empirical pre-state verification "
        "(Finding 17 / slice 16); reading code is hypothesis, running it "
        "is fact."
    )


def test_cli_list_outputs_expected_names():
    result = subprocess.run(
        ["shop-templates", "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stderr == ""
    listed = result.stdout.strip().splitlines()
    assert listed == EXPECTED_TEMPLATES


def test_cli_show_writes_template_content_to_stdout():
    expected = _read_template("bc-implementer")
    result = subprocess.run(
        ["shop-templates", "show", "bc-implementer"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == expected
    assert result.stderr == ""


def test_cli_show_unknown_template_exits_nonzero_with_stderr():
    result = subprocess.run(
        ["shop-templates", "show", "no-such-template"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert "no template named" in result.stderr
    assert "bc-implementer" in result.stderr  # available list cited
