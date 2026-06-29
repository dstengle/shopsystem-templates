"""Tests for the Claude-OAuth POPULATE step in the rendered
``bin/agent-vault-approve-claude`` (bugfix lead-al1r).

ROOT CAUSE (proven at the DB level against a live agent-vault 0.32.0 server):
``agent-vault vault proposal approve <n> CLAUDE_OAUTH='{...}' --yes`` SILENTLY
DROPS the ``KEY=VALUE`` override for an OAuth-TYPED credential (the override
only applies for ``type=static``). The proposal-approve still APPROVES the
proposal and ensures the oauth slot exists, but the token material never lands
through it: ``credentials.ciphertext`` is length 0 and
``credential_oauth.refresh_token_ct / token_expires_at / connected_at`` stay
NULL -> the credential reads back blank ("Claude tokens not in the UI").

SUPPORTED MECHANISM (verified live against agent-vault 0.32.0): oauth tokens
are populated via the cookie-authenticated endpoints the Web UI "Save Tokens"
form drives, NOT proposal-approve:

  - ``POST /v1/auth/login`` -> ``Set-Cookie: av_session=...; HttpOnly`` (a
    MEMBER/owner browser-session cookie; the CLI's vault-scoped av_sess_ Bearer
    is rejected "Member role required").
  - ``POST /v1/credentials/oauth/tokens`` with body ``{vault, key,
    access_token, refresh_token, token_url, client_id}`` -- the broker
    validates the refresh token by performing a refresh-grant against
    ``token_url`` before persisting, so a stored credential is refreshable by
    construction.

ADDITIVE: this bugfix does NOT remove the proposal-approve flow that the
lead-held approve-claude scenarios pin (d8422606299d8819 proposal-number
identity; 74d0086b73d4e477 both-tokens-from-credentials.json;
e59b29a6fc34f60a sources-ops-coordinates). It APPENDS the corrective
OAUTH-TOKENS-POPULATE step (delimited by OAUTH-TOKENS-POPULATE-BEGIN/END) that
actually lands the refreshable token material the KEY=VALUE proposal-approve
drops. broker/13 (1d08c456af08d577) single-handoff and broker/11
(72af524bca85f59c) operator-supplied-at-approve-time are preserved.

Acceptance combines grep-predicates over the RENDERED body with a BEHAVIORAL
bash slice that runs the extracted populate block under a stub ``curl``,
recording the requests it issues.
"""
import json
import os
import subprocess
import tempfile

from shop_templates.cli import render_ops_template


def _approve(slug: str = "acme") -> str:
    return render_ops_template("agent-vault-approve-claude", slug)


def _populate_block(slug: str = "acme") -> str:
    """Extract the OAUTH-TOKENS-POPULATE block — the corrective step delimited
    by the OAUTH-TOKENS-POPULATE-BEGIN/END markers."""
    lines = _approve(slug).splitlines()
    start = next(i for i, l in enumerate(lines) if "OAUTH-TOKENS-POPULATE-BEGIN" in l)
    end = next(i for i, l in enumerate(lines) if "OAUTH-TOKENS-POPULATE-END" in l)
    return "\n".join(lines[start : end + 1])


# -----------------------------------------------------------------------
# A) The corrective populate step exists and uses the supported endpoints
# -----------------------------------------------------------------------


def test_approve_claude_has_oauth_tokens_populate_block():
    body = _approve()
    assert "OAUTH-TOKENS-POPULATE-BEGIN" in body and "OAUTH-TOKENS-POPULATE-END" in body, (
        "approve-claude must carry a delimited OAUTH-TOKENS-POPULATE step — the "
        "proposal-approve KEY=VALUE path drops the oauth token material"
    )


def test_approve_claude_obtains_member_session_cookie_via_login():
    """The populate step authenticates via ``POST /v1/auth/login`` into a cookie
    jar (the UI's HttpOnly member session-cookie auth), not the CLI av_sess_
    Bearer (rejected 'Member role required')."""
    block = _populate_block()
    assert "/v1/auth/login" in block, (
        "populate step must obtain a session cookie via POST /v1/auth/login"
    )
    assert "--cookie-jar" in block or " -c " in block, (
        "the login response cookie must be captured into a cookie jar (curl -c)"
    )


def test_approve_claude_posts_to_oauth_tokens_endpoint():
    block = _populate_block()
    assert "/v1/credentials/oauth/tokens" in block, (
        "populate step must POST to /v1/credentials/oauth/tokens (the supported "
        "oauth-credential populate endpoint)"
    )


def test_approve_claude_populate_uses_cookie_auth_not_authorization_header():
    """The oauth/tokens + login calls use cookie/session auth — the UI fetch
    wrapper sends NO Authorization header and no av_sess_ Bearer."""
    block = _populate_block()
    low = block.lower()
    assert "authorization:" not in low, (
        "the supported endpoints use cookie/session auth, not an Authorization header"
    )
    assert "--cookie " in block or " -b " in block, (
        "the captured session cookie must be replayed on the oauth/tokens call (curl -b)"
    )


# -----------------------------------------------------------------------
# B) The oauth/tokens body carries the refresh machinery
# -----------------------------------------------------------------------


def test_approve_claude_tokens_body_carries_access_and_refresh_tokens():
    block = _populate_block()
    assert "access_token" in block, "oauth/tokens body must carry access_token"
    assert "refresh_token" in block, (
        "oauth/tokens body must carry refresh_token — a single token cannot "
        "refresh; the bug symptom is exactly a NULL refresh_token_ct"
    )


def test_approve_claude_tokens_body_carries_token_url_and_client_id():
    block = _populate_block()
    assert "token_url" in block, (
        "oauth/tokens body must carry token_url (the refresh machinery the "
        "broker validates against)"
    )
    assert "client_id" in block, "oauth/tokens body must carry client_id"


def test_approve_claude_parameterizes_oauth_defaults_matching_provision():
    """token_url + client_id are parameterized with the SAME verified defaults
    provision uses, so an Anthropic-endpoint change stays a one-line edit and
    the two scripts cannot drift."""
    body = _approve()
    assert (
        'CLAUDE_OAUTH_TOKEN_URL="${CLAUDE_OAUTH_TOKEN_URL:-https://console.anthropic.com/v1/oauth/token}"'
        in body
    ), "approve-claude must parameterize CLAUDE_OAUTH_TOKEN_URL with the verified default"
    assert (
        'CLAUDE_OAUTH_CLIENT_ID="${CLAUDE_OAUTH_CLIENT_ID:-9d1c250a-e61b-44d9-88ed-5944d1962f5e}"'
        in body
    ), "approve-claude must parameterize CLAUDE_OAUTH_CLIENT_ID with the verified default"


# -----------------------------------------------------------------------
# C) Preserved invariants: proposal-approve flow (lead pins) + operator secret
# -----------------------------------------------------------------------


def test_approve_claude_preserves_proposal_approve_flow():
    """ADDITIVE: the lead-held approve-claude scenarios (d8422606299d8819) pin
    the `proposal approve <num>` flow; this bugfix appends the populate step
    rather than removing that flow."""
    body = _approve()
    assert "agent-vault vault proposal approve" in body, (
        "the proposal-approve flow the lead scenarios pin must be preserved"
    )
    assert "$OPS_AGENT_VAULT_CONTAINER" in body, (
        "the ops-coordinates container reference (e59b29a6fc34f60a) must be preserved"
    )


def test_approve_claude_still_reads_operator_supplied_tokens_at_approve_time():
    """broker/11 @72af524bca85f59c preserved: the real secret is supplied only
    at approve-time by the operator (read from ~/.claude/.credentials.json or a
    positional override), never automated."""
    body = _approve()
    assert ".claude/.credentials.json" in body
    assert "accessToken" in body and "refreshToken" in body, (
        "approve-claude must extract accessToken + refreshToken from the "
        "operator's credentials file"
    )


# -----------------------------------------------------------------------
# D) Slug-clean
# -----------------------------------------------------------------------


def test_approve_claude_is_slug_clean():
    body = render_ops_template("agent-vault-approve-claude", "dummyco")
    assert "shopsystem" not in body, f"dummyco render leaked shopsystem:\n{body}"
    assert "dstengle" not in body, f"dummyco render leaked dstengle:\n{body}"


# -----------------------------------------------------------------------
# E) BEHAVIORAL slice — the populate block issues the right requests
# -----------------------------------------------------------------------


def _run_populate_block_under_stub_curl(access: str, refresh: str, owner_pw="ownerpw"):
    """Run the extracted OAUTH-TOKENS-POPULATE block under a stub ``curl``
    (recording every invocation's URL + stdin body), with the precursor vars the
    block consumes pre-set.

    Returns (returncode, curl_log, stderr).
    """
    block = _populate_block("acme")
    d = tempfile.mkdtemp()
    curl_log = os.path.join(d, "curl.log")
    owner_assign = (
        f"export AGENT_VAULT_OWNER_PASSWORD={owner_pw!r}\n" if owner_pw is not None else ""
    )
    harness = f"""set +e
OPS_SLUG=acme
OPS_AGENT_VAULT_ADDR=http://acme-agent-vault:14321
VAULT=acme
CRED_FILE=/tmp/none
ACCESS_TOKEN={access!r}
REFRESH_TOKEN={refresh!r}
{owner_assign}
curl() {{
  local url="" jar="" out=""
  local args=("$@")
  for ((i=0;i<${{#args[@]}};i++)); do
    case "${{args[i]}}" in
      http*) url="${{args[i]}}" ;;
      -c|--cookie-jar) jar="${{args[i+1]}}" ;;
      -o) out="${{args[i+1]}}" ;;
    esac
  done
  local bodyin; bodyin="$(cat 2>/dev/null)"
  {{ echo "URL=$url"; echo "BODY=$bodyin"; }} >> {curl_log!r}
  if [[ "$url" == *"/v1/auth/login"* && -n "$jar" ]]; then
    printf '#HttpOnly_h\\tFALSE\\t/\\tFALSE\\t0\\tav_session\\tav_sess_x\\n' > "$jar"
  fi
  [[ -n "$out" ]] && : > "$out"
  if [[ "$url" == *"/v1/credentials/oauth/tokens"* ]]; then printf '{{}}\\n200'; else printf '200'; fi
  return 0
}}
{block}
"""
    proc = subprocess.run(["bash", "-c", harness], capture_output=True, text=True)
    cl = open(curl_log).read() if os.path.exists(curl_log) else ""
    return proc.returncode, cl, proc.stderr


def test_behavioral_populate_posts_login_then_oauth_tokens_with_supplied_tokens():
    rc, curl_log, stderr = _run_populate_block_under_stub_curl(
        access="acc-OPERATOR", refresh="ref-OPERATOR"
    )
    assert rc == 0, f"populate block must succeed under stubs; stderr={stderr!r}"
    assert "/v1/auth/login" in curl_log, f"must POST /v1/auth/login:\n{curl_log}"
    assert "/v1/credentials/oauth/tokens" in curl_log, (
        f"must POST /v1/credentials/oauth/tokens:\n{curl_log}"
    )
    assert "acc-OPERATOR" in curl_log, f"access token must reach the body:\n{curl_log}"
    assert "ref-OPERATOR" in curl_log, f"refresh token must reach the body:\n{curl_log}"


def test_behavioral_populate_aborts_on_empty_supplied_tokens():
    """An empty access/refresh token aborts (non-zero, diagnostic) rather than
    POSTing a blank credential — the no-blank-write faithfulness guard."""
    rc, curl_log, stderr = _run_populate_block_under_stub_curl(access="", refresh="")
    assert rc != 0, "populate must abort when no usable tokens are supplied"
    assert "/v1/credentials/oauth/tokens" not in curl_log, (
        "populate must NOT POST a blank credential to oauth/tokens"
    )
    assert stderr.strip(), "the abort must emit a diagnostic on stderr"


def test_behavioral_populate_aborts_without_owner_password():
    """Without an owner password the member session cookie cannot be minted;
    abort with a diagnostic rather than silently leaving the credential blank."""
    rc, curl_log, stderr = _run_populate_block_under_stub_curl(
        access="a", refresh="r", owner_pw=None
    )
    assert rc != 0, "populate must abort when AGENT_VAULT_OWNER_PASSWORD is unset"
    assert "/v1/credentials/oauth/tokens" not in curl_log
    assert "AGENT_VAULT_OWNER_PASSWORD" in stderr, (
        "the abort must name the missing owner password"
    )
