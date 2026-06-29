"""Hermetic out-of-process harness for the rendered
``bin/agent-vault-approve-claude`` (lead-m1dc robustness pins 219/220/221).

The rendered script is run as a real subprocess with PATH-stubbed ``docker`` and
``curl`` (``jq`` and the shell builtins stay real) and a stub ``ops-coordinates``
sourced from the script's own directory. Every knob below simulates one input /
endpoint / prior-state condition keyed into the stubs, so the tests can prove:

  * the precondition gate fires BEFORE any mutating call (zero partial state),
  * a re-run reuses an already-ensured slot instead of aborting,
  * a re-run re-POSTs fresh token material as a supported update path.

The stubs record every invocation. A "mutating call" is, precisely, a
``vault proposal approve`` (docker exec) or a POST to ``/v1/auth/login`` or
``/v1/credentials/oauth/tokens`` (curl). Reachability HEAD probes are NOT
mutations and are recorded distinctly (METHOD=HEAD).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field

from shop_templates.cli import render_ops_template


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    curl_log: str
    docker_log: str
    mutation_log: str

    # --- derived predicates over the recorded stub traffic --------------
    def _curl_lines(self) -> list[str]:
        return [l for l in self.curl_log.splitlines() if l.strip()]

    def posted_to(self, url_fragment: str) -> bool:
        """True iff a POST (not a HEAD probe) hit a URL containing the fragment."""
        return any(
            l.startswith("METHOD=POST") and url_fragment in l for l in self._curl_lines()
        )

    def post_body_to(self, url_fragment: str) -> str:
        for l in self._curl_lines():
            if l.startswith("METHOD=POST") and url_fragment in l:
                return l
        return ""

    @property
    def approved_a_proposal(self) -> bool:
        return "proposal approve" in self.mutation_log

    @property
    def made_any_mutating_call(self) -> bool:
        return (
            self.approved_a_proposal
            or self.posted_to("/v1/auth/login")
            or self.posted_to("/v1/credentials/oauth/tokens")
        )


def _coordinates_body(slug: str, ok: bool) -> str:
    if not ok:
        # File present and sources cleanly, but defines NONE of the OPS_*
        # coordinates the script needs — the "unresolvable ops-coordinates" gap.
        return "#!/usr/bin/env bash\n# intentionally defines no OPS_* coordinates\n:\n"
    return (
        "#!/usr/bin/env bash\n"
        f'OPS_SLUG="{slug}"\n'
        f'OPS_VAULT_CONTAINER="{slug}-agent-vault"\n'
        f'OPS_AGENT_VAULT_CONTAINER="{slug}-agent-vault"\n'
        f'OPS_VAULT_NAME="{slug}"\n'
        'OPS_BROKER_LOCAL_ADDR="http://localhost:14321"\n'
        f'OPS_BROKER_ADDR="http://{slug}-agent-vault:14321"\n'
        f'OPS_AGENT_VAULT_ADDR="http://{slug}-agent-vault:14321"\n'
    )


def _docker_stub(slug: str, *, broker_up: bool, pending: bool, slot_exists: bool,
                 docker_log: str, mut_log: str) -> str:
    # A real broker REJECTS re-approving an already-approved proposal. Modelling
    # that (proposal approve fails when the slot already exists) is what forces
    # the idempotent re-run to reuse the slot instead of re-approving (220/221).
    approve_branch = (
        'echo "proposal approve: $args" >> {ml!r}\n'
        '      echo "Error: proposal already approved" >&2; exit 1'
        if slot_exists
        else 'echo "proposal approve: $args" >> {ml!r}\n'
        '      echo "approved"; exit 0'
    ).format(ml=mut_log)
    return f"""#!/usr/bin/env bash
echo "docker $*" >> {docker_log!r}
args="$*"
case "$1" in
  ps)
    {'echo "%s-agent-vault"' % slug if broker_up else ':'}
    exit 0 ;;
  exec)
    if [[ "$args" == *"vault token"* ]]; then echo "av_sess_stub"; exit 0; fi
    if [[ "$args" == *"proposal approve"* ]]; then
      {approve_branch}
    fi
    if [[ "$args" == *"proposal list"* && "$args" == *"--status pending"* ]]; then
      {'echo "  3  pending  CLAUDE_OAUTH  2026-06-29 16:58"' if pending else ':'}
      exit 0
    fi
    if [[ "$args" == *"proposal list"* ]]; then
      {'echo "  3  approved  CLAUDE_OAUTH  2026-06-29 16:58"' if slot_exists else ':'}
      exit 0
    fi
    exit 0 ;;
esac
exit 0
"""


def _curl_stub(*, reachable: bool, login_status: str, tokens_status: str,
               curl_log: str) -> str:
    reach_exit = 0 if reachable else 7
    return f"""#!/usr/bin/env bash
url="" jar="" method="GET" head=0
args=("$@")
for ((i=0;i<${{#args[@]}};i++)); do
  case "${{args[i]}}" in
    http*) url="${{args[i]}}" ;;
    -I|--head) head=1 ;;
    -X) method="${{args[i+1]}}" ;;
    --cookie-jar|-c) jar="${{args[i+1]}}" ;;
  esac
done
[[ $head -eq 1 ]] && method="HEAD"
bodyin=""
[[ "$method" != "HEAD" ]] && bodyin="$(cat 2>/dev/null)"
echo "METHOD=$method URL=$url BODY=$bodyin" >> {curl_log!r}
if [[ "$method" == "HEAD" ]]; then exit {reach_exit}; fi
if [[ "$url" == *"/v1/auth/login"* ]]; then
  [[ -n "$jar" ]] && printf '#HttpOnly_h\\tFALSE\\t/\\tFALSE\\t0\\tav_session\\tav_sess_x\\n' > "$jar"
  printf '{login_status}'
  exit 0
fi
if [[ "$url" == *"/v1/credentials/oauth/tokens"* ]]; then
  printf '{{}}\\n{tokens_status}'
  exit 0
fi
printf '200'
exit 0
"""


def run_approve_claude(
    *,
    slug: str = "acme",
    access: str | None = "acc-DEFAULT",
    refresh: str | None = "ref-DEFAULT",
    creds_file_missing: bool = False,
    override_arg: str | None = None,
    owner_password: str | None = "ownerpw",
    ops_coordinates_ok: bool = True,
    broker_up: bool = True,
    endpoints_reachable: bool = True,
    pending_proposal: bool = True,
    slot_exists: bool = False,
    login_status: str = "200",
    tokens_status: str = "200",
    write_env: str | None = "3",
) -> RunResult:
    d = tempfile.mkdtemp()
    bindir = os.path.join(d, "bin")
    stubdir = os.path.join(d, "stubbin")
    os.makedirs(bindir)
    os.makedirs(stubdir)

    script = os.path.join(bindir, "agent-vault-approve-claude")
    with open(script, "w") as f:
        f.write(render_ops_template("agent-vault-approve-claude", slug))
    os.chmod(script, 0o755)

    with open(os.path.join(bindir, "ops-coordinates"), "w") as f:
        f.write(_coordinates_body(slug, ops_coordinates_ok))

    docker_log = os.path.join(d, "docker.log")
    mut_log = os.path.join(d, "mutations.log")
    curl_log = os.path.join(d, "curl.log")

    docker_path = os.path.join(stubdir, "docker")
    with open(docker_path, "w") as f:
        f.write(_docker_stub(slug, broker_up=broker_up, pending=pending_proposal,
                             slot_exists=slot_exists, docker_log=docker_log,
                             mut_log=mut_log))
    os.chmod(docker_path, 0o755)

    curl_path = os.path.join(stubdir, "curl")
    with open(curl_path, "w") as f:
        f.write(_curl_stub(reachable=endpoints_reachable, login_status=login_status,
                           tokens_status=tokens_status, curl_log=curl_log))
    os.chmod(curl_path, 0o755)

    # Claude credentials file.
    cred_file = os.path.join(d, "credentials.json")
    if creds_file_missing:
        cred_file = os.path.join(d, "no-such-credentials.json")
    else:
        with open(cred_file, "w") as f:
            json.dump(
                {"claudeAiOauth": {
                    "accessToken": access if access is not None else "",
                    "refreshToken": refresh if refresh is not None else "",
                    "expiresAt": 9999999999,
                }},
                f,
            )

    # Realistic .env: footing/provision persisted the create-time proposal number.
    if write_env is not None:
        with open(os.path.join(d, ".env"), "w") as f:
            f.write(f"BC_BASE_IMAGE_RESOLVED=x\nCLAUDE_OAUTH_PROPOSAL_NUM={write_env}\n")

    # Hermetic env: scrub any leaked AGENT_VAULT_* / OPS_* / CLAUDE_* from the
    # container so the rendered script resolves coordinates ONLY from the stub
    # ops-coordinates and the knobs below.
    env = {
        k: v
        for k, v in os.environ.items()
        if not (
            k.startswith("AGENT_VAULT_")
            or k.startswith("OPS_")
            or k.startswith("CLAUDE_")
        )
    }
    env["PATH"] = stubdir + os.pathsep + os.environ.get("PATH", "")
    env["CLAUDE_CREDENTIALS_FILE"] = cred_file
    env["AGENT_VAULT_OWNER_EMAIL"] = f"owner@{slug}.local"
    if owner_password is not None:
        env["AGENT_VAULT_OWNER_PASSWORD"] = owner_password

    cmd = ["bash", script]
    if override_arg is not None:
        cmd.append(override_arg)

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=d)

    def _read(p: str) -> str:
        return open(p).read() if os.path.exists(p) else ""

    return RunResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        curl_log=_read(curl_log),
        docker_log=_read(docker_log),
        mutation_log=_read(mut_log),
    )
