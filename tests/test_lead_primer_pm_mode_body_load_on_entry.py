"""Acceptance pin for lead-r5sk (request_maintenance role-delta).

The lead-primer's "### Standing rule: PM-mode entry classification" block must
END with a new bolded paragraph, "**Load the mode body on entry.**", that names
`shop-templates show lead-pm` as the on-entry mode-body load command. The load
chain (@-imports in CLAUDE.md) carries the PM-mode entry TRIGGER (this block)
but not the lead-pm mode's operating BODY; PDR-033 (grounded in lead-ac1f.1)
left the router entering PM mode without the mode body in context. The delta
closes that gap with a lazy load-on-entry instruction.

The primer is served through the package's public template-access surface
``read_claude_md_primer("lead")`` — the same package-data source from which the
lead-primer pour is rendered, so a re-poured lead shop inherits the paragraph.
"""

from shop_templates.cli import read_claude_md_primer

_PM_HEADING = "### Standing rule: PM-mode entry classification"
_NEXT_HEADING = "### Standing rule: effectively-empty product-discovery bootstrap"


def _body() -> str:
    body = read_claude_md_primer("lead")
    assert body, "canonical lead primer body is empty"
    return body


def _pm_block() -> str:
    body = _body()
    start = body.index(_PM_HEADING)
    end = body.index(_NEXT_HEADING, start)
    return body[start:end]


def test_pm_mode_block_ends_with_load_the_mode_body_on_entry_paragraph() -> None:
    block = _pm_block().rstrip()
    # The block's LAST paragraph must be the load-on-entry instruction.
    last_para = block.rsplit("\n\n", 1)[-1].strip()
    assert last_para.startswith("**Load the mode body on entry.**"), (
        "the PM-mode entry classification block must END with the "
        "'**Load the mode body on entry.**' paragraph; last paragraph was:\n"
        f"{last_para!r}"
    )


def test_load_on_entry_paragraph_names_show_lead_pm_command() -> None:
    block = _pm_block()
    assert "**Load the mode body on entry.**" in block
    assert "shop-templates show lead-pm" in block, (
        "the load-on-entry paragraph must name `shop-templates show lead-pm` "
        "as the on-entry mode-body load command"
    )
    # The paragraph must state the load is the FIRST act of PM-mode entry and
    # that the router MUST perform it on entry.
    assert "MUST load the mode body" in block
    assert "first act of every PM-mode entry" in block


def test_no_duplicate_load_on_entry_paragraph() -> None:
    body = _body()
    assert body.count("**Load the mode body on entry.**") == 1, (
        "exactly one load-on-entry paragraph must be present (no double-insert)"
    )
