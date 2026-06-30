"""Pins the starter bin/bootstrap baked-version VERIFY GATE that sits BEFORE
the in-image `shop-templates bootstrap` render (lead-b2iz; PDR-026, ADR-040).

bin/bootstrap pulls the bc-lead/bc-base image on a floating tag and then runs
the in-image render. A stale/cached :latest would otherwise render an ANCIENT
shop with no signal. This gate reads the pulled image's baked shop-templates
version from PDR-026 provenance — the OCI label "shopsystem.shop-templates.version"
via `docker image inspect`, or `printenv SHOP_TEMPLATES_VERSION` of a container
started from it — and compares it to an expected-minimum floor known to
bin/bootstrap, WITHOUT invoking `pip show` or any python in the image. At or
above the floor it proceeds to render (current behavior preserved); below the
floor it refuses: NO render, non-zero exit, a diagnostic naming the stale
version, the expected minimum, and an actionable remediation.

These behaviors are exercised by RUNNING the rendered bin/bootstrap
out-of-process against a PATH-stubbed `docker` that returns a configurable
baked version, so the assertions are about what bootstrap actually executes —
not about what its comments say. The "no render on stale" assertion is
load-bearing: it proves the in-image render is never invoked below the floor.

Scenarios:
  @scenario_hash:4457c8c280d4fbf4 — proceeds when baked version >= floor.
  @scenario_hash:e9d64a8acc917efb — refuses loudly when below floor.
"""
from __future__ import annotations

import os
import re
import stat as _stat
import subprocess
from pathlib import Path

import pytest

from shop_templates.cli import read_starter_file

LABEL = "shopsystem.shop-templates.version"

# A fake `docker` that logs every invocation and answers the calls bin/bootstrap
# makes: `pull` (no-op), `inspect --format {{RepoDigests}}` (a digest), `image
# inspect` (the baked-version label read), and `run` (printenv version read /
# the `shop-templates bootstrap` render / the `bash ./bin/footing` launch). The
# render branch materializes bin/footing in the fork so the existing footing
# existence guard passes on the proceed path.
_FAKE_DOCKER = r"""#!/usr/bin/env bash
LOG="$FAKE_DOCKER_LOG"
printf '%s\n' "$*" >> "$LOG"
sub="${1:-}"; shift || true
case "$sub" in
  pull)
    exit 0 ;;
  inspect)
    # docker inspect --format '{{index .RepoDigests 0}}' IMG
    echo "ghcr.io/dstengle/shopsystem-bc-base@sha256:deadbeefcafef00ddeadbeefcafef00ddeadbeefcafef00ddeadbeefcafef00d"
    exit 0 ;;
  image)
    # docker image inspect --format '<label fmt>' IMG  -> baked version label read
    if [ "${FAKE_LABEL_EMPTY:-0}" = "1" ]; then
      echo ""
    else
      echo "$FAKE_BAKED_VERSION"
    fi
    exit 0 ;;
  run)
    all="$*"
    case "$all" in
      *"printenv SHOP_TEMPLATES_VERSION"*)
        echo "$FAKE_BAKED_VERSION"
        exit 0 ;;
      *"shop-templates bootstrap"*)
        mkdir -p "$FAKE_FORK_DIR/bin"
        printf '#!/usr/bin/env bash\ntrue\n' > "$FAKE_FORK_DIR/bin/footing"
        exit 0 ;;
      *)
        # footing-launch run (`bash ./bin/footing`) — no-op
        exit 0 ;;
    esac ;;
  *)
    exit 0 ;;
esac
"""

# A fake `stat` so the proceed path's `stat -L -c '%g' /var/run/docker.sock`
# (SOCKET_GID resolution) does not abort under `set -e` on a host with no
# docker socket. Returns a plausible gid; delegates nothing else.
_FAKE_STAT = r"""#!/usr/bin/env bash
echo 999
exit 0
"""


class BootstrapRun:
    def __init__(self, proc: subprocess.CompletedProcess, log: str):
        self.proc = proc
        self.returncode = proc.returncode
        self.stdout = proc.stdout
        self.stderr = proc.stderr
        self.docker_log = log

    @property
    def output(self) -> str:
        return self.stdout + self.stderr

    def render_invoked(self) -> bool:
        """True iff a `docker run ... shop-templates bootstrap ...` (the in-image
        render) was actually invoked."""
        for line in self.docker_log.splitlines():
            if line.startswith("run ") and "shop-templates bootstrap" in line:
                return True
        return False

    def version_read_via_provenance(self) -> bool:
        """True iff the baked version was read via `docker image inspect` of the
        PDR-026 label OR a `printenv SHOP_TEMPLATES_VERSION` container run."""
        label_read = any(
            line.startswith("image inspect") and LABEL in line
            for line in self.docker_log.splitlines()
        )
        printenv_read = any(
            line.startswith("run ") and "printenv SHOP_TEMPLATES_VERSION" in line
            for line in self.docker_log.splitlines()
        )
        return label_read or printenv_read

    def used_pip_or_python_in_image(self) -> bool:
        """True iff any docker invocation read the version via `pip show` or a
        python invocation in the image (the FORBIDDEN read paths)."""
        for line in self.docker_log.splitlines():
            if "pip show" in line:
                return True
            if re.search(r"\bpython[0-9.]*\b", line):
                return True
        return False


def _make_stub(stub_dir: Path, name: str, body: str) -> None:
    p = stub_dir / name
    p.write_text(body)
    p.chmod(p.stat().st_mode | _stat.S_IEXEC | _stat.S_IXGRP | _stat.S_IXOTH)


def run_bootstrap(
    tmp_path: Path,
    *,
    baked_version: str,
    floor: str,
    label_empty: bool = False,
    repo_name: str = "acme-lead",
) -> BootstrapRun:
    """Render the starter bin/bootstrap into a fork named <repo_name> and run it
    out-of-process with a PATH-stubbed `docker`/`stat`, simulating a pulled image
    whose baked shop-templates version is `baked_version` against an
    expected-minimum `floor`. Returns a BootstrapRun exposing exit code, output,
    and the docker invocation log."""
    fork = tmp_path / repo_name
    (fork / "bin").mkdir(parents=True)
    (fork / "bin" / "bootstrap").write_text(read_starter_file("bin/bootstrap"))

    stub_dir = tmp_path / "stub"
    stub_dir.mkdir()
    log = stub_dir / "docker.log"
    log.write_text("")
    _make_stub(stub_dir, "docker", _FAKE_DOCKER)
    _make_stub(stub_dir, "stat", _FAKE_STAT)

    env = dict(os.environ)
    env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"
    env["EXPECTED_MIN_SHOP_TEMPLATES_VERSION"] = floor
    env["FAKE_BAKED_VERSION"] = baked_version
    env["FAKE_LABEL_EMPTY"] = "1" if label_empty else "0"
    env["FAKE_FORK_DIR"] = str(fork)
    env["FAKE_DOCKER_LOG"] = str(log)
    # Keep the run fully non-interactive and self-contained.
    env["BOOTSTRAP_REPO_NAME"] = repo_name

    proc = subprocess.run(
        ["bash", str(fork / "bin" / "bootstrap")],
        cwd=str(fork),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
    )
    return BootstrapRun(proc, log.read_text())


# -----------------------------------------------------------------------
# Behavior 1 (@scenario_hash:4457c8c280d4fbf4):
# proceeds when the baked version is at or above the expected minimum, reading
# the version via PDR-026 provenance and never via pip show / python.
# -----------------------------------------------------------------------


def test_proceeds_to_render_when_baked_version_at_or_above_floor(tmp_path):
    run = run_bootstrap(tmp_path, baked_version="0.48.0", floor="0.48.0")
    assert run.returncode == 0, (
        f"bootstrap must proceed (exit 0) when baked >= floor; "
        f"stderr={run.stderr!r}"
    )
    assert run.render_invoked(), (
        "bootstrap must proceed to the in-image `shop-templates bootstrap` "
        "render when the baked version meets the expected minimum"
    )


def test_proceeds_when_baked_version_strictly_above_floor(tmp_path):
    run = run_bootstrap(tmp_path, baked_version="0.49.3", floor="0.48.0")
    assert run.returncode == 0, f"stderr={run.stderr!r}"
    assert run.render_invoked()


def test_version_read_uses_pdr026_provenance_not_pip_or_python(tmp_path):
    run = run_bootstrap(tmp_path, baked_version="0.48.0", floor="0.48.0")
    assert run.version_read_via_provenance(), (
        "bootstrap must read the baked version via `docker image inspect` of "
        f"the {LABEL!r} label or `printenv SHOP_TEMPLATES_VERSION`"
    )
    assert not run.used_pip_or_python_in_image(), (
        "bootstrap must NOT read the version via `pip show` or any python in "
        "the image"
    )


def test_version_read_falls_back_to_printenv_when_label_absent(tmp_path):
    # Image inspect returns an empty label; bootstrap must fall back to the
    # `printenv SHOP_TEMPLATES_VERSION` container read and still proceed.
    run = run_bootstrap(
        tmp_path, baked_version="0.48.0", floor="0.48.0", label_empty=True
    )
    assert run.returncode == 0, f"stderr={run.stderr!r}"
    assert run.version_read_via_provenance()
    assert run.render_invoked()
    assert not run.used_pip_or_python_in_image()


# -----------------------------------------------------------------------
# Behavior 2 (@scenario_hash:e9d64a8acc917efb):
# refuses loudly when the baked version is below the expected minimum — no
# render, non-zero exit, diagnostic naming stale + expected-min + remediation.
# -----------------------------------------------------------------------


def test_refuses_and_does_not_render_when_baked_version_below_floor(tmp_path):
    run = run_bootstrap(tmp_path, baked_version="0.10.0", floor="0.48.0")
    assert run.returncode != 0, (
        "bootstrap must exit NON-ZERO when the baked version is below the "
        "expected minimum"
    )
    assert not run.render_invoked(), (
        "LOAD-BEARING: bootstrap must NOT invoke the in-image "
        "`shop-templates bootstrap` render against a stale image below the floor"
    )


def test_below_floor_diagnostic_names_stale_expected_and_remediation(tmp_path):
    run = run_bootstrap(tmp_path, baked_version="0.10.0", floor="0.48.0")
    err = run.stderr
    assert "0.10.0" in err, (
        f"diagnostic must name the stale baked version it read; stderr={err!r}"
    )
    assert "0.48.0" in err, (
        f"diagnostic must name the expected-minimum it required; stderr={err!r}"
    )
    low = err.lower()
    assert ("docker pull" in low) or ("pull" in low and "image" in low), (
        "diagnostic must give an actionable remediation for obtaining the "
        f"current image (e.g. a docker pull); stderr={err!r}"
    )


def test_below_floor_read_still_uses_provenance_not_pip_or_python(tmp_path):
    # Even on the refuse path the version it read must come from PDR-026
    # provenance, never pip show / python.
    run = run_bootstrap(tmp_path, baked_version="0.10.0", floor="0.48.0")
    assert run.version_read_via_provenance()
    assert not run.used_pip_or_python_in_image()


# -----------------------------------------------------------------------
# Floor-sourcing (tmpl-deb.4): the expected-minimum floor is an env-overridable
# literal in bin/bootstrap, kept current with the shop-templates version so a
# release bump carries it forward (tracks the framework, not a frozen value).
# -----------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _bootstrap_body() -> str:
    return read_starter_file("bin/bootstrap")


def _pyproject_version() -> str:
    text = (_REPO_ROOT / "pyproject.toml").read_text()
    m = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', text)
    assert m, "could not find [project].version in pyproject.toml"
    return m.group(1)


def test_floor_is_env_overridable_literal_in_bootstrap():
    body = _bootstrap_body()
    assert re.search(
        r'EXPECTED_MIN_SHOP_TEMPLATES_VERSION="\$\{EXPECTED_MIN_SHOP_TEMPLATES_VERSION:-[0-9]+\.[0-9]+\.[0-9]+\}"',
        body,
    ), (
        "bin/bootstrap must carry an env-overridable expected-minimum floor "
        'literal: EXPECTED_MIN_SHOP_TEMPLATES_VERSION="${EXPECTED_MIN_SHOP_TEMPLATES_VERSION:-X.Y.Z}"'
    )


def test_floor_default_tracks_current_shop_templates_version():
    """Currency guard: the baked-in floor default must equal the current
    shop-templates [project].version, so each release bump carries the floor
    forward (the floor tracks the framework, never a frozen value)."""
    body = _bootstrap_body()
    m = re.search(
        r'EXPECTED_MIN_SHOP_TEMPLATES_VERSION="\$\{EXPECTED_MIN_SHOP_TEMPLATES_VERSION:-([0-9]+\.[0-9]+\.[0-9]+)\}"',
        body,
    )
    assert m, "no expected-minimum floor default literal found in bin/bootstrap"
    assert m.group(1) == _pyproject_version(), (
        f"the bin/bootstrap floor default {m.group(1)!r} must equal the current "
        f"shop-templates version {_pyproject_version()!r}; a release bump must "
        f"carry the floor forward"
    )
