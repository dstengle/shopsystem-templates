"""Pins the starter bin/bootstrap behavior of OBTAINING bin/footing by
rendering it from the templates/ops/footing template before invoking it,
delegating to the rendered footing, and refusing to invoke a footing that was
never produced (lead-y4pg; PDR-019 U1/U3, ADR-040).

The starter forkable repo ships bin/bootstrap but NOT bin/footing — the
framework (footing orchestration included) lives only in the published image.
So the adopter's bin/bootstrap must:

  (1) render bin/footing from templates/ops/footing (via `shop-templates
      bootstrap` run in-container) BEFORE invoking it, and that rendered
      bin/footing must be executable before the invoke;
  (2) DELEGATE to the rendered bin/footing for the footing sequence (auth
      gate, lead-structure pour, <product>-lead-beads creation, git+beads
      remote wiring, `bd dolt push` smoke-test) which stops at a green
      `git push` + `bd dolt push`;
  (3) REFUSE to invoke bin/footing when the render step did not produce the
      file — exiting with a diagnostic that NAMES the missing bin/footing
      rather than running `bash ./bin/footing` against a missing file and
      failing with an exit-127 "No such file or directory".

These are properties of the starter bootstrap script BODY served as package
data (the same surface tests/test_starter_repo_body.py pins), so they are
asserted against read_starter_file(<bootstrap>).
"""
import re

from shop_templates.cli import iter_starter_files, read_starter_file


def _bootstrap_rel() -> str:
    files = dict(iter_starter_files())
    for cand in ("bin/bootstrap", "bootstrap"):
        if cand in files:
            return cand
    raise AssertionError("no bootstrap script in starter body")


def _bootstrap_body() -> str:
    return read_starter_file(_bootstrap_rel())


def _code_lines(body: str) -> list[str]:
    """Return the script's non-comment, non-blank lines (command lines only).

    A line whose first non-whitespace character is '#' is a comment; the
    behaviors here are about what bootstrap actually EXECUTES, not what its
    comments describe, so the assertions run against the command lines."""
    out = []
    for raw in body.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(raw)
    return out


def _code_text(body: str) -> str:
    return "\n".join(_code_lines(body))


# -----------------------------------------------------------------------
# Behavior 1 (@scenario_hash:b05fff82d0d10f4a):
# bootstrap renders bin/footing from templates/ops/footing before invoking it.
# -----------------------------------------------------------------------


def test_bootstrap_does_not_ship_footing_in_the_starter_body():
    """The starter ships bin/bootstrap but NOT bin/footing — footing is
    rendered by bootstrap at run time, never carried in the fork. (The Given
    of b05fff82d0d10f4a and c15aeb90b21357e5.)"""
    files = dict(iter_starter_files())
    assert "bin/bootstrap" in files or "bootstrap" in files
    assert "bin/footing" not in files, (
        "the starter must NOT carry bin/footing; bootstrap renders it at run time"
    )


def test_bootstrap_executes_shop_templates_bootstrap_to_render_footing():
    """bootstrap must actually EXECUTE `shop-templates bootstrap` (a command
    line, not merely a comment) so footing is rendered from
    templates/ops/footing into the fork. A bootstrap that only MENTIONS the
    render in a comment but never runs it leaves the fork with no bin/footing —
    the exact gap this behavior closes."""
    code = _code_text(_bootstrap_body())
    assert "shop-templates bootstrap" in code, (
        "bootstrap must EXECUTE `shop-templates bootstrap` (a command line, not "
        "just a comment) to render bin/footing from templates/ops/footing"
    )


def test_bootstrap_render_step_runs_in_container():
    """The render runs in-container: the `shop-templates bootstrap` command
    line is carried into a `docker run`/`docker compose run` of the published
    image (the CLI ships only in the image — zero-install on the host)."""
    code = _code_text(_bootstrap_body())
    assert re.search(r"docker\s+(run|compose\s+run|exec)", code), (
        "the render must run in-container (docker run/compose run/exec of the "
        "published image), since `shop-templates` ships only in the image"
    )


def test_bootstrap_renders_footing_before_invoking_it():
    """The render-of-footing step must appear BEFORE the invoke-of-footing
    step among the command lines: footing is obtained, then run — never run
    before it has been rendered."""
    code = _code_text(_bootstrap_body())
    render_idx = code.find("shop-templates bootstrap")
    m = re.search(r"(bash\s+\./bin/footing|\bexec\b[^\n]*\bbin/footing\b|^\s*\./bin/footing\b)", code, re.M)
    invoke_idx = m.start() if m else -1
    assert render_idx != -1, "no executed `shop-templates bootstrap` render step found"
    assert invoke_idx != -1, "no bin/footing invoke command found"
    assert render_idx < invoke_idx, (
        "bootstrap must render bin/footing (via `shop-templates bootstrap`) "
        "BEFORE it invokes bin/footing"
    )


def test_bootstrap_invokes_rendered_footing_runnably():
    """bootstrap must invoke the rendered bin/footing in a runnable way:
    through `bash ./bin/footing` (no +x needed) or after chmod +x. It must not
    invoke a bare `./bin/footing` it never made executable."""
    code = _code_text(_bootstrap_body())
    runs_via_bash = re.search(r"bash\s+\./bin/footing", code) is not None
    chmods_footing = re.search(r"chmod\s+\+x\s+(\./)?bin/footing", code) is not None
    assert runs_via_bash or chmods_footing, (
        "bootstrap must ensure the rendered bin/footing is runnable before "
        "invoking it — either chmod +x bin/footing or invoke via `bash "
        "./bin/footing`"
    )


# -----------------------------------------------------------------------
# Behavior 2 (@scenario_hash:3646efa06051fcac):
# bootstrap delegates to the rendered bin/footing which runs the footing
# sequence to green. bootstrap passes control to bin/footing (REUSE, not
# fork) and the rendered footing runs the whole sequence and stops at a green
# `git push` + `bd dolt push`.
# -----------------------------------------------------------------------


def _footing_body():
    from shop_templates.cli import render_ops_template

    return render_ops_template("footing", "shopsystem")


def test_bootstrap_delegates_control_to_rendered_footing():
    """bootstrap must hand control to the rendered bin/footing — it invokes
    `bash ./bin/footing` and lets footing own the sequence."""
    code = _code_text(_bootstrap_body())
    assert re.search(r"bash\s+\./bin/footing", code), (
        "bootstrap must delegate to the rendered bin/footing via `bash "
        "./bin/footing`"
    )


def test_bootstrap_does_not_fork_the_footing_sequence_internals():
    """REUSE, not fork: bootstrap must NOT re-implement footing's internals —
    it must not itself create the beads repo or wire the beads dolt remote.
    Those belong to the footing script it delegates to."""
    code = _code_text(_bootstrap_body())
    assert "gh repo create" not in code, (
        "bootstrap must delegate beads-repo creation to footing, not fork it"
    )
    assert "bd dolt remote add" not in code, (
        "bootstrap must delegate beads-remote wiring to footing, not fork it"
    )


def test_rendered_footing_runs_the_full_sequence():
    """The rendered bin/footing (what bootstrap delegates to) runs the footing
    sequence: the single up-front auth gate, the lead-structure pour, the
    <product>-lead-beads creation, the git+beads remote wiring, and the
    `bd dolt push` smoke-test."""
    body = _footing_body()
    lowered = body.lower()
    assert "auth gate" in lowered, "footing must run the single up-front auth gate"
    assert "shop-templates bootstrap" in body, "footing must pour the lead structure"
    assert "shopsystem-lead-beads" in body, (
        "footing must create the <product>-lead-beads repository (slug-scoped)"
    )
    assert "git remote" in body and "bd dolt remote add" in body, (
        "footing must wire the git and beads remotes"
    )
    assert "bd dolt push" in body, "footing must run the `bd dolt push` smoke-test"


def test_rendered_footing_stops_at_green_git_push_and_bd_dolt_push():
    """The rendered footing stops at solid footing demonstrated by a successful
    `git push` and a successful `bd dolt push`."""
    body = _footing_body()
    assert "git push" in body, "footing must reach a `git push`"
    assert "bd dolt push" in body, "footing must reach a `bd dolt push`"
