"""shop-shell broker-credential sourcing: donor-recovery of CA_PEM/ADDR must
be decoupled from token presence (lead-7gvm — conformance bugfix to lead-held
features/templates/183 @scenario_hash:2adc62a25c401e4b, mirrored BC-locally in
features/bootstrap_shop_shell_ca_guard.feature).

The bug: the rendered bin/shop-shell gates its `docker inspect ... .Config.Env`
donor-recovery block behind `if [ -z "$AGENT_VAULT_TOKEN" ]`, so it fires ONLY
when the token is absent. The multi-line CA PEM cannot survive shop-shell's
`.env` parser (it captures only the first line of a multi-line value), so the
common operator state is: `.env` supplies AGENT_VAULT_TOKEN but NOT
AGENT_VAULT_CA_PEM. In that state the token-gated donor block is SKIPPED,
AGENT_VAULT_CA_PEM launches EMPTY, and claude's TLS to the :14322 broker proxy
silently fails cert validation — the exact silent-broken token-present/CA-empty
state scenario 183 forbids.

The fix (conformance to 183): run donor-recovery when ANY of
{AGENT_VAULT_TOKEN, AGENT_VAULT_CA_PEM} is empty and a donor BC is available,
backfilling ONLY the empty fields (preserving any value `.env` already
provided), and fail loud (no `docker run`) only if the TOKEN is still empty
after both sources.

These are properties of the rendered shop-shell BODY, exercised by extracting
the credential-acquisition region and running it under bash with a stubbed
`docker` whose `inspect` emits a donor environment. The donor-availability and
backfill behavior is proven by RUNNING the region, not by substring-matching.
"""
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

from shop_templates.cli import render_ops_template

_SLUG = "dummyco"


def _shop_shell_body() -> str:
    return render_ops_template("shop-shell", _SLUG)


def _credential_region(body: str) -> str:
    """Return the broker-credential-acquisition region of the rendered
    shop-shell: from the line that initializes AGENT_VAULT_ADDR through the
    line that exports the four AGENT_VAULT_* variables after both sources.

    This is the self-contained block the bug lives in; extracting it lets us
    execute the real sourcing logic under bash with a stubbed docker without
    reaching the `exec docker run` launch line."""
    lines = body.splitlines()
    start = next(
        i for i, ln in enumerate(lines)
        if ln.strip().startswith("AGENT_VAULT_ADDR=")
    )
    # The region ends at the `export AGENT_VAULT_ADDR ...` line that follows
    # both sources and the token fail-loud guard.
    end = next(
        i for i, ln in enumerate(lines)
        if i > start and ln.strip().startswith("export AGENT_VAULT_ADDR")
    )
    return "\n".join(lines[start : end + 1])


def _run_region(
    tmp_path: Path,
    *,
    env_token: str,
    env_ca: str,
    donor_token: str,
    donor_addr: str,
    donor_ca: str,
    donor_available: bool,
):
    """Execute the credential-acquisition region under bash.

    `.env` is simulated by exporting env_token/env_ca into the shell before
    the region (the region reads AGENT_VAULT_* from the environment via the
    `:-` defaults, which is exactly what `set -a; source .env` populates).
    `docker` is stubbed: `docker ps` lists a donor container iff
    donor_available; `docker inspect` emits the donor environment. After the
    region runs we print the resolved variables, or `__FAILED__<rc>` if the
    region's fail-loud guard exited non-zero.
    """
    region = _credential_region(_shop_shell_body())

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    donor_name = f"{_SLUG}-bc-launcher" if donor_available else ""
    docker_stub = bin_dir / "docker"
    docker_stub.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            if [[ "$1" == "ps" ]]; then
              {f'echo {donor_name}' if donor_available else ':'}
              exit 0
            fi
            if [[ "$1" == "inspect" ]]; then
              printf '%s\\n' "AGENT_VAULT_ADDR={donor_addr}"
              printf '%s\\n' "AGENT_VAULT_TOKEN={donor_token}"
              printf '%s\\n' "AGENT_VAULT_VAULT=donor-vault"
              printf '%s\\n' "AGENT_VAULT_CA_PEM={donor_ca}"
              exit 0
            fi
            exit 0
            """
        )
    )
    docker_stub.chmod(0o755)

    # agent-vault stub: the CA self-source step (`agent-vault ca fetch`) must
    # NOT be how the token-present/CA-empty case is healed — emit nothing so
    # the only CA source under test is donor-recovery.
    av_stub = bin_dir / "agent-vault"
    av_stub.write_text("#!/usr/bin/env bash\nexit 1\n")
    av_stub.chmod(0o755)

    script = (
        # Match the rendered shop-shell's own shell options exactly, so the
        # extracted region is exercised under the same set -e / pipefail
        # discipline production runs it under.
        "set -euo pipefail\n"
        f'REPO_ROOT="{repo_root}"\n'
        f'AGENT_VAULT_TOKEN="{env_token}"\n'
        f'AGENT_VAULT_CA_PEM="{env_ca}"\n'
        "export AGENT_VAULT_TOKEN AGENT_VAULT_CA_PEM\n"
        + region
        + "\n"
        'echo "TOKEN=[$AGENT_VAULT_TOKEN]"\n'
        'echo "ADDR=[$AGENT_VAULT_ADDR]"\n'
        'echo "CA=[$AGENT_VAULT_CA_PEM]"\n'
    )

    env = dict(os.environ)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    # The region must resolve AGENT_VAULT_* from the simulated .env exports,
    # not from the ambient operator environment running the test.
    for k in ("AGENT_VAULT_ADDR", "AGENT_VAULT_VAULT"):
        env.pop(k, None)

    proc = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
    )
    return proc


def _parse(out: str, key: str) -> str:
    for ln in out.splitlines():
        if ln.startswith(f"{key}=["):
            return ln[len(key) + 2 : -1]
    return "<unset>"


def test_token_present_ca_empty_donor_available_backfills_ca_preserving_token(
    tmp_path,
):
    """The silent-broken state 183 forbids: `.env` supplies the TOKEN but not
    the CA. With a donor available, donor-recovery must fire (NOT be skipped by
    a token-presence gate) and backfill the EMPTY CA while PRESERVING the
    .env-provided token."""
    proc = _run_region(
        tmp_path,
        env_token="env-token-xyz",
        env_ca="",
        donor_token="donor-token-SHOULD-NOT-WIN",
        donor_addr="donor-addr:14322",
        donor_ca="DONOR-CA-MATERIAL",
        donor_available=True,
    )
    assert proc.returncode == 0, (
        "region must not fail loud when the token is present:\n"
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert _parse(proc.stdout, "CA") == "DONOR-CA-MATERIAL", (
        "donor-recovery must backfill the empty AGENT_VAULT_CA_PEM even when "
        "the token is already present (decoupled from token-absence). Got: "
        f"{proc.stdout!r}"
    )
    assert _parse(proc.stdout, "TOKEN") == "env-token-xyz", (
        "donor-recovery must PRESERVE the .env-provided token and only "
        f"backfill empty fields. Got: {proc.stdout!r}"
    )


def test_token_absent_after_both_sources_fails_loud_without_docker_run(tmp_path):
    """If, after `.env` and donor-recovery, the TOKEN is still empty (no donor
    available), the region must fail loud (exit non-zero) rather than fall
    through to launch."""
    proc = _run_region(
        tmp_path,
        env_token="",
        env_ca="",
        donor_token="",
        donor_addr="",
        donor_ca="",
        donor_available=False,
    )
    assert proc.returncode != 0, (
        "region must fail loud when no token can be obtained from either "
        f"source. stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


def test_token_absent_but_donor_available_recovers_full_env(tmp_path):
    """Token absent in `.env` but a donor is available: donor-recovery fills
    token + addr + CA and the region succeeds (the pre-existing token-absence
    recovery path still works — additive, not regressed)."""
    proc = _run_region(
        tmp_path,
        env_token="",
        env_ca="",
        donor_token="donor-token-abc",
        donor_addr="donor-addr:14322",
        donor_ca="DONOR-CA",
        donor_available=True,
    )
    assert proc.returncode == 0, (
        f"donor recovery must succeed. stderr={proc.stderr!r}"
    )
    assert _parse(proc.stdout, "TOKEN") == "donor-token-abc"
    assert _parse(proc.stdout, "CA") == "DONOR-CA"


def test_env_ca_present_is_not_clobbered_by_donor(tmp_path):
    """If `.env` somehow provided BOTH token and CA, and the region still
    consults a donor (because some other field is empty), the donor must not
    overwrite the .env-provided CA — only empty fields are backfilled."""
    proc = _run_region(
        tmp_path,
        env_token="env-token",
        env_ca="ENV-CA-MATERIAL",
        donor_token="donor-token",
        donor_addr="donor-addr:14322",
        donor_ca="DONOR-CA-MATERIAL",
        donor_available=True,
    )
    assert proc.returncode == 0
    assert _parse(proc.stdout, "TOKEN") == "env-token"
    assert _parse(proc.stdout, "CA") == "ENV-CA-MATERIAL", (
        "a .env-provided CA must be preserved, never clobbered by the donor. "
        f"Got: {proc.stdout!r}"
    )
