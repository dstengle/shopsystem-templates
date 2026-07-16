"""Regression: the bc-primer session-start work-tracker health-gate
decision table must NOT leave a fresh 0-issue-with-committed-prefix BC in an
uncovered cell (lead-bo85 / GAP C, origin finding tied to lead-pqlx).

Bug: the "Heal an unprovisioned-but-recoverable tracker" section gated the
adopt-heal path on "the committed registry names a definite issue_prefix AND
carries at least one issue" (the >=1-issue AND-condition), while the
"Unhealable" block was gated only on "the committed registry names no
issue_prefix to adopt" (no issue-count condition). A freshly-bootstrapped BC
that commits a prefix but ZERO issues therefore matched NEITHER branch —
needs >=1 issue for adopt-heal, has a prefix so is not unhealable — an
uncovered decision-table cell in the shipped canonical bc primer.

Fix (a): drop the ">=1 issue" AND-condition from the adopt-heal gate, so a
committed prefix ALONE qualifies for adopt regardless of issue count (a
0-issue registry is a valid empty no-op import). These assertions are pinned
to the rendered bc primer body served through the package's public
template-access surface (read_claude_md_primer("bc")).
"""
import re

from shop_templates.cli import read_claude_md_primer


def _adopt_heal_section(primer: str) -> str:
    """Isolate the '### Heal an unprovisioned-but-recoverable tracker'
    section body — from that heading up to the next '### ' heading."""
    m = re.search(
        r"^###\s+Heal an unprovisioned-but-recoverable tracker\s*$"
        r"(?P<body>.*?)"
        r"^###\s",
        primer,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert m is not None, (
        "rendered bc primer does not carry a 'Heal an unprovisioned-but-"
        "recoverable tracker' section to gate the adopt-heal path"
    )
    return m.group("body")


def test_adopt_heal_gate_does_not_require_at_least_one_issue():
    """The adopt-heal gate must NOT require the committed registry to carry
    '>=1 issue'. A committed prefix alone qualifies for the heal; the buggy
    '...and carries at least one issue' AND-condition must be gone."""
    section = _adopt_heal_section(read_claude_md_primer("bc"))
    # Normalize soft-wraps: collapse whitespace runs so a line-wrapped
    # "carries at\nleast one issue" is still caught as a contiguous phrase.
    lowered = re.sub(r"\s+", " ", section).lower()
    assert "at least one issue" not in lowered, (
        "adopt-heal gate still requires the committed registry to carry at "
        "least one issue — a fresh 0-issue-with-committed-prefix BC is left "
        "in an uncovered decision-table cell (matches neither adopt-heal nor "
        "unhealable)"
    )
    # The gate must still name a committed issue_prefix as the trigger.
    assert "issue_prefix" in lowered and "committed" in lowered, (
        "adopt-heal gate no longer names the committed issue_prefix as the "
        "heal trigger"
    )


def test_fresh_zero_issue_with_committed_prefix_is_covered():
    """The rendered health-step contract must explicitly cover the fresh
    0-issue-with-committed-prefix case: a committed prefix alone is
    adopt-healable regardless of issue count (including zero)."""
    section = _adopt_heal_section(read_claude_md_primer("bc")).lower()
    assert ("zero issue" in section or "0 issue" in section
            or "0-issue" in section or "zero committed issue" in section), (
        "adopt-heal section does not name the fresh zero-issue-with-"
        "committed-prefix case, leaving that decision-table cell uncovered"
    )
    assert ("regardless" in section or "whether it carries" in section
            or "alone qualifies" in section or "any issue count" in section), (
        "adopt-heal section does not state a committed prefix qualifies for "
        "the heal regardless of how many issues the registry carries"
    )
