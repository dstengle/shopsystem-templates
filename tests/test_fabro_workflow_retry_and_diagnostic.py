"""The POURED templates/fabro/workflow.fabro carries the re-homed retry +
diagnostic-block fixes (work_id lead-s6cy).

These pin the two behaviors the running fabro engage currently lacks — the
mirror fixes (bc-launcher assets/fabro-def/workflow.fabro) never reached the
pour source, so they are re-homed here onto the SAME poured template that
fabro_def_poured_projection.feature (@bc:shopsystem-templates) already pins.
Additive to that surface; no ADR-051 invariant superseded.

(1) RETRY (closes lead-6ev8): the six LLM/ACP agent nodes carry REAL
    workflow-level bounded retry — `max_retries=N` + `retry_policy=exponential`
    (classify=4; suff/plan/impl/review/impl_f=3) — not the inert `retry=` attr
    (the NEGATIVE CONTROL that fails-fast to the failsafe on the first 429).

(2) DIAGNOSTIC (closes lead-01jw.3): the failsafe `emit_blk` sources its
    diagnostic marker strings from the single SHARED Python anchor module
    (ADR-062), NOT hardcoded into the `.fabro` graph, and emits the diagnostic
    triple (failing-node + reason-class + detail-marker + run tail).
"""
import re
from importlib.resources import files

import pytest

_WF = files("shop_templates.templates.fabro").joinpath("workflow.fabro").read_text()

# The six LLM/ACP judgment-agent nodes and their required bounded-retry counts.
_AGENT_RETRY_COUNTS = {
    "classify": 4,
    "suff": 3,
    "plan": 3,
    "impl": 3,
    "review": 3,
    "impl_f": 3,
}

# The ADR-062 reason-class literals are DIAGNOSTIC-only tokens — they must not
# appear anywhere in the graph (they live only in the shared anchor module).
_REASON_CLASS_LITERALS = ("deliverable-gate", "infra-path", "llm-path")
# The detail-marker literals ARE mentioned in the pre-existing credentials
# comment (the HTTPS_PROXY -> agent-vault / anthropic-oauth-shim note), so the
# hardcode ban is enforced against the emit_blk node body, not the whole file.
_DETAIL_MARKER_LITERALS = ("oauth-shim", "agent-vault", "proxy", "rate-limit-429")


def _node_decl(name: str) -> str:
    """Return the full `<name> [ ... ]` attribute block for a graph node."""
    # A node decl starts at `<name>  [` at column 0-ish and runs to the first
    # closing `]` that ends the attribute list.
    m = re.search(rf"(?m)^\s*{re.escape(name)}\s+\[", _WF)
    assert m, f"node {name!r} not found in workflow.fabro"
    start = m.start()
    depth = 0
    i = m.end() - 1
    for j in range(i, len(_WF)):
        if _WF[j] == "[":
            depth += 1
        elif _WF[j] == "]":
            depth -= 1
            if depth == 0:
                return _WF[start : j + 1]
    raise AssertionError(f"unterminated node decl for {name!r}")


# --------------------------------------------------------------------------
# (1) RETRY — real bounded retry on all six agent nodes.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("node,count", sorted(_AGENT_RETRY_COUNTS.items()))
def test_agent_node_carries_real_bounded_exponential_retry(node, count):
    decl = _node_decl(node)
    assert re.search(rf"\bmax_retries\s*=\s*{count}\b", decl), (
        f"agent node {node!r} must carry real max_retries={count} "
        f"(bounded retry, total-wait-bounded); got:\n{decl}"
    )
    assert re.search(r"\bretry_policy\s*=\s*exponential\b", decl), (
        f"agent node {node!r} must carry retry_policy=exponential (spaced, "
        f"per-attempt-capped exponential backoff); got:\n{decl}"
    )


@pytest.mark.parametrize("node", sorted(_AGENT_RETRY_COUNTS))
def test_agent_node_does_not_carry_the_inert_retry_negative_control(node):
    """The inert `retry=<N>` attr is the NEGATIVE CONTROL (0 real max_retries,
    0 retry_policy) that fails-fast on the first 429; it must NOT be present on
    the agent nodes — real max_retries + retry_policy replaced it."""
    decl = _node_decl(node)
    assert not re.search(r"[,\[\s]retry\s*=", decl), (
        f"agent node {node!r} still carries the inert `retry=` negative control; "
        f"it must be replaced by max_retries + retry_policy=exponential:\n{decl}"
    )


# --------------------------------------------------------------------------
# (2) DIAGNOSTIC — emit_blk sources the vocab from the shared anchor (ADR-062).
# --------------------------------------------------------------------------
def test_emit_blk_no_longer_carries_the_content_free_failsafe_summary():
    decl = _node_decl("emit_blk")
    assert "a deliverable-side gate or step failed" not in decl, (
        "emit_blk still carries the content-free failsafe summary; it must be "
        "replaced by the diagnostic triple sourced from the shared anchor"
    )


def test_emit_blk_sources_diagnostic_from_the_shared_python_anchor_module():
    decl = _node_decl("emit_blk")
    assert "shop_templates.fabro_diagnostics" in decl, (
        "emit_blk must source its diagnostic marker strings from the single "
        "shared Python anchor module `shop_templates.fabro_diagnostics` "
        "(ADR-062), not hardcode them into the .fabro graph"
    )


def test_reason_class_literals_not_hardcoded_anywhere_in_the_graph():
    """A one-runtime hardcode REDs the parity pin: the operator-facing
    reason-class tokens are diagnostic-only and must NOT appear anywhere in the
    .fabro graph — they live only in the shared anchor module (ADR-062)."""
    for lit in _REASON_CLASS_LITERALS:
        assert lit not in _WF, (
            f"reason-class literal {lit!r} is hardcoded into workflow.fabro; per "
            f"ADR-062 it must be sourced from the shared anchor module, never the "
            f"graph"
        )


def test_detail_marker_vocab_not_hardcoded_in_the_emit_blk_node():
    """The emit_blk failsafe node must NOT hardcode the infra detail-marker
    vocab — it sources those strings from the shared anchor (ADR-062). (The
    pre-existing credentials COMMENT may mention them; the emit_blk node body
    may not.)"""
    decl = _node_decl("emit_blk")
    for lit in _DETAIL_MARKER_LITERALS:
        assert lit not in decl, (
            f"detail-marker literal {lit!r} is hardcoded into the emit_blk node; "
            f"per ADR-062 it must be sourced from the shared anchor module"
        )


def test_emit_blk_still_emits_blocked_never_a_silent_complete():
    """The failsafe still routes to a work_done(blocked) emit — the diagnostic
    replaces the summary CONTENT, it does not weaken the blocked-never-complete
    ADR-051 invariant."""
    decl = _node_decl("emit_blk")
    assert "--status blocked" in decl
    assert "shop-msg respond work_done" in decl
