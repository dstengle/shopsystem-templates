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
    target.mkdir()
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
    for name in ("compose.yaml", "shop-shell", "Dockerfile.shopsystem-shell"):
        body = render_ops_template(name, "dummyco")
        assert "{{" not in body, f"{name} has unrendered placeholder: {body!r}"
        assert "}}" not in body, f"{name} has unrendered placeholder: {body!r}"


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
    # errors out with NO host-cred fallback: no host ~/.claude or ~/.gitconfig mounts
    assert "/.claude" not in body, "shop-shell must not mount host ~/.claude"
    assert ".gitconfig" not in body, "shop-shell must not mount host ~/.gitconfig"


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
