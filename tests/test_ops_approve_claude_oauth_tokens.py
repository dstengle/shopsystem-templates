"""Render-fidelity + behavioral tests for the Claude-OAuth populate path in the
rendered ``bin/agent-vault-approve-claude`` (bugfix lead-al1r).

ROOT CAUSE (proven at the DB level against a live agent-vault 0.32.0 server):
``agent-vault vault proposal approve <n> CLAUDE_OAUTH='{...}' --yes`` SILENTLY
DROPS the ``KEY=VALUE`` override for an OAuth-TYPED credential (the override
only applies for ``type=static``). The CLAUDE_OAUTH oauth slot is created
(token_url + client_id land) but the token material never does:
``credentials.ciphertext`` is length 0 and ``credential_oauth.refresh_token_ct
/ token_expires_at / connected_at`` are all NULL -> the credential reads back
blank ("Claude tokens not in the UI").

SUPPORTED MECHANISM (verified live against agent-vault 0.32.0): OAuth
credentials are populated via the cookie-authenticated endpoints the Web UI
"Save Tokens" form drives, NOT proposal-approve:

  - ``POST /v1/auth/login`` -> ``Set-Cookie: av_session=...; HttpOnly`` (a
    browser-session cookie; the UI fetch wrapper sends NO ``Authorization``
    header).
  - ``POST /v1/credentials/oauth/tokens`` with body ``{vault, key,
    access_token, refresh_token, token_url, client_id}`` -- the broker
    validates the refresh token by performing a refresh-grant against
    ``token_url`` before persisting, so a stored credential is refreshable by
    construction.

bin/agent-vault-approve-claude is the single operator approval handoff
(broker/13 @1d08c456af08d577) and the tokens it carries are operator-supplied
at approve-time from ~/.claude/.credentials.json (broker/11 @72af524bca85f59c);
this fix changes only HOW the supplied tokens are persisted (the supported
endpoint instead of the dropping proposal-approve path), not WHEN/WHENCE the
secret is supplied.

Acceptance is grep-predicate over the RENDERED body plus a BEHAVIORAL bash
slice that runs the rendered script under a stub ``curl`` and a fake
credentials file, recording the requests it issues.
"""
import json
import os
import subprocess
import tempfile

from shop_templates.cli import render_ops_template


def _approve(slug: str = "acme") -> str:
    return render_ops_template("agent-vault-approve-claude", slug)


# -----------------------------------------------------------------------
# A) The dropping proposal-approve path is GONE for CLAUDE_OAUTH
# -----------------------------------------------------------------------


def test_approve_claude_does_not_use_proposal_approve_for_claude_oauth():
    """The fix removes the structurally-wrong ``proposal approve <n>
    CLAUDE_OAUTH=<value>`` path: for an oauth-typed credential agent-vault
    silently drops that override, so the token never lands."""
    body = _approve()
    for line in body.splitlines():
        if "proposal approve" in line:
            assert "CLAUDE_OAUTH" not in line, (
                "approve-claude must NOT seed CLAUDE_OAUTH via `proposal approve "
                f"<n> CLAUDE_OAUTH=...` (the dropped-override defect): {line!r}"
            )


# -----------------------------------------------------------------------
# B) The supported cookie-authenticated endpoints
# -----------------------------------------------------------------------


def test_approve_claude_obtains_session_cookie_via_login():
    """It authenticates via ``POST /v1/auth/login`` into a cookie jar (the UI's
    HttpOnly session-cookie auth), not an av_sess_ Bearer."""
    body = _approve()
    assert "/v1/auth/login" in body, (
        "approve-claude must obtain a session cookie via POST /v1/auth/login"
    )
    assert ("--cookie-jar" in body) or (" -c " in body) or ("-c " in body), (
        "the login response cookie must be captured into a cookie jar (curl -c)"
    )


def test_approve_claude_posts_to_oauth_tokens_endpoint():
    """It populates the credential via the supported ``POST
    /v1/credentials/oauth/tokens`` endpoint (the UI 'Save Tokens' form)."""
    body = _approve()
    assert "/v1/credentials/oauth/tokens" in body, (
        "approve-claude must POST the tokens to /v1/credentials/oauth/tokens "
        "(the supported oauth-credential populate endpoint)"
    )


def test_approve_claude_uses_cookie_auth_not_authorization_header():
    """The oauth/tokens + login calls use cookie/session auth — the UI fetch
    wrapper sends NO Authorization header and uses no av_sess_ Bearer."""
    body = _approve()
    low = body.lower()
    assert "authorization:" not in low, (
        "the supported endpoints use cookie/session auth, not an Authorization "
        "header"
    )
    # The cookie jar is replayed on the tokens call (curl -b/--cookie).
    assert ("--cookie " in body) or ("-b " in body), (
        "the captured session cookie must be replayed on the oauth/tokens call "
        "(curl -b)"
    )


# -----------------------------------------------------------------------
# C) The oauth/tokens body carries the refresh machinery
# -----------------------------------------------------------------------


def test_approve_claude_tokens_body_carries_access_and_refresh_tokens():
    body = _approve()
    assert "access_token" in body, "oauth/tokens body must carry access_token"
    assert "refresh_token" in body, (
        "oauth/tokens body must carry refresh_token — a single token cannot "
        "refresh; the bug symptom is exactly a NULL refresh_token_ct"
    )


def test_approve_claude_tokens_body_carries_token_url_and_client_id():
    body = _approve()
    assert "token_url" in body, (
        "oauth/tokens body must carry token_url (the refresh machinery the "
        "broker validates against)"
    )
    assert "client_id" in body, "oauth/tokens body must carry client_id"


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
# D) Operator-supplied-at-approve-time secret preserved (broker/11)
# -----------------------------------------------------------------------


def test_approve_claude_still_reads_operator_supplied_tokens_at_approve_time():
    """broker/11 @72af524bca85f59c preserved: the real secret is supplied only
    at approve-time by the operator running the command — read from the host
    ~/.claude/.credentials.json (or a positional override), never automated."""
    body = _approve()
    assert ".claude/.credentials.json" in body, (
        "the operator's tokens are read at approve-time from "
        "~/.claude/.credentials.json (operator-supplied, not automated transport)"
    )
    assert "accessToken" in body and "refreshToken" in body, (
        "approve-claude must extract accessToken + refreshToken from the "
        "operator's credentials file"
    )


# -----------------------------------------------------------------------
# E) Slug-clean
# -----------------------------------------------------------------------


def test_approve_claude_is_slug_clean():
    body = render_ops_template("agent-vault-approve-claude", "dummyco")
    assert "shopsystem" not in body, f"dummyco render leaked shopsystem:\n{body}"
    assert "dstengle" not in body, f"dummyco render leaked dstengle:\n{body}"


# -----------------------------------------------------------------------
# F) BEHAVIORAL slice — the rendered script issues the right requests
# -----------------------------------------------------------------------


def _run_approve_claude_under_stub_curl(access: str, refresh: str):
    """Run the rendered approve-claude under a stub ``curl`` (recording every
    invocation's URL + stdin body) and a stub ``agent-vault`` (recording any
    invocation), with a fake ~/.claude/.credentials.json supplying the tokens.

    Returns (returncode, curl_log, agent_vault_log, stderr).
    """
    body = _approve("acme")
    d = tempfile.mkdtemp()
    cred = os.path.join(d, "credentials.json")
    with open(cred, "w") as fh:
        json.dump(
            {"claudeAiOauth": {"accessToken": access, "refreshToken": refresh,
                               "expiresAt": 9999999999}},
            fh,
        )
    curl_log = os.path.join(d, "curl.log")
    av_log = os.path.join(d, "av.log")
    script = os.path.join(d, "approve-claude")
    with open(script, "w") as fh:
        fh.write(body)
    os.chmod(script, 0o755)
    # ops-coordinates is sourced by the script; provide a minimal stub on the
    # same dir (the script sources "$(dirname)/ops-coordinates").
    with open(os.path.join(d, "ops-coordinates"), "w") as fh:
        fh.write(
            "OPS_SLUG=acme\n"
            "OPS_VAULT_NAME=acme\n"
            "OPS_AGENT_VAULT_CONTAINER=acme-agent-vault\n"
            "OPS_BROKER_ADDR=http://acme-agent-vault:14321\n"
            "OPS_AGENT_VAULT_ADDR=http://acme-agent-vault:14321\n"
            "OPS_BROKER_LOCAL_ADDR=http://localhost:14321\n"
        )
    harness = f"""set +e
export HOME={d!r}
mkdir -p {d!r}/.claude
cp {cred!r} {d!r}/.claude/.credentials.json
export AGENT_VAULT_OWNER_PASSWORD=ownerpw
# stub curl: record url + stdin body; emit a fake av_session cookie into the
# -c jar on login; emit success on the tokens call.
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
  if [[ "$url" == *"/v1/auth/login"* ]]; then
    [[ -n "$jar" ]] && printf '#HttpOnly_h\\tFALSE\\t/\\tFALSE\\t0\\tav_session\\tav_sess_x\\n' > "$jar"
  fi
  [[ -n "$out" ]] && : > "$out"
  printf '200'
  return 0
}}
export -f curl
agent-vault() {{ echo "AV: $*" >> {av_log!r}; return 0; }}
export -f agent-vault
bash {script!r}
"""
    proc = subprocess.run(["bash", "-c", harness], capture_output=True, text=True)
    cl = open(curl_log).read() if os.path.exists(curl_log) else ""
    al = open(av_log).read() if os.path.exists(av_log) else ""
    return proc.returncode, cl, al, proc.stderr


def test_behavioral_approve_claude_posts_login_then_oauth_tokens_with_supplied_tokens():
    rc, curl_log, av_log, stderr = _run_approve_claude_under_stub_curl(
        access="acc-OPERATOR", refresh="ref-OPERATOR"
    )
    assert rc == 0, f"approve-claude must succeed under stubs; stderr={stderr!r}"
    assert "/v1/auth/login" in curl_log, (
        f"approve-claude must POST /v1/auth/login; curl log:\n{curl_log}"
    )
    assert "/v1/credentials/oauth/tokens" in curl_log, (
        f"approve-claude must POST /v1/credentials/oauth/tokens; curl log:\n{curl_log}"
    )
    # The operator-supplied tokens ride the oauth/tokens body.
    assert "acc-OPERATOR" in curl_log, (
        f"the operator access token must reach the oauth/tokens body:\n{curl_log}"
    )
    assert "ref-OPERATOR" in curl_log, (
        f"the operator refresh token must reach the oauth/tokens body:\n{curl_log}"
    )
    # The dropping proposal-approve path is NOT used to seed CLAUDE_OAUTH.
    assert "proposal approve" not in av_log, (
        f"approve-claude must NOT seed CLAUDE_OAUTH via proposal approve:\n{av_log}"
    )


def test_behavioral_approve_claude_aborts_on_empty_supplied_tokens():
    """When the operator's credentials yield an empty access/refresh token the
    script aborts (non-zero, diagnostic) rather than POSTing a blank credential
    — the same no-blank-writeback faithfulness guard the provision path holds."""
    rc, curl_log, av_log, stderr = _run_approve_claude_under_stub_curl(
        access="", refresh=""
    )
    assert rc != 0, "approve-claude must abort when no usable tokens are supplied"
    assert "/v1/credentials/oauth/tokens" not in curl_log, (
        "approve-claude must NOT POST a blank credential to oauth/tokens"
    )
    assert stderr.strip(), "the abort must emit a diagnostic on stderr"
