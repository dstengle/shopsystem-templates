"""Slug-parametric ops scaffolding tests (lead-faua / WS-2).

These pin the product-scoped generification of the lead-shop ops
scaffolding (compose.yaml, bin/shop-shell, Dockerfile) plus the folded-in
proven instance improvements (pg_isready healthcheck, POSTGRES_PASSWORD
default, agent-vault service, broker-wired shop-shell).

Every `shopsystem-*` literal in the rendered ops/ derives from the
bootstrap product slug via the SAME substitution mechanism the rest of
bootstrap uses. The product slug is the `--shop-name` with a trailing
`-product` stripped: `dummyco-product` -> `dummyco`,
`shopsystem-product` -> `shopsystem`.

Acceptance is verified two ways:
  - a real `dummyco-product` bootstrap yields dummyco-scoped ops with ZERO
    residual `shopsystem-*` literals;
  - a real `shopsystem-product` bootstrap still yields working
    shopsystem-scoped ops (additive — the pre-existing fleet keeps
    working), preserving the lead-held invariants.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from shop_templates.cli import (
    _ops_slug,
    render_ops_template,
)

_SRC = str(Path(__file__).resolve().parent.parent / "src")


def _yaml_load(text: str):
    """Parse YAML, preferring an in-process import, falling back to a
    yaml-capable interpreter round-tripped through JSON (the conftest
    pattern; the test venv may lack PyYAML)."""
    try:  # pragma: no cover - environment dependent
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ModuleNotFoundError:
        pass
    import json
    import shutil

    helper = (
        "import sys, json, yaml\n"
        "json.dump(yaml.safe_load(sys.stdin.read()), sys.stdout)\n"
    )
    for interp in (sys.executable, shutil.which("python3"), shutil.which("python")):
        if not interp:
            continue
        proc = subprocess.run(
            [interp, "-c", helper], input=text, capture_output=True, text=True
        )
        if proc.returncode == 0:
            return json.loads(proc.stdout)
    raise AssertionError("no yaml-capable interpreter available")


def _make_bd_shim(shim_dir: Path) -> None:
    """Write a hermetic `bd` shim into shim_dir that satisfies bootstrap's
    bd subprocess contract WITHOUT touching the network.

    These ops tests assert only on the rendered ops scaffolding (compose.yaml,
    bin/shop-shell, Dockerfile); they do not exercise bd's real Dolt push. The
    bootstrap flow, however, now runs a genuine `bd dolt push` smoke-test
    (scenario 5ae67969a7f205d5, supersedes 62eb2a8b9b617f4b) that configures a
    Dolt remote and pushes to it — real network I/O that would otherwise reach
    github.com/dstengle/*-beads and make these tests non-hermetic (and flaky on
    429 / diverged history). The shim models the real bd dolt contract well
    enough for bootstrap: `bd init` creates .beads/, `bd dolt remote add <name>
    <url>` persists the remote, `bd dolt remote list` reports it (so the
    smoke-test's missing-remote guard sees the configured remote), and a bare
    `bd dolt push` exits 0. It rejects the non-existent
    `bd dolt push <positional-url>` shape so a regression to the old buggy call
    would still surface here.
    """
    shim_dir.mkdir(parents=True, exist_ok=True)
    bd_path = shim_dir / "bd"
    bd_path.write_text(
        "#!/usr/bin/env bash\n"
        'remote_state="$PWD/.beads/.shim_remotes"\n'
        'if [[ "$1" == "init" ]]; then\n'
        '  mkdir -p .beads\n'
        '  : > .beads/.shim_init\n'
        '  exit 0\n'
        'fi\n'
        'if [[ "$1" == "dolt" && "$2" == "remote" && "$3" == "list" ]]; then\n'
        '  [[ -s "$remote_state" ]] && cat "$remote_state"\n'
        '  exit 0\n'
        'fi\n'
        'if [[ "$1" == "dolt" && "$2" == "remote" && "$3" == "add" ]]; then\n'
        '  [[ -n "$4" && -n "$5" ]] || { echo "remote add needs <name> <url>" >&2; exit 2; }\n'
        '  mkdir -p .beads\n'
        '  echo "$4 $5" >> "$remote_state"\n'
        '  exit 0\n'
        'fi\n'
        'if [[ "$1" == "dolt" && "$2" == "push" ]]; then\n'
        '  shift 2\n'
        '  while [[ $# -gt 0 ]]; do\n'
        '    case "$1" in\n'
        '      --remote) shift 2 ;;\n'
        '      --remote=*) shift ;;\n'
        '      -*) shift ;;\n'
        '      *) echo "bd dolt push takes no positional argument: $1" >&2; exit 2 ;;\n'
        '    esac\n'
        '  done\n'
        '  exit 0\n'
        'fi\n'
        "exit 0\n"
    )
    bd_path.chmod(0o755)


def _bootstrap(tmp_path: Path, shop_name: str) -> Path:
    """Run a `shop-templates bootstrap --shop-type lead` into a fresh git repo
    under tmp_path and return the target dir. A hermetic `bd` shim is placed
    ahead of the real `bd` on PATH so bootstrap's `bd dolt push` smoke-test
    does no network I/O (these tests assert on rendered files, not on push)."""
    target = tmp_path / shop_name
    target.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    shim_dir = tmp_path / "_bd_shim"
    _make_bd_shim(shim_dir)
    env = dict(os.environ)
    env["PYTHONPATH"] = _SRC + os.pathsep + env.get("PYTHONPATH", "")
    env["BD_NON_INTERACTIVE"] = "1"
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "shop_templates",
            "bootstrap",
            "--shop-type",
            "lead",
            "--shop-name",
            shop_name,
            "--target",
            str(target),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, (
        f"bootstrap failed for {shop_name}: rc={proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    return target


# -----------------------------------------------------------------------
# Slug derivation
# -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "shop_name,expected",
    [
        ("dummyco-product", "dummyco"),
        ("shopsystem-product", "shopsystem"),
        ("acme", "acme"),
        ("dummyco-product-product", "dummyco-product"),
    ],
)
def test_ops_slug_strips_product_suffix(shop_name, expected):
    assert _ops_slug(shop_name) == expected


# -----------------------------------------------------------------------
# render_ops_template substitutes the slug (no raw placeholder leaks)
# -----------------------------------------------------------------------


def test_render_ops_template_leaves_no_unrendered_placeholder():
    # Only the {{OPS_*}} ops placeholders must be fully substituted; docker
    # Go-template format strings ({{.Names}} etc.) are legitimately retained.
    for name in ("compose.yaml", "shop-shell"):
        body = render_ops_template(name, "dummyco")
        assert "{{OPS_" not in body, (
            f"{name} has an unrendered ops placeholder: {body!r}"
        )


# -----------------------------------------------------------------------
# (1) Product-scoped generification — dummyco
# -----------------------------------------------------------------------


def test_dummyco_compose_is_fully_slug_scoped(tmp_path):
    target = _bootstrap(tmp_path, "dummyco-product")
    text = (target / "compose.yaml").read_text()
    data = _yaml_load(text)

    services = data["services"]
    # container names slug-scoped
    assert services["postgres"]["container_name"] == "dummyco-postgres"
    assert "agent-vault" in services, "agent-vault service must be present"
    assert services["agent-vault"]["container_name"] == "dummyco-agent-vault"

    # network slug-scoped
    assert "dummyco" in data["networks"]
    assert data["networks"]["dummyco"]["name"] == "dummyco"

    # named volume slug-scoped
    assert "dummyco-agent-vault-data" in (data.get("volumes") or {})

    # ZERO residual shopsystem-* literals anywhere in rendered compose
    assert "shopsystem" not in text, (
        f"dummyco compose.yaml leaked a shopsystem literal:\n{text}"
    )


def test_dummyco_compose_host_ports_are_product_distinct(tmp_path):
    """A 2nd product must not collide on host ports with a running
    shopsystem fleet: the published host port derives from the slug (and is
    env-overridable)."""
    dummy = _bootstrap(tmp_path / "a", "dummyco-product")
    shop = _bootstrap(tmp_path / "b", "shopsystem-product")
    d = _yaml_load((dummy / "compose.yaml").read_text())
    s = _yaml_load((shop / "compose.yaml").read_text())

    def _host_port(parsed):
        ports = parsed["services"]["postgres"]["ports"]
        # short form "<host>:5432" — extract the host side (may carry an
        # env-override default like "${X:-5544}").
        spec = str(ports[0])
        return spec.rsplit(":", 1)[0]

    assert _host_port(d) != _host_port(s), (
        "dummyco and shopsystem must publish distinct host ports"
    )
    # env-overridable
    assert "POSTGRES_PORT" in (dummy / "compose.yaml").read_text()


def test_dummyco_shop_shell_is_slug_scoped_thin_wrapper(tmp_path):
    """175 + 172/134 (lead-ss6k): the dummyco thin wrapper is slug-scoped
    (DUMMYCO_DATA, --network dummyco) and delegates the brokered launch to
    bc-container in an ephemeral product-neutral bc-lead launcher (which stands
    up the leaf-BC ALSO on bc-lead, since the leaf needs the docker CLI too) —
    the ONLY `shopsystem` literal permitted is the framework image ref
    shopsystem-bc-lead (launcher AND leaf-BC runtime); all other tokens are
    slug-parametric, and the wrapper constructs no proxy URL, fetches no CA, and
    mounts no host credentials."""
    target = _bootstrap(tmp_path, "dummyco-product")
    body = (target / "bin" / "shop-shell").read_text()

    # ADR-043 single-source (lead-ml51): the data root and docker network are
    # referenced from the ops-coordinates artifact ($OPS_DATA_ROOT / $OPS_NETWORK),
    # not re-spelled as slug literals in the wrapper.
    assert "$OPS_DATA_ROOT" in body
    assert "$OPS_NETWORK" in body
    assert "$HOME/.local/share/" not in body

    # ADR-046 (lead-ml51): the framework image is no longer a baked product
    # literal — the wrapper references the single-sourced $OPS_FRAMEWORK_IMAGE and
    # carries no ghcr.io/dstengle/shopsystem-bc-lead literal. (The full
    # zero-shopsystem byte contract is pinned by scenario 827dec9656d97a38.)
    assert "$OPS_FRAMEWORK_IMAGE" in body, (
        "thin wrapper must reference the single-sourced $OPS_FRAMEWORK_IMAGE"
    )
    assert "ghcr.io/dstengle/shopsystem-bc-lead" not in body, (
        "thin wrapper must NOT bake the framework image as a product literal"
    )
    assert "shopsystem-bc-base" not in body, (
        "thin wrapper must NOT carry shopsystem-bc-base"
    )
    assert "fleet" not in body.lower(), f"dummyco shop-shell leaked a fleet literal:\n{body}"

    # Thin-wrapper delegation present: env-file, ephemeral bc-base run, the
    # bc-container launch flags, and attach.
    for needle in (
        "--env-file",
        "docker run --rm",
        "-it",
        "/var/run/docker.sock:/var/run/docker.sock",
        "bc-container launch",
        "--workspace-mount",
        "--mount-docker-socket",
        "--startup-prompt",
        "bc-container attach",
    ):
        assert needle in body, f"thin wrapper missing delegation needle {needle!r}"

    # Delegated concerns are NOT re-derived in the wrapper (172/134 forbidden).
    for forbidden in (
        "14322",
        "HTTPS_PROXY",
        "agent-vault ca fetch",
        "agent-vault-check",
        "SHOPSYSTEM_SHELL_IMAGE",
        "DUMMYCO_SHELL_IMAGE",
        "docker build",
    ):
        assert forbidden not in body, (
            f"thin wrapper must NOT re-derive delegated concern {forbidden!r}"
        )

    # NO host credential or config dotfiles are mounted (ADR-028).
    for hostcred in ("$HOME/.claude", "$HOME/.gitconfig", "~/.claude", "~/.gitconfig"):
        assert hostcred not in body, (
            f"thin wrapper must not mount host credential {hostcred!r}"
        )


# NOTE (PDR-020 slice 2): the dedicated shell-image Dockerfile tests
# (lead-2ra5 ARG SHELL_BASE_IMAGE recipe / lead-hguw brokered-runnable
# claude+CA image / lead-30fs git+https VCS-pinned CLI installs) were REMOVED
# here. The shell image and its Dockerfile.<slug>-shell are retired —
# bin/shop-shell now delegates the brokered launch to bc-container in an
# ephemeral product-neutral bc-base, so there is no shell Dockerfile to pin.
# The converged thin-wrapper shape is pinned by
# tests/test_ops_converged_shop_shell.py (172/134/174/175/137).


# -----------------------------------------------------------------------
# (2) Folded-in proven improvements (slug-scoped)
# -----------------------------------------------------------------------


def test_compose_has_pg_isready_healthcheck_and_password_default(tmp_path):
    target = _bootstrap(tmp_path, "dummyco-product")
    data = _yaml_load((target / "compose.yaml").read_text())
    pg = data["services"]["postgres"]

    hc = pg["healthcheck"]
    test = hc["test"]
    assert test[0] == "CMD-SHELL"
    # lead-sgxd 87acbbbe: the healthcheck targets the configured POSTGRES_USER
    # (the slug "dummyco"), not the nonexistent literal "postgres" role.
    assert "pg_isready -U dummyco" in test[1]
    assert "pg_isready -U postgres" not in test[1]
    assert hc["interval"] == "10s"
    assert hc["timeout"] == "5s"
    assert hc["retries"] == 5

    # env-overridable POSTGRES_PASSWORD default
    text = (target / "compose.yaml").read_text()
    assert "POSTGRES_PASSWORD" in text
    assert "${POSTGRES_PASSWORD:-" in text


def test_agent_vault_service_has_its_own_healthcheck_and_volume(tmp_path):
    target = _bootstrap(tmp_path, "dummyco-product")
    data = _yaml_load((target / "compose.yaml").read_text())
    av = data["services"]["agent-vault"]
    assert "healthcheck" in av, "agent-vault must have a healthcheck"
    # mounts the slug-scoped named volume
    vol_sources = []
    for v in av.get("volumes", []) or []:
        if isinstance(v, dict):
            vol_sources.append(v.get("source"))
        else:
            vol_sources.append(str(v).split(":", 1)[0])
    assert "dummyco-agent-vault-data" in vol_sources


# -----------------------------------------------------------------------
# shopsystem-product additive invariants (lead-held hashes preserved)
# -----------------------------------------------------------------------


def test_shopsystem_product_preserves_lead_held_invariants(tmp_path):
    target = _bootstrap(tmp_path, "shopsystem-product")
    compose = (target / "compose.yaml").read_text()
    shell = (target / "bin" / "shop-shell").read_text()
    data = _yaml_load(compose)

    # 133: postgres on the shopsystem network
    assert "shopsystem" in data["networks"]
    # 138: pgdata source derived from SHOPSYSTEM_DATA, env-overridable, never in repo
    pg = data["services"]["postgres"]
    src = None
    for v in pg["volumes"]:
        if isinstance(v, dict) and v.get("target") == "/var/lib/postgresql/data":
            src = v.get("source")
        elif isinstance(v, str) and "/var/lib/postgresql/data" in v:
            src = v.rsplit(":", 1)[0] if v.count(":") >= 2 else v.split(":")[0]
    assert src is not None and "SHOPSYSTEM_DATA" in src
    assert ".local/share/shopsystem" in src
    assert str(target) not in src  # never resolves into the repo
    # 172/134 (lead-ss6k): shop-shell is the executable thin bash wrapper that
    # brings up compose services and delegates the brokered launch to
    # bc-container in an ephemeral product-neutral bc-lead launcher, which
    # stands up the leaf-BC ALSO on bc-lead (no dedicated shell image).
    assert shell.splitlines()[0] == "#!/usr/bin/env bash"
    assert os.access(target / "bin" / "shop-shell", os.X_OK)
    assert "docker compose" in shell and "up -d postgres" in shell
    assert "docker run --rm" in shell
    # ADR-046 (lead-ml51): the framework image is the single-sourced
    # $OPS_FRAMEWORK_IMAGE reference, no longer a baked shopsystem-bc-lead literal.
    assert "$OPS_FRAMEWORK_IMAGE" in shell
    assert "ghcr.io/dstengle/shopsystem-bc-lead" not in shell
    assert "bc-container launch" in shell and "bc-container attach" in shell
    # the retired dedicated-shell-image knob is gone
    assert "SHOPSYSTEM_SHELL_IMAGE" not in shell


# -----------------------------------------------------------------------
# (WS-2 / lead-w87b) agent-vault-provision + agent-vault-check ops files
#
# These two scripts are AUTHORED FROM the behavioral spec (the instance
# copies live in the shopsystem-product lead host, outside this BC root and
# never read). They must be rendered into ops/ INCLUDING the slug-derived
# broker container/vault/network/proxy, with NO shopsystem-*/fleet literals
# in a dummyco render, the Claude-OAuth dashboard paste preserved as the one
# human gate, and the check non-fatal (exits 0 even on a soft warning).
# -----------------------------------------------------------------------


def _no_placeholder_leak(name):
    body = render_ops_template(name, "dummyco")
    assert "{{OPS_" not in body, f"{name} leaked an unrendered ops placeholder"


def test_render_ops_template_agent_vault_scripts_have_no_placeholder_leak():
    _no_placeholder_leak("agent-vault-provision")
    _no_placeholder_leak("agent-vault-check")


def test_dummyco_bootstrap_writes_executable_agent_vault_scripts(tmp_path):
    target = _bootstrap(tmp_path, "dummyco-product")
    for rel in ("bin/agent-vault-provision", "bin/agent-vault-check"):
        dest = target / rel
        assert dest.exists(), f"bootstrap must render {rel}"
        assert os.access(dest, os.X_OK), f"{rel} must be executable"
        assert dest.read_text().splitlines()[0] == "#!/usr/bin/env bash"


def test_dummyco_agent_vault_provision_is_slug_scoped_and_human_gated(tmp_path):
    target = _bootstrap(tmp_path, "dummyco-product")
    body = (target / "bin" / "agent-vault-provision").read_text()

    # broker container + vault + network derive from the dummyco slug, and
    # the broker container matches what compose names the agent-vault service.
    assert "dummyco-agent-vault" in body, (
        "provision must target the slug-derived broker container "
        "<slug>-agent-vault that compose defines"
    )
    # vault/broker coordinates are slug-derived, NOT a default-product literal.
    assert "dummyco" in body
    # lead-beym (ADR-026 D2): the provision script now mints the slug-derived
    # <slug>-fleet AGENT token (dummyco-fleet), so the bare token "fleet" is a
    # legitimate slug-scoped substring here. What must NOT leak is the
    # DEFAULT-PRODUCT broker literal `shopsystem-fleet` (the original guard's
    # real intent) — assert that specifically rather than banning "fleet"
    # wholesale, which would conflict with the mandated dummyco-fleet mint.
    assert "shopsystem-fleet" not in body, (
        f"provision leaked the default-product broker literal 'shopsystem-fleet':\n{body}"
    )
    assert "dummyco-fleet" in body, (
        "provision must mint the slug-derived <slug>-fleet agent (dummyco-fleet)"
    )
    # ZERO residual shopsystem literals (slug is dummyco, not shopsystem)
    assert "shopsystem" not in body, (
        f"dummyco provision leaked a shopsystem literal:\n{body}"
    )
    assert "shopsystem-agent-vault-1" not in body
    # the Claude-OAuth credential is the one HUMAN GATE (CORRECTED, lead-yrex):
    # provision now CREATES a pre-populated OAuth-typed proposal and STOPs for
    # the operator to APPROVE it (token paste at the approve URL) — replacing
    # the old manual dashboard-paste hand-create.
    low = body.lower()
    assert "vault proposal approve" in body, (
        "provision must instruct the operator to APPROVE the printed OAuth proposal"
    )
    assert ("oauth" in low) or ("claude" in low), (
        "provision must reference the Claude-OAuth credential approval"
    )
    # an explicit human-gated halt for the approval step
    assert any(tok in body for tok in ("read -r", "read -p", 'read ')), (
        "provision must STOP/await for the operator to approve the OAuth proposal"
    )


def test_agent_vault_provision_credential_keys_are_screaming_snake(tmp_path):
    # lead-l95x established the SCREAMING_SNAKE invariant (agent-vault 0.32.0
    # `vault credential set` REJECTS kebab-case credential KEY names). lead-8jar
    # CORRECTS the key NAMES to the live vault's authoritative keys
    # (GITHUB_USERNAME / GITHUB_TOKEN) — still SCREAMING_SNAKE, no kebab. The
    # test's intent (no kebab credential keys) is preserved with corrected names.
    body = render_ops_template("agent-vault-provision", "dummyco")

    # the credential KEY names stored via `vault credential set` are
    # SCREAMING_SNAKE_CASE (key=value form).
    assert "GITHUB_USERNAME=${GITHUB_USERNAME}" in body, (
        "provision must store the username under the SCREAMING_SNAKE key "
        "GITHUB_USERNAME"
    )
    assert "GITHUB_TOKEN=${GITHUB_TOKEN}" in body, (
        "provision must store the token under the SCREAMING_SNAKE key GITHUB_TOKEN"
    )
    # the service-add step references the SCREAMING_SNAKE keys.
    assert "--username-key GITHUB_USERNAME" in body, (
        "service add must reference --username-key GITHUB_USERNAME"
    )
    assert "--password-key GITHUB_TOKEN" in body, (
        "service add must reference --password-key GITHUB_TOKEN"
    )
    # NO kebab credential key remains ANYWHERE (args, --*-key refs, comments).
    assert "github-pat" not in body, (
        f"provision leaked a kebab-case credential key 'github-pat':\n{body}"
    )


def test_provision_registers_all_five_live_fleet_services(tmp_path):
    # lead-8jar (WS-2 / dummyco spike iter-6): the rendered provision script
    # registered only ONE service (github basic) -> a fresh BC's Claude calls
    # 401 because no claude-api service attaches the OAuth bearer. The live
    # `fleet` vault carries FIVE services; the rendered script must mirror them
    # (slug-clean, vault selector is $VAULT not the literal "fleet").
    body = render_ops_template("agent-vault-provision", "dummyco")

    # 1. github-git — the PRESERVED existing clone/git service (basic).
    assert "--name github-git" in body, (
        "the existing github clone/git service must be preserved as github-git"
    )
    assert "--host github.com" in body
    assert "--auth-type basic" in body
    assert "--username-key GITHUB_USERNAME" in body
    assert "--password-key GITHUB_TOKEN" in body

    # 2. github-api — bearer GITHUB_TOKEN against api.github.com.
    assert "--name github-api" in body, "must add github-api service"
    assert "--host api.github.com" in body
    assert "--token-key GITHUB_TOKEN" in body

    # 3/4/5. the three claude-* bearer services keyed on CLAUDE_OAUTH.
    assert "--name claude-api" in body, "must add claude-api service"
    assert "--host api.anthropic.com" in body
    assert "--name claude-platform" in body, "must add claude-platform service"
    assert "--host platform.claude.com" in body
    assert "--name claude-mcp-proxy" in body, "must add claude-mcp-proxy service"
    assert "--host mcp-proxy.anthropic.com" in body
    assert "--token-key CLAUDE_OAUTH" in body, (
        "claude-* services must bearer-attach the CLAUDE_OAUTH credential"
    )

    # slug-clean: the rendered vault selector is $VAULT, never the literal
    # live-fleet vault name "fleet" hard-coded into a service-add.
    assert "--vault fleet" not in body, (
        "rendered provision must use the slug-derived $VAULT, not literal 'fleet'"
    )


def test_provision_github_credential_keys_are_authoritative(tmp_path):
    # lead-8jar: the live vault's AUTHORITATIVE github credential KEYS are
    # GITHUB_USERNAME / GITHUB_TOKEN (corrects the prior GITHUB_PAT_USER /
    # GITHUB_PAT phrasing). They remain SCREAMING_SNAKE; the prior PAT keys
    # must NOT survive anywhere (credential set, --*-key refs, shell vars).
    body = render_ops_template("agent-vault-provision", "dummyco")
    assert "GITHUB_USERNAME=${GITHUB_USERNAME}" in body, (
        "credential set must store the username under GITHUB_USERNAME"
    )
    assert "GITHUB_TOKEN=${GITHUB_TOKEN}" in body, (
        "credential set must store the token under GITHUB_TOKEN"
    )
    assert "GITHUB_PAT" not in body, (
        f"provision must not carry the stale GITHUB_PAT* keys:\n{body}"
    )


def test_provision_human_gate_actionable_name_is_screaming_snake(tmp_path):
    # FOLD-IN lead-eqzi (P1): agent-vault enforces SCREAMING_SNAKE credential
    # KEYS. The human-gate's ACTIONABLE credential name the operator is told to
    # create must be CLAUDE_OAUTH (not kebab claude-oauth). Prose descriptions
    # ("Claude-OAuth") are fine; the actionable kebab key must be gone.
    body = render_ops_template("agent-vault-provision", "dummyco")
    assert "CLAUDE_OAUTH" in body, (
        "human-gate must instruct creating the CLAUDE_OAUTH credential"
    )
    assert "claude-oauth" not in body, (
        f"human-gate must not name a kebab 'claude-oauth' credential:\n{body}"
    )


def test_provision_env_writeback_includes_vault_and_ca_pem(tmp_path):
    # FOLD-IN lead-71tq (P2): the provision .env writeback must add the launch
    # vault selector AGENT_VAULT_VAULT and the broker CA AGENT_VAULT_CA_PEM
    # (fetched via `agent-vault ca fetch`) so a plain launch from .env trusts
    # the MITM proxy.
    body = render_ops_template("agent-vault-provision", "dummyco")
    assert "AGENT_VAULT_VAULT=" in body, (
        ".env writeback must set AGENT_VAULT_VAULT (launch vault selector)"
    )
    assert "AGENT_VAULT_CA_PEM=" in body, (
        ".env writeback must set AGENT_VAULT_CA_PEM (broker CA)"
    )
    assert "ca fetch" in body, (
        "provision must fetch the broker CA via `agent-vault ca fetch`"
    )


def test_dummyco_agent_vault_check_is_slug_scoped_and_non_fatal(tmp_path):
    target = _bootstrap(tmp_path, "dummyco-product")
    body = (target / "bin" / "agent-vault-check").read_text()

    # broker container / network / proxy derive from the dummyco slug
    assert "dummyco-agent-vault" in body, (
        "check must probe the slug-derived broker container"
    )
    assert "shopsystem" not in body, (
        f"dummyco check leaked a shopsystem literal:\n{body}"
    )
    assert "fleet" not in body
    # 30-day GitHub-PAT expiry advisory
    low = body.lower()
    assert "30" in body, "check must reference the 30-day expiry window"
    assert "github" in low or "pat" in low, (
        "check must reference the GitHub PAT it advises on"
    )
    # NON-FATAL: must exit 0 even on a soft warning. A `set -e` that aborts
    # the calling shell on a warning is forbidden — assert the script either
    # avoids `set -e` or, if present, is explicitly non-fatal (exit 0).
    assert "exit 1" not in body, (
        "check must be non-fatal — it must not exit non-zero on a soft warning"
    )
    assert "exit 0" in body, "check must explicitly exit 0 (non-fatal advisory)"


def test_shopsystem_bootstrap_renders_working_agent_vault_scripts(tmp_path):
    # additive: the shopsystem-product slug still gets working, slug-scoped
    # provision/check (shopsystem IS the slug here, so the literal is legit).
    target = _bootstrap(tmp_path, "shopsystem-product")
    for rel in ("bin/agent-vault-provision", "bin/agent-vault-check"):
        dest = target / rel
        assert dest.exists(), f"shopsystem bootstrap must render {rel}"
        assert os.access(dest, os.X_OK)
    provision = (target / "bin" / "agent-vault-provision").read_text()
    assert "shopsystem-agent-vault" in provision, (
        "shopsystem provision must target the shopsystem broker container"
    )
