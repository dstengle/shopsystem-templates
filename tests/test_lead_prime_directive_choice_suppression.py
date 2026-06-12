"""Pins the canonical lead.md primer (read_claude_md_primer("lead")) for the
WS-4 part-1 revision (lead-f3gm): the PRIME DIRECTIVE block must OPEN the
file before the SHOP_NAME heading and appear exactly once, and the
choice-suppression standing rule must carry the positive-reframe body with
exactly three triggers and the positive-standing-order closer.

These assert observable rendered template content (the package-data boundary
via read_claude_md_primer), not prose. {{SHOP_NAME}} parameterization must be
preserved.
"""
from shop_templates.cli import read_claude_md_primer

PRIME_DIRECTIVE_HEADING = "# PRIME DIRECTIVE — act, do not ask"
SHOP_NAME_HEADING = "# {{SHOP_NAME}} — lead shop instructions"
CHOICE_SUPPRESSION_HEADING = "### Standing rule: choice suppression"


def _lead_primer() -> str:
    return read_claude_md_primer("lead")


def test_prime_directive_block_present_exactly_once():
    primer = _lead_primer()
    assert primer.count(PRIME_DIRECTIVE_HEADING) == 1, (
        "canonical lead.md must carry exactly one PRIME DIRECTIVE block "
        f"(found {primer.count(PRIME_DIRECTIVE_HEADING)})"
    )


def test_prime_directive_opens_file_before_shop_name_heading():
    primer = _lead_primer()
    pd_index = primer.index(PRIME_DIRECTIVE_HEADING)
    shop_index = primer.index(SHOP_NAME_HEADING)
    assert pd_index < shop_index, (
        "PRIME DIRECTIVE block must be positioned BEFORE the "
        "'# {{SHOP_NAME}} — lead shop instructions' heading"
    )
    # It must OPEN the file: nothing but optional whitespace precedes it.
    assert primer[:pd_index].strip() == "", (
        "PRIME DIRECTIVE block must be the first content in canonical lead.md"
    )


def test_choice_suppression_body_is_positive_reframe_with_three_triggers():
    primer = _lead_primer()
    assert CHOICE_SUPPRESSION_HEADING in primer, (
        "canonical lead.md must keep the choice-suppression heading"
    )
    # Body leads with the DECIDE-AND-ACT directive.
    assert "DECIDE EVERY OPERATIONAL QUESTION YOURSELF AND ACT ON IT" in primer, (
        "choice-suppression body must lead with the positive DECIDE-AND-ACT "
        "directive"
    )
    # Exactly three triggers, including the unauthorized-outward-facing one.
    assert "**Scope or vocabulary**" in primer
    assert "**PO / Architect routing for ambiguous clarifies**" in primer
    assert "**Unauthorized outward-facing action**" in primer, (
        "choice-suppression body must carry the third trigger "
        "'Unauthorized outward-facing action'"
    )
    # The intermediate 'Carve-out' framing must be gone.
    assert "Carve-out" not in primer, (
        "intermediate 'Carve-out' choice-suppression framing must be replaced"
    )
    # Positive-standing-order closer.
    assert "This is a positive standing order, not a prohibition." in primer, (
        "choice-suppression body must close with the positive-standing-order "
        "statement"
    )


def test_shop_name_parameterization_preserved():
    primer = _lead_primer()
    assert "{{SHOP_NAME}}" in primer, (
        "{{SHOP_NAME}} parameterization must be preserved in canonical lead.md"
    )
