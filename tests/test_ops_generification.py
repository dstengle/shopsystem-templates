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


def _bootstrap(tmp_path: Path, shop_name: str) -> Path:
    """Run a real `shop-templates bootstrap --shop-type lead` into a fresh
    git repo under tmp_path and return the target dir."""
    target = tmp_path / shop_name
    target.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = _SRC + os.pathsep + env.get("PYTHONPATH", "")
    env["BD_NON_INTERACTIVE"] = "1"
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
    for name in ("compose.yaml", "shop-shell", "Dockerfile.shopsystem-shell"):
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


def test_dummyco_shop_shell_is_slug_scoped_and_broker_wired(tmp_path):
    target = _bootstrap(tmp_path, "dummyco-product")
    body = (target / "bin" / "shop-shell").read_text()

    # data env + network derive from slug
    assert "DUMMYCO_DATA" in body
    assert "--network dummyco" in body
    # no residual shopsystem literal
    assert "shopsystem" not in body, (
        f"dummyco shop-shell leaked a shopsystem literal:\n{body}"
    )
    # broker-wiring present
    for needle in (
        "AGENT_VAULT_ADDR",
        "AGENT_VAULT_TOKEN",
        "AGENT_VAULT_CA_PEM",
        "HTTPS_PROXY",
        "agent-vault:14322",
        "GIT_AUTHOR_NAME",
        "GIT_COMMITTER_NAME",
        "agent-vault-check",
    ):
        assert needle in body, f"shop-shell missing broker-wiring needle {needle!r}"
    # errors out with NO host-cred fallback: no host ~/.claude or ~/.gitconfig
    # MOUNTS (`-v ...:...`). Doc-comment mentions of the policy are fine; an
    # actual bind mount of either host path is forbidden (ADR-028).
    import re as _re

    mount_lines = _re.findall(r"-v\s+\S+", body)
    for ml in mount_lines:
        assert ".claude" not in ml, f"shop-shell must not mount host ~/.claude: {ml}"
        assert ".gitconfig" not in ml, (
            f"shop-shell must not mount host ~/.gitconfig: {ml}"
        )
    # error-out path present (no host-cred fallback)
    assert "Aborting" in body or "exit 1" in body


def test_dummyco_dockerfile_keeps_from_user_cli(tmp_path):
    target = _bootstrap(tmp_path, "dummyco-product")
    # Dockerfile filename may be product-scoped or stay shopsystem-shell;
    # accept either, assert the pinned recipe invariants.
    candidates = list(target.glob("Dockerfile.*-shell"))
    assert candidates, "expected a Dockerfile.<slug>-shell recipe"
    body = candidates[0].read_text()
    assert "FROM ghcr.io/dstengle/devcontainer-python-node-claude:latest" in body
    assert any(
        ln.lstrip().startswith("USER") and ln.split()[1] not in ("root", "0")
        for ln in body.splitlines()
    ), "Dockerfile must keep a non-root USER"
    assert any(
        cli in body for cli in ("shop-msg", "scenarios", "shop-templates")
    ), "Dockerfile must install a framework CLI"


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
    assert "pg_isready -U postgres" in test[1]
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
    # 134: shop-shell executable bash wrapper + docker compose up + docker run + --user vscode
    assert shell.splitlines()[0] == "#!/usr/bin/env bash"
    assert os.access(target / "bin" / "shop-shell", os.X_OK)
    assert "docker compose" in shell and "up -d postgres" in shell
    assert "docker run" in shell
    assert "--user vscode" in shell
    assert "--user $(id -u):$(id -g)" not in shell


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
    # the Claude-OAuth dashboard paste is preserved as the one HUMAN GATE:
    # the script STOPs for the dashboard step (does not automate it).
    low = body.lower()
    assert "dashboard" in low, "provision must reference the OAuth dashboard step"
    assert ("oauth" in low) or ("claude" in low), (
        "provision must reference the Claude-OAuth credential paste"
    )
    # an explicit human-gated halt for the dashboard step
    assert any(tok in body for tok in ("read -r", "read -p", 'read ')), (
        "provision must STOP/await for the human dashboard paste"
    )


def test_agent_vault_provision_credential_keys_are_screaming_snake(tmp_path):
    # lead-l95x: agent-vault 0.32.0 `vault credential set` REJECTS kebab-case
    # credential KEY names — they must be SCREAMING_SNAKE_CASE. The rendered
    # provision script must therefore store + reference GITHUB_PAT_USER /
    # GITHUB_PAT as credential keys, with NO kebab `github-pat` key surviving
    # in the credential-set args, the --*-key refs, or comments quoting them.
    body = render_ops_template("agent-vault-provision", "dummyco")

    # the credential KEY names stored via `vault credential set` are
    # SCREAMING_SNAKE_CASE (key=value form, value still ${GITHUB_PAT...}).
    assert "GITHUB_PAT_USER=${GITHUB_PAT_USER}" in body, (
        "provision must store the username under the SCREAMING_SNAKE key "
        "GITHUB_PAT_USER"
    )
    assert "GITHUB_PAT=${GITHUB_PAT}" in body, (
        "provision must store the PAT under the SCREAMING_SNAKE key GITHUB_PAT"
    )
    # the service-add step references the SCREAMING_SNAKE keys.
    assert "--username-key GITHUB_PAT_USER" in body, (
        "service add must reference --username-key GITHUB_PAT_USER"
    )
    assert "--password-key GITHUB_PAT" in body, (
        "service add must reference --password-key GITHUB_PAT"
    )
    # NO kebab credential key remains ANYWHERE (args, --*-key refs, comments).
    assert "github-pat" not in body, (
        f"provision leaked a kebab-case credential key 'github-pat':\n{body}"
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
