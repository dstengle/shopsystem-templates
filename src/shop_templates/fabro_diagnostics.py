"""Single SHARED fabro-diagnostic anchor module (ADR-062).

The reason-class + detail-marker vocabulary is an OPERATOR-FACING cross-runtime
parity surface. Per ADR-062 it MUST live in ONE shared Python anchor module both
runtimes read, and MUST NOT be hardcoded into the `.fabro` graph. This module is
that anchor: the poured `workflow.fabro` failsafe node (`emit_blk`) sources its
diagnostic marker strings from here rather than baking them into the graph, so a
one-runtime hardcode can never drift the parity surface.

It mirrors the tmux launch-diagnostic cause-marker idiom
(`bc_launcher.diagnostics` — `bc_container_launch_failure_diagnostic`): a literal,
grep-able token in a `cause:`/`reason-class=` field so an operator (or tool) can
grep for the failure class and be pointed at the right repair.

The diagnostic emitted on the failsafe path is a TRIPLE:

    failing-node identifier
      + reason-class {deliverable-gate, infra-path, llm-path, unknown}
      + infra detail-marker {oauth-shim, agent-vault, proxy, rate-limit-429}
      + the captured run tail

Even the last-resort/unclassified path emits ``reason-class=unknown`` WITH the
captured run tail — never a bare empty block, never a silent complete.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# The closed-set vocabularies — the SINGLE source of truth (ADR-062).
# ---------------------------------------------------------------------------

#: The reason-class closed set. ``unknown`` is the mandatory last-resort class so
#: the failsafe never has to emit a bare/empty diagnostic.
REASON_CLASSES: Tuple[str, ...] = (
    "deliverable-gate",
    "infra-path",
    "llm-path",
    "unknown",
)

#: The infra detail-marker vocabulary — the specific infra sub-cause an operator
#: greps for. Parallels the launcher cause-marker tokens (``agent-vault`` is the
#: shared token across both runtimes' idioms).
DETAIL_MARKERS: Tuple[str, ...] = (
    "oauth-shim",
    "agent-vault",
    "proxy",
    "rate-limit-429",
)

# ---------------------------------------------------------------------------
# Classification: run-tail (+ optional failing node) -> (reason-class, marker).
# ---------------------------------------------------------------------------

# Native gate nodes in the poured workflow.fabro whose failure is, by
# construction, a deliverable-side gate failure (RED-before-GREEN, work-done-gate
# C1/C2/C3) rather than infra or an LLM transient.
_DELIVERABLE_GATE_NODES = frozenset({"redgate", "wdg_r", "wdg_f"})


def _detail_marker_from_tail(tail: str) -> Optional[str]:
    """Return the infra detail-marker the run tail points at, or ``None``.

    Ordered most-specific-first so an oauth 401/403 is attributed to the shim
    rather than the generic proxy it rides.
    """
    low = tail.lower()
    # Rate-limit / 429 from the LLM provider.
    if "429" in low or "rate limit" in low or "rate-limit" in low or "rate_limit" in low:
        return "rate-limit-429"
    # OAuth token-broker / shim auth failures.
    if "oauth" in low or "401" in low or "403" in low or "unauthorized" in low:
        return "oauth-shim"
    # agent-vault broker readiness / reachability.
    if "agent-vault" in low or "agent vault" in low or "vault" in low:
        return "agent-vault"
    # Egress proxy failures.
    if "proxy" in low or "https_proxy" in low or "http_proxy" in low:
        return "proxy"
    return None


def classify(run_tail: str, failing_node: str = "") -> Tuple[str, Optional[str]]:
    """Classify a failure into ``(reason_class, detail_marker)`` from the vocab.

    ``reason_class`` is always one of :data:`REASON_CLASSES`; ``detail_marker`` is
    either ``None`` or one of :data:`DETAIL_MARKERS`. An unrecognized tail maps to
    the last-resort ``("unknown", None)`` — never an out-of-vocab or empty value.
    """
    tail = run_tail or ""
    marker = _detail_marker_from_tail(tail)

    if marker == "rate-limit-429":
        # A provider 429 is an LLM-path transient (the retry target).
        return "llm-path", marker
    if marker is not None:
        # oauth-shim / agent-vault / proxy are all infra-path sub-causes.
        return "infra-path", marker

    low = tail.lower()
    # Deliverable-side gate failures: the native gate nodes, or explicit gate /
    # RED-before-GREEN / scenario-hash signals in the tail.
    if (failing_node in _DELIVERABLE_GATE_NODES) or any(
        sig in low
        for sig in (
            "work-done-gate",
            "work_done gate",
            "scenario_hash",
            "@scenario_hash",
            "red-before-green",
            "red before green",
            "gate",
        )
    ):
        return "deliverable-gate", None

    return "unknown", None


# ---------------------------------------------------------------------------
# Summary builder: the diagnostic TRIPLE, never a bare empty block.
# ---------------------------------------------------------------------------

_NO_TAIL_PLACEHOLDER = "(no run tail captured)"


def build_blocked_summary(failing_node: str, run_tail: str) -> str:
    """Build the work_done(blocked) ``--summary`` diagnostic TRIPLE.

    Carries the failing-node identifier, the reason-class, the infra
    detail-marker (or ``none``), and the captured run tail. The last-resort path
    (unclassifiable) still emits ``reason-class=unknown`` WITH the captured tail;
    the result is NEVER a bare empty block and NEVER a silent complete.
    """
    node = (failing_node or "").strip() or "unclassified"
    tail = (run_tail or "").strip()
    reason_class, detail_marker = classify(tail, failing_node=failing_node or "")
    marker_field = detail_marker if detail_marker is not None else "none"
    tail_field = tail if tail else _NO_TAIL_PLACEHOLDER
    return (
        f"blocked: failing-node={node} reason-class={reason_class} "
        f"detail-marker={marker_field} | run-tail: {tail_field}"
    )


# ---------------------------------------------------------------------------
# CLI: the entry the poured emit_blk `script=` node invokes.
# ---------------------------------------------------------------------------

_HOOK_CONTEXT_ENV = "FABRO_HOOK_CONTEXT"


def _read_hook_context() -> Tuple[str, str]:
    """Return ``(failing_node, run_tail)`` from the fabro hook context env.

    ``FABRO_HOOK_CONTEXT`` is fabro's per-node run-context channel; when present
    it is JSON and may carry the failing node id and a recent run tail under a few
    documented key spellings. Missing / malformed context yields ``("", "")`` so
    the caller falls back to args / stdin and still emits a non-silent diagnostic.
    """
    raw = os.environ.get(_HOOK_CONTEXT_ENV, "").strip()
    if not raw:
        return "", ""
    try:
        ctx = json.loads(raw)
    except (ValueError, TypeError):
        return "", raw  # keep the raw context as the tail rather than dropping it
    if not isinstance(ctx, dict):
        return "", raw
    node = str(
        ctx.get("failing_node")
        or ctx.get("failed_node")
        or ctx.get("node_id")
        or ""
    )
    tail = str(
        ctx.get("run_tail")
        or ctx.get("tail")
        or ctx.get("output")
        or ctx.get("stderr")
        or ""
    )
    return node, tail


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Print the diagnostic TRIPLE for the failsafe emit.

    Resolution order for the failing node and run tail: the fabro hook context
    (``FABRO_HOOK_CONTEXT``), then ``--failing-node`` / ``--run-tail`` args, then
    STDIN for the run tail. Whatever is available is classified via the shared
    vocab; the output is never a bare empty block.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="shop_templates.fabro_diagnostics",
        description="Emit the fabro failsafe diagnostic triple (ADR-062).",
    )
    parser.add_argument("--failing-node", default="", help="the node that failed")
    parser.add_argument("--run-tail", default="", help="captured run tail text")
    args = parser.parse_args(list(argv) if argv is not None else None)

    node, tail = _read_hook_context()
    if not node:
        node = args.failing_node
    if not tail:
        tail = args.run_tail
    if not tail and not sys.stdin.isatty():
        try:
            tail = sys.stdin.read()
        except (OSError, ValueError):
            tail = ""

    print(build_blocked_summary(node, tail))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
