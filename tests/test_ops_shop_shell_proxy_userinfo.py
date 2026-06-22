"""shop-shell broker-proxy URL must embed the broker token+vault as userinfo
(lead-5et9 — HTTP 407 bugfix).

The bug: the rendered bin/shop-shell builds the outbound proxy as the BARE
broker endpoint with NO ${AGENT_VAULT_TOKEN}:${AGENT_VAULT_VAULT}@ userinfo:

    HTTPS_PROXY="${HTTPS_PROXY:-http://agent-vault:14322}"
    HTTP_PROXY="${HTTP_PROXY:-http://agent-vault:14322}"

The agent-vault transparent proxy on :14322 requires Basic proxy auth
identifying the agent+vault. With no token in the proxy URL the broker rejects
claude's outbound request with HTTP 407 Proxy Authentication Required
(Proxy-Authenticate: Basic realm="agent-vault"), the live blocker stopping an
operator from running the lead agent via bin/shop-shell.

The fix (additive to lead-held scenario 172 @scenario_hash:5335c39eb06f7493,
which pins only the literal "14322" on an HTTPS_PROXY assignment — that literal
is PRESERVED): build the default proxy URL with the broker credentials the
script already has in hand and exports upstream:

    HTTPS_PROXY="${HTTPS_PROXY:-http://${AGENT_VAULT_TOKEN}:${AGENT_VAULT_VAULT}@agent-vault:14322}"
    HTTP_PROXY="${HTTP_PROXY:-http://${AGENT_VAULT_TOKEN}:${AGENT_VAULT_VAULT}@agent-vault:14322}"

Keep it overridable (${VAR:-...}); embed token+vault RAW (no percent-encoding),
matching the working BC fleet form (cf. bc-launcher scenario 45
@scenario_hash:c4e88075a0b4bd00).

These are properties of the rendered shop-shell BODY, proven by extracting the
proxy-construction region and EXECUTING it under `set -euo pipefail` with the
broker token+vault stubbed, then asserting the resolved HTTPS_PROXY/HTTP_PROXY
values carry the userinfo — not by substring-matching alone.
"""
import subprocess

from shop_templates.cli import render_ops_template

_SLUG = "dummyco"
_TOKEN = "av_agt_TESTTOKEN"
_VAULT = "fleet"
_EXPECTED = f"http://{_TOKEN}:{_VAULT}@agent-vault:14322"


def _shop_shell_body() -> str:
    return render_ops_template("shop-shell", _SLUG)


def _proxy_region(body: str) -> str:
    """Return the proxy-construction region of the rendered shop-shell: from
    the HTTPS_PROXY assignment through the `export HTTPS_PROXY HTTP_PROXY` line.

    Extracting this self-contained block lets us execute the real proxy-URL
    construction under bash without reaching the credential-acquisition,
    CA-materialization, or `exec docker run` launch lines."""
    lines = body.splitlines()
    start = next(
        i for i, ln in enumerate(lines)
        if ln.strip().startswith("HTTPS_PROXY=")
    )
    end = next(
        i for i, ln in enumerate(lines)
        if i >= start and ln.strip().startswith("export HTTPS_PROXY")
    )
    return "\n".join(lines[start : end + 1])


def _run_region(*, https_override: str = "", http_override: str = ""):
    """Execute the proxy-construction region under bash with the broker
    token+vault stubbed (as upstream sourcing+export would have set them), then
    print the resolved HTTPS_PROXY/HTTP_PROXY values."""
    region = _proxy_region(_shop_shell_body())
    script = (
        "set -euo pipefail\n"
        f'AGENT_VAULT_TOKEN="{_TOKEN}"\n'
        f'AGENT_VAULT_VAULT="{_VAULT}"\n'
        f'HTTPS_PROXY="{https_override}"\n'
        f'HTTP_PROXY="{http_override}"\n'
        "export AGENT_VAULT_TOKEN AGENT_VAULT_VAULT HTTPS_PROXY HTTP_PROXY\n"
        + region
        + "\n"
        'echo "HTTPS_PROXY=[$HTTPS_PROXY]"\n'
        'echo "HTTP_PROXY=[$HTTP_PROXY]"\n'
    )
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True
    )


def _parse(out: str, key: str) -> str:
    for ln in out.splitlines():
        if ln.startswith(f"{key}=["):
            return ln[len(key) + 2 : -1]
    return "<unset>"


def test_https_proxy_default_embeds_token_and_vault_userinfo():
    """With no operator override, the resolved HTTPS_PROXY must be the broker
    endpoint carrying the ${AGENT_VAULT_TOKEN}:${AGENT_VAULT_VAULT}@ userinfo —
    NOT the bare http://agent-vault:14322 that triggers HTTP 407."""
    proc = _run_region()
    assert proc.returncode == 0, (
        f"proxy region must run clean: stdout={proc.stdout!r} "
        f"stderr={proc.stderr!r}"
    )
    assert _parse(proc.stdout, "HTTPS_PROXY") == _EXPECTED, (
        "HTTPS_PROXY default must embed the broker token+vault as userinfo "
        f"(got {_parse(proc.stdout, 'HTTPS_PROXY')!r}, want {_EXPECTED!r}); a "
        "bare http://agent-vault:14322 default is the HTTP 407 bug."
    )


def test_http_proxy_default_embeds_token_and_vault_userinfo():
    """The lowercase-twin HTTP_PROXY default must carry the same userinfo."""
    proc = _run_region()
    assert proc.returncode == 0, (
        f"proxy region must run clean: stderr={proc.stderr!r}"
    )
    assert _parse(proc.stdout, "HTTP_PROXY") == _EXPECTED, (
        "HTTP_PROXY default must embed the broker token+vault as userinfo "
        f"(got {_parse(proc.stdout, 'HTTP_PROXY')!r}, want {_EXPECTED!r})."
    )


def test_operator_override_still_wins_https_and_http():
    """The fix must KEEP the overridable ${VAR:-...} default form: an operator
    who pre-sets HTTPS_PROXY/HTTP_PROXY keeps their value, the credentialed
    default applying only when the variable is empty."""
    override = "http://my-corp-proxy:3128"
    proc = _run_region(https_override=override, http_override=override)
    assert proc.returncode == 0, f"stderr={proc.stderr!r}"
    assert _parse(proc.stdout, "HTTPS_PROXY") == override, (
        "operator HTTPS_PROXY override must win over the credentialed default."
    )
    assert _parse(proc.stdout, "HTTP_PROXY") == override, (
        "operator HTTP_PROXY override must win over the credentialed default."
    )


def test_endpoint_literal_14322_preserved_on_https_proxy_assignment():
    """Scenario 172 (@scenario_hash:5335c39eb06f7493) pins the literal "14322"
    carried on an HTTPS_PROXY assignment. The userinfo fix is ADDITIVE: the
    literal endpoint substring must remain on the HTTPS_PROXY assignment."""
    body = _shop_shell_body()
    https_lines = [
        ln for ln in body.splitlines() if ln.strip().startswith("HTTPS_PROXY=")
    ]
    assert https_lines, "shop-shell must carry an HTTPS_PROXY assignment"
    assert any("14322" in ln for ln in https_lines), (
        "scenario 172's literal '14322' must remain on an HTTPS_PROXY "
        f"assignment after the userinfo fix; got {https_lines!r}"
    )
