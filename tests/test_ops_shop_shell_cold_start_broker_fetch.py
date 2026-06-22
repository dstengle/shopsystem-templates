"""shop-shell COLD-START broker-fetch of the agent-vault MITM CA (lead-4him —
tightening of existing-but-unpinned bin/shop-shell CA-sourcing, pinning
lead-held scenario 192 @scenario_hash:513cf8ea1a8ff4e9, mirrored BC-locally in
features/bootstrap_shop_shell_cold_start_broker_fetch.feature).

The tightening (additive to scenario 183 @scenario_hash:2adc62a25c401e4b, which
only PERMITS broker-fetch and ALLOWS fail-loud): on a fully-cold start — the
agent-vault broker container running but ZERO BC containers present — the
rendered bin/shop-shell must OBTAIN the CA FROM THE BROKER via the literal
`agent-vault ca fetch` executed against the agent-vault container, independent
of any BC donor container. The prior fix (lead-7gvm) recovers the CA from a
running BC container via `docker inspect`; on a cold start there is no donor, so
that warm path yields fail-loud rather than a working shell. Scenario 192
requires the cold-start broker-fetch to SUCCEED.

Properties asserted here:
- BEHAVIORAL: executing the rendered CA-sourcing region under `set -euo
  pipefail` with the agent-vault container reachable and NO BC donor present
  fills AGENT_VAULT_CA_PEM with the multi-line PEM the broker emits, INTACT
  (not truncated to a single line), and the region succeeds (does not fail
  loud) — a cold-start operator reaches the launch with a non-empty CA and no
  donor BC.
- BROKER FETCH NOT GATED ON TOKEN: the `agent-vault ca fetch` path is reachable
  when only the broker ADDRESS is known.
- ORDER: the broker fetch is attempted before / independently of donor-BC
  recovery (`docker inspect`), which is demoted to a lower-priority fallback.
- ARTIFACT SURFACE (the scenario's literal-substring legs): the rendered body
  carries `agent-vault ca fetch` and references AGENT_VAULT_CA_PEM on the
  `docker run` invocation.
"""
import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

from shop_templates.cli import render_ops_template

_SLUG = "dummyco"


def _shop_shell_body(slug: str = _SLUG) -> str:
    return render_ops_template("shop-shell", slug)


def _ca_sourcing_region(body: str) -> str:
    """Return the credential + CA-sourcing region of the rendered shop-shell:
    from the line that initializes AGENT_VAULT_ADDR through the CA fail-loud
    guard's `exit 1` (the last line before HTTPS_PROXY wiring).

    Executing this region lets us prove the cold-start broker-fetch fills the
    CA without reaching `exec docker run`.
    """
    lines = body.splitlines()
    start = next(
        i for i, ln in enumerate(lines)
        if ln.strip().startswith("AGENT_VAULT_ADDR=")
    )
    # The region ends at the CA fail-loud guard's closing `fi` — the last line
    # of the CA-acquisition block before the HTTPS_PROXY wiring. We anchor on
    # the HTTPS_PROXY assignment that follows and take everything up to it.
    end = next(
        i for i, ln in enumerate(lines)
        if i > start and ln.strip().startswith("HTTPS_PROXY=")
    )
    return "\n".join(lines[start:end])


_MULTILINE_CA = (
    "-----BEGIN CERTIFICATE-----\n"
    "LINE1ofCAmaterialAAAA\n"
    "LINE2ofCAmaterialBBBB\n"
    "LINE3ofCAmaterialCCCC\n"
    "-----END CERTIFICATE-----"
)


def _run_cold_start(tmp_path: Path, *, env_token: str = "env-token-xyz"):
    """Execute the CA-sourcing region on a COLD start.

    Stubs:
    - `docker ps` lists ONLY the agent-vault container — NO bc-* donor.
    - `docker exec <agent-vault> agent-vault ca fetch` emits the multi-line CA.
    - `docker inspect` emits nothing (there is no donor to inspect).

    The simulated `.env` supplies the broker TOKEN + ADDR (broker address
    known) but NOT the CA. The region must broker-fetch the CA, capture it
    intact, and succeed.
    """
    region = _ca_sourcing_region(_shop_shell_body())

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # docker stub: cold start — agent-vault present, zero bc-* containers.
    # `docker exec ... agent-vault ca fetch` emits the multi-line PEM.
    # `docker inspect` (donor recovery) finds nothing.
    docker_stub = bin_dir / "docker"
    docker_stub.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            if [[ "$1" == "compose" ]]; then exit 0; fi
            if [[ "$1" == "ps" ]]; then
              # Cold start: only the agent-vault broker is up, NO bc-* donor.
              echo "{_SLUG}-postgres"
              echo "{_SLUG}-agent-vault"
              exit 0
            fi
            if [[ "$1" == "exec" ]]; then
              # docker exec ... agent-vault ca fetch -> emit the multi-line PEM.
              # The CA must be captured intact, so emit a genuine multi-line value.
              for a in "$@"; do
                if [[ "$a" == "fetch" ]]; then
                  printf '%s\\n' "{_MULTILINE_CA}"
                  exit 0
                fi
              done
              exit 0
            fi
            if [[ "$1" == "inspect" ]]; then
              # No donor container exists to inspect on a cold start.
              exit 0
            fi
            exit 0
            """
        )
    )
    docker_stub.chmod(0o755)

    # A bare `agent-vault` on PATH must NOT be the source — emit nothing, so
    # the only working CA source under test is the docker-exec broker fetch
    # against the agent-vault container.
    av_stub = bin_dir / "agent-vault"
    av_stub.write_text("#!/usr/bin/env bash\nexit 1\n")
    av_stub.chmod(0o755)

    # agent-vault-check is invoked late; stub it harmlessly (region stops
    # before it, but be safe).
    check_stub = bin_dir / "agent-vault-check"
    check_stub.write_text("#!/usr/bin/env bash\nexit 0\n")
    check_stub.chmod(0o755)

    script = (
        "set -euo pipefail\n"
        f'REPO_ROOT="{repo_root}"\n'
        f'AGENT_VAULT_TOKEN="{env_token}"\n'
        'AGENT_VAULT_ADDR="broker-addr:14322"\n'
        'AGENT_VAULT_CA_PEM=""\n'
        "export AGENT_VAULT_TOKEN AGENT_VAULT_ADDR AGENT_VAULT_CA_PEM\n"
        + region
        + "\n"
        'echo "__CA_BEGIN__"\n'
        'printf "%s\\n" "$AGENT_VAULT_CA_PEM"\n'
        'echo "__CA_END__"\n'
    )

    env = dict(os.environ)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    for k in ("AGENT_VAULT_VAULT",):
        env.pop(k, None)

    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, env=env
    )


def _extract_ca(out: str) -> str:
    lines = out.splitlines()
    try:
        b = lines.index("__CA_BEGIN__")
        e = lines.index("__CA_END__")
    except ValueError:
        return "<unparseable>"
    return "\n".join(lines[b + 1 : e])


def test_cold_start_broker_fetch_fills_multiline_ca_no_donor(tmp_path):
    """COLD start: agent-vault broker reachable, ZERO BC donor containers. The
    region must broker-fetch the CA via `agent-vault ca fetch` against the
    agent-vault container, capture the multi-line PEM intact, and succeed —
    reaching the launch with a non-empty CA and no donor BC."""
    proc = _run_cold_start(tmp_path)
    assert proc.returncode == 0, (
        "cold-start CA-sourcing must succeed via broker-fetch when the broker "
        "is reachable and no donor BC is present (it must NOT fail loud):\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    ca = _extract_ca(proc.stdout)
    assert ca == _MULTILINE_CA, (
        "the broker-fetched CA must be captured intact (multi-line, not "
        f"truncated to a single line). Got: {ca!r}"
    )
    # Multi-line intact: the captured CA must carry all of its lines.
    assert ca.count("\n") == _MULTILINE_CA.count("\n") == 4, (
        "the captured CA was truncated — multi-line PEM must survive intact. "
        f"Got {ca.count(chr(10)) + 1} line(s): {ca!r}"
    )


def test_broker_fetch_reachable_when_only_broker_address_is_known(tmp_path):
    """The broker fetch must NOT be gated on broker-token presence: the
    `agent-vault ca fetch` path is reachable when only the broker ADDRESS is
    known (no token). The CA must still be obtained from the broker.

    Executes only up to and including the broker-fetch line (stopping before
    the unrelated downstream token fail-loud guard, which on a no-token cold
    start would abort the region for a reason orthogonal to this property),
    then echoes the CA to prove the fetch filled it with no token present.
    """
    body = _shop_shell_body()
    lines = body.splitlines()
    start = next(
        i for i, ln in enumerate(lines)
        if ln.strip().startswith("AGENT_VAULT_ADDR=")
    )
    # Take everything through the closing `fi` of the broker-fetch `if` block
    # (the first `agent-vault ca fetch` and its enclosing guard), so the
    # captured assignment is syntactically complete.
    fetch = next(
        i for i, ln in enumerate(lines)
        if i >= start and "agent-vault ca fetch" in ln
    )
    fetch_fi = next(
        i for i, ln in enumerate(lines)
        if i > fetch and ln.strip() == "fi"
    )
    region = "\n".join(lines[start : fetch_fi + 1])

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    docker_stub = bin_dir / "docker"
    docker_stub.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            if [[ "$1" == "exec" ]]; then
              for a in "$@"; do
                if [[ "$a" == "fetch" ]]; then
                  printf '%s\\n' "{_MULTILINE_CA}"
                  exit 0
                fi
              done
              exit 0
            fi
            exit 0
            """
        )
    )
    docker_stub.chmod(0o755)

    script = (
        "set -euo pipefail\n"
        f'REPO_ROOT="{repo_root}"\n'
        # NO token, NO .env — only the broker ADDRESS is known.
        'AGENT_VAULT_TOKEN=""\n'
        'AGENT_VAULT_ADDR="broker-addr:14322"\n'
        'AGENT_VAULT_CA_PEM=""\n'
        "export AGENT_VAULT_TOKEN AGENT_VAULT_ADDR AGENT_VAULT_CA_PEM\n"
        + region
        + "\n"
        'echo "__CA_BEGIN__"\nprintf "%s\\n" "$AGENT_VAULT_CA_PEM"\n'
        'echo "__CA_END__"\n'
    )
    env = dict(os.environ)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env.pop("AGENT_VAULT_VAULT", None)
    proc = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, env=env
    )
    assert proc.returncode == 0, (
        f"broker fetch region must not abort with no token. "
        f"stderr={proc.stderr!r}"
    )
    ca = _extract_ca(proc.stdout)
    assert ca == _MULTILINE_CA, (
        "with only the broker ADDRESS known (no token), the broker-fetch of "
        "the CA must still be reachable and fill the CA. The fetch must not be "
        f"gated on token presence. Got CA={ca!r}\nstderr={proc.stderr!r}"
    )


# ---- Artifact-surface (literal-substring) legs of scenario 192 ----

@pytest.mark.parametrize("slug", ["shopsystem", "dummyco"])
def test_body_broker_fetches_ca_via_literal_agent_vault_ca_fetch(slug):
    """The rendered body sources the CA from the running broker by the literal
    substring `agent-vault ca fetch`."""
    body = _shop_shell_body(slug)
    assert "agent-vault ca fetch" in body


@pytest.mark.parametrize("slug", ["shopsystem", "dummyco"])
def test_body_broker_fetch_runs_against_agent_vault_container(slug):
    """The broker-fetch executes against the agent-vault container (a
    docker-exec into the {{OPS_SLUG}}-agent-vault container), so it does not
    depend on any BC container being present."""
    body = _shop_shell_body(slug)
    # The fetch must be wired through the agent-vault container, not a bare
    # host `agent-vault` binary (which does not exist on the host).
    assert re.search(
        rf"docker exec[^\n]*{slug}-agent-vault[^\n]*agent-vault ca fetch",
        body,
    ), (
        "the `agent-vault ca fetch` must run via `docker exec` into the "
        f"{slug}-agent-vault container, independent of any BC container."
    )


def _first_code_line(body: str, needle: str) -> int:
    """Index of the first NON-COMMENT line containing needle; -1 if absent.
    Comments may mention these literals in prose, so order/launch assertions
    must look only at executable lines."""
    for i, ln in enumerate(body.splitlines()):
        if ln.lstrip().startswith("#"):
            continue
        if needle in ln:
            return i
    return -1


@pytest.mark.parametrize("slug", ["shopsystem", "dummyco"])
def test_body_broker_fetch_ordered_before_donor_inspect(slug):
    """CA sourcing orders the broker fetch before / independently of donor-BC
    recovery (`docker inspect`): the first `agent-vault ca fetch` must appear
    before the donor `docker inspect` so donor recovery is a lower-priority
    fallback, not required for the cold-start CA."""
    body = _shop_shell_body(slug)
    fetch_idx = _first_code_line(body, "agent-vault ca fetch")
    inspect_idx = _first_code_line(body, "docker inspect")
    assert fetch_idx != -1, "no `agent-vault ca fetch` code line"
    assert inspect_idx != -1, "no `docker inspect` code line"
    assert fetch_idx < inspect_idx, (
        "the broker fetch (`agent-vault ca fetch`) must be ordered before the "
        "donor-BC recovery (`docker inspect`) so the CA is obtained on a cold "
        "start without a donor; donor recovery is only a lower-priority "
        "fallback."
    )


@pytest.mark.parametrize("slug", ["shopsystem", "dummyco"])
def test_body_passes_ca_pem_on_docker_run(slug):
    """The resulting CA material is passed into the launched container by
    referencing AGENT_VAULT_CA_PEM on the `docker run` invocation."""
    body = _shop_shell_body(slug)
    lines = body.splitlines()
    run_idx = _first_code_line(body, "docker run")
    assert run_idx != -1, "no `docker run` launch line"
    tail = "\n".join(lines[run_idx:])
    assert "AGENT_VAULT_CA_PEM" in tail, (
        "AGENT_VAULT_CA_PEM must be referenced on the `docker run` invocation."
    )
