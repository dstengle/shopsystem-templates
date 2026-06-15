"""Pin lead-xgs0: @scenario_hash moves from dispatch-time to AUTHORING-time.

Per ADR-036 D3 (block-only canonicalization), the PO computes `scenarios
hash` of the scenario BLOCK and writes `@scenario_hash:<hash>` alone on its
own line directly above the `Scenario:`/`Scenario Outline:` line — as part
of authoring. The old deferral prose (PO authors WITHOUT the tag; "hash
computation is not yours") is inverted/removed for `@scenario_hash`.

`@bc:<name>` is unchanged: it stays DISPATCH-time and Architect-owned.

The companion lead-architect change is VERIFY-not-introduce: the Architect
recomputes-to-confirm the authored `@scenario_hash` at dispatch rather than
being the sole introducer; it still adds `@bc` and still re-runs the
pre-state `@scenario_hash` enumeration.
"""
from shop_templates.cli import _read_template


def _po() -> str:
    body = _read_template("lead-po")
    assert body is not None, "lead-po template must exist"
    return body


def _architect() -> str:
    body = _read_template("lead-architect")
    assert body is not None, "lead-architect template must exist"
    return body


# --- CHANGE 1a: authoring-time instruction in lead-po ---

def test_lead_po_instructs_authoring_time_scenario_hash_computation():
    """The PO computes+writes @scenario_hash at authoring time."""
    body = _po()
    lower = body.lower()
    # block-only canonicalization per ADR-036 D3
    assert "scenarios hash" in lower
    assert "block-only" in lower, (
        "lead-po must describe block-only canonicalization (the hash is "
        "computed over the scenario block)"
    )
    # The authoring activity directs writing the @scenario_hash tag, and
    # frames it as part of authoring ("as part of authoring" / "before
    # authoring is done").
    assert "write `@scenario_hash" in lower or "writes `@scenario_hash" in lower, (
        "lead-po must instruct the PO to write the @scenario_hash tag at "
        "authoring time"
    )
    assert "as part of authoring" in lower or "before authoring is" in lower, (
        "lead-po must frame @scenario_hash computation as part of authoring"
    )


def test_lead_po_instructs_scenario_hash_alone_on_line_above_scenario():
    """@scenario_hash is written alone on its own line directly above the
    Scenario:/Scenario Outline: keyword line."""
    body = _po().lower()
    assert "alone on its own line" in body or "alone on its line" in body, (
        "lead-po must instruct the @scenario_hash tag is written alone on "
        "its own line"
    )
    assert "scenario outline" in body, (
        "lead-po must reference Scenario:/Scenario Outline: as the line the "
        "tag sits directly above"
    )


# --- CHANGE 1c: authoring sufficiency check carries reproducing-hash criterion ---

def test_lead_po_authoring_sufficiency_check_includes_reproducing_hash():
    """The authoring sufficiency check requires the on-disk @scenario_hash
    tag to reproduce under `scenarios hash` of the block."""
    body = _po()
    lower = body.lower()
    # locate the authoring sufficiency check section
    assert "Sufficiency check — authoring a scenario" in body
    assert "reproduc" in lower, (
        "authoring sufficiency check must include the reproducing-hash-tag "
        "criterion (scenarios hash of the block reproduces the on-disk tag)"
    )


# --- CHANGE 1b: old prohibition removed/inverted ---

def test_lead_po_no_longer_prohibits_authoring_scenario_hash():
    """The old 'author without the @scenario_hash tag' prohibition and the
    'hash computation is not yours' constraint are removed for
    @scenario_hash."""
    body = _po()
    assert "without the\n  `@scenario_hash:`" not in body
    assert "without the `@scenario_hash:`" not in body
    assert "Hash computation is `scenarios hash`'s job, not yours." not in body, (
        "the 'hash computation is not yours' constraint must be removed/inverted "
        "for @scenario_hash"
    )


# --- @bc preserved as Architect/dispatch-time in lead-po ---

def test_lead_po_preserves_bc_tag_as_architect_dispatch_time():
    """@bc:<name> stays DISPATCH-time / Architect-owned in lead-po."""
    body = _po()
    lower = body.lower()
    assert "@bc" in body
    assert "architect" in lower
    assert "dispatch" in lower or "assignment" in lower, (
        "lead-po must keep @bc as added at dispatch/assignment time by the "
        "Architect"
    )


# --- CHANGE 2: lead-architect verify-not-introduce ---

def test_lead_architect_verifies_authored_scenario_hash_not_introduces():
    """The Architect recomputes-to-confirm the authored @scenario_hash at
    dispatch rather than being the sole introducer."""
    body = _architect()
    lower = body.lower()
    # The old "You do not add either tag by hand" sole-introducer prose is gone.
    assert "You do not add either" not in body, (
        "lead-architect must no longer frame the Architect as the sole "
        "introducer of @scenario_hash"
    )
    # verify-not-introduce framing
    assert "recompute" in lower or "reproduc" in lower, (
        "lead-architect must direct recompute-to-confirm of the authored "
        "@scenario_hash"
    )
    assert "verif" in lower


def test_lead_architect_still_adds_bc_tag_at_dispatch():
    """@bc:<name> stays Architect/dispatch-time in lead-architect."""
    body = _architect()
    assert "@bc" in body
    assert "--bc-tag" in body or "adds\n   `@bc" in body or "adds `@bc" in body, (
        "lead-architect must still add @bc:<name> at dispatch"
    )


def test_lead_architect_still_runs_prestate_enumeration():
    """The pre-state @scenario_hash enumeration step is left intact."""
    body = _architect()
    assert 'grep -r "@scenario_hash" features/' in body, (
        "lead-architect must still re-run the pre-state @scenario_hash "
        "enumeration"
    )
    assert "enumerat" in body.lower()
