"""Shared fixtures and pytest-bdd step definitions for shopsystem-templates.

The scenarios under features/ pin the BC's outward contract — the
`shop-templates` CLI surface and the structural section headers each
role-template markdown file carries. The CLI is invoked via subprocess
(the same boundary downstream callers use); content checks read the
template via the same CLI subcommand so any drift between the CLI's
view of the package data and the file system surfaces here.

Style mirrors shopsystem-messaging/tests/conftest.py and
shopsystem-scenarios/tests/conftest.py — subprocess + a `context` dict
fixture carrying cross-step state.
"""
from __future__ import annotations

import subprocess

import pytest
from pytest_bdd import given, parsers, then, when


# -----------------------------------------------------------------------
# Shared cross-step state
# -----------------------------------------------------------------------


@pytest.fixture
def context() -> dict:
    return {}


def _run_shop_templates(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["shop-templates", *args],
        capture_output=True,
        text=True,
    )


# -----------------------------------------------------------------------
# Given steps
# -----------------------------------------------------------------------


@given(
    parsers.parse(
        'a template name "{name}" that is in the list output by '
        '"shop-templates list"'
    )
)
def given_template_name_in_list(name: str, context: dict) -> None:
    # Verify empirically that the name appears in `shop-templates list`
    # output — the Given's contract is part of the scenario's premise and
    # a future drop of a template would silently undermine the When/Then
    # steps if we didn't check it here.
    result = _run_shop_templates("list")
    assert result.returncode == 0, (
        f"shop-templates list failed; stderr:\n{result.stderr}"
    )
    listed = result.stdout.strip().splitlines()
    assert name in listed, (
        f"premise of Given violated: {name!r} is not in shop-templates list "
        f"output {listed!r}"
    )
    context["available_templates"] = listed


@given(
    parsers.parse(
        'a template name "{name}" that is not in the list output by '
        '"shop-templates list"'
    )
)
def given_template_name_not_in_list(name: str, context: dict) -> None:
    result = _run_shop_templates("list")
    assert result.returncode == 0, (
        f"shop-templates list failed; stderr:\n{result.stderr}"
    )
    listed = result.stdout.strip().splitlines()
    assert name not in listed, (
        f"premise of Given violated: {name!r} unexpectedly appears in "
        f"shop-templates list output {listed!r}"
    )
    context["available_templates"] = listed


# -----------------------------------------------------------------------
# When steps
# -----------------------------------------------------------------------


@when(parsers.parse('I run "shop-templates list"'))
def when_run_list(context: dict) -> None:
    result = _run_shop_templates("list")
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr


@when(parsers.parse('I run "shop-templates show {name}"'))
def when_run_show(name: str, context: dict) -> None:
    result = _run_shop_templates("show", name)
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr
    context["shown_template_name"] = name


@when(
    parsers.parse(
        'I read the {name} template via "shop-templates show {name_again}"'
    )
)
def when_read_template_via_show(name: str, name_again: str, context: dict) -> None:
    # Belt-and-braces: the two name slots must agree, otherwise the
    # scenario text is internally inconsistent and any Then assertion
    # would be assertion-by-coincidence.
    assert name == name_again, (
        f"scenario inconsistency: 'the {name} template' but "
        f"'shop-templates show {name_again}'"
    )
    result = _run_shop_templates("show", name)
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr
    context["shown_template_name"] = name
    # The Then-steps for these scenarios refer to "the content" — keep an
    # explicit alias so the assertion language matches the feature text.
    context["template_content"] = result.stdout


# -----------------------------------------------------------------------
# Then steps — generic CLI assertions
# -----------------------------------------------------------------------


@then("the exit code is 0")
def then_exit_code_is_zero(context: dict) -> None:
    rc = context["cli_returncode"]
    assert rc == 0, (
        f"expected exit code 0; got {rc}; stderr:\n{context.get('cli_stderr', '')}"
    )


@then("the exit code is non-zero")
def then_exit_code_is_nonzero(context: dict) -> None:
    rc = context["cli_returncode"]
    assert rc != 0, (
        f"expected non-zero exit; got {rc}; stderr:\n{context.get('cli_stderr', '')}"
    )


@then("stderr is empty")
def then_stderr_is_empty(context: dict) -> None:
    stderr = context["cli_stderr"]
    assert stderr == "", f"expected empty stderr; got {stderr!r}"


@then("stdout is empty")
def then_stdout_is_empty(context: dict) -> None:
    stdout = context["cli_stdout"]
    assert stdout == "", f"expected empty stdout; got {stdout!r}"


# -----------------------------------------------------------------------
# Then steps — shop-templates list shape
# -----------------------------------------------------------------------


@then(
    parsers.re(
        r'stdout is exactly the four names '
        r'"(?P<n1>[^"]+)", "(?P<n2>[^"]+)", "(?P<n3>[^"]+)", "(?P<n4>[^"]+)", '
        r'one per line in that sorted order'
    )
)
def then_stdout_is_exactly_four_names_sorted(
    n1: str, n2: str, n3: str, n4: str, context: dict
) -> None:
    expected = [n1, n2, n3, n4]
    # Pin the sorted-order contract explicitly: if the scenario text
    # claims "sorted order" but the literal sequence supplied is not
    # actually sorted, the scenario is internally inconsistent and the
    # downstream assertion would be meaningless.
    assert expected == sorted(expected), (
        f"scenario premise violated: supplied names {expected!r} are not "
        f"in sorted order"
    )
    stdout = context["cli_stdout"]
    # The CLI uses print() per line, which emits a trailing newline after
    # the last line. Split on newlines and drop the final empty entry
    # that comes from that trailing newline.
    lines = stdout.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    assert lines == expected, (
        f"expected stdout lines {expected!r}; got {lines!r}"
    )


# -----------------------------------------------------------------------
# Then steps — shop-templates show byte-for-byte equivalence
# -----------------------------------------------------------------------


@then(
    "stdout equals the package-data file contents for that template, "
    "byte-for-byte (no extra trailing newline beyond what the file itself carries)"
)
def then_stdout_equals_package_data_byte_for_byte(context: dict) -> None:
    # Re-read the underlying template through the same package-data
    # boundary the CLI uses. Importing inside the step (rather than at
    # module top) keeps the conftest cleanly isolated from src/ — only
    # this assertion needs the boundary helper, and only at run time.
    from shop_templates.cli import _read_template

    name = context["shown_template_name"]
    expected = _read_template(name)
    assert expected is not None, (
        f"premise of Then violated: package data has no template named {name!r}"
    )
    actual = context["cli_stdout"]
    assert actual == expected, (
        f"shop-templates show {name} did not emit byte-identical content "
        f"to the package-data file.\n"
        f"len(expected)={len(expected)} len(actual)={len(actual)}\n"
        f"expected_repr_tail={expected[-40:]!r}\n"
        f"actual_repr_tail={actual[-40:]!r}"
    )


# -----------------------------------------------------------------------
# Then steps — shop-templates show unknown-template error shape
# -----------------------------------------------------------------------


@then(parsers.parse('stderr names the offending input "{name}"'))
def then_stderr_names_offending_input(name: str, context: dict) -> None:
    stderr = context["cli_stderr"]
    assert name in stderr, (
        f"expected stderr to name offending input {name!r}; got:\n{stderr}"
    )


@then(
    "stderr cites the list of available templates so the caller can recover"
)
def then_stderr_cites_available_templates(context: dict) -> None:
    stderr = context["cli_stderr"]
    # "cites the list" is satisfied when at least one real template name
    # appears in stderr — the caller can derive the available set from
    # there. We require every known template name to appear, which is
    # the strongest reading of "cites the list" and matches the
    # implementation's `Available: <comma-joined names>` shape.
    available = context.get("available_templates")
    if available is None:
        # Recover the list directly if a preceding Given did not stash it.
        result = _run_shop_templates("list")
        assert result.returncode == 0, (
            f"shop-templates list failed; stderr:\n{result.stderr}"
        )
        available = result.stdout.strip().splitlines()
    for name in available:
        assert name in stderr, (
            f"expected stderr to cite available template {name!r}; got:\n{stderr}"
        )


# -----------------------------------------------------------------------
# Then steps — template content / section-header assertions
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'the content contains a "{section_header}" section header'
    )
)
def then_content_contains_section_header(
    section_header: str, context: dict
) -> None:
    content = context["template_content"]
    assert section_header in content, (
        f"template {context.get('shown_template_name')!r} is missing "
        f"section header {section_header!r}"
    )


@then(
    'the content names "empirical" pre-state verification as the discipline '
    "for choosing between assign_scenarios, request_bugfix, and request_maintenance"
)
def then_content_names_empirical_pre_state_verification(context: dict) -> None:
    content = context["template_content"].lower()
    # Pin Finding 17 / S16: the discriminator is "empirical". The
    # surrounding message-type vocabulary must also appear so this isn't
    # satisfied by an unrelated use of "empirical" elsewhere in the
    # template.
    assert "empirical" in content, (
        "template must use the word 'empirical' for pre-state verification "
        "(Finding 17 / S16)"
    )
    for token in (
        "assign_scenarios",
        "request_bugfix",
        "request_maintenance",
    ):
        assert token in content, (
            f"template must reference message-type {token!r} in the "
            "pre-state-verification discipline section"
        )


@then(
    'the content distinguishes "reading code" (hypothesis) from "running it" '
    "(fact) as the basis for that choice"
)
def then_content_distinguishes_reading_from_running(context: dict) -> None:
    content = context["template_content"].lower()
    # The Finding 17 prose introduced the
    # "reading code is hypothesis / running it is fact" distinction. Pin
    # both halves of the contrast — either alone is satisfiable by an
    # unrelated sentence, but both together unambiguously identify this
    # discipline.
    assert "reading code" in content, (
        "template must reference 'reading code' as the hypothesis side of "
        "the pre-state-verification distinction (Finding 17 / S16)"
    )
    assert "running it" in content, (
        "template must reference 'running it' as the fact side of the "
        "pre-state-verification distinction (Finding 17 / S16)"
    )
    assert "hypothesis" in content, (
        "template must label the 'reading code' side as a hypothesis "
        "(Finding 17 / S16)"
    )
    assert "fact" in content, (
        "template must label the 'running it' side as a fact "
        "(Finding 17 / S16)"
    )


# -----------------------------------------------------------------------
# Then steps — role-complete restructure: identity / posture / CLI ordering
# -----------------------------------------------------------------------
#
# Scenarios lead-kq0 (f1ac9534c1d58318, e522f7393dfcd1c1, a481db51463526d2,
# a6b3e510821aba52) pin the structural ordering of the lead-po and
# lead-architect templates: role identity (depth-1 #) and default-posture
# header (depth-2 ##) must lead the document, and procedural shop-msg CLI
# content must come after both the posture header AND after every §3.2
# activity has been named at least once. The §3.2 activity lists for each
# role are hard-coded below because the scenarios reference them by index
# ("scenario 10" / "scenario 14") within the dispatched feature file.

_LEAD_PO_ACTIVITY_NAMES_FROM_SCENARIO_10 = (
    "Interview stakeholder",
    "Maintain product brief",
    "Write PDR for new functionality",
    "Write Gherkin scenarios",
    "Respond to BC `clarify`",
)

_LEAD_ARCHITECT_ACTIVITY_NAMES_FROM_SCENARIO_14 = (
    "Write ADRs",
    "Maintain structurizr workspace",
    "Collaborate with PO on BC decomposition",
    "Assign scenarios to BCs",
    "Reconcile scenario registers",
    # The naming scenario phrases this one as an alternation:
    # either "Send `request_bugfix`" appears OR both message-type names
    # appear. Treat the canonical token as `request_bugfix` for ordering
    # purposes — that is the substring all renderings share.
    "request_bugfix",
    "Read a BC-shop's card via `request_shop_card`",
    "Respond to BC `clarify`",
)


def _first_index(content: str, needle: str) -> int:
    idx = content.find(needle)
    assert idx >= 0, f"expected substring {needle!r} to appear in content"
    return idx


@then(parsers.parse('a "{header}" identity header appears in the output'))
def then_identity_header_appears(header: str, context: dict) -> None:
    # The identity header is the depth-1 (#) heading that opens the role
    # prompt — the bare-presence check; ordering is asserted by separate
    # byte-offset steps below.
    content = context["template_content"]
    assert header in content, (
        f"template {context.get('shown_template_name')!r} is missing identity "
        f"header {header!r}"
    )
    # Stash the offset for the byte-offset Then steps that follow.
    context["identity_header_offset"] = content.index(header)


@then(parsers.parse('a "{header}" posture header appears in the output'))
def then_posture_header_appears(header: str, context: dict) -> None:
    content = context["template_content"]
    assert header in content, (
        f"template {context.get('shown_template_name')!r} is missing posture "
        f"header {header!r}"
    )
    context["posture_header_offset"] = content.index(header)
    context["posture_header_text"] = header


@then(
    parsers.parse(
        'the byte offset of the identity header is less than the byte offset '
        'of the first occurrence of the string "{needle}"'
    )
)
def then_identity_before_needle(needle: str, context: dict) -> None:
    content = context["template_content"]
    identity_offset = context["identity_header_offset"]
    needle_offset = _first_index(content, needle)
    assert identity_offset < needle_offset, (
        f"identity header at byte {identity_offset} must precede first "
        f"{needle!r} at byte {needle_offset}; template "
        f"{context.get('shown_template_name')!r}"
    )


@then(
    parsers.parse(
        'the byte offset of the posture header is less than the byte offset '
        'of the first occurrence of the string "{needle}"'
    )
)
def then_posture_before_needle(needle: str, context: dict) -> None:
    content = context["template_content"]
    posture_offset = context["posture_header_offset"]
    needle_offset = _first_index(content, needle)
    assert posture_offset < needle_offset, (
        f"posture header at byte {posture_offset} must precede first "
        f"{needle!r} at byte {needle_offset}; template "
        f"{context.get('shown_template_name')!r}"
    )


# -----------------------------------------------------------------------
# Then steps — role-complete restructure: §3.2 activity coverage
# -----------------------------------------------------------------------
#
# Scenarios dddd6c3b2eed7e45 (PO) and 0aea22a97e63d4f8 (Architect) pin
# that each §3.2 activity must be NAMED in the template. The qualifier
# variant additionally asserts that a qualifier word appears in proximity
# to the activity name. The alternation variant accepts either the
# "Send `request_bugfix`" phrasing or both bare message-type names.


@then(
    parsers.re(
        r'^the content names the activity "(?P<activity>[^"]+)"$'
    )
)
def then_content_names_activity(activity: str, context: dict) -> None:
    content = context["template_content"]
    assert activity in content, (
        f"template {context.get('shown_template_name')!r} does not name §3.2 "
        f"activity {activity!r}"
    )


@then(
    parsers.re(
        r'^the content names the activity "(?P<activity>[^"]+)" with the '
        r'qualifier "(?P<qualifier>[^"]+)"$'
    )
)
def then_content_names_activity_with_qualifier(
    activity: str, qualifier: str, context: dict
) -> None:
    content = context["template_content"]
    assert activity in content, (
        f"template {context.get('shown_template_name')!r} does not name §3.2 "
        f"activity {activity!r}"
    )
    # The qualifier must appear in the same paragraph / contiguous block as
    # the activity name. We approximate "same block" as: somewhere within
    # 200 bytes after the activity name OR on the same line. That's broad
    # enough to allow a parenthetical, a sentence-following clause, or the
    # next sentence, but tight enough that the qualifier is contextually
    # bound to the activity rather than an unrelated mention elsewhere.
    idx = content.index(activity)
    window = content[idx : idx + 200 + len(activity)]
    assert qualifier in window, (
        f"qualifier {qualifier!r} must appear near activity {activity!r} in "
        f"template {context.get('shown_template_name')!r}; window after "
        f"activity:\n{window!r}"
    )


@then(
    parsers.re(
        r'^the content names the activity "(?P<activity>[^"]+)" with the '
        r'qualifier "(?P<q1>[^"]+)" or "(?P<q2>[^"]+)"$'
    )
)
def then_content_names_activity_with_either_qualifier(
    activity: str, q1: str, q2: str, context: dict
) -> None:
    content = context["template_content"]
    assert activity in content, (
        f"template {context.get('shown_template_name')!r} does not name §3.2 "
        f"activity {activity!r}"
    )
    idx = content.index(activity)
    window = content[idx : idx + 200 + len(activity)]
    assert q1 in window or q2 in window, (
        f"at least one of qualifiers {q1!r} / {q2!r} must appear near "
        f"activity {activity!r} in template "
        f"{context.get('shown_template_name')!r}; window after activity:\n"
        f"{window!r}"
    )


@then(
    parsers.re(
        r'^the content names the activity "(?P<activity>[^"]+)" or '
        r'equivalently mentions both "(?P<token_a>[^"]+)" and '
        r'"(?P<token_b>[^"]+)" as dispatch vehicles$'
    )
)
def then_content_names_activity_or_equivalent_pair(
    activity: str, token_a: str, token_b: str, context: dict
) -> None:
    content = context["template_content"]
    # Either: the explicit "Send `request_bugfix`" phrasing appears,
    # OR both message-type names appear somewhere in the content. The
    # latter satisfies the §3.2 activity entry "Send `request_bugfix` /
    # `request_maintenance`" without forcing the template to repeat the
    # "Send " prefix.
    if activity in content:
        return
    assert token_a in content and token_b in content, (
        f"template {context.get('shown_template_name')!r} must either name "
        f"activity {activity!r} OR mention both {token_a!r} and {token_b!r} "
        f"as dispatch vehicles; neither condition held"
    )


# -----------------------------------------------------------------------
# Given + Then steps — §3.2 activity guidance coverage (scenarios
# 9a9421ad59ee5d67 and 5ccb3fb1122f9341)
# -----------------------------------------------------------------------
#
# The Given step stashes the activity list (literal phrasing as it
# appears in the dispatched scenario) on context. The Then step iterates
# that list and, for each activity, verifies either:
#   (a) the activity name appears on a line that also contains a colon
#       followed by non-whitespace prose (one-line guidance), OR
#   (b) the activity name appears as a subsection heading whose body
#       carries at least one sentence of prose, OR
#   (c) within a 240-byte window after the activity name the literal
#       phrase "guidance pending" appears (case-insensitive).
# The "no bare list item" assertion checks that no line of the form
# "- <activity>" or "* <activity>" exists without trailing colon/prose.


def _activity_block_satisfies_guidance(content: str, activity: str) -> tuple[bool, str]:
    """Return (ok, reason) for the activity-guidance check.

    The check accepts any of three shapes:
      1. "guidance pending" within a 240-byte window after the activity
         name (case-insensitive).
      2. A line that names the activity AND contains a colon followed by
         non-whitespace prose on the same line — one-line guidance.
      3. A subsection heading (## or ### or ####) whose text names the
         activity, with at least one non-blank, non-heading line after
         it in the same subsection — multi-line guidance.
    """
    lower_content = content.lower()
    lower_activity = activity.lower()

    # Shape 1: explicit "guidance pending" marker near the activity.
    idx = lower_content.find(lower_activity)
    while idx != -1:
        window = lower_content[idx : idx + 240 + len(lower_activity)]
        if "guidance pending" in window:
            return True, "guidance-pending marker present"
        idx = lower_content.find(lower_activity, idx + 1)

    # Shapes 2 and 3: walk line by line.
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if activity not in line:
            continue
        stripped = line.lstrip()
        # Shape 3: heading naming the activity.
        if stripped.startswith("#"):
            # Look for at least one non-blank, non-heading line after.
            for j in range(i + 1, len(lines)):
                follow = lines[j].strip()
                if follow.startswith("#"):
                    break  # next heading reached; no body in this subsection
                if follow:
                    return True, "subsection-with-body"
            # Heading with no body — fall through to bare-list check.
            continue
        # Shape 2: one-line guidance. Activity name followed by a colon
        # and then non-whitespace on the same line.
        after = line.split(activity, 1)[1]
        if ":" in after:
            tail = after.split(":", 1)[1]
            if tail.strip():
                return True, "one-line guidance"
        # Bullet line with just the activity name and nothing else after.
        # Continue scanning — another occurrence might satisfy.
    return False, "no satisfying block found"


@given(
    parsers.re(
        r'^the §3\.2 PO activities (?P<activity_list>".+")$'
    )
)
def given_po_activity_list(activity_list: str, context: dict) -> None:
    # `activity_list` is the literal comma- and "and"-separated tail
    # after "the §3.2 PO activities ". Extract each quoted activity name
    # in order; ", and " is just punctuation between items.
    import re

    items = re.findall(r'"([^"]+)"', activity_list)
    assert items, (
        f"Given step parsed no activity names out of {activity_list!r}"
    )
    context["activity_list"] = items


@given(
    parsers.re(
        r'^the §3\.2 Architect activities (?P<activity_list>".+")$'
    )
)
def given_architect_activity_list(activity_list: str, context: dict) -> None:
    import re

    items = re.findall(r'"([^"]+)"', activity_list)
    assert items, (
        f"Given step parsed no activity names out of {activity_list!r}"
    )
    context["activity_list"] = items


@then(
    'for each activity in that list, the content has a contiguous block — '
    'either a subsection that names the activity or a line that names the '
    'activity — that contains at minimum one sentence of guidance OR an '
    'explicit marker of the form "guidance pending" (case-insensitive)'
)
def then_each_activity_has_guidance(context: dict) -> None:
    content = context["template_content"]
    activities = context["activity_list"]
    failures: list[str] = []
    for activity in activities:
        ok, reason = _activity_block_satisfies_guidance(content, activity)
        if not ok:
            failures.append(f"  - {activity!r}: {reason}")
    assert not failures, (
        f"template {context.get('shown_template_name')!r} has activities "
        f"without guidance or a 'guidance pending' marker:\n"
        + "\n".join(failures)
    )


@then(
    parsers.re(
        r'^no §3\.2 (PO|Architect) activity appears as a bare list item with '
        r'neither guidance nor a "guidance pending" marker$'
    )
)
def then_no_bare_list_item(context: dict) -> None:
    content = context["template_content"]
    activities = context["activity_list"]
    lower = content.lower()
    failures: list[str] = []
    for activity in activities:
        # A bare list item is a line that starts with a bullet marker
        # (- or *) followed by only the activity name and optional
        # whitespace, with no trailing prose on the same line AND no
        # "guidance pending" marker in the immediate vicinity.
        for line in content.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("- ") or stripped.startswith("* ")):
                continue
            payload = stripped[2:].strip()
            if payload != activity:
                continue
            # Bare list item suspected. Check for nearby guidance-pending.
            idx = lower.find(activity.lower())
            window = lower[idx : idx + 240 + len(activity)]
            if "guidance pending" not in window:
                failures.append(
                    f"  - {activity!r}: bare list item without guidance "
                    f"or 'guidance pending' marker"
                )
    assert not failures, (
        f"template {context.get('shown_template_name')!r} has bare §3.2 "
        f"activity list items:\n" + "\n".join(failures)
    )


# -----------------------------------------------------------------------
# Then steps — role-complete restructure: CLI subordination ordering
# (scenarios e522f7393dfcd1c1 and a6b3e510821aba52)
# -----------------------------------------------------------------------


@then(
    'every heading whose text mentions "shop-msg" appears at heading depth '
    'three (###) or deeper, never at depth two (##) or depth one (#)'
)
def then_shop_msg_headings_depth_three_or_deeper(context: dict) -> None:
    content = context["template_content"]
    offenders: list[tuple[int, str]] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            continue
        if "shop-msg" not in stripped:
            continue
        # Count the leading # characters to determine depth.
        depth = 0
        for ch in stripped:
            if ch == "#":
                depth += 1
            else:
                break
        if depth < 3:
            offenders.append((lineno, line.rstrip()))
    assert not offenders, (
        f"template {context.get('shown_template_name')!r} has shop-msg "
        f"headings at depth < 3:\n"
        + "\n".join(f"  line {n}: {l!r}" for n, l in offenders)
    )


@then(
    parsers.parse(
        'the first occurrence of the substring "shop-msg" in the content '
        'appears after the "{header}" header'
    )
)
def then_first_shop_msg_after_header(header: str, context: dict) -> None:
    content = context["template_content"]
    header_idx = content.find(header)
    assert header_idx >= 0, (
        f"premise of Then violated: template "
        f"{context.get('shown_template_name')!r} is missing header {header!r}"
    )
    shop_msg_idx = content.find("shop-msg")
    assert shop_msg_idx >= 0, (
        f"premise of Then violated: template "
        f"{context.get('shown_template_name')!r} has no 'shop-msg' substring"
    )
    assert header_idx < shop_msg_idx, (
        f"header {header!r} at byte {header_idx} must precede first "
        f"'shop-msg' at byte {shop_msg_idx} in template "
        f"{context.get('shown_template_name')!r}"
    )


@then(
    parsers.re(
        r'^the first occurrence of the substring "shop-msg" in the content '
        r'appears after every §3\.2 (?P<role>PO|Architect) activity name '
        r'from scenario (?P<scen_idx>\d+) has appeared at least once$'
    )
)
def then_first_shop_msg_after_all_activities(
    role: str, scen_idx: str, context: dict
) -> None:
    content = context["template_content"]
    if role == "PO":
        activities = _LEAD_PO_ACTIVITY_NAMES_FROM_SCENARIO_10
    elif role == "Architect":
        activities = _LEAD_ARCHITECT_ACTIVITY_NAMES_FROM_SCENARIO_14
    else:
        raise AssertionError(f"unrecognized role {role!r}")
    shop_msg_idx = content.find("shop-msg")
    assert shop_msg_idx >= 0, (
        f"premise of Then violated: template "
        f"{context.get('shown_template_name')!r} has no 'shop-msg' substring"
    )
    missing: list[str] = []
    too_late: list[tuple[str, int, int]] = []
    for activity in activities:
        idx = content.find(activity)
        if idx < 0:
            missing.append(activity)
            continue
        if idx >= shop_msg_idx:
            too_late.append((activity, idx, shop_msg_idx))
    assert not missing, (
        f"premise of Then violated: template "
        f"{context.get('shown_template_name')!r} is missing §3.2 {role} "
        f"activity name(s): {missing!r}"
    )
    assert not too_late, (
        f"first 'shop-msg' at byte {shop_msg_idx} in template "
        f"{context.get('shown_template_name')!r} precedes §3.2 {role} "
        f"activity name(s) (each must appear at least once before):\n"
        + "\n".join(
            f"  - {a!r} first appears at byte {ai} (>= {smi})"
            for a, ai, smi in too_late
        )
    )
