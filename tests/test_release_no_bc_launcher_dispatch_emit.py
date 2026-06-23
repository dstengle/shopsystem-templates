"""Pin the post-ADR-022 no-emit shape of .github/workflows/release.yml
(scenario 846e4e663198ce78, lead-ucpj).

Per ADR-022 the cross-repo repository_dispatch fan-in that previously
notified the bc-launcher on each release was RETIRED with no successor (the
prior scenario 26ca8a14e01db50c was retired by lead-zgrk). release.yml is
NOT deleted — it retains its release-guard version-hygiene job (scenario
192, 88a5418db371a12a). This module PINS that surviving no-emit shape as a
registered, hashed behavior — register parity with shopsystem-scenarios
(lead-vusv) and shopsystem-messaging (lead-0udp).

The behavior already exists on main; this is a pin-of-existing registration,
not a behavior change. The load-bearing subtlety the scenario asserts is the
COMMENT-vs-EXECUTABLE distinction: release.yml's header comment legitimately
NAMES the bc-launcher to explain that nothing is emitted to it. A naive
substring scan of the raw file would false-positive on that comment. So the
assertions run against the EXECUTABLE body (YAML comment lines stripped),
and a token appearing ONLY in a descriptive comment must NOT fail the
scenario. The non-vacuity fixtures below prove the assert-absent legs are
genuinely RED when an emit lives in the executable region.
"""
from __future__ import annotations

import pytest

import yaml

from _release_workflow import (
    executable_body as _executable_body,
    release_workflow_path as _release_workflow_path,
    strip_inline_comment as _strip_inline_comment,
)


# --------------------------------------------------------------------------
# Non-vacuity fixtures: an emit-bearing EXECUTABLE body must FAIL the
# assert-absent legs; a comment-only token must NOT.
# --------------------------------------------------------------------------

# The pre-lead-zgrk emit shape: a real repository_dispatch step in the
# executable region carrying the cross-repo token. This MUST trip the
# assert-absent legs (proves the test is not tautological).
_EMIT_BEARING_BODY = """\
name: release
on:
  push:
    tags:
      - "v*"
jobs:
  notify-launcher:
    runs-on: ubuntu-latest
    steps:
      - name: Notify shopsystem-bc-launcher via repository_dispatch
        run: |
          curl -X POST \\
            -H "Authorization: token ${{ secrets.BC_LAUNCHER_DISPATCH_TOKEN }}" \\
            https://api.github.com/repos/dstengle/shopsystem-bc-launcher/dispatches \\
            -d '{"event_type": "repository_dispatch"}'
"""

# A body whose ONLY mention of the emit constants is in descriptive comments.
# This must NOT trip the assert-absent legs (the comment-vs-executable
# distinction is the whole point of the scenario).
_COMMENT_ONLY_BODY = """\
name: release
# This workflow no longer performs a repository_dispatch to
# dstengle/shopsystem-bc-launcher and uses no BC_LAUNCHER_DISPATCH_TOKEN.
on:
  push:
    tags:
      - "v*"
jobs:
  release-guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Guard tag matches pyproject  # not a dispatch
        run: python3 scripts/check_tag_matches_pyproject_version.py
"""


def _assert_no_emit(body: str) -> None:
    """The three assert-absent checks against an executable body."""
    assert "repository_dispatch" not in body
    assert "dstengle/shopsystem-bc-launcher" not in body
    assert "BC_LAUNCHER_DISPATCH_TOKEN" not in body


def test_executable_body_helper_strips_only_comments():
    """The comment-strip is real: a token in a full-line comment is removed,
    while an executable token on the same kind of line is retained."""
    body = _executable_body(_COMMENT_ONLY_BODY)
    assert "repository_dispatch" not in body
    assert "shopsystem-bc-launcher" not in body
    assert "BC_LAUNCHER_DISPATCH_TOKEN" not in body
    # The executable content survives the strip.
    assert "check_tag_matches_pyproject_version.py" in body
    assert "release-guard" in body


def test_inline_comment_is_stripped_executable_prefix_kept():
    line = 'run: do-thing  # repository_dispatch to bc-launcher'
    out = _strip_inline_comment(line)
    assert out == "run: do-thing"
    # And a `#` inside quotes is NOT treated as a comment.
    assert _strip_inline_comment("run: echo '#notacomment'") == "run: echo '#notacomment'"


def test_emit_bearing_executable_body_fails_assert_absent():
    """NON-VACUITY: if the emit WERE present in the executable region, the
    assert-absent legs must be RED. We assert each leg trips."""
    body = _executable_body(_EMIT_BEARING_BODY)
    # The emit constants survive the comment-strip because they are
    # executable, not commented.
    assert "repository_dispatch" in body or "/dispatches" in body
    assert "shopsystem-bc-launcher" in body
    assert "BC_LAUNCHER_DISPATCH_TOKEN" in body
    with pytest.raises(AssertionError):
        _assert_no_emit(body)


def test_comment_only_token_does_not_fail_assert_absent():
    """A token appearing only in a descriptive YAML comment, absent from the
    executable body, does NOT cause the assert-absent legs to fail."""
    body = _executable_body(_COMMENT_ONLY_BODY)
    _assert_no_emit(body)  # must not raise


# --------------------------------------------------------------------------
# The real pin: assert the ON-DISK release.yml executable body has no emit
# and retains the release-guard version-hygiene job (scenario 192).
# --------------------------------------------------------------------------

def test_release_yml_executable_body_has_no_bc_launcher_emit():
    wf = _release_workflow_path()
    assert wf.is_file(), f"missing release workflow at {wf}"
    body = _executable_body(wf.read_text())
    _assert_no_emit(body)
    # Structurally: no job/step targets a dispatches endpoint in the
    # executable body.
    parsed = yaml.safe_load(body)
    assert isinstance(parsed, dict)
    for job in (parsed.get("jobs") or {}).values():
        for step in (job.get("steps") or []):
            text = "\n".join(
                v for v in (step.get("uses"), step.get("run"), step.get("name"))
                if isinstance(v, str)
            )
            assert "dispatches" not in text


def test_release_yml_retains_release_guard_version_hygiene_job():
    wf = _release_workflow_path()
    body = _executable_body(wf.read_text())
    parsed = yaml.safe_load(body)
    jobs = parsed.get("jobs") or {}
    assert "release-guard" in jobs, (
        "the release-guard version-hygiene job (scenario 192) must remain "
        "present and undisturbed in the executable body"
    )
    guard = jobs["release-guard"]
    step_text = "\n".join(
        v
        for step in (guard.get("steps") or [])
        for v in (step.get("uses"), step.get("run"), step.get("name"))
        if isinstance(v, str)
    )
    assert "check_tag_matches_pyproject_version" in step_text, (
        "the release-guard job must still invoke the scenario-192 "
        "tag-equals-pyproject version guard"
    )
