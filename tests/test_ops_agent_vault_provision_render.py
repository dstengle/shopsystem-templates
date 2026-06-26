"""Render-fidelity tests for the agent-vault ops scaffolding (lead-beym).

Two render defects surfaced by the dummyco instantiation spike (iter-3):

  DEFECT 1 (P0): ``bin/agent-vault-provision`` was authored against a
  FICTIONAL agent-vault CLI — it called ``agent-vault put`` which does not
  exist in agent-vault 0.32.0. With ``set -euo pipefail`` the failing
  ``put`` aborts the script before the human gate whenever ``GITHUB_PAT`` is
  set. The GitHub-PAT path is rewritten against the REAL 0.32.0 surface per
  ADR-026 D2 (owner -> vault -> credential -> service -> agent), it mints the
  ``<slug>-fleet`` agent token, and writes the real broker addr + token back
  to ``.env`` (Brief 011 Step 4).

  DEFECT 2 (P1): the ``compose.yaml`` agent-vault healthcheck used the
  bash-only ``/dev/tcp`` redirect; the ``infisical/agent-vault`` image runs
  ``sh`` (no bash), so the probe failed every interval and the broker
  reported ``unhealthy`` despite serving. Replaced with an sh-compatible
  ``nc -z`` probe. The postgres ``pg_isready`` healthcheck is unchanged.

Acceptance is grep-predicate over the RENDERED ops bodies (no live broker in
the BC env): the real agent-vault verbs were verified against the installed
agent-vault 0.32.0 ``--help`` surface; the end-to-end provisioning against a
live broker is validated by the lead's dummyco spike.
"""
import re

import yaml

from shop_templates.cli import render_ops_template

# The real agent-vault 0.32.0 top-level verbs (verified against the installed
# /usr/local/bin/agent-vault --help in this env). Any `agent-vault <verb>`
# invocation in the rendered provision script must use one of these.
_REAL_TOP_VERBS = {
    "account",
    "agent",
    "auth",
    "ca",
    "catalog",
    "help",
    "master-password",
    "owner",
    "run",
    "server",
    "user",
    "vault",
    "version",
}

# Verbs that were authored against the FICTIONAL API and must never appear.
_FICTIONAL_VERBS = {"put", "get-secret", "store", "write", "secret"}


def _provision(slug: str = "shopsystem") -> str:
    return render_ops_template("agent-vault-provision", slug)


def _compose(slug: str = "shopsystem") -> str:
    return render_ops_template("compose.yaml", slug)


def _agent_vault_invocations(body: str):
    """Yield the first token after each ``agent-vault`` word in the body
    (the sub-verb), skipping the shebang/comment lines and the
    container-name literals (`<slug>-agent-vault`, `agent-vault-provision`)."""
    for m in re.finditer(r"agent-vault\s+([a-z][a-z0-9-]*)", body):
        # Skip hyphenated container/script names that merely contain the
        # word "agent-vault" (e.g. "shopsystem-agent-vault", which the regex
        # cannot match because of the preceding non-space, and
        # "agent-vault-provision"/"agent-vault-data" which the captured verb
        # would be "provision"/"data"/"check" — those are not CLI calls).
        yield m.group(1)


# -----------------------------------------------------------------------
# DEFECT 1 — no fictional verbs; real 0.32.0 surface only
# -----------------------------------------------------------------------


def test_provision_has_no_fictional_agent_vault_put():
    body = _provision()
    assert "agent-vault put" not in body, (
        "rendered provision still calls the FICTIONAL `agent-vault put` verb"
    )


def _shell_lines(body: str):
    """Yield the executable shell lines of the script — comment lines and any
    text inside a ``cat <<EOF ... EOF`` heredoc (operator-facing prose, not
    CLI calls) are excluded so prose like "Open the agent-vault dashboard"
    is not mistaken for an ``agent-vault dashboard`` invocation."""
    in_heredoc = False
    for line in body.splitlines():
        stripped = line.strip()
        if in_heredoc:
            if stripped == "EOF":
                in_heredoc = False
            continue
        if re.search(r"<<-?\s*['\"]?EOF['\"]?", line):
            in_heredoc = True
            continue
        if stripped.startswith("#"):
            continue
        yield line


def test_provision_uses_only_real_top_level_verbs():
    body = _provision()
    # Examine only lines that actually invoke the CLI binary (a real call has
    # `agent-vault <verb>` where <verb> is a top-level command). The script
    # invokes the CLI inside the broker container via `docker exec ... \n  agent-vault ...`.
    invocation_re = re.compile(r"(?:^|[\s|&;])agent-vault\s+([a-z][a-z0-9-]+)")
    bad = []
    for line in _shell_lines(body):
        for m in invocation_re.finditer(line):
            verb = m.group(1)
            # `agent-vault-provision` / `agent-vault-check` / `agent-vault-data`
            # are file/container names, not CLI calls: the captured verb would
            # be `provision`/`check`/`data`. Those substrings only appear after
            # a hyphen, so guard against them.
            if re.search(rf"agent-vault-{verb}\b", line):
                continue
            if verb in _FICTIONAL_VERBS:
                bad.append(("fictional", verb, line.strip()))
            elif verb not in _REAL_TOP_VERBS:
                bad.append(("unknown", verb, line.strip()))
    assert not bad, f"non-real agent-vault verbs found: {bad}"


def test_provision_github_path_uses_real_d2_flow():
    """ADR-026 D2 owner -> vault -> credential -> service -> agent flow,
    expressed with the real 0.32.0 sub-verbs."""
    body = _provision()
    # owner registration (first registrant becomes instance owner)
    assert "agent-vault auth register" in body, "missing owner/auth register leg"
    # vault create
    assert "agent-vault vault create" in body, "missing `vault create` leg"
    # credential set (real verb is `vault credential set <key=value>`)
    assert "agent-vault vault credential set" in body, (
        "missing `vault credential set` leg"
    )
    # service add wiring github.com Basic over the MITM proxy
    assert "agent-vault vault service add" in body, "missing `vault service add` leg"
    assert "--auth-type basic" in body, "github service must wire Basic auth"
    assert "github.com" in body, "github service must target github.com host"


def test_provision_wires_service_over_mitm_proxy():
    """ADR-026 D2: both legs broker over the single MITM proxy listener
    (container port 14322)."""
    body = _provision()
    assert "14322" in body, (
        "provision must reference the MITM proxy listener port 14322"
    )


# -----------------------------------------------------------------------
# DEFECT 1 (folded-in) — mint <slug>-fleet token + write .env
# -----------------------------------------------------------------------


def test_provision_mints_slug_fleet_agent_token():
    body = _provision("shopsystem")
    assert "agent-vault agent create" in body, "missing `agent create` token mint"
    assert "shopsystem-fleet" in body, (
        "must mint the <slug>-fleet agent (shopsystem-fleet for default slug)"
    )
    # token-only output so the av_agt_... token can be captured programmatically
    assert "--token-only" in body, (
        "agent create must use --token-only to capture the raw av_agt_ token"
    )


def test_provision_writes_addr_and_token_to_env():
    body = _provision()
    # The provision script must write both keys back to .env.
    assert "AGENT_VAULT_ADDR" in body, "provision must write AGENT_VAULT_ADDR to .env"
    assert "AGENT_VAULT_TOKEN" in body, (
        "provision must write AGENT_VAULT_TOKEN to .env"
    )
    # The write must target the .env file (replacing the changeme placeholders).
    assert ".env" in body, "provision must reference the .env file it updates"
    # The two changeme placeholders for ADDR/TOKEN must be the replacement
    # targets (so they do not survive after provision).
    assert "<changeme-broker-address>" in body, (
        "provision must replace the <changeme-broker-address> placeholder"
    )
    assert "<changeme-broker-token>" in body, (
        "provision must replace the <changeme-broker-token> placeholder"
    )


def test_provision_preserves_claude_oauth_human_gate():
    """ADR-026 D4 (CORRECTED, lead-yrex): the refreshing Claude-OAuth credential
    IS scriptable on 0.32.0 via the `vault proposal create -f -` credential-slot
    path. The human gate is no longer a manual dashboard paste — it is the
    operator APPROVING the pre-populated OAuth proposal (token paste at the
    approve URL). The HUMAN GATE banner is preserved; the gate references
    Claude-OAuth and instructs approve.

    SUPERSEDED PRE-STATE (lead-8vxy / PDR-019 U6 / ADR-040 D2): the gate USED
    to BLOCK on an interactive ``read -r -p "Press ENTER ..."`` wait. That
    blocking wait is RETIRED — provision is now lead-driveable: it REPORTS the
    proposal number + the exact approve command and RESUMES (no interactive
    prompt). Scenario @1d08c456af08d577 pins the report-and-resume contract;
    this test now asserts the gate is NOT a blocking read-prompt."""
    body = _provision()
    assert "HUMAN GATE" in body, "Claude-OAuth human gate banner must be preserved"
    assert "claude-oauth" in body.lower(), "human gate must reference Claude-OAuth"
    # the gate now instructs the operator to APPROVE the printed proposal.
    assert "vault proposal approve" in body, (
        "human gate must instruct the operator to approve the printed proposal"
    )
    # The gate must NOT block on an interactive read-prompt — provision is
    # lead-driveable (reports the handoff and resumes), per @1d08c456af08d577.
    assert not re.search(r"\bread\b[^\n]*\s-[a-zA-Z]*[ps]", body), (
        "the blocking interactive read-prompt is retired — provision must "
        "report the proposal handoff and resume (lead-driveable, no interactive "
        "wait)"
    )


# -----------------------------------------------------------------------
# DEFECT 2 — sh-compatible compose healthcheck
# -----------------------------------------------------------------------


def test_compose_agent_vault_healthcheck_is_sh_compatible():
    body = _compose()
    assert "/dev/tcp" not in body, (
        "compose healthcheck must not use the bash-only /dev/tcp redirect"
    )
    # an sh-shipped probe: nc or wget
    assert ("nc" in body and "14321" in body) or "wget" in body, (
        "compose agent-vault healthcheck must use an sh-compatible nc/wget probe"
    )


def _agent_vault_named_volume_mount(slug: str):
    """Return the agent-vault service's named-volume mount dict (the entry whose
    source is the ``<slug>-agent-vault-data`` named volume) from the rendered,
    parsed compose document."""
    doc = yaml.safe_load(_compose(slug))
    svc = doc["services"]["agent-vault"]
    named_source = f"{slug}-agent-vault-data"
    for mount in svc["volumes"]:
        if isinstance(mount, dict) and mount.get("source") == named_source:
            return mount
    raise AssertionError(
        f"agent-vault service has no named-volume mount with source "
        f"{named_source!r}; volumes={svc.get('volumes')!r}"
    )


def test_compose_agent_vault_named_volume_mounts_at_data():
    """P0 credential-loss regression (lead-kznj): the agent-vault named volume
    must mount at target ``/data`` — the infisical/agent-vault:latest declared
    storage path (VOLUME /data, HOME=/data, CA at /data/agent-vault-ca.pem).

    The 0.16.0 naming refactor regressed the target to ``/vault/file``, an
    unused path, so the broker wrote its real vault to the unmounted image
    default ``/data`` — an ephemeral anonymous volume destroyed on
    recreate/restart, losing all provisioned credentials."""
    mount = _agent_vault_named_volume_mount("dummyco")
    assert mount["target"] == "/data", (
        "agent-vault named volume must mount at /data (the image storage path); "
        f"got target {mount.get('target')!r}"
    )
    assert mount["target"] != "/vault/file", (
        "target /vault/file is the regressed, unmounted path — the persistent "
        "vault is lost on recreate when the named volume is not at /data"
    )


def test_compose_agent_vault_named_volume_source_and_type_intact():
    """Scenario 170 (@scenario_hash:8fcf898fdeebc6be) pins the volume NAME
    ({{OPS_SLUG}}-agent-vault-data) and the long-form ``type: volume`` entry —
    the target correction must leave both untouched."""
    mount = _agent_vault_named_volume_mount("dummyco")
    assert mount["type"] == "volume", "long-form `type: volume` entry must be preserved"
    assert mount["source"] == "dummyco-agent-vault-data", (
        "named-volume source ({{OPS_SLUG}}-agent-vault-data) must be unchanged "
        "(scenario 170 pins the volume name)"
    )


def test_compose_postgres_healthcheck_targets_configured_user():
    # lead-sgxd 87acbbbe: the healthcheck targets the CONFIGURED POSTGRES_USER
    # (the slug), not the literal "postgres" role (which does not exist and logs
    # 'role "postgres" does not exist' every interval).
    body = _compose("shopsystem")
    assert "pg_isready -U shopsystem" in body, (
        "postgres healthcheck must target the configured POSTGRES_USER (the slug)"
    )
    assert "pg_isready -U postgres" not in body, (
        "postgres healthcheck must not probe the nonexistent literal 'postgres' role"
    )


# -----------------------------------------------------------------------
# Slug-clean — a non-shopsystem slug render carries no shopsystem/dstengle
# -----------------------------------------------------------------------


def test_dummyco_provision_and_compose_are_slug_clean():
    for name in ("agent-vault-provision", "compose.yaml"):
        body = render_ops_template(name, "dummyco")
        low = body.lower()
        assert "shopsystem" not in low, (
            f"dummyco render of {name} leaked a shopsystem literal"
        )
        assert "dstengle" not in low, (
            f"dummyco render of {name} leaked a dstengle literal"
        )
    # and the fleet token is dummyco-scoped
    prov = render_ops_template("agent-vault-provision", "dummyco")
    assert "dummyco-fleet" in prov, (
        "dummyco provision must mint a dummyco-fleet agent (slug-derived)"
    )
