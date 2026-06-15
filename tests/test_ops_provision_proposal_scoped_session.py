"""Render-fidelity tests for the vault-scoped session wiring on the
Claude-OAuth proposal gate (lead-9qdn).

PRE-STATE (broken as-rendered, v0.10.0): the rendered bin/agent-vault-provision
runs ``vault proposal create -f - --json --vault $VAULT`` against the OWNER
session (a plain ``docker exec`` with no vault scope). agent-vault 0.32.0
refuses with ``Error: Session requires vault scope`` — proposal create/approve
run in AGENT mode and need a vault-scoped session, even though the prior
owner-session ``vault create`` / ``credential set`` / ``service add`` all
succeeded (WALL-2, lead-held cold-walkthrough, slug acme).

PROVEN FIX (verified live against the acme throwaway broker): mint a
vault-scoped session via ``agent-vault vault token --vault $VAULT`` (yields an
``av_sess_...`` token), then run the proposal subcommands with
``-e AGENT_VAULT_TOKEN=<scoped session> -e AGENT_VAULT_ADDR=http://localhost:14321
-e AGENT_VAULT_VAULT=$VAULT`` — NOT the bare owner session.

Acceptance is grep-predicate over the RENDERED provision body (no live broker in
the BC env). The CLI verb/flag surface (``vault token --vault``, the three env
vars) was verified against the installed agent-vault 0.32.0; the end-to-end
create -> approve -> oauth-credential-without-scope-error is the lead's
throwaway-broker validation.
"""

from shop_templates.cli import render_ops_template


def _provision(slug: str = "shopsystem") -> str:
    return render_ops_template("agent-vault-provision", slug)


# -----------------------------------------------------------------------
# A) Mint the vault-scoped session BEFORE the proposal step
# -----------------------------------------------------------------------


def test_provision_mints_vault_scoped_session_via_vault_token():
    """The gate mints a vault-scoped session via
    ``agent-vault vault token --vault $VAULT`` (the proven av_sess_ minter)."""
    body = _provision()
    assert "agent-vault vault token --vault" in body, (
        "the proposal gate must mint a vault-scoped session via "
        "`agent-vault vault token --vault \"$VAULT\"` (the verified av_sess_ "
        "minter) before the proposal step"
    )


def test_provision_scoped_session_minted_before_proposal_create():
    """The vault-scoped session mint must come BEFORE the proposal-create
    invocation — proposal create runs under the scoped session, so the mint
    has to precede it in the rendered body."""
    body = _provision()
    token_idx = body.find("agent-vault vault token --vault")
    create_idx = body.find("agent-vault vault proposal create")
    assert token_idx != -1, "scoped-session mint (`vault token --vault`) missing"
    assert create_idx != -1, "proposal create invocation missing"
    assert token_idx < create_idx, (
        "the `vault token --vault` scoped-session mint must precede the "
        "`vault proposal create` invocation"
    )


# -----------------------------------------------------------------------
# B) proposal create/approve run under the scoped session (three -e vars)
# -----------------------------------------------------------------------


def test_provision_defines_scoped_dexec_with_three_env_vars():
    """A scoped exec array passes the three verified env vars: the scoped
    session as AGENT_VAULT_TOKEN, the broker's own API addr at
    http://localhost:14321, and AGENT_VAULT_VAULT — NOT the bare owner session."""
    body = _provision()
    assert "-e AGENT_VAULT_TOKEN=" in body, (
        "scoped exec must pass the minted scoped session as -e AGENT_VAULT_TOKEN="
    )
    assert "-e AGENT_VAULT_ADDR=http://localhost:14321" in body, (
        "scoped exec must pass -e AGENT_VAULT_ADDR=http://localhost:14321 "
        "(the broker's own API port, since proposal runs inside the container)"
    )
    assert "-e AGENT_VAULT_VAULT=" in body, (
        "scoped exec must pass -e AGENT_VAULT_VAULT=$VAULT"
    )


def test_provision_proposal_create_runs_under_scoped_exec():
    """The `vault proposal create` invocation must run under the scoped exec
    array (DEXEC_SCOPED), not the bare owner DEXEC."""
    body = _provision()
    # The proposal-create line must reference the scoped exec array expansion.
    create_lines = [
        ln for ln in body.splitlines()
        if "agent-vault vault proposal create" in ln
    ]
    assert create_lines, "proposal create invocation missing"
    assert all("DEXEC_SCOPED" in ln for ln in create_lines), (
        f"`vault proposal create` must run under ${{DEXEC_SCOPED[@]}} (the "
        f"vault-scoped exec), not the bare owner DEXEC: {create_lines!r}"
    )


def test_provision_proposal_approve_carries_scoped_session_env():
    """`proposal approve` (the operator-run command in the human-gate prompt)
    must carry the scoped-session env so it runs under vault scope too — the
    three env vars (or the scoped exec) appear on/near the approve path."""
    body = _provision()
    assert "vault proposal approve" in body, "approve command must still render"
    # The scoped session env vars must be present so approve runs under scope.
    # AGENT_VAULT_TOKEN with the scoped session is the load-bearing marker.
    assert "AGENT_VAULT_TOKEN=" in body and "http://localhost:14321" in body, (
        "the approve path must carry the scoped-session env "
        "(AGENT_VAULT_TOKEN=<scoped> + http://localhost:14321) so the operator "
        "approve runs under vault scope, not the bare owner session"
    )


def test_provision_proposal_create_not_bare_owner_dexec():
    """Belt-and-suspenders: the proposal-create line must NOT use the bare
    owner DEXEC expansion (the pre-state that triggered the scope error)."""
    body = _provision()
    for ln in body.splitlines():
        if "agent-vault vault proposal create" in ln:
            assert '"${DEXEC[@]}"' not in ln, (
                f"proposal create must not run under the bare owner "
                f'"${{DEXEC[@]}}": {ln!r}'
            )


# -----------------------------------------------------------------------
# C) The existing proposal-number capture is PRESERVED unchanged
# -----------------------------------------------------------------------


def test_provision_preserves_proposal_number_capture():
    """The tolerant (number|id):[0-9]+ parse that captures the proposal number
    from `proposal create --json` output must be PRESERVED unchanged (the
    scoped `proposal create --json` output still carries {"id":N,...})."""
    body = _provision()
    assert '"(number|id)"[[:space:]]*:[[:space:]]*[0-9]+' in body, (
        "the tolerant proposal-number parse must be preserved unchanged"
    )
    assert "PROPOSAL_NUM=" in body, "proposal-number capture var must be preserved"


# -----------------------------------------------------------------------
# D) All other provision steps stay on the OWNER DEXEC, unchanged
# -----------------------------------------------------------------------


def test_provision_owner_steps_stay_on_owner_dexec():
    """Owner register/login, vault create, credential set, the five service
    adds, fleet-token mint, and ca fetch stay on the OWNER DEXEC (they worked);
    only the proposal subcommands move to the scoped exec."""
    body = _provision()
    owner_markers = (
        "agent-vault auth register",
        "agent-vault vault create",
        "agent-vault vault credential set",
        "agent-vault agent create",
        "agent-vault ca fetch",
    )
    for marker in owner_markers:
        assert marker in body, f"owner step {marker!r} must still render"
        # Only the actual invocation lines (which carry a ${DEXEC...} exec
        # expansion) are checked — comment/prose lines that merely name the
        # verb are skipped.
        invocation_lines = [
            ln for ln in body.splitlines()
            if marker in ln and "${DEXEC" in ln
        ]
        assert invocation_lines, (
            f"owner step {marker!r} must run under an exec expansion"
        )
        for ln in invocation_lines:
            assert '"${DEXEC[@]}"' in ln, (
                f"owner step must stay on the owner DEXEC (not scoped): {ln!r}"
            )
    # The five services stay rendered.
    for svc in ("github-git", "github-api", "claude-api", "claude-platform", "claude-mcp-proxy"):
        assert f"--name {svc}" in body, f"service {svc} must still render"


# -----------------------------------------------------------------------
# E) Slug-clean — no product literals leak through the scoped wiring
# -----------------------------------------------------------------------


def test_provision_scoped_session_is_slug_clean():
    """A render for slug X must carry no FOREIGN product literals — not the
    source-fixed `shopsystem`/`dstengle`, nor the walkthrough slug `acme` the
    scoped-session fix was proven against. (The target slug X itself rendering
    is correct slug projection, so it is not asserted absent.)"""
    body = render_ops_template("agent-vault-provision", "dummyco")
    for literal in ("shopsystem", "dstengle", "acme"):
        assert literal not in body, f"dummyco render leaked {literal!r}:\n{body}"
