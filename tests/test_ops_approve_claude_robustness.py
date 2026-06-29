"""Robustness behavioral tests for the rendered ``bin/agent-vault-approve-claude``
(lead-m1dc pins 219 / 220 / 221).

These run the RENDERED script out-of-process under PATH-stubbed ``docker`` /
``curl`` (``_approve_claude_harness``), proving the script's control flow rather
than asserting over its text. 219 (precondition gate + zero partial state) is the
load-bearing one: on any missing precondition the script must make NO mutating
call — no ``proposal approve``, no ``POST /v1/auth/login``, no
``POST /v1/credentials/oauth/tokens``.
"""
from _approve_claude_harness import run_approve_claude


# =====================================================================
# 219 — precondition gate (verify-all-before-mutate) + ZERO partial state
# =====================================================================


def test_happy_path_completes_and_performs_the_full_flow():
    """Positive control: with every input present and endpoints reachable the
    gate lets the run through and it performs the full flow."""
    r = run_approve_claude()
    assert r.returncode == 0, f"happy path must complete; stderr={r.stderr!r}"
    assert r.approved_a_proposal, "happy path must approve the pending proposal"
    assert r.posted_to("/v1/auth/login"), "happy path must perform the owner login"
    assert r.posted_to("/v1/credentials/oauth/tokens"), "happy path must writeback tokens"


def test_missing_owner_password_makes_zero_partial_changes():
    """THE bug: the v0.47.0 login path needs an owner password, but the check
    used to run AFTER the proposal/slot was ensured -> partial state. The gate
    must reject a missing owner password BEFORE any mutating call."""
    r = run_approve_claude(owner_password=None)
    assert r.returncode != 0, "a missing owner password must fail the run"
    assert "AGENT_VAULT_OWNER_PASSWORD" in r.stderr, (
        f"diagnostic must name the missing owner password; stderr={r.stderr!r}"
    )
    assert not r.made_any_mutating_call, (
        "ZERO partial state: no proposal approve / login POST / oauth-tokens POST "
        f"may happen on a missing precondition.\nmutations={r.mutation_log!r}\n"
        f"curl={r.curl_log!r}"
    )


def test_missing_claude_tokens_makes_zero_partial_changes():
    r = run_approve_claude(creds_file_missing=True)
    assert r.returncode != 0
    assert "agent-vault-approve-claude" in r.stderr.lower()
    assert not r.made_any_mutating_call, (
        f"missing Claude tokens must make zero mutating calls; mutations={r.mutation_log!r} curl={r.curl_log!r}"
    )


def test_missing_refresh_token_makes_zero_partial_changes():
    """A single token cannot refresh; an access token without a refresh token is
    still a missing precondition and must make zero partial changes."""
    r = run_approve_claude(access="acc-only", refresh="")
    assert r.returncode != 0
    assert "refresh" in r.stderr.lower(), f"diagnostic must name the refresh token; {r.stderr!r}"
    assert not r.made_any_mutating_call


def test_unresolvable_ops_coordinates_makes_zero_partial_changes():
    r = run_approve_claude(ops_coordinates_ok=False)
    assert r.returncode != 0
    assert "ops-coordinates" in r.stderr.lower() or "OPS_" in r.stderr, (
        f"diagnostic must name the unresolvable ops-coordinates; {r.stderr!r}"
    )
    assert not r.made_any_mutating_call


def test_broker_down_makes_zero_partial_changes():
    r = run_approve_claude(broker_up=False)
    assert r.returncode != 0
    assert not r.made_any_mutating_call, (
        f"an unreachable broker must make zero mutating calls; mutations={r.mutation_log!r}"
    )


def test_unreachable_endpoint_makes_zero_partial_changes():
    """Reachability is verified before any mutating step; an unreachable endpoint
    aborts with zero partial changes (the HEAD reachability probe is not a mutation)."""
    r = run_approve_claude(endpoints_reachable=False)
    assert r.returncode != 0
    assert "unreachable" in r.stderr.lower() or "reach" in r.stderr.lower(), (
        f"diagnostic must name the unreachable endpoint; {r.stderr!r}"
    )
    assert not r.made_any_mutating_call, (
        f"an unreachable endpoint must make zero mutating calls; mutations={r.mutation_log!r} curl={r.curl_log!r}"
    )
