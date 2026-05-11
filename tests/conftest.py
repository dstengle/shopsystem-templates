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
