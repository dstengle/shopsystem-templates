"""Render-fidelity tests for the Claude-OAuth proposal-create/approve gate
(lead-yrex).

The prior Claude-OAuth human gate stopped the provision script for a manual
DASHBOARD PASTE because the prior probe (lead-5jbc) concluded the refreshing
OAuth credential type had "NO CLI path to provision". That finding was
INCOMPLETE — it only tested the flat ``proposal create --credential KEY=desc``
(static) path. lead-yrex verified against a throwaway ``infisical/agent-vault``
broker (same image id as the live fleet broker, agent-vault 0.32.0) that the
structured OAuth credential SLOT IS scriptable via the CLI JSON mode
``agent-vault vault proposal create -f -`` (stdin JSON). The gate now CREATES a
pre-populated OAuth-typed CLAUDE_OAUTH credential-slot proposal; the operator's
role drops to APPROVING that proposal (token paste or Connect) at the printed
approve URL.

Acceptance is grep-predicate over the RENDERED provision body (no live broker
in the BC env). The CLI verb/flag surface was verified against the installed
agent-vault 0.32.0 ``vault proposal create --help`` / ``vault proposal approve
--help``; the end-to-end proposal-create -> approve -> oauth-credential-with-
token_url is the lead's throwaway-broker validation.
"""
import json
import re

from shop_templates.cli import render_ops_template


def _provision(slug: str = "shopsystem") -> str:
    return render_ops_template("agent-vault-provision", slug)


# -----------------------------------------------------------------------
# A) OAuth-typed proposal-create via `vault proposal create -f -`
# -----------------------------------------------------------------------


def test_provision_creates_oauth_proposal_via_stdin_json():
    """The Claude-OAuth gate creates the credential SLOT via the verified
    stdin-JSON mode ``agent-vault vault proposal create -f -`` — NOT the flat
    --credential flag (which only carries the static path)."""
    body = _provision()
    assert "agent-vault vault proposal create -f -" in body, (
        "Claude-OAuth gate must create the slot via `vault proposal create -f -` "
        "(stdin JSON), the verified 0.32.0 scriptable OAuth path"
    )


def test_provision_oauth_proposal_json_carries_verified_slot_schema():
    """The proposal JSON body carries the verified oauth credential-slot
    schema: a credentials array with one CLAUDE_OAUTH slot of type oauth,
    action:set, an oauth block carrying token_url, and NO value field (the
    server rejects a value for oauth creds)."""
    body = _provision()
    # The slot fields the verified 0.32.0 server validates.
    assert '"type":"oauth"' in body or '"type": "oauth"' in body, (
        "proposal slot must declare the oauth credential type"
    )
    assert '"action":"set"' in body or '"action": "set"' in body, (
        "proposal slot must use action:set"
    )
    assert '"key":"CLAUDE_OAUTH"' in body or '"key": "CLAUDE_OAUTH"' in body, (
        "proposal slot must name the CLAUDE_OAUTH credential key"
    )
    # token_url is REQUIRED for oauth credentials (server: oauth.token_url is required).
    assert '"token_url"' in body, (
        "oauth block must carry token_url (the refresh machinery the server requires)"
    )


def test_provision_oauth_proposal_slot_has_no_value_field():
    """The server rejects a value for oauth credentials (tokens are obtained
    via the connect/approve flow). The rendered slot JSON must NOT set a
    "value" on the CLAUDE_OAUTH oauth slot."""
    body = _provision()
    # No "value": key anywhere in the proposal JSON heredoc. The whole script
    # carries no JSON "value" field for the oauth slot.
    assert '"value"' not in body, (
        'oauth credential slot must NOT carry a "value" field — the server '
        "rejects a value for oauth creds (tokens come via approve/connect)"
    )


def test_provision_oauth_proposal_omits_authorization_url():
    """authorization_url is OMITTED so approval shows the token-paste path
    (the realistic Claude case — we have a pasted token, not an interactive
    consent app)."""
    body = _provision()
    assert "authorization_url" not in body, (
        "authorization_url must be omitted so approval shows the token-paste "
        "path (the realistic Claude case)"
    )


# -----------------------------------------------------------------------
# B) Approve-the-proposal human gate (not dashboard hand-create)
# -----------------------------------------------------------------------


def test_provision_human_gate_instructs_approve_the_proposal():
    """The human-gate prompt instructs the operator to APPROVE the printed
    proposal — showing the verified ``vault proposal approve`` command — not
    to hand-create a credential in the dashboard Credentials tab."""
    body = _provision()
    assert "vault proposal approve" in body, (
        "human gate must show the `vault proposal approve <number> "
        "CLAUDE_OAUTH=<accessToken> --yes` command"
    )


def test_provision_removes_dashboard_paste_gate_and_no_cli_path_copy():
    """The old step-4b dashboard-paste box and its "CANNOT be created from
    this script" / "NO CLI path to provision" copy must be removed — the OAuth
    type IS scriptable via the proposal credential-slot path on 0.32.0."""
    body = _provision()
    low = body.lower()
    assert "dashboard paste" not in low, (
        "the old dashboard-paste gate copy must be removed"
    )
    assert "no cli path" not in low, (
        'the stale "NO CLI path to provision" copy must be removed/corrected'
    )
    assert "cannot be created" not in low, (
        'the stale "CANNOT be created from this script" copy must be corrected'
    )
    assert "no cli" not in low, (
        "the stale 'has no CLI path' header copy must be corrected"
    )
    # The operator is NOT told to add a credential in the dashboard Credentials tab.
    assert "credentials tab" not in low, (
        "operator must approve the proposal, not hand-create in a Credentials tab"
    )


# -----------------------------------------------------------------------
# C) Stored credential is refresh-capable oauth, NOT a flat credential set
# -----------------------------------------------------------------------


def test_provision_does_not_flat_credential_set_claude_oauth():
    """The script MUST NOT fall back to a flat
    ``vault credential set CLAUDE_OAUTH=<token>`` for the Claude credential —
    the oauth proposal (carrying token_url) is the refresh machinery. (The
    github creds still use credential set; only CLAUDE_OAUTH must not.)"""
    body = _provision()
    assert "credential set CLAUDE_OAUTH" not in body, (
        "CLAUDE_OAUTH must NOT be stored via a flat `credential set` (that is "
        "the static path); it is the refresh-capable oauth proposal slot"
    )
    # belt-and-suspenders: no `CLAUDE_OAUTH=<...>` inside a `credential set` line.
    for line in body.splitlines():
        if "credential set" in line:
            assert "CLAUDE_OAUTH" not in line, (
                f"flat credential set must not carry CLAUDE_OAUTH: {line!r}"
            )


# -----------------------------------------------------------------------
# E) Parameterized oauth config vars with verified defaults
# -----------------------------------------------------------------------


def test_provision_parameterizes_oauth_token_url_default():
    body = _provision()
    assert (
        'CLAUDE_OAUTH_TOKEN_URL="${CLAUDE_OAUTH_TOKEN_URL:-https://console.anthropic.com/v1/oauth/token}"'
        in body
    ), "provision must parameterize CLAUDE_OAUTH_TOKEN_URL with the verified default"


def test_provision_parameterizes_oauth_client_id_default():
    body = _provision()
    assert (
        'CLAUDE_OAUTH_CLIENT_ID="${CLAUDE_OAUTH_CLIENT_ID:-9d1c250a-e61b-44d9-88ed-5944d1962f5e}"'
        in body
    ), "provision must parameterize CLAUDE_OAUTH_CLIENT_ID with the verified default"


def test_provision_oauth_fields_come_from_script_vars():
    """The oauth block fields must be rendered from the script vars (E), not
    hard-coded inline — so a future Anthropic-endpoint change is a one-line
    edit. The token_url/client_id values appear via the shell vars."""
    body = _provision()
    assert "${CLAUDE_OAUTH_TOKEN_URL}" in body, (
        "oauth.token_url in the proposal JSON must come from $CLAUDE_OAUTH_TOKEN_URL"
    )
    assert "${CLAUDE_OAUTH_CLIENT_ID}" in body, (
        "oauth.client_id in the proposal JSON must come from $CLAUDE_OAUTH_CLIENT_ID"
    )


# -----------------------------------------------------------------------
# D) ADR-026 D4 preserved — human supplies the secret; post-gate verification
# -----------------------------------------------------------------------


def test_provision_retains_post_gate_oauth_verification():
    """ADR-026 D4: a human still supplies the real secret at approve time. The
    post-gate verification must confirm the approved oauth credential landed in
    the vault (e.g. via `vault credential list`) before continuing."""
    body = _provision()
    assert "vault credential list" in body, (
        "post-gate verification must confirm the approved CLAUDE_OAUTH landed "
        "(e.g. via `vault credential list`)"
    )


# -----------------------------------------------------------------------
# F) All other provision steps unchanged
# -----------------------------------------------------------------------


def test_provision_other_steps_unchanged():
    body = _provision()
    # owner / vault / five services / github creds 4a / fleet mint / ca fetch / .env
    assert "agent-vault auth register" in body
    assert "agent-vault vault create" in body
    assert "GITHUB_USERNAME=${GITHUB_USERNAME}" in body
    assert "GITHUB_TOKEN=${GITHUB_TOKEN}" in body
    for svc in ("github-git", "github-api", "claude-api", "claude-platform", "claude-mcp-proxy"):
        assert f"--name {svc}" in body, f"service {svc} must still render"
    assert "--token-key CLAUDE_OAUTH" in body, "claude-* bearer services stay"
    assert "agent-vault agent create" in body and "shopsystem-fleet" in body
    assert "agent-vault ca fetch" in body
    assert "AGENT_VAULT_ADDR" in body and "AGENT_VAULT_TOKEN" in body


# -----------------------------------------------------------------------
# G) Slug-clean
# -----------------------------------------------------------------------


def test_provision_oauth_gate_is_slug_clean():
    body = render_ops_template("agent-vault-provision", "dummyco")
    assert "shopsystem" not in body, f"dummyco render leaked shopsystem:\n{body}"
    assert "dstengle" not in body, f"dummyco render leaked dstengle:\n{body}"
