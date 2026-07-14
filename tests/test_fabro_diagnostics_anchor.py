"""Unit tests for the single SHARED fabro-diagnostic anchor module (ADR-062).

work_id lead-s6cy. Re-homes the diagnostic-block fix (closes lead-01jw.3) into
the shop-templates POURED fabro def. Per ADR-062 the reason-class + detail-marker
vocabulary is an OPERATOR-FACING cross-runtime parity surface: it MUST live in a
single shared Python anchor module both runtimes read, NOT be hardcoded into the
`.fabro` graph. This module is that anchor. It mirrors the tmux launch-diagnostic
cause-marker idiom (bc_container_launch_failure_diagnostic) — a literal, grep-able
token in the diagnostic so an operator is pointed at the right repair.

The failsafe `emit_blk` node sources its diagnostic TRIPLE from this module:
failing-node identifier + reason-class{deliverable-gate, infra-path, llm-path,
unknown} + infra detail-marker{oauth-shim, agent-vault, proxy, rate-limit-429} +
the captured run tail. Even the last-resort/unclassified path emits
reason-class=unknown WITH the captured tail — never a bare empty block, never a
silent complete.
"""
import json

import pytest

from shop_templates import fabro_diagnostics as fd


# --------------------------------------------------------------------------
# The closed-set vocabularies are the single source of truth (ADR-062).
# --------------------------------------------------------------------------
def test_reason_classes_are_the_exact_closed_set():
    """The reason-class vocabulary is the exact ADR-062 closed set, in the
    documented order, with `unknown` present as the last-resort class."""
    assert tuple(fd.REASON_CLASSES) == (
        "deliverable-gate",
        "infra-path",
        "llm-path",
        "unknown",
    )
    assert "unknown" in fd.REASON_CLASSES


def test_detail_markers_are_the_exact_infra_vocab():
    """The infra detail-marker vocabulary is the exact ADR-062 set."""
    assert tuple(fd.DETAIL_MARKERS) == (
        "oauth-shim",
        "agent-vault",
        "proxy",
        "rate-limit-429",
    )


# --------------------------------------------------------------------------
# classify: run-tail content -> (reason-class, detail-marker) from the vocab.
# --------------------------------------------------------------------------
def test_classify_rate_limit_429_is_llm_path():
    rc, dm = fd.classify("anthropic returned HTTP 429 Too Many Requests")
    assert rc == "llm-path"
    assert dm == "rate-limit-429"


def test_classify_oauth_shim_auth_failure_is_infra_path():
    rc, dm = fd.classify("oauth-shim refused: 401 Unauthorized from the token broker")
    assert rc == "infra-path"
    assert dm == "oauth-shim"


def test_classify_agent_vault_failure_is_infra_path():
    rc, dm = fd.classify("agent-vault broker unreachable at readiness barrier")
    assert rc == "infra-path"
    assert dm == "agent-vault"


def test_classify_proxy_failure_is_infra_path():
    rc, dm = fd.classify("HTTPS_PROXY egress proxy connection refused")
    assert rc == "infra-path"
    assert dm == "proxy"


def test_classify_gate_failure_is_deliverable_gate_with_no_infra_marker():
    rc, dm = fd.classify(
        "work-done-gate C2 failed: no @scenario_hash tag reachable in features/"
    )
    assert rc == "deliverable-gate"
    assert dm is None


def test_classify_unrecognized_tail_is_unknown_last_resort():
    rc, dm = fd.classify("something entirely unrecognized happened here")
    assert rc == "unknown"
    assert dm is None


def test_classify_return_values_are_always_from_the_closed_vocab():
    for tail in ("429", "oauth", "vault", "proxy", "gate", "", "gibberish"):
        rc, dm = fd.classify(tail)
        assert rc in fd.REASON_CLASSES
        assert dm is None or dm in fd.DETAIL_MARKERS


# --------------------------------------------------------------------------
# build_blocked_summary: the diagnostic TRIPLE, never a bare empty block.
# --------------------------------------------------------------------------
def test_blocked_summary_carries_failing_node_reason_class_and_tail():
    s = fd.build_blocked_summary(
        failing_node="impl",
        run_tail="anthropic returned HTTP 429 Too Many Requests on attempt 4",
    )
    assert "impl" in s
    assert "llm-path" in s
    assert "rate-limit-429" in s
    # the captured run tail is carried verbatim into the summary
    assert "429" in s


def test_blocked_summary_last_resort_is_unknown_with_tail_never_empty():
    """The unclassified last-resort path emits reason-class=unknown WITH the
    captured tail — never a bare empty block, never a silent complete."""
    tail = "opaque failure with no recognizable marker whatsoever"
    s = fd.build_blocked_summary(failing_node="review", run_tail=tail)
    assert s.strip(), "summary must never be a bare empty block"
    assert "unknown" in s
    assert "review" in s
    assert tail in s, "the captured run tail must be present even on the unknown path"


def test_blocked_summary_reason_class_is_always_from_the_closed_set():
    for node, tail in (
        ("classify", "429 rate limit"),
        ("integ", "proxy refused"),
        ("wdg_r", "gate failed"),
        ("impl", "who knows"),
        ("", ""),
    ):
        s = fd.build_blocked_summary(failing_node=node, run_tail=tail)
        assert any(rc in s for rc in fd.REASON_CLASSES)


def test_blocked_summary_empty_capture_still_emits_reason_class_never_bare():
    """Even when the run-tail capture yields nothing, the summary is not a bare
    empty block: it still carries a reason-class (unknown) so the operator never
    gets a silent complete."""
    s = fd.build_blocked_summary(failing_node="", run_tail="")
    assert s.strip()
    assert "unknown" in s


# --------------------------------------------------------------------------
# main(): the CLI the poured emit_blk `script=` node invokes. Reads the fabro
# hook context (failing node + run tail) and prints the diagnostic summary.
# --------------------------------------------------------------------------
def test_main_reads_fabro_hook_context_and_prints_triple(capsys, monkeypatch):
    ctx = {
        "failing_node": "impl",
        "run_tail": "anthropic 429 Too Many Requests; retries exhausted",
    }
    monkeypatch.setenv("FABRO_HOOK_CONTEXT", json.dumps(ctx))
    rc = fd.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "impl" in out
    assert "llm-path" in out
    assert "rate-limit-429" in out
    assert "429" in out


def test_main_with_no_context_still_prints_unknown_never_silent(capsys, monkeypatch):
    monkeypatch.delenv("FABRO_HOOK_CONTEXT", raising=False)
    rc = fd.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip(), "main must never print a bare empty block"
    assert "unknown" in out


def test_main_reads_run_tail_from_stdin_fallback(capsys, monkeypatch):
    monkeypatch.delenv("FABRO_HOOK_CONTEXT", raising=False)
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("agent-vault broker unreachable"))
    rc = fd.main(["--failing-node", "integ"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "integ" in out
    assert "infra-path" in out
    assert "agent-vault" in out
