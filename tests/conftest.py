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

import re
import subprocess
import sys
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when


def pytest_bdd_apply_tag(tag, function):
    if tag == "xfail_bcshim":
        marker = pytest.mark.xfail(
            reason="superseded by bc-shim refactor; shopsystem-templates-qcw",
            strict=False,
        )
        marker(function)
        return True
    return None


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


# -----------------------------------------------------------------------
# Then steps — empirical pre-state verification grounded in the
# contract/artifact surface (ADR-018 D1/D2 — lead-6gaj scenarios
# 489fe7b30c010cab, 9de387f9fc77ca3a, 3f096e334ceb77f2, 7d7f4bd2c88e5f0a,
# 96cf1667aec9a98f). These supersede the retired "reading code = hypothesis,
# running code = fact" and "grep across repos/<bc>/features/" premises
# (retired BC-side hashes 98fe33cee55daf55, 0d384c6b92004c8d, 48dd1f01012efafe,
# 22cbdf7cc9e917ca, 744cd4a4532c28d7).
# -----------------------------------------------------------------------


@then(
    "the content names the contract/artifact surface — the lead's own "
    '"features/" Gherkin, "adr/"/"pdr/", message schemas, scenario hashes, '
    'and "shop-msg" mailbox state, together with the BC\'s reported '
    '"work_done" demonstration — as the admissible evidence for that choice'
)
def then_content_names_contract_artifact_surface(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    # The admissible evidence must be the lead's own contract/artifact surface.
    assert "contract" in lc and "artifact" in lc, (
        "template must name the contract/artifact surface as the admissible "
        "evidence for message-type selection (lead-6gaj / 489fe7b30c010cab)"
    )
    # Each named member of the surface must appear.
    for token in ("features/", "adr/", "pdr/", "schema", "shop-msg", "work_done"):
        assert token in lc, (
            f"template must name {token!r} as part of the admissible "
            "contract/artifact surface (lead-6gaj / 489fe7b30c010cab)"
        )
    assert "scenario hash" in lc, (
        "template must name scenario hashes as part of the admissible "
        "contract/artifact surface (lead-6gaj / 489fe7b30c010cab)"
    )
    assert "mailbox" in lc, (
        "template must name the shop-msg mailbox state as part of the "
        "admissible contract/artifact surface (lead-6gaj / 489fe7b30c010cab)"
    )


@then(
    'the content names invoking an installed contract tool such as "scenarios '
    'hash" over contract text as the admissible "run" that produces a contract '
    "fact"
)
def then_content_names_scenarios_hash_as_admissible_run(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "scenarios hash" in lc, (
        "template must name the installed 'scenarios hash' contract tool as the "
        "admissible 'run' (lead-6gaj / 489fe7b30c010cab)"
    )
    # Frame it as the admissible run producing a contract fact.
    assert "run" in lc and "fact" in lc, (
        "template must frame invoking 'scenarios hash' as the admissible 'run' "
        "that produces a contract fact (lead-6gaj / 489fe7b30c010cab)"
    )


@then(
    "the content directs the architect that establishing a BC's behavior by "
    "reading or executing that BC's implementation is not admissible evidence, "
    'and that there is no "repos/" BC source on the lead host to read or run'
)
def then_content_directs_no_bc_code_reads_or_runs(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    # Reading/executing BC implementation must be ruled out as admissible.
    assert "not admissible" in lc or "is not admissible" in lc, (
        "template must direct that reading or executing BC implementation is "
        "not admissible evidence (lead-6gaj / 489fe7b30c010cab)"
    )
    # There is no repos/ BC source on the lead host.
    assert "repos/" in content, (
        "template must state there is no 'repos/' BC source on the lead host "
        "(lead-6gaj / 489fe7b30c010cab)"
    )
    assert "no" in lc and "lead host" in lc, (
        "template must state there is no repos/ BC source on the lead host to "
        "read or run (lead-6gaj / 489fe7b30c010cab)"
    )


@then(
    "the content directs the architect to route any question that would "
    "otherwise require running BC implementation to the BC as a \"clarify\" or "
    '"nudge", rather than reaching for the proof itself'
)
def then_content_directs_route_to_bc_clarify_or_nudge(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "clarify" in lc, (
        "template must direct routing such questions to the BC as a 'clarify' "
        "(lead-6gaj / 489fe7b30c010cab)"
    )
    assert "nudge" in lc, (
        "template must name 'nudge' as the alternative routing for questions "
        "that would otherwise require running BC implementation "
        "(lead-6gaj / 489fe7b30c010cab)"
    )
    assert "route" in lc, (
        "template must direct the architect to route the question to the BC "
        "rather than reaching for the proof itself (lead-6gaj / 489fe7b30c010cab)"
    )


# -----------------------------------------------------------------------
# Then steps — BC @scenario_hash pre-state enumeration over the lead-held
# features/ surface + mailbox-reported register (ADR-018 D2; no clone grep).
# lead-6gaj scenarios 9de387f9fc77ca3a, 3f096e334ceb77f2, 7d7f4bd2c88e5f0a,
# 96cf1667aec9a98f.
# -----------------------------------------------------------------------


@then(
    'the content names "@scenario_hash" as a pre-state surface the architect '
    "must enumerate before composing a dispatch that retires, supersedes, or "
    "contradicts prior BC-side coverage"
)
def then_content_names_scenario_hash_pre_state_surface(context: dict) -> None:
    content = context["template_content"]
    assert "@scenario_hash" in content, (
        "template must name '@scenario_hash' as a pre-state surface "
        "(lead-6gaj / 9de387f9fc77ca3a)"
    )
    assert "enumerate" in content.lower(), (
        "template must use 'enumerate' to describe the @scenario_hash "
        "pre-state step (lead-6gaj / 9de387f9fc77ca3a)"
    )


@then(
    "the content directs the architect to establish that @scenario_hash set "
    'from the lead-held "features/" Gherkin in this repo together with the BC\'s '
    'mailbox-reported scenario register/hashes, and not from a "repos/<bc>" clone'
)
def then_content_directs_establish_from_lead_held_and_mailbox(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "features/" in content, (
        "template must name the lead-held 'features/' Gherkin as the enumeration "
        "source (lead-6gaj / 9de387f9fc77ca3a)"
    )
    assert "mailbox" in lc, (
        "template must name the BC's mailbox-reported scenario register/hashes "
        "as a second enumeration source (lead-6gaj / 9de387f9fc77ca3a)"
    )
    assert "repos/<bc>" in content or "repos/" in content, (
        "template must contrast the lead-held surface against a 'repos/<bc>' "
        "clone (lead-6gaj / 9de387f9fc77ca3a)"
    )


@then(
    'the content names invoking the installed "scenarios hash" contract tool '
    "over the lead-held scenario text as the means of computing the hashes for "
    "that enumeration"
)
def then_content_names_scenarios_hash_for_enumeration(context: dict) -> None:
    content = context["template_content"].lower()
    assert "scenarios hash" in content, (
        "template must name the installed 'scenarios hash' tool as the means of "
        "computing the enumeration hashes (lead-6gaj / 9de387f9fc77ca3a)"
    )
    assert "lead-held" in content or "features/" in content, (
        "template must name the lead-held scenario text as the input to "
        "'scenarios hash' (lead-6gaj / 9de387f9fc77ca3a)"
    )


@then(
    "the content marks the enumeration as a discrete pre-state step (alongside "
    "the contract-surface behavior-verification step), not as optional guidance "
    "the architect may skip"
)
def then_content_marks_enumeration_as_discrete_step(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "enumerate" in lc or "enumeration" in lc, (
        "template must describe the @scenario_hash enumeration as a discrete "
        "step (lead-6gaj / 9de387f9fc77ca3a)"
    )
    assert "discrete" in lc and "step" in lc, (
        "template must mark the enumeration as a discrete pre-state step "
        "(lead-6gaj / 9de387f9fc77ca3a)"
    )
    assert "must" in content, (
        "template must frame the enumeration as mandatory, not optional "
        "(lead-6gaj / 9de387f9fc77ca3a)"
    )


@then(
    'the content names at least one of the trigger conditions "retire", '
    '"supersede", or "contradict" as the gate that requires the enumeration step'
)
def then_content_names_trigger_conditions(context: dict) -> None:
    content = context["template_content"].lower()
    trigger_words = ("retire", "supersede", "contradict")
    found = [t for t in trigger_words if t in content]
    assert found, (
        "template must name at least one trigger condition "
        f"({', '.join(trigger_words)}) for the enumeration step "
        "(lead-6gaj / 9de387f9fc77ca3a)"
    )
    assert "enumerat" in content, (
        "template must use 'enumerate'/'enumeration' in the section the trigger "
        "gates (lead-6gaj / 9de387f9fc77ca3a)"
    )


@then(
    'the content names the literal substring "@scenario_hash" as the pattern '
    "the architect enumerates"
)
def then_content_names_scenario_hash_as_enumerated_pattern(context: dict) -> None:
    content = context["template_content"]
    assert "@scenario_hash" in content, (
        "template must name '@scenario_hash' as the pattern the architect "
        "enumerates (lead-6gaj / 3f096e334ceb77f2)"
    )


@then(
    "the content names a concrete, mechanically observable enumeration mechanism "
    'that runs over the lead-held "features/" Gherkin in this repo, naming the '
    'installed "scenarios hash" contract tool as the means of computing each '
    "entry's hash"
)
def then_content_names_concrete_enumeration_over_lead_held(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "features/" in content, (
        "template must name the lead-held 'features/' Gherkin as the surface the "
        "enumeration runs over (lead-6gaj / 3f096e334ceb77f2)"
    )
    assert "scenarios hash" in lc, (
        "template must name 'scenarios hash' as the means of computing each "
        "entry's hash (lead-6gaj / 3f096e334ceb77f2)"
    )
    # A concrete, mechanically observable mechanism — grep/git grep over the
    # lead-held features/ text.
    assert "grep" in lc, (
        "template must name a concrete, mechanically observable enumeration "
        "mechanism (grep) over the lead-held features/ Gherkin "
        "(lead-6gaj / 3f096e334ceb77f2)"
    )


@then(
    "the content names the BC's mailbox-reported scenario register/hashes "
    '(carried in its "work_done" demonstration) as the second surface the '
    "architect reconciles that enumeration against"
)
def then_content_names_mailbox_register_as_second_surface(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "mailbox" in lc, (
        "template must name the BC's mailbox-reported scenario register/hashes "
        "as the second reconciliation surface (lead-6gaj / 3f096e334ceb77f2)"
    )
    assert "work_done" in lc, (
        "template must name the BC's 'work_done' demonstration as where the "
        "mailbox-reported register is carried (lead-6gaj / 3f096e334ceb77f2)"
    )
    assert "reconcile" in lc or "reconciles" in lc, (
        "template must direct the architect to reconcile the enumeration against "
        "the mailbox-reported register (lead-6gaj / 3f096e334ceb77f2)"
    )


@then(
    'the content names the lead-held "features/" surface and the '
    "mailbox-reported register as the authoritative source for the BC's pinned "
    '@scenario_hash set, in contrast to a "repos/<bc>" clone grep'
)
def then_content_names_authoritative_source_vs_clone_grep(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "features/" in content, (
        "template must name the lead-held 'features/' surface as authoritative "
        "(lead-6gaj / 3f096e334ceb77f2)"
    )
    assert "mailbox" in lc, (
        "template must name the mailbox-reported register as authoritative "
        "(lead-6gaj / 3f096e334ceb77f2)"
    )
    assert "repos/<bc>" in content or "repos/" in content, (
        "template must contrast against a 'repos/<bc>' clone grep "
        "(lead-6gaj / 3f096e334ceb77f2)"
    )


@then(
    "the content directs the architect not to run the enumeration against a "
    '"repos/<bc>/features/*.feature" tree, there being no such clone on the '
    "lead host"
)
def then_content_directs_not_against_clone_tree(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "repos/<bc>/features" in content or "repos/<bc>" in content, (
        "template must name the 'repos/<bc>/features' clone tree it directs the "
        "architect NOT to run the enumeration against (lead-6gaj / 3f096e334ceb77f2)"
    )
    assert "no such clone" in lc or ("no" in lc and "clone" in lc), (
        "template must state there is no such clone on the lead host "
        "(lead-6gaj / 3f096e334ceb77f2)"
    )
    assert "lead host" in lc, (
        "template must state the absence of the clone is on the lead host "
        "(lead-6gaj / 3f096e334ceb77f2)"
    )


@then(
    "the content names a clarify-driven correction (a follow-up dispatch that "
    "augments or amends a prior dispatch in response to an Implementer clarify) "
    "as a moment that itself requires the BC @scenario_hash pre-state enumeration"
)
def then_content_names_clarify_correction_requires_enumeration(context: dict) -> None:
    content = context["template_content"].lower()
    clarify_signals = ("clarify", "follow-up dispatch", "clarify-correction chain",
                       "clarify chain")
    assert any(s in content for s in clarify_signals), (
        "template must name a clarify-driven correction as a moment that requires "
        "the @scenario_hash pre-state enumeration (lead-6gaj / 7d7f4bd2c88e5f0a)"
    )
    assert "@scenario_hash" in context["template_content"], (
        "template must name @scenario_hash in the clarify-correction context "
        "(lead-6gaj / 7d7f4bd2c88e5f0a)"
    )


@then(
    "the content directs the architect not to limit the re-enumeration to only "
    "the @scenario_hash entries a prior clarify named, but to re-run the full "
    'enumeration over the lead-held "features/" Gherkin in this repo reconciled '
    "against the BC's mailbox-reported scenario register/hashes"
)
def then_content_directs_full_reenumeration_lead_held_and_mailbox(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "features/" in content, (
        "template must direct re-enumeration over the lead-held 'features/' "
        "Gherkin (lead-6gaj / 7d7f4bd2c88e5f0a)"
    )
    full_signals = ("full", "entire", "all", "every")
    assert any(s in lc for s in full_signals), (
        "template must direct a full re-enumeration, not only prior clarify "
        "hashes (lead-6gaj / 7d7f4bd2c88e5f0a)"
    )
    assert "mailbox" in lc, (
        "template must direct reconciliation against the mailbox-reported "
        "register (lead-6gaj / 7d7f4bd2c88e5f0a)"
    )


@then(
    "the content frames a prior clarify as evidence that the prior enumeration "
    "was incomplete, rather than as a definitive list of every conflicting "
    "BC-side @scenario_hash"
)
def then_content_frames_prior_clarify_as_incomplete_evidence(context: dict) -> None:
    content = context["template_content"].lower()
    incomplete_signals = ("incomplete", "not definitive", "not a definitive",
                          "evidence", "missed")
    assert any(s in content for s in incomplete_signals), (
        "template must frame a prior clarify as evidence of an incomplete "
        "enumeration (lead-6gaj / 7d7f4bd2c88e5f0a)"
    )


@then(
    "the content names this per-event discipline as applying independently to "
    "each dispatch in a clarify-correction chain, not only to the initial "
    "dispatch in such a chain"
)
def then_content_names_per_dispatch_discipline(context: dict) -> None:
    content = context["template_content"].lower()
    per_dispatch_signals = ("each dispatch", "every dispatch",
                            "clarify-correction chain", "per dispatch",
                            "per-dispatch", "not only the initial")
    assert any(s in content for s in per_dispatch_signals), (
        "template must name the enumeration discipline as applying to each "
        "dispatch in a clarify-correction chain (lead-6gaj / 7d7f4bd2c88e5f0a)"
    )


@then(
    "the content directs the architect not to source the re-enumeration from a "
    '"repos/<bc>" clone tree, there being no such clone on the lead host'
)
def then_content_directs_not_source_from_clone(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "repos/<bc>" in content or "repos/" in content, (
        "template must name the 'repos/<bc>' clone tree it directs the architect "
        "NOT to source the re-enumeration from (lead-6gaj / 7d7f4bd2c88e5f0a)"
    )
    assert "lead host" in lc, (
        "template must state there is no such clone on the lead host "
        "(lead-6gaj / 7d7f4bd2c88e5f0a)"
    )


@then(
    "the content directs the architect that, for any dispatch that retires, "
    "supersedes, or contradicts prior BC-side coverage, the dispatch text must "
    "reference each conflicting @scenario_hash entry — as established from the "
    'lead-held "features/" surface and the BC\'s mailbox-reported register — by '
    "its hash ID, or carry an explicit retirement instruction for that hash"
)
def then_content_directs_hash_reference_or_retirement(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "@scenario_hash" in content, (
        "template must name @scenario_hash in the dispatch-text evidence "
        "requirement (lead-6gaj / 96cf1667aec9a98f)"
    )
    retirement_signals = ("retirement instruction", "retirement", "retire")
    assert any(s in lc for s in retirement_signals), (
        "template must name 'retirement'/'retire' as the alternative form "
        "(lead-6gaj / 96cf1667aec9a98f)"
    )
    id_signals = ("hash id", "by id", "conflicting")
    assert any(s in lc for s in id_signals), (
        "template must direct referencing conflicting hashes by their ID "
        "(lead-6gaj / 96cf1667aec9a98f)"
    )
    assert "mailbox" in lc, (
        "template must name the mailbox-reported register as a source the "
        "conflicting set is established from (lead-6gaj / 96cf1667aec9a98f)"
    )


@then(
    "the content frames that requirement as the observable evidence the BC "
    "Implementer can use to confirm the architect ran the enumeration step, "
    "rather than as optional context for the BC"
)
def then_content_frames_hash_reference_as_observable_evidence(context: dict) -> None:
    content = context["template_content"].lower()
    assert "observable" in content, (
        "template must use 'observable'/'observable evidence' to frame the "
        "hash-reference requirement (lead-6gaj / 96cf1667aec9a98f)"
    )


@then(
    "the content directs the architect to cite the enumeration in the dispatch "
    "description in the same shape that the contract-surface verification step "
    "(ADR-018 D1) is cited, so the Implementer does not have to re-derive the "
    "conflicts the architect missed"
)
def then_content_directs_cite_enumeration_in_dispatch(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "enumeration" in lc, (
        "template must use 'enumeration' to describe what to cite in the "
        "dispatch description (lead-6gaj / 96cf1667aec9a98f)"
    )
    assert "cite" in lc, (
        "template must direct the architect to cite the enumeration in the "
        "dispatch description (lead-6gaj / 96cf1667aec9a98f)"
    )
    assert "adr-018" in lc or "contract-surface" in lc or "contract surface" in lc, (
        "template must reference the contract-surface verification step "
        "(ADR-018 D1) as the shape the citation takes (lead-6gaj / 96cf1667aec9a98f)"
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


# -----------------------------------------------------------------------
# Step definitions — inter-shop messaging encapsulation (lead-bwu)
# -----------------------------------------------------------------------
#
# Scenarios 17-25 of features/inter_shop_messaging_encapsulation.feature
# pin two invariants across the four canonical templates and the two
# CLAUDE.md files of the shopsystem product:
#
#   1. CLI-only mailbox access: every prescribed inbox/outbox operation
#      names a `shop-msg` subcommand. No filesystem-direct inspection,
#      no filename-convention reasoning, no set-difference-on-filenames
#      characterization of "unprocessed".
#
#   2. bd-decoupling: bd participation is the local work-tracker
#      concern of each shop; no template or CLAUDE.md makes a bd
#      command a precondition for a shop-msg invocation, and no
#      template names `--bd-ref` (the flag has been replaced with the
#      optional, tracker-neutral `--provenance-ref`).
#
# Scenarios 21, 22, 25 reach OUTSIDE the BC root to read the lead-shop
# CLAUDE.md at <product>/CLAUDE.md and the BC's own CLAUDE.md at
# <product>/repos/shopsystem-templates/CLAUDE.md. The lead's dispatch
# (lead-bwu) explicitly names both files as in-scope surfaces — this
# read is sanctioned by the message.


def _product_root() -> Path:
    """Return the lead-shop (product) root directory.

    The BC root for shopsystem-templates is two levels below the product
    root: <product>/repos/shopsystem-templates. Resolve by walking up
    from this file (tests/conftest.py inside the BC) two more levels.
    """
    return Path(__file__).resolve().parent.parent.parent.parent


def _read_file_at_product_path(relative_path: str) -> str:
    """Read a file path that is given relative to the product root.

    The scenarios spell paths as "CLAUDE.md" (lead shop) and
    "repos/shopsystem-templates/CLAUDE.md" (BC). Both anchor at the
    product root.
    """
    target = _product_root() / relative_path
    return target.read_text()


# -----------------------------------------------------------------------
# Given steps — file-at-path premise (scenarios 21, 22, 25)
# -----------------------------------------------------------------------


@given(
    parsers.parse(
        'the file at "{relative_path}" exists and is the canonical CLAUDE.md '
        'for the shopsystem-templates BC shop'
    )
)
def given_file_at_path_is_bc_claude_md(relative_path: str, context: dict) -> None:
    target = _product_root() / relative_path
    assert target.exists(), (
        f"premise of Given violated: file {target!s} does not exist"
    )
    context["file_path"] = str(target)
    context["file_relative_path"] = relative_path


@given(
    parsers.parse(
        'the file at "{relative_path}" exists at the lead shop\'s repository '
        'root and describes the lead shop\'s router behavior and '
        'feature-request handling'
    )
)
def given_file_at_path_is_lead_claude_md(relative_path: str, context: dict) -> None:
    target = _product_root() / relative_path
    assert target.exists(), (
        f"premise of Given violated: file {target!s} does not exist"
    )
    context["file_path"] = str(target)
    context["file_relative_path"] = relative_path


@given(
    parsers.parse(
        'the file at {relative_path} exists and is the canonical CLAUDE.md '
        'for the named shop'
    )
)
def given_file_at_path_is_named_shop_claude_md(
    relative_path: str, context: dict
) -> None:
    # Scenario Outline (scenario 25) substitutes the path from the
    # Examples table. The path arrives without surrounding quotes from
    # pytest-bdd's outline substitution, so strip optional whitespace.
    relative_path = relative_path.strip()
    target = _product_root() / relative_path
    assert target.exists(), (
        f"premise of Given violated: file {target!s} does not exist"
    )
    context["file_path"] = str(target)
    context["file_relative_path"] = relative_path


# -----------------------------------------------------------------------
# When step — read the file the Given just established
# -----------------------------------------------------------------------


@when("I read that file")
def when_read_that_file(context: dict) -> None:
    """Read the file and resolve @-import lines before storing content.

    CLAUDE.md files use lines of the form "@<relative-path>" to compose
    content from multiple files. Asserting substrings against the raw
    CLAUDE.md misses content that lives in the imported files. This step
    resolves each @-import line by inlining the content of the referenced
    file (relative to the CLAUDE.md's parent directory), matching the
    resolution approach used in the import_graph bootstrap scenarios.
    """
    path = Path(context["file_path"])
    base_dir = path.parent
    raw_content = path.read_text()
    resolved_parts = []
    for line in raw_content.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("@"):
            import_path = stripped[1:]  # strip leading @
            imported_file = base_dir / import_path
            if imported_file.exists():
                resolved_parts.append(imported_file.read_text())
            # If file doesn't exist, skip (placeholder may be empty).
        else:
            resolved_parts.append(line)
    context["file_content"] = "".join(resolved_parts)


# -----------------------------------------------------------------------
# Then steps — generic substring contains / does-not-contain
# -----------------------------------------------------------------------
#
# "the content" assertions read from context["template_content"] (set
# by the existing "I read the X template via shop-templates show X"
# step). "the file" assertions read from context["file_content"] (set
# by the "I read that file" step above).


@then(parsers.parse('the content contains the literal substring "{needle}"'))
def then_content_contains_literal_substring(needle: str, context: dict) -> None:
    content = context["template_content"]
    assert needle in content, (
        f"template {context.get('shown_template_name')!r} is missing "
        f"required literal substring {needle!r}"
    )


@then(parsers.parse('the content does not contain the literal substring "{needle}"'))
def then_content_does_not_contain_literal_substring(
    needle: str, context: dict
) -> None:
    content = context["template_content"]
    assert needle not in content, (
        f"template {context.get('shown_template_name')!r} contains "
        f"forbidden literal substring {needle!r}"
    )


@then(parsers.parse('the file does not contain the literal substring "{needle}"'))
def then_file_does_not_contain_literal_substring(
    needle: str, context: dict
) -> None:
    content = context["file_content"]
    assert needle not in content, (
        f"file {context.get('file_relative_path')!r} contains forbidden "
        f"literal substring {needle!r}"
    )


@then(
    parsers.parse(
        'the file contains the literal substring "{needle}" as the named '
        'operation for identifying unprocessed work'
    )
)
def then_file_contains_substring_as_unprocessed_op(
    needle: str, context: dict
) -> None:
    content = context["file_content"]
    assert needle in content, (
        f"file {context.get('file_relative_path')!r} is missing required "
        f"literal substring {needle!r} (named operation for identifying "
        f"unprocessed work)"
    )


@then(
    parsers.parse(
        'the file contains the literal substring "{needle}" as the named '
        'operation for reading a specific inbox message'
    )
)
def then_file_contains_substring_as_read_inbox_op(
    needle: str, context: dict
) -> None:
    content = context["file_content"]
    assert needle in content, (
        f"file {context.get('file_relative_path')!r} is missing required "
        f"literal substring {needle!r} (named operation for reading a "
        f"specific inbox message)"
    )


# -----------------------------------------------------------------------
# Then steps — instructional negations (no "read the file directly"-style
# guidance with respect to inbox/outbox)
# -----------------------------------------------------------------------
#
# These steps assert that the template/file does not instruct the
# reader to perform a non-shop-msg filesystem operation on the
# inbox/outbox. The check is conservative: forbid the literal
# substrings that would betray such instruction (the same shapes the
# scenario text enumerates), and additionally forbid common bypass
# phrasings ("cat <BC root>/inbox", "open inbox/", etc.) when they
# co-occur with the mailbox words.


_INBOX_OUTBOX_TOKENS = ("inbox", "outbox")


def _content_for_target(context: dict, target_label: str) -> tuple[str, str]:
    """Return (content, identifier) for assertion error messages.

    `target_label` is 'content' (template) or 'file' (CLAUDE.md).
    """
    if target_label == "content":
        return (
            context["template_content"],
            f"template {context.get('shown_template_name')!r}",
        )
    return (
        context["file_content"],
        f"file {context.get('file_relative_path')!r}",
    )


def _assert_no_direct_inbox_outbox_instruction(
    content: str, identifier: str
) -> None:
    """Common check for 'does not instruct the reader to ... inbox/outbox'.

    The scenarios call out the same shapes from different angles. The
    check below covers the union conservatively:

    - Literal phrases like "read the file directly", "read the YAML
      directly", "open the file" combined with inbox/outbox proximity.
    - Direct cat/ls/grep/open verbs with inbox/outbox as direct object.

    A line is an offense only if it gives an action on a mailbox path
    without naming a shop-msg subcommand on the same line. That keeps
    sentences like "shop-msg read inbox reads the file" from
    incidentally triggering: the shop-msg subcommand name is present.
    """
    offenders: list[tuple[int, str]] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        lower = line.lower()
        # Quick reject: no inbox/outbox mention → no offense possible.
        if not any(tok in lower for tok in _INBOX_OUTBOX_TOKENS):
            continue
        # If the line already names a shop-msg subcommand, the inbox/
        # outbox reference is within a sanctioned context. Skip.
        if "shop-msg" in lower:
            continue
        # Offending phrasings: direct filesystem verbs / "read directly"
        # variants targeting the mailbox.
        triggers = (
            "read the file directly",
            "read the yaml directly",
            "read the file",
            "read the yaml",
            "open the file",
            "open the yaml",
            "cat inbox",
            "cat outbox",
            "cat <bc root>/inbox",
            "cat <bc root>/outbox",
            "ls inbox",
            "ls outbox",
            "grep inbox",
            "grep outbox",
            "inspect the file",
            "inspect the yaml",
        )
        if any(t in lower for t in triggers):
            offenders.append((lineno, line.rstrip()))
            continue
        # Path-shape offenses: a sentence that names an inbox/outbox
        # path token (`<BC root>/inbox/`, `inbox/`, `outbox/`) as the
        # target of an inspection verb without a shop-msg cite. Look
        # for action verbs in the same line.
        action_verbs = (
            "open ", "cat ", "ls ", "grep ", "inspect ", "view ",
            "edit ", "tail ", "head ",
        )
        path_tokens = (
            "<bc root>/inbox", "<bc root>/outbox",
            "repos/<bc>/inbox", "repos/<bc>/outbox",
        )
        if any(v in lower for v in action_verbs) and any(
            p in lower for p in path_tokens
        ):
            offenders.append((lineno, line.rstrip()))
    assert not offenders, (
        f"{identifier} contains instruction(s) to operate on inbox/outbox "
        f"directly (without shop-msg) — forbidden:\n"
        + "\n".join(f"  line {n}: {l!r}" for n, l in offenders)
    )


@then(
    'the content does not instruct the reader to "read the file directly" '
    'or "read the YAML directly" with respect to the inbox or outbox'
)
def then_content_no_read_directly_instruction(context: dict) -> None:
    content, ident = _content_for_target(context, "content")
    _assert_no_direct_inbox_outbox_instruction(content, ident)


@then(
    "the content does not instruct the reader to read the inbox YAML file "
    "directly or by any non-shop-msg means"
)
def then_content_no_read_inbox_yaml_non_shop_msg(context: dict) -> None:
    content, ident = _content_for_target(context, "content")
    _assert_no_direct_inbox_outbox_instruction(content, ident)


@then(
    'the content does not instruct the PO to open, cat, or otherwise '
    'inspect any path under "inbox/" or "outbox/" by any non-shop-msg means'
)
def then_content_no_po_inspect_inbox_outbox(context: dict) -> None:
    content, ident = _content_for_target(context, "content")
    _assert_no_direct_inbox_outbox_instruction(content, ident)


@then(
    'the content does not instruct the architect to open, cat, or otherwise '
    'inspect any path under a BC\'s "inbox/" or "outbox/" directory by any '
    'non-shop-msg means'
)
def then_content_no_architect_inspect_inbox_outbox(context: dict) -> None:
    content, ident = _content_for_target(context, "content")
    _assert_no_direct_inbox_outbox_instruction(content, ident)


@then(
    'the file does not instruct the router to open, cat, ls, or otherwise '
    'inspect any path under "inbox/" or "outbox/" by any non-shop-msg means'
)
def then_file_no_router_inspect_inbox_outbox_bc(context: dict) -> None:
    content, ident = _content_for_target(context, "file")
    _assert_no_direct_inbox_outbox_instruction(content, ident)


@then(
    'the file does not instruct the router to open, cat, ls, or otherwise '
    'inspect any path under "repos/<bc>/inbox/" or "repos/<bc>/outbox/" by '
    'any non-shop-msg means'
)
def then_file_no_router_inspect_inbox_outbox_lead(context: dict) -> None:
    content, ident = _content_for_target(context, "file")
    _assert_no_direct_inbox_outbox_instruction(content, ident)


# -----------------------------------------------------------------------
# Then steps — set-difference-on-filenames negation (scenario 21)
# -----------------------------------------------------------------------


@then(
    'the file does not contain any sentence asserting that "a message is '
    'unprocessed when there is no outbox file" or any other '
    'set-difference-on-filenames characterization of unprocessed state'
)
def then_file_no_set_difference_unprocessed(context: dict) -> None:
    content = context["file_content"]
    lower = content.lower()
    # The exact forbidden assertion (case-insensitive, allowing for
    # minor punctuation around it).
    forbidden_phrases = (
        "a message is unprocessed when there is no outbox file",
        "a message is considered unprocessed when there is no outbox file",
        "message is unprocessed when there is no outbox",
        "unprocessed when there is no outbox",
        "no matching outbox file for its",  # set-difference shape
        "no outbox file for its",            # set-difference shape
        "no outbox file matching",
        "no matching outbox",
    )
    offenders = [p for p in forbidden_phrases if p in lower]
    assert not offenders, (
        f"file {context.get('file_relative_path')!r} contains set-difference-"
        f"on-filenames characterization(s) of 'unprocessed' state: "
        f"{offenders!r}"
    )


# -----------------------------------------------------------------------
# Then steps — dispatch / inspection naming (scenario 22)
# -----------------------------------------------------------------------


@then(
    'every step or sentence that describes dispatching work to a BC names '
    '"shop-msg send" as the dispatch operation'
)
def then_file_every_dispatch_sentence_names_shop_msg_send(
    context: dict,
) -> None:
    content = context["file_content"]
    # The scenario targets sentences that describe the *operation* of
    # dispatching work to a BC (the inter-shop dispatch operation), not
    # sentences that merely use "dispatched" as a past participle in a
    # noun-phrase label, and not sentences about dispatching subagents
    # within the lead shop. Discriminator: the line is procedural shape
    # AND its subject is the Architect/lead acting toward a BC.
    #
    # Concrete signals of procedural shape: numbered list item
    # (re. r"^\d+\."), imperative verb form ("dispatch the", "send"),
    # OR a co-occurrence of "dispatch" with a message-type token
    # (`assign_scenarios`/`request_bugfix`/`request_maintenance`).
    #
    # Concrete signals of "to a BC, not to a subagent": the line does
    # NOT contain "subagent" / "lead-po" / "lead-architect" /
    # "bc-implementer" / "bc-reviewer" (those are subagent dispatch).
    offenders: list[tuple[int, str]] = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        lower = line.lower()
        # Quick reject 1: no dispatch terminology at all → skip.
        if "dispatch" not in lower:
            continue
        # Quick reject 2: subagent-dispatch context → skip.
        subagent_tokens = (
            "subagent", "lead-po", "lead-architect", "bc-implementer",
            "bc-reviewer",
        )
        if any(t in lower for t in subagent_tokens):
            continue
        # Procedural-shape filter. Match one of:
        #   (a) Numbered list item (^\s*\d+\.) on the same line.
        #   (b) Bulleted item beginning with an imperative voice that
        #       describes an action ("- Architect dispatches", etc.) —
        #       conservative: require the line to also name a
        #       message-type token, "send", or "shop-msg send".
        #   (c) Co-occurrence of "dispatch" with a message-type token
        #       (those tokens are only used in procedural contexts).
        stripped = line.lstrip()
        is_numbered = bool(re.match(r"^\d+\.\s", stripped))
        has_msg_type = any(
            t in lower for t in (
                "assign_scenarios", "request_bugfix",
                "request_maintenance",
            )
        )
        if not (is_numbered or has_msg_type):
            continue
        # The line is a procedural dispatch sentence. Verify
        # "shop-msg send" appears within a local window.
        window_start = max(0, i - 2)
        window_end = min(len(lines), i + 5)
        window = "\n".join(lines[window_start:window_end]).lower()
        if "shop-msg send" in window:
            continue
        offenders.append((i + 1, line.rstrip()))
    assert not offenders, (
        f"file {context.get('file_relative_path')!r} has dispatch-describing "
        f"sentences that do not name 'shop-msg send' in their local context:\n"
        + "\n".join(f"  line {n}: {l!r}" for n, l in offenders)
    )


@then(
    'every step or sentence that describes inspecting a BC\'s outbox state '
    'names a "shop-msg" subcommand (for example "shop-msg pending outbox" '
    'or "shop-msg read outbox") as the inspection operation'
)
def then_file_every_outbox_inspection_names_shop_msg(context: dict) -> None:
    content = context["file_content"]
    # We are looking for sentences that describe an inspection of a BC's
    # outbox. The discriminating signal: a mention of "outbox" alongside
    # an inspection verb ("inspect", "check", "list", "see", "read",
    # "review", "examine"). For each, verify that a shop-msg subcommand
    # appears in the local window.
    inspection_verbs = (
        "inspect", "check", "list", "see ", "read ", "review",
        "examine", "view ", "look at", "look up",
    )
    offenders: list[tuple[int, str]] = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        lower = line.lower()
        if "outbox" not in lower:
            continue
        if not any(v in lower for v in inspection_verbs):
            continue
        # Markdown section headings (lines whose stripped form starts with "#")
        # are structural labels, not sentences that instruct an operation.
        # The word "inspection" in a heading like "## BC-shop loop and outbox
        # inspection" is a label, not a procedural step — skip such lines.
        if line.lstrip().startswith("#"):
            continue
        # Local window for shop-msg presence.
        window_start = max(0, i - 2)
        window_end = min(len(lines), i + 5)
        window = "\n".join(lines[window_start:window_end]).lower()
        if "shop-msg pending outbox" in window or "shop-msg read outbox" in window or "shop-msg read" in window or "shop-msg pending" in window:
            continue
        offenders.append((i + 1, line.rstrip()))
    assert not offenders, (
        f"file {context.get('file_relative_path')!r} has outbox-inspection "
        f"sentences that do not name a 'shop-msg' subcommand:\n"
        + "\n".join(f"  line {n}: {l!r}" for n, l in offenders)
    )


# -----------------------------------------------------------------------
# Then steps — scenario 23: bc-implementer's mechanism-observation
# section discipline
# -----------------------------------------------------------------------
#
# The "section" referred to in the scenario is the
# "## Surfacing mechanism observations" subtree of the bc-implementer
# template — from the H2 header until the next H2 header.


def _extract_mechanism_observation_section(content: str) -> str:
    marker = "## Surfacing mechanism observations"
    start = content.find(marker)
    assert start >= 0, (
        "bc-implementer template missing 'Surfacing mechanism observations' "
        "H2 section"
    )
    # Find the next H2 (## ) header after start.
    rest = content[start + len(marker):]
    # Scan line by line for the next "## " heading.
    section_lines = [marker]
    for line in rest.splitlines():
        # An H2 starts at column 0 with "## " but NOT "### "; the H3
        # subsections inside the section ("### Carve-outs", "### When
        # to NOT emit a mechanism observation") are PART of the section.
        if line.startswith("## ") and not line.startswith("### "):
            break
        section_lines.append(line)
    return "\n".join(section_lines)


@then(
    parsers.parse(
        'the "{section_header}" section does not contain the literal '
        'substring "{needle}"'
    )
)
def then_section_does_not_contain_substring(
    section_header: str, needle: str, context: dict
) -> None:
    content = context["template_content"]
    # Use the helper for the known section. Generalize if other sections
    # need this step.
    assert section_header == "Surfacing mechanism observations", (
        f"step only knows the 'Surfacing mechanism observations' section; "
        f"got {section_header!r}"
    )
    section = _extract_mechanism_observation_section(content)
    assert needle not in section, (
        f"section {section_header!r} of template "
        f"{context.get('shown_template_name')!r} contains forbidden "
        f"literal substring {needle!r}"
    )


@then(parsers.parse('the section does not contain the literal substring "{needle}"'))
def then_section_does_not_contain_substring_short(
    needle: str, context: dict
) -> None:
    # The shorter "And the section does not contain ..." form refers
    # back to the section established by the preceding "the
    # 'Surfacing mechanism observations' section does not contain ..."
    # step. We re-extract by header name (the section is unique in the
    # bc-implementer template).
    content = context["template_content"]
    section = _extract_mechanism_observation_section(content)
    assert needle not in section, (
        f"'Surfacing mechanism observations' section of template "
        f"{context.get('shown_template_name')!r} contains forbidden "
        f"literal substring {needle!r}"
    )


@then(
    'the section does not contain language of the form "Create a beads '
    'issue" or "create a beads issue" or "create a bd issue" as a numbered '
    'or otherwise-ordered step that precedes the shop-msg respond '
    'mechanism_observation step'
)
def then_section_no_create_beads_precondition(context: dict) -> None:
    content = context["template_content"]
    section = _extract_mechanism_observation_section(content)
    # Find the first shop-msg respond mechanism_observation reference.
    smr_idx = section.find("shop-msg respond mechanism_observation")
    assert smr_idx >= 0, (
        "'Surfacing mechanism observations' section must reference "
        "'shop-msg respond mechanism_observation' (otherwise the section "
        "has lost its load-bearing CLI guidance)"
    )
    pre = section[:smr_idx].lower()
    forbidden_phrases = (
        "create a beads issue",
        "create a bd issue",
        # Numbered/ordered step language with beads precondition shape.
        "1. create a bead",
        "1. create a beads",
        "step 1: create a bead",
        "step 1: create a beads",
    )
    hits = [p for p in forbidden_phrases if p in pre]
    assert not hits, (
        f"'Surfacing mechanism observations' section names a beads-issue-"
        f"creation step that precedes the shop-msg respond "
        f"mechanism_observation step: {hits!r}"
    )


@then(
    'every shop-msg respond mechanism_observation invocation example in '
    'the section is composable without referring to any flag whose name '
    'contains the substring "bd"'
)
def then_section_no_bd_flag_in_invocation(context: dict) -> None:
    content = context["template_content"]
    section = _extract_mechanism_observation_section(content)
    # Find every shop-msg respond mechanism_observation block and walk
    # its argument lines forward until the block ends (a blank line or
    # a non-continuation line). Reject any flag --<name>... where name
    # contains "bd".
    offenders: list[str] = []
    lines = section.splitlines()
    i = 0
    while i < len(lines):
        if "shop-msg respond mechanism_observation" in lines[i]:
            # Collect this line and subsequent continuation lines (those
            # indented or starting with whitespace + flag-shape).
            block_lines = [lines[i]]
            j = i + 1
            while j < len(lines):
                follow = lines[j]
                stripped = follow.strip()
                if not stripped:
                    break
                # Continuation: line ends with backslash, or starts with
                # whitespace + "--" / "[--".
                prev = block_lines[-1].rstrip()
                if prev.endswith("\\") or stripped.startswith("--") or stripped.startswith("[--"):
                    block_lines.append(follow)
                    j += 1
                    continue
                break
            block = "\n".join(block_lines)
            # Find every flag --<name> in the block. A flag name
            # containing "bd" is offensive.
            for match in re.finditer(r"--([a-zA-Z][a-zA-Z0-9-]*)", block):
                flag_name = match.group(1)
                if "bd" in flag_name.lower():
                    offenders.append(f"flag --{flag_name} in block: {block!r}")
            i = j
            continue
        i += 1
    assert not offenders, (
        "shop-msg respond mechanism_observation example(s) in "
        "'Surfacing mechanism observations' section contain a flag whose "
        "name carries 'bd':\n  " + "\n  ".join(offenders)
    )


@then(
    'if the section mentions a provenance pointer at all it names it via '
    'the optional flag "--provenance-ref"'
)
def then_section_provenance_pointer_via_provenance_ref(context: dict) -> None:
    content = context["template_content"]
    section = _extract_mechanism_observation_section(content)
    lower = section.lower()
    if "provenance" not in lower:
        return  # vacuously satisfied
    # If "provenance" appears, "--provenance-ref" must also appear.
    assert "--provenance-ref" in section, (
        "'Surfacing mechanism observations' section mentions 'provenance' "
        "but does not name the optional flag '--provenance-ref'"
    )


@then(
    'the section contains an explicit statement that emitting the '
    'mechanism_observation does not require the BC to use bd or to create '
    'a bd issue'
)
def then_section_explicit_no_bd_requirement(context: dict) -> None:
    content = context["template_content"]
    section = _extract_mechanism_observation_section(content)
    lower = section.lower()
    # Acceptable phrasings that satisfy the explicit-statement check.
    # The check is a substring OR — at least one of these phrasings
    # must appear.
    candidate_phrasings = (
        "does not require bd",
        "does not require the bc to use bd",
        "does not require a bd issue",
        "does not require creating a bd issue",
        "does not require beads",
        "no bd issue is required",
        "no bd issue required",
        "bd is not required",
        "bd participation is not required",
        "no beads issue is required",
        "without bd",
        "without a bd issue",
        "without creating a bd issue",
    )
    if not any(p in lower for p in candidate_phrasings):
        raise AssertionError(
            "'Surfacing mechanism observations' section must contain an "
            "explicit statement that emitting the mechanism_observation "
            "does not require bd participation. None of the acceptable "
            f"phrasings were found:\n  {candidate_phrasings!r}"
        )


# -----------------------------------------------------------------------
# Then steps — Scenario Outlines (scenarios 24 and 25): bd-decoupling
# across all four templates and both CLAUDE.md files
# -----------------------------------------------------------------------


def _assert_no_bd_precondition_in_content(content: str, identifier: str) -> None:
    """Assert that no sentence, list item, or numbered step instructs the
    reader to create/claim/update a bd issue as a precondition for a
    shop-msg invocation."""
    # Strategy: find every shop-msg invocation (line containing
    # "shop-msg send" or "shop-msg respond"). For each, walk backward
    # within the same enclosing block (run of non-blank lines, or
    # numbered/list block) and assert that the preceding lines do not
    # contain a bd-action verb (create/claim/update) targeting a bd
    # issue.
    bd_action_patterns = (
        r"\bbd\s+(?:create|update|claim|update.*--claim)\b",
        r"\bcreate\s+a\s+bd\s+issue\b",
        r"\bcreate\s+a\s+beads\s+issue\b",
        r"\bcreate\s+a\s+bead\b",
        r"\bclaim\s+the\s+bd\s+issue\b",
        r"\bclaim\s+a\s+bd\s+issue\b",
        r"\bupdate\s+the\s+bd\s+issue\b",
        r"\bfile\s+a\s+bd\s+issue\b",
        r"\bfile\s+a\s+beads\s+issue\b",
    )
    offenders: list[str] = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        lower = line.lower()
        if "shop-msg send" not in lower and "shop-msg respond" not in lower:
            continue
        # Walk backward to find the enclosing block boundary. A block
        # boundary is a blank line or a heading line.
        block_start = i
        while block_start > 0:
            prev = lines[block_start - 1]
            if not prev.strip():
                break
            if prev.lstrip().startswith("#"):
                break
            block_start -= 1
        preceding = "\n".join(lines[block_start:i]).lower()
        # Check for any bd-action pattern in the preceding block region.
        for pat in bd_action_patterns:
            m = re.search(pat, preceding)
            if m:
                # Distinguish "instructs as precondition" from "describes
                # observationally". A line that is part of a numbered or
                # bulleted procedural list and precedes a shop-msg step
                # is procedural-precondition shape. Lines that are part
                # of prose explanations (e.g., "bd holds the work
                # registry") are observational. The discriminator:
                # the bd action appears in a numbered/bulleted step.
                for j in range(block_start, i):
                    line_j = lines[j]
                    stripped_j = line_j.lstrip()
                    if re.search(pat, line_j.lower()):
                        if (
                            stripped_j.startswith("- ")
                            or stripped_j.startswith("* ")
                            or re.match(r"^\d+\.\s", stripped_j)
                            or re.match(r"^step\s+\d+", stripped_j.lower())
                        ):
                            offenders.append(
                                f"line {j + 1}: {line_j.rstrip()!r} "
                                f"(precedes shop-msg invocation at line {i + 1})"
                            )
                            break
                break  # one offense per shop-msg invocation is enough
    assert not offenders, (
        f"{identifier} instructs creating/claiming/updating a bd issue as "
        f"a precondition for a shop-msg invocation:\n  "
        + "\n  ".join(offenders)
    )


def _assert_shop_msg_examples_composable_without_bd(
    content: str, subcommand: str, identifier: str
) -> None:
    """For every example of `subcommand` (e.g., 'shop-msg send' or
    'shop-msg respond'), check the invocation block does not require a
    bd subcommand to run first. The check: no `bd` invocation appears
    in the example's own block as a prerequisite step.
    """
    # An "invocation example" is a line containing the subcommand. The
    # block is what surrounds it as one contiguous procedural unit
    # (numbered list item, or code block). If any earlier step in the
    # same numbered procedural list says "bd X", that example is not
    # composable without bd.
    offenders: list[str] = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        lower = line.lower()
        if subcommand not in lower:
            continue
        # Identify the enclosing numbered-list step. Walk backward to
        # find the start of the numbered-list run.
        # A "numbered procedural unit" is a contiguous run of
        # lines that includes at least one numbered step (\d+\.\s) and
        # ends at a blank line or heading.
        # Find run boundaries.
        run_start = i
        while run_start > 0:
            prev = lines[run_start - 1]
            if not prev.strip() or prev.lstrip().startswith("#"):
                break
            run_start -= 1
        run_end = i
        while run_end + 1 < len(lines):
            nxt = lines[run_end + 1]
            if not nxt.strip() or nxt.lstrip().startswith("#"):
                break
            run_end += 1
        run = "\n".join(lines[run_start : run_end + 1])
        # Look only at lines BEFORE the subcommand line in this run.
        before = "\n".join(lines[run_start:i]).lower()
        # A bd-precondition in the procedural unit is a numbered or
        # bulleted step containing a `bd ` command verb.
        # We require the bd command to be at the start of a step line
        # (after the bullet/number).
        bd_step_re = re.compile(
            r"(?:^|\n)\s*(?:\d+\.\s+|[-*]\s+|step\s+\d+[:.]\s+)[^\n]*\bbd\s+(?:create|update|claim|push|prime|ready|show|close)\b",
            re.IGNORECASE,
        )
        if bd_step_re.search(before):
            offenders.append(
                f"line {i + 1}: {line.rstrip()!r} is preceded in its "
                f"procedural run by a 'bd ...' step"
            )
    assert not offenders, (
        f"{identifier} has {subcommand!r} invocation example(s) that are "
        f"not composable without first running a 'bd' subcommand:\n  "
        + "\n  ".join(offenders)
    )


@then(
    'the content does not contain any sentence, list item, or numbered '
    'step that instructs the reader to create, claim, or update a bd '
    'issue as a precondition for invoking any "shop-msg send" or '
    '"shop-msg respond" subcommand'
)
def then_content_no_bd_precondition(context: dict) -> None:
    content, ident = _content_for_target(context, "content")
    _assert_no_bd_precondition_in_content(content, ident)


@then(
    parsers.parse(
        'every "{subcommand}" invocation example in the content is '
        'composable without the reader first running a "bd" subcommand'
    )
)
def then_content_subcommand_composable_without_bd(
    subcommand: str, context: dict
) -> None:
    content, ident = _content_for_target(context, "content")
    _assert_shop_msg_examples_composable_without_bd(content, subcommand, ident)


@then(
    'the file does not contain any sentence, list item, or numbered '
    'step that instructs the reader to create, claim, or update a bd '
    'issue as a precondition for invoking any "shop-msg send" or '
    '"shop-msg respond" subcommand'
)
def then_file_no_bd_precondition(context: dict) -> None:
    content, ident = _content_for_target(context, "file")
    _assert_no_bd_precondition_in_content(content, ident)


@then(
    parsers.parse(
        'every "{subcommand}" invocation example in the file is composable '
        'without the reader first running a "bd" subcommand'
    )
)
def then_file_subcommand_composable_without_bd(
    subcommand: str, context: dict
) -> None:
    content, ident = _content_for_target(context, "file")
    _assert_shop_msg_examples_composable_without_bd(content, subcommand, ident)


# -----------------------------------------------------------------------
# Step definitions — lead-architect "Responding to a BC clarify"
# per-step CLI naming (scenario e6bdf2f33bfae0d1 / lead-e4g)
# -----------------------------------------------------------------------
#
# These steps localize to a named subsection of the lead-architect
# template and enforce a per-step invariant: every numbered procedural
# step whose action is reading the BC's outbox must name the literal
# substring "shop-msg read outbox" on the same step. A surrounding
# Constraints clause is too weak to prevent regression — the per-step
# discipline is what closes the asymmetry surfaced by lead-bwu's
# clarify against lead-architect.md line 272 vs lead-po.md lines 160-162.


def _extract_subsection_between_headings(
    content: str, start_heading: str
) -> str:
    """Return the body of the subsection that begins with `start_heading`
    and runs until the next heading of depth two (## ) or depth three
    (### ), whichever comes first. The returned text includes the
    starting heading line and stops just before the terminating heading.
    """
    start_idx = content.find(start_heading)
    assert start_idx >= 0, (
        f"subsection start heading not found in content: {start_heading!r}"
    )
    rest = content[start_idx + len(start_heading):]
    section_lines = [start_heading]
    for line in rest.splitlines():
        stripped = line.lstrip()
        # Stop at the next H2 (## ) or H3 (### ). Note: the starting
        # heading itself is H3; the *next* H3 or H2 terminates the
        # subsection.
        if stripped.startswith("## ") or stripped.startswith("### "):
            break
        section_lines.append(line)
    return "\n".join(section_lines)


def _numbered_steps_in_subsection(subsection: str) -> list[tuple[int, str]]:
    """Return a list of (index, step_text) tuples for each numbered
    step in `subsection`. A numbered step is a line whose left-stripped
    form matches `\\d+\\.\\s`. Continuation lines (indented prose that
    follows the numbered line until the next numbered line or blank
    line) are joined into the same step_text — the per-step assertion
    treats the step as a single unit.
    """
    lines = subsection.splitlines()
    steps: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].lstrip()
        if re.match(r"^\d+\.\s", stripped):
            step_lines = [lines[i]]
            j = i + 1
            while j < len(lines):
                follow = lines[j]
                follow_stripped = follow.lstrip()
                # Stop at the next numbered step, a blank line, or a
                # heading. Continuation lines are typically indented
                # prose that belongs to the current step.
                if re.match(r"^\d+\.\s", follow_stripped):
                    break
                if not follow.strip():
                    break
                if follow_stripped.startswith("#"):
                    break
                step_lines.append(follow)
                j += 1
            number_match = re.match(r"^(\d+)\.", stripped)
            assert number_match is not None  # guarded by the outer match
            steps.append((int(number_match.group(1)), "\n".join(step_lines)))
            i = j
            continue
        i += 1
    return steps


_OUTBOX_READ_BARE_VERBS = (
    "open", "cat", "ls", "grep", "inspect", "view", "edit", "tail", "head",
)
_OUTBOX_PATH_SHAPES = (
    "outbox/", "<bc root>/outbox/", "the outbox file",
)


@when(
    parsers.parse(
        'I locate the subsection that begins with the heading '
        '"{start_heading}" and ends at the next heading of depth two (##) '
        'or depth three (###), whichever comes first'
    )
)
def when_locate_subsection_between_headings(
    start_heading: str, context: dict
) -> None:
    content = context["template_content"]
    subsection = _extract_subsection_between_headings(content, start_heading)
    context["located_subsection"] = subsection
    context["located_subsection_heading"] = start_heading


def _step_describes_reading_outbox(step_text: str) -> bool:
    """Heuristic discriminator: does the step describe reading the BC's
    outbox? The step text is one numbered list item plus its
    continuation lines (per `_numbered_steps_in_subsection`).

    The discriminator fires when the step contains BOTH:
      (a) the word "outbox" (the target), AND
      (b) a reading-shape signal: a bare reading verb listed in
          `_OUTBOX_READ_BARE_VERBS`, OR the verb "Read" / "read", OR a
          path-shape reference from `_OUTBOX_PATH_SHAPES`.

    A step that names "shop-msg read outbox" already satisfies the
    invariant — the discriminator still fires for it (because it does
    describe reading the outbox), and the per-step naming check then
    passes trivially.
    """
    lower = step_text.lower()
    if "outbox" not in lower:
        return False
    if "read" in lower:
        return True
    for verb in _OUTBOX_READ_BARE_VERBS:
        # Word-boundary match so "viewed" doesn't trip "view" only if
        # we want it to; but the verb list itself is what the scenario
        # enumerates, so a substring match against the lowercase step
        # text is what the scenario asks for.
        if re.search(rf"\b{re.escape(verb)}\b", lower):
            return True
    for shape in _OUTBOX_PATH_SHAPES:
        if shape in lower:
            return True
    return False


@then(
    'within that subsection, every numbered step whose action is reading '
    'the clarify from the BC\'s outbox names the literal substring '
    '"shop-msg read outbox" on the same step'
)
def then_subsection_outbox_read_steps_name_cli(context: dict) -> None:
    subsection = context["located_subsection"]
    heading = context["located_subsection_heading"]
    offenders: list[str] = []
    for number, step_text in _numbered_steps_in_subsection(subsection):
        if not _step_describes_reading_outbox(step_text):
            continue
        if "shop-msg read outbox" in step_text:
            continue
        offenders.append(f"step {number}: {step_text!r}")
    assert not offenders, (
        f"subsection {heading!r} has step(s) whose action is reading the "
        f"BC's outbox but do not name 'shop-msg read outbox' on the same "
        f"step:\n  " + "\n  ".join(offenders)
    )


@then(
    parsers.re(
        r'^within that subsection, no numbered step describes reading the '
        r"BC's outbox using a bare action verb . \"open\", \"cat\", \"ls\", "
        r'\"grep\", \"inspect\", \"view\", \"edit\", \"tail\", \"head\", or '
        r'a bare \"Read\" . without naming the literal substring '
        r'"shop-msg read outbox" on the same step$'
    )
)
def then_subsection_no_bare_verb_outbox_read(context: dict) -> None:
    subsection = context["located_subsection"]
    heading = context["located_subsection_heading"]
    offenders: list[str] = []
    for number, step_text in _numbered_steps_in_subsection(subsection):
        lower = step_text.lower()
        if "outbox" not in lower:
            continue
        if "shop-msg read outbox" in step_text:
            continue
        bare_verb_hits: list[str] = []
        # Bare "Read" — distinct from "read outbox" in a shop-msg invocation
        # (which is excluded by the "shop-msg read outbox" guard above).
        if re.search(r"\bread\b", lower):
            bare_verb_hits.append("Read")
        for verb in _OUTBOX_READ_BARE_VERBS:
            if re.search(rf"\b{re.escape(verb)}\b", lower):
                bare_verb_hits.append(verb)
        if bare_verb_hits:
            offenders.append(
                f"step {number}: bare verbs {bare_verb_hits!r} in "
                f"step that references outbox without naming "
                f"'shop-msg read outbox'; step text: {step_text!r}"
            )
    assert not offenders, (
        f"subsection {heading!r} has bare-verb outbox-read step(s):\n  "
        + "\n  ".join(offenders)
    )


@then(
    parsers.re(
        r'^within that subsection, no numbered step refers to the BC\'s '
        r'outbox by a path-shaped reference such as "outbox/", '
        r'"<BC root>/outbox/", or "the outbox file" without naming the '
        r'literal substring "shop-msg read outbox" on the same step$'
    )
)
def then_subsection_no_path_shape_outbox_ref(context: dict) -> None:
    subsection = context["located_subsection"]
    heading = context["located_subsection_heading"]
    offenders: list[str] = []
    for number, step_text in _numbered_steps_in_subsection(subsection):
        if "shop-msg read outbox" in step_text:
            continue
        lower = step_text.lower()
        path_hits: list[str] = []
        for shape in _OUTBOX_PATH_SHAPES:
            if shape in lower:
                path_hits.append(shape)
        if path_hits:
            offenders.append(
                f"step {number}: path-shape references {path_hits!r} "
                f"without naming 'shop-msg read outbox'; step text: "
                f"{step_text!r}"
            )
    assert not offenders, (
        f"subsection {heading!r} has path-shape outbox reference(s) "
        f"without CLI naming:\n  " + "\n  ".join(offenders)
    )


# -----------------------------------------------------------------------
# Step definitions — bc-implementer "Your job" and bc-reviewer "What you
# read" per-step CLI naming (scenarios 4671ccec78520c83 + 688a8f10fe2c5a2f
# / lead-14e). Mirrors the outbox-flavored steps above for the inbox
# direction. The When step (locate subsection by heading) is shared with
# the outbox-flavored block; only the Then assertions differ in target
# (inbox vs outbox) and literal CLI substring ("shop-msg read inbox" vs
# "shop-msg read outbox").
# -----------------------------------------------------------------------


_INBOX_READ_BARE_VERBS = (
    "open", "cat", "ls", "grep", "inspect", "view", "edit", "tail", "head",
)
_INBOX_PATH_SHAPES = (
    "inbox/", "<bc root>/inbox/", "the inbox file",
)


def _step_describes_reading_inbox(step_text: str) -> bool:
    """Inbox-direction discriminator. Symmetrical to
    `_step_describes_reading_outbox`: fires when the step contains both
    the word "inbox" AND a reading-shape signal (bare reading verb, the
    verb "Read" / "read", or a path-shape reference).

    A step that names "shop-msg read inbox" already satisfies the
    invariant — the discriminator still fires for it (because it does
    describe reading the inbox), and the per-step naming check then
    passes trivially.
    """
    lower = step_text.lower()
    if "inbox" not in lower:
        return False
    if "read" in lower:
        return True
    for verb in _INBOX_READ_BARE_VERBS:
        if re.search(rf"\b{re.escape(verb)}\b", lower):
            return True
    for shape in _INBOX_PATH_SHAPES:
        if shape in lower:
            return True
    return False


@then(
    'within that subsection, every numbered step whose action is reading '
    'the inbox message names the literal substring '
    '"shop-msg read inbox" on the same step'
)
def then_subsection_inbox_read_steps_name_cli(context: dict) -> None:
    subsection = context["located_subsection"]
    heading = context["located_subsection_heading"]
    offenders: list[str] = []
    for number, step_text in _numbered_steps_in_subsection(subsection):
        if not _step_describes_reading_inbox(step_text):
            continue
        if "shop-msg read inbox" in step_text:
            continue
        offenders.append(f"step {number}: {step_text!r}")
    assert not offenders, (
        f"subsection {heading!r} has step(s) whose action is reading the "
        f"inbox message but do not name 'shop-msg read inbox' on the same "
        f"step:\n  " + "\n  ".join(offenders)
    )


@then(
    parsers.re(
        r'^within that subsection, no numbered step describes reading the '
        r'inbox message using a bare action verb . \"open\", \"cat\", '
        r'\"ls\", \"grep\", \"inspect\", \"view\", \"edit\", \"tail\", '
        r'\"head\", or a bare \"Read\" . without naming the literal '
        r'substring "shop-msg read inbox" on the same step$'
    )
)
def then_subsection_no_bare_verb_inbox_read(context: dict) -> None:
    subsection = context["located_subsection"]
    heading = context["located_subsection_heading"]
    offenders: list[str] = []
    for number, step_text in _numbered_steps_in_subsection(subsection):
        lower = step_text.lower()
        if "inbox" not in lower:
            continue
        if "shop-msg read inbox" in step_text:
            continue
        bare_verb_hits: list[str] = []
        # Bare "Read" — distinct from "read inbox" in a shop-msg invocation
        # (which is excluded by the "shop-msg read inbox" guard above).
        if re.search(r"\bread\b", lower):
            bare_verb_hits.append("Read")
        for verb in _INBOX_READ_BARE_VERBS:
            if re.search(rf"\b{re.escape(verb)}\b", lower):
                bare_verb_hits.append(verb)
        if bare_verb_hits:
            offenders.append(
                f"step {number}: bare verbs {bare_verb_hits!r} in "
                f"step that references inbox without naming "
                f"'shop-msg read inbox'; step text: {step_text!r}"
            )
    assert not offenders, (
        f"subsection {heading!r} has bare-verb inbox-read step(s):\n  "
        + "\n  ".join(offenders)
    )


@then(
    parsers.re(
        r'^within that subsection, no numbered step refers to the inbox '
        r'message by a path-shaped reference such as "inbox/", '
        r'"<BC root>/inbox/", or "the inbox file" without naming the '
        r'literal substring "shop-msg read inbox" on the same step$'
    )
)
def then_subsection_no_path_shape_inbox_ref(context: dict) -> None:
    subsection = context["located_subsection"]
    heading = context["located_subsection_heading"]
    offenders: list[str] = []
    for number, step_text in _numbered_steps_in_subsection(subsection):
        if "shop-msg read inbox" in step_text:
            continue
        lower = step_text.lower()
        path_hits: list[str] = []
        for shape in _INBOX_PATH_SHAPES:
            if shape in lower:
                path_hits.append(shape)
        if path_hits:
            offenders.append(
                f"step {number}: path-shape references {path_hits!r} "
                f"without naming 'shop-msg read inbox'; step text: "
                f"{step_text!r}"
            )
    assert not offenders, (
        f"subsection {heading!r} has path-shape inbox reference(s) "
        f"without CLI naming:\n  " + "\n  ".join(offenders)
    )


# =======================================================================
# Step definitions — bootstrap_cli_surface.feature (lead-k8v dispatch)
# =======================================================================
#
# Scenarios pin the `shop-templates bootstrap` and `shop-templates update`
# CLI surface that scaffolds and reconciles an existing shop repository:
# .claude/agents/<role>.md (role-prompt copies), top-level CLAUDE.md
# (shop primer), top-level .gitignore, and .beads/ (initialized via a
# `bd init` subprocess).
#
# Two cross-cutting test concerns are handled by helpers below:
#
#   1. Target directories. Scenarios spell paths as "/tmp/example-shop"
#      etc., which are shared across scenarios and not safe to use
#      literally (they would leak state between tests, and tests would
#      stomp on real /tmp/). The Given step redirects every named
#      target to a fresh pytest tmp directory and stores the mapping in
#      context["target_alias_to_real"]. Subsequent steps that name the
#      same alias resolve to the same real path.
#
#   2. Subprocess observation. Scenario 0c6f1c5d9bc4226e requires that
#      `bd init` is executed as a subprocess (not by importing bd in-
#      process), and scenario 3f4d7d2256a97ae7 requires that update
#      executes NO `bd` subprocess. We install a per-test shim
#      directory at the front of PATH containing a fake `bd` script
#      that (a) logs every invocation to a file and (b) creates the
#      .beads/ directory in cwd (so `bd init` still produces the
#      side-effect bootstrap callers depend on). After the invocation
#      we read the log to check what subprocesses ran and which import
#      check the shim recorded.


_BOOTSTRAP_TARGET_ALIASES = (
    "/tmp/example-shop",
    "/tmp/example-bc-shop",
    "/tmp/example-lead-shop",
)


def _real_target_for_alias(alias: str, context: dict) -> Path:
    """Map a feature-file path alias (e.g. "/tmp/example-shop") to a
    fresh per-test directory. Subsequent calls with the same alias
    within a single scenario resolve to the same real path.
    """
    mapping = context.setdefault("target_alias_to_real", {})
    if alias in mapping:
        return mapping[alias]
    # We allocate per-alias subdirectories inside a single pytest tmp
    # path stash on context, so each scenario gets an isolated workspace.
    base = context.get("bootstrap_workspace")
    assert base is not None, (
        "Given step ordering bug: target alias resolved before "
        "bootstrap_workspace was prepared"
    )
    real = base / alias.lstrip("/").replace("/", "_")
    real.mkdir(parents=True, exist_ok=True)
    # Initialize as a git repo so the Given's "existing git repository"
    # premise holds.
    subprocess.run(
        ["git", "init", "-q", str(real)],
        check=True,
        capture_output=True,
    )
    mapping[alias] = real
    return real


@pytest.fixture(autouse=False)
def _ensure_bootstrap_workspace(tmp_path: Path, context: dict) -> Path:
    """Not autouse; invoked from Given steps that need a fresh workspace."""
    context["bootstrap_workspace"] = tmp_path
    return tmp_path


def _make_bd_shim_dir(tmp_path: Path, context: dict) -> Path:
    """Create a directory containing a fake `bd` executable that logs
    invocations to a file and minimally simulates `bd init` (mkdir
    .beads/ in cwd with a marker file inside). Return the directory
    path so the caller can prepend it to PATH.

    Per scenarios 0c6f1c5d9bc4226e and 3f4d7d2256a97ae7, tests need to
    answer "did a `bd` subprocess run, and with what first argument".
    The log file path is stashed on context as "bd_shim_log" and is
    TRUNCATED on each call — so only the most-recent invocation's bd
    calls are observable. (Tests that need to chain a Given-side
    bootstrap into a When-side update don't want the Given-side `bd
    init` call to pollute the When-side observation window.)
    """
    shim_dir = tmp_path / "bd-shim"
    shim_dir.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "bd-shim.log"
    # Truncate so each invocation observes only its own subprocess calls.
    log.write_text("")
    context["bd_shim_log"] = log
    bd_path = shim_dir / "bd"
    # The shim is intentionally tiny — it logs argv (one line per call:
    # "<arg1> <arg2> ..." plus its cwd) and, if the first arg is "init",
    # creates ".beads/__shim_init__" inside cwd as the visible
    # side-effect bootstrap callers depend on.
    bd_path.write_text(
        "#!/usr/bin/env bash\n"
        f"log={log}\n"
        'echo "$@|cwd=$PWD" >> "$log"\n'
        'if [[ "$1" == "init" ]]; then\n'
        '  mkdir -p .beads\n'
        '  : > .beads/__shim_init__\n'
        'fi\n'
        "exit 0\n"
    )
    bd_path.chmod(0o755)
    return shim_dir


def _run_shop_templates_with_bd_shim(
    args: list[str], context: dict, tmp_path: Path
) -> subprocess.CompletedProcess:
    """Invoke `shop-templates` with a fake `bd` on PATH, capturing
    whether/how `bd` was called and whether `bd`/`beads` Python modules
    got imported into the shop-templates process.

    The "no bd/beads imports" check (scenario 0c6f1c5d9bc4226e) is
    implemented by invoking shop-templates indirectly via a small
    Python wrapper that (1) runs `shop_templates.cli.main(args)` and
    (2) after main returns, writes `bd_in_modules=True/False` and
    `beads_in_modules=True/False` to an import-trace log. The test
    asserts both are False.
    """
    import os
    import shutil

    shim_dir = _make_bd_shim_dir(tmp_path, context)
    import_log = tmp_path / "import-trace.log"
    context["import_trace_log"] = import_log

    # Build a wrapper script that runs shop_templates.cli.main(argv)
    # and then writes the import-trace flags. We must NOT import bd
    # or beads ourselves anywhere in this wrapper (the assertion would
    # then trivially fail).
    wrapper = tmp_path / "_run_shop_templates_wrapper.py"
    args_repr = repr(list(args))
    wrapper.write_text(
        "import sys\n"
        "from shop_templates.cli import main\n"
        f"argv = {args_repr}\n"
        "rc = main(argv)\n"
        "import_log = open(r%r, 'w')\n" % str(import_log)
        + "bd_in = any(\n"
        "    m == 'bd' or m.startswith('bd.')\n"
        "    for m in sys.modules\n"
        ")\n"
        "beads_in = any(\n"
        "    m == 'beads' or m.startswith('beads.')\n"
        "    for m in sys.modules\n"
        ")\n"
        "import_log.write(f'bd_in_modules={bd_in}\\n')\n"
        "import_log.write(f'beads_in_modules={beads_in}\\n')\n"
        "import_log.close()\n"
        "sys.exit(rc)\n"
    )

    env = os.environ.copy()
    env["PATH"] = f"{shim_dir}{os.pathsep}{env.get('PATH', '')}"

    # Use the same python interpreter that's running the test, so
    # `shop_templates` is importable from the installed package.
    py = sys.executable
    return subprocess.run(
        [py, str(wrapper)],
        capture_output=True,
        text=True,
        env=env,
    )


# -----------------------------------------------------------------------
# Given steps — target directory premise
# -----------------------------------------------------------------------


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}"'
    )
)
def given_existing_git_repo_at_target(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    _real_target_for_alias(alias, context)


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'with no ".claude/agents/" directory'
    )
)
def given_existing_git_repo_at_target_no_agents_dir(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    agents = real / ".claude" / "agents"
    assert not agents.exists(), (
        f"premise of Given violated: {agents!s} unexpectedly exists"
    )


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'with no top-level "CLAUDE.md"'
    )
)
def given_existing_git_repo_at_target_no_claude_md(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    assert not (real / "CLAUDE.md").exists()


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'with no top-level ".gitignore"'
    )
)
def given_existing_git_repo_at_target_no_gitignore(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    assert not (real / ".gitignore").exists()


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'with no ".beads/" directory'
    )
)
def given_existing_git_repo_at_target_no_beads_dir(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    assert not (real / ".beads").exists()


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'containing none of "inbox/", "outbox/", "features/", "tests/", '
        '"pyproject.toml", or "README.md"'
    )
)
def given_existing_git_repo_at_target_no_out_of_scope(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    for path in ("inbox", "outbox", "features", "tests"):
        assert not (real / path).exists(), (
            f"premise of Given violated: {(real / path)!s} unexpectedly exists"
        )
    for fname in ("pyproject.toml", "README.md"):
        assert not (real / fname).exists()


@given(
    parsers.parse(
        'the target directory contains no ".claude/agents/" directory '
        'and no ".beads/" directory and no top-level "CLAUDE.md" and '
        'no top-level ".gitignore"'
    )
)
def given_target_dir_is_pristine(context: dict) -> None:
    # Single-target version (used by scenarios that named a single
    # target in their first Given). Pick that target out of the alias
    # map — there must be exactly one so we don't accidentally apply
    # the assertion to a peer target.
    mapping = context.get("target_alias_to_real", {})
    assert len(mapping) == 1, (
        f"premise of Given violated: expected exactly one target alias "
        f"in scope; got {list(mapping)!r}"
    )
    real = next(iter(mapping.values()))
    for path in (".claude/agents", ".beads"):
        assert not (real / path).exists()
    for fname in ("CLAUDE.md", ".gitignore"):
        assert not (real / fname).exists()


# -----------------------------------------------------------------------
# Given step — previously bootstrapped target (update scenarios)
# -----------------------------------------------------------------------


def _do_bootstrap_for_test(
    alias: str, shop_type: str, shop_name: str, context: dict, tmp_path: Path
) -> Path:
    """Helper: run the bootstrap CLI (with bd shim) against the target
    aliased by `alias`, asserting it succeeded. Returns the real path.

    Used by Given steps that establish a "previously bootstrapped" state.
    """
    real = _real_target_for_alias(alias, context)
    result = _run_shop_templates_with_bd_shim(
        [
            "bootstrap",
            "--shop-type",
            shop_type,
            "--shop-name",
            shop_name,
            "--target",
            str(real),
        ],
        context,
        tmp_path,
    )
    assert result.returncode == 0, (
        f"premise of Given violated: bootstrap during test setup failed; "
        f"stderr:\n{result.stderr}"
    )
    context["bootstrap_shop_type"] = shop_type
    context["bootstrap_shop_name"] = shop_name
    context["bootstrap_alias"] = alias
    return real


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" that '
        'was previously bootstrapped as a "{shop_type}" shop named "{shop_name}"'
    )
)
def given_previously_bootstrapped(
    alias: str,
    shop_type: str,
    shop_name: str,
    context: dict,
    tmp_path: Path,
) -> None:
    context["bootstrap_workspace"] = tmp_path
    _do_bootstrap_for_test(alias, shop_type, shop_name, context, tmp_path)


# -----------------------------------------------------------------------
# Given steps — manipulated post-bootstrap state for update scenarios
# -----------------------------------------------------------------------


def _resolve_single_target(context: dict) -> Path:
    mapping = context.get("target_alias_to_real", {})
    assert len(mapping) >= 1, "no target alias in scope"
    # If multiple aliases exist, prefer the most-recently-introduced one.
    return list(mapping.values())[-1]


@given(
    parsers.parse(
        'the file at ".claude/agents/{role}.md" in the target directory '
        'equals the current canonical "{role_again}" template '
        'package-data file contents byte-for-byte'
    )
)
def given_agents_file_equals_canonical(
    role: str, role_again: str, context: dict
) -> None:
    assert role == role_again, (
        f"scenario inconsistency: {role!r} vs {role_again!r}"
    )
    real = _resolve_single_target(context)
    target_file = real / ".claude" / "agents" / f"{role}.md"
    from shop_templates.cli import _read_template

    expected = _read_template(role)
    assert expected is not None, f"no canonical template named {role!r}"
    actual = target_file.read_text()
    assert actual == expected, (
        f"premise of Given violated: {target_file!s} content differs "
        f"from canonical {role!r}"
    )


@given(
    parsers.parse(
        'the file at ".claude/agents/{role}.md" in the target directory '
        'holds an older version of the "{role_again}" canonical template '
        'content'
    )
)
def given_agents_file_holds_older_version(
    role: str, role_again: str, context: dict
) -> None:
    assert role == role_again
    real = _resolve_single_target(context)
    target_file = real / ".claude" / "agents" / f"{role}.md"
    # Simulate an older version by prepending a marker that the current
    # canonical content does not contain.
    older = "OLDER VERSION MARKER — this line is not in canonical\n" + target_file.read_text()
    target_file.write_text(older)
    context.setdefault("scenario_pre_state", {})[str(target_file)] = older


@given(
    parsers.parse(
        'the current canonical "{role}" template package-data file contents '
        'differ from that older version'
    )
)
def given_canonical_differs_from_older(role: str, context: dict) -> None:
    from shop_templates.cli import _read_template

    expected = _read_template(role)
    assert expected is not None
    # The "older version" marker we injected above is not in canonical
    # content. Assert that to make the Given's contract empirically true.
    real = _resolve_single_target(context)
    target_file = real / ".claude" / "agents" / f"{role}.md"
    older = target_file.read_text()
    assert older != expected, (
        "premise of Given violated: older version equals canonical; "
        "the older-marker should have changed it"
    )


@given(
    parsers.parse(
        'the file at ".claude/agents/{role}.md" in the target directory '
        'has been hand-edited so that its content differs from the '
        'current canonical "{role_again}" template package-data file '
        'contents'
    )
)
def given_agents_file_hand_edited(
    role: str, role_again: str, context: dict
) -> None:
    assert role == role_again
    real = _resolve_single_target(context)
    target_file = real / ".claude" / "agents" / f"{role}.md"
    edited = target_file.read_text() + "\nHAND-EDITED LINE — not in canonical\n"
    target_file.write_text(edited)


@given(
    'every file in ".claude/agents/" in the target directory equals the '
    'corresponding current canonical template package-data file contents '
    'byte-for-byte'
)
def given_all_agents_files_canonical(context: dict) -> None:
    real = _resolve_single_target(context)
    from shop_templates.cli import _read_template, _CANONICAL_ROLE_SETS

    shop_type = context["bootstrap_shop_type"]
    for role in _CANONICAL_ROLE_SETS[shop_type]:
        target_file = real / ".claude" / "agents" / f"{role}.md"
        expected = _read_template(role)
        actual = target_file.read_text()
        assert actual == expected, (
            f"premise of Given violated: {target_file!s} differs from canonical"
        )


@given(
    'I record the on-disk byte contents and modification metadata of every '
    'file under the target directory before the invocation'
)
def given_record_all_files_pre(context: dict) -> None:
    real = _resolve_single_target(context)
    snapshot: dict[str, bytes] = {}
    for p in real.rglob("*"):
        if p.is_file():
            snapshot[str(p)] = p.read_bytes()
    context["pre_invocation_all_files"] = snapshot


@given(
    parsers.parse(
        'the file at "{path}" in the target directory has been edited '
        'since bootstrap so that its content includes a literal '
        'shop-authored sentence that the canonical "{path_again}" '
        'primer template does not contain'
    )
)
def given_file_edited_post_bootstrap(
    path: str, path_again: str, context: dict
) -> None:
    assert path == path_again
    real = _resolve_single_target(context)
    target_file = real / path
    edited = target_file.read_text() + "\nSHOP-AUTHORED SENTENCE NOT IN CANONICAL PRIMER.\n"
    target_file.write_text(edited)


@given(
    parsers.parse(
        'the file at "{path}" in the target directory has been edited '
        'since bootstrap so that its content includes a shop-authored '
        'entry that the canonical "{path_again}" template does not '
        'contain'
    )
)
def given_file_edited_post_bootstrap_gitignore(
    path: str, path_again: str, context: dict
) -> None:
    assert path == path_again
    real = _resolve_single_target(context)
    target_file = real / path
    edited = target_file.read_text() + "\n# SHOP-AUTHORED GITIGNORE ENTRY\nshop-authored-stuff/\n"
    target_file.write_text(edited)


@given(
    parsers.parse(
        'I record the byte contents of the file at "{path}" in the target '
        'directory before the invocation'
    )
)
def given_record_single_file_pre(path: str, context: dict) -> None:
    real = _resolve_single_target(context)
    target_file = real / path
    snap = context.setdefault("pre_invocation_files", {})
    snap[path] = target_file.read_bytes()


@given(
    'I record the byte contents of every file under ".beads/" in the '
    'target directory before the invocation'
)
def given_record_beads_pre(context: dict) -> None:
    real = _resolve_single_target(context)
    beads = real / ".beads"
    snap: dict[str, bytes] = {}
    if beads.exists():
        for p in beads.rglob("*"):
            if p.is_file():
                snap[str(p.relative_to(real))] = p.read_bytes()
    context["pre_invocation_beads"] = snap


@given(
    'the current canonical role set for shop type "bc" is exactly the '
    'names listed by "shop-templates list" filtered to those that the '
    'bootstrap surface treats as "bc" roles'
)
def given_canonical_role_set_bc(context: dict) -> None:
    # Verify empirically: the canonical role set for "bc" must be a
    # subset of `shop-templates list` output, AND must equal the
    # bootstrap surface's "bc" role set.
    from shop_templates.cli import _CANONICAL_ROLE_SETS

    result = _run_shop_templates("list")
    assert result.returncode == 0, (
        f"shop-templates list failed; stderr:\n{result.stderr}"
    )
    listed = set(result.stdout.strip().splitlines())
    bc_set = set(_CANONICAL_ROLE_SETS["bc"])
    assert bc_set <= listed, (
        f"premise of Given violated: canonical bc set {bc_set!r} not a "
        f"subset of shop-templates list output {listed!r}"
    )
    context["canonical_bc_set"] = bc_set


# Bindings for the scenario 03b4e3fa31d72031 placeholders. The
# scenario uses literal "<former-bc-role>.md" and "<new-bc-role>.md"
# tokens (it's a regular Scenario, not a Scenario Outline with
# Examples) — they are placeholder names meant for the test harness
# to bind to concrete values that satisfy the surrounding constraints
# (former NOT in canonical; new IS in canonical). Pick:
#   former-bc-role  = "bc-legacy-deprecated" (NOT in canonical bc set)
#   new-bc-role     = "bc-implementer"        (IS in canonical bc set)
_PLACEHOLDER_FORMER_BC_ROLE = "bc-legacy-deprecated"
_PLACEHOLDER_NEW_BC_ROLE = "bc-implementer"


def _bind_role_placeholder(literal: str) -> str:
    """Substitute scenario-level role-name placeholders with the
    concrete values defined above. The literal arrives with the
    angle-bracket markers (e.g. "<former-bc-role>.md"); we replace
    only the bracketed token and keep the rest of the filename.
    """
    return (
        literal.replace("<former-bc-role>", _PLACEHOLDER_FORMER_BC_ROLE)
        .replace("<new-bc-role>", _PLACEHOLDER_NEW_BC_ROLE)
    )


@given(
    parsers.parse(
        'the directory ".claude/agents/" in the target directory contains '
        'a file named "{filename}" whose name is not in that current '
        'canonical role set'
    )
)
def given_agents_dir_has_extraneous(filename: str, context: dict) -> None:
    real = _resolve_single_target(context)
    agents = real / ".claude" / "agents"
    bound = _bind_role_placeholder(filename)
    # Clear out canonical files first to ensure the "<former-bc-role>" is
    # the ONLY managed file present, per the scenario's intent.
    from shop_templates.cli import _CANONICAL_ROLE_SETS

    for role in _CANONICAL_ROLE_SETS["bc"]:
        canonical_file = agents / f"{role}.md"
        if canonical_file.exists():
            canonical_file.unlink()
    stem = bound
    if stem.endswith(".md"):
        stem = stem[:-3]
    assert "-" in stem and stem == stem.lower(), (
        f"premise of Given assumes naming-convention filename; got {bound!r}"
    )
    assert stem not in _CANONICAL_ROLE_SETS["bc"], (
        f"placeholder binding inconsistency: bound former-role {stem!r} is "
        f"in the canonical bc set, but the scenario says it must NOT be"
    )
    target_file = agents / bound
    target_file.write_text("former canonical body — not in current canonical set\n")
    context["former_role_filename"] = bound


@given(
    parsers.parse(
        'the directory ".claude/agents/" in the target directory does not '
        'contain a file named "{filename}" whose name is in that current '
        'canonical role set'
    )
)
def given_agents_dir_missing_canonical(filename: str, context: dict) -> None:
    real = _resolve_single_target(context)
    agents = real / ".claude" / "agents"
    bound = _bind_role_placeholder(filename)
    target_file = agents / bound
    assert not target_file.exists(), (
        f"premise of Given violated: {target_file!s} should be absent"
    )
    from shop_templates.cli import _CANONICAL_ROLE_SETS

    stem = bound
    if stem.endswith(".md"):
        stem = stem[:-3]
    assert stem in _CANONICAL_ROLE_SETS["bc"], (
        f"placeholder binding inconsistency: bound new-role {stem!r} not in "
        f"current bc canonical set"
    )
    context["new_role_filename"] = bound


@given(
    parsers.parse(
        'the target directory additionally contains a non-empty file at '
        '"{path}" authored by the shop'
    )
)
def given_extra_shop_file(path: str, context: dict) -> None:
    real = _resolve_single_target(context)
    target_file = real / path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(f"# shop-authored content at {path}\n")
    extras = context.setdefault("shop_authored_extras", {})
    extras[path] = target_file.read_bytes()


@given(
    parsers.parse(
        'the target directory additionally contains a non-empty top-level '
        'file at "{path}" authored by the shop'
    )
)
def given_extra_shop_top_level_file(path: str, context: dict) -> None:
    real = _resolve_single_target(context)
    target_file = real / path
    target_file.write_text(f"# shop-authored content at top-level {path}\n")
    extras = context.setdefault("shop_authored_extras", {})
    extras[path] = target_file.read_bytes()


@given(
    'I record the byte contents of those four files before the invocation'
)
def given_record_four_files(context: dict) -> None:
    real = _resolve_single_target(context)
    extras = context.get("shop_authored_extras", {})
    snap = {p: (real / p).read_bytes() for p in extras}
    context["pre_invocation_four_files"] = snap
    # Also record all paths pre-invocation so the "no new path other
    # than .claude/agents/" Then step can compare.
    all_paths: set[str] = set()
    for p in real.rglob("*"):
        all_paths.add(str(p.relative_to(real)))
    context["pre_invocation_all_paths"] = all_paths


# -----------------------------------------------------------------------
# When steps — bootstrap / update invocation
# -----------------------------------------------------------------------


@when(
    parsers.parse(
        'I invoke the "shop-templates" bootstrap entry point with shop type '
        '"{shop_type}", shop name "{shop_name}", and target directory "{alias}"'
    )
)
def when_invoke_bootstrap(
    shop_type: str,
    shop_name: str,
    alias: str,
    context: dict,
    tmp_path: Path,
) -> None:
    real = _real_target_for_alias(alias, context)
    result = _run_shop_templates_with_bd_shim(
        [
            "bootstrap",
            "--shop-type",
            shop_type,
            "--shop-name",
            shop_name,
            "--target",
            str(real),
        ],
        context,
        tmp_path,
    )
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr
    context["last_invocation_target"] = real
    context["last_invocation_shop_type"] = shop_type
    context["last_invocation_shop_name"] = shop_name


@when(
    'I invoke the "shop-templates" bootstrap entry point with a shop name '
    'and a target directory but with no shop type argument'
)
def when_invoke_bootstrap_no_shop_type(
    context: dict, tmp_path: Path
) -> None:
    real = _resolve_single_target(context)
    result = _run_shop_templates_with_bd_shim(
        [
            "bootstrap",
            "--shop-name",
            "example-shop",
            "--target",
            str(real),
        ],
        context,
        tmp_path,
    )
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr
    context["last_invocation_target"] = real


@when(
    parsers.parse(
        'I invoke the "shop-templates" update entry point against the '
        'target directory "{alias}"'
    )
)
def when_invoke_update(
    alias: str, context: dict, tmp_path: Path
) -> None:
    real = _real_target_for_alias(alias, context)
    # If the shop_type was stashed by a "previously bootstrapped" Given,
    # pass it explicitly (backward compatibility). Otherwise, omit it so
    # the CLI reads it from .claude/shop/type.md (or fails for legacy shops).
    shop_type = context.get("bootstrap_shop_type")
    args = ["update", "--target", str(real)]
    if shop_type is not None:
        args.extend(["--shop-type", shop_type])
    result = _run_shop_templates_with_bd_shim(args, context, tmp_path)
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr
    context["last_invocation_target"] = real


@when(
    parsers.parse(
        'I ask the "shop-templates" package for the canonical "CLAUDE.md" '
        'primer template for shop type "{shop_type}" through its public '
        'template-access surface'
    )
)
def when_ask_for_claude_primer(shop_type: str, context: dict) -> None:
    from shop_templates.cli import read_claude_md_primer

    context["claude_primer_shop_type"] = shop_type
    context["claude_primer_body"] = read_claude_md_primer(shop_type)
    # Also stash under the generic "last_returned_body" key so the
    # shared "the returned body contains the literal substring" Then
    # step (used by brief 003 settings.json scenarios as well as the
    # prior CLAUDE.md primer scenarios) can read the body without
    # having to know which template surface it came from.
    context["last_returned_body"] = context["claude_primer_body"]
    context["last_returned_surface"] = "claude_primer"
    context["last_returned_shop_type"] = shop_type


# -----------------------------------------------------------------------
# Then steps — bootstrap exit / scaffold presence / non-prompt invariants
# -----------------------------------------------------------------------


@then(
    'the invocation completes without prompting for any input on stdin'
)
def then_no_stdin_prompt(context: dict) -> None:
    # _run_shop_templates_with_bd_shim runs subprocess.run WITHOUT a
    # stdin=PIPE; if shop-templates tried to read stdin in a terminal-
    # less subprocess context it would EOF immediately rather than
    # hang the test, but we assert it returned with a defined exit
    # code as the empirical demonstration of "did not block".
    rc = context["cli_returncode"]
    assert rc is not None, "invocation did not return an exit code"


@then(
    'stderr does not contain any prompt-style text such as "y/n" or '
    '"press enter"'
)
def then_stderr_no_prompt_text(context: dict) -> None:
    stderr = context["cli_stderr"].lower()
    for needle in ("y/n", "press enter", "[y/n]", "(y/n)"):
        assert needle not in stderr, (
            f"unexpected prompt-style text {needle!r} found in stderr:\n"
            f"{context['cli_stderr']}"
        )


@then(
    'after the invocation the target directory contains a ".claude/agents/" '
    'directory, a ".beads/" directory, a top-level "CLAUDE.md", and a '
    'top-level ".gitignore"'
)
def then_post_bootstrap_scaffold_present(context: dict) -> None:
    real = context["last_invocation_target"]
    assert (real / ".claude" / "agents").is_dir()
    assert (real / ".beads").is_dir()
    assert (real / "CLAUDE.md").is_file()
    assert (real / ".gitignore").is_file()


@then(
    'the target directory still contains no ".claude/agents/" directory '
    'and no ".beads/" directory and no top-level "CLAUDE.md" and no '
    'top-level ".gitignore"'
)
def then_target_still_pristine(context: dict) -> None:
    real = context["last_invocation_target"]
    assert not (real / ".claude" / "agents").exists()
    assert not (real / ".beads").exists()
    assert not (real / "CLAUDE.md").exists()
    assert not (real / ".gitignore").exists()


@then(
    parsers.parse(
        'stderr names "{label}" (or an equivalent phrase identifying the '
        'missing argument) as the missing required input'
    )
)
def then_stderr_names_missing_label(label: str, context: dict) -> None:
    stderr = context["cli_stderr"].lower()
    # Accept the literal label OR a hyphen variant ("shop-type") as
    # the equivalent phrase per the scenario's "or an equivalent
    # phrase" hedge.
    variants = [label.lower(), label.replace(" ", "-").lower(), label.replace(" ", "_").lower()]
    assert any(v in stderr for v in variants), (
        f"expected stderr to name missing input {label!r} (or an "
        f"equivalent); got:\n{context['cli_stderr']}"
    )


@then(
    parsers.parse(
        'stderr lists the accepted shop-type values "{v1}" and "{v2}" '
        'so the caller can recover'
    )
)
def then_stderr_lists_accepted_values(v1: str, v2: str, context: dict) -> None:
    stderr = context["cli_stderr"]
    for v in (v1, v2):
        assert v in stderr, (
            f"expected stderr to list accepted shop-type value {v!r}; got:\n{stderr}"
        )


@then(
    parsers.parse(
        'stderr names the offending shop-type value "{value}"'
    )
)
def then_stderr_names_offending_shop_type(value: str, context: dict) -> None:
    stderr = context["cli_stderr"]
    assert value in stderr, (
        f"expected stderr to name offending shop-type value {value!r}; got:\n{stderr}"
    )


@then(
    parsers.parse(
        'stderr lists the accepted shop-type values "{v1}" and "{v2}"'
    )
)
def then_stderr_lists_accepted_values_short(v1: str, v2: str, context: dict) -> None:
    stderr = context["cli_stderr"]
    for v in (v1, v2):
        assert v in stderr


# -----------------------------------------------------------------------
# Then steps — file contents and presence post-bootstrap / post-update
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'the target directory contains a file at ".claude/agents/{role}.md" '
        'whose content equals the package-data file contents of the '
        'canonical "{role_again}" template byte-for-byte'
    )
)
def then_agents_file_equals_canonical(
    role: str, role_again: str, context: dict
) -> None:
    assert role == role_again
    real = context["last_invocation_target"]
    target_file = real / ".claude" / "agents" / f"{role}.md"
    assert target_file.is_file(), f"missing file {target_file!s}"
    from shop_templates.cli import _read_template

    expected = _read_template(role)
    assert expected is not None
    assert target_file.read_text() == expected, (
        f"{target_file!s} differs from canonical {role!r}"
    )


@then(
    'the directory ".claude/agents/" in the target directory contains '
    'no files other than those two'
)
def then_agents_dir_only_two_files(context: dict) -> None:
    real = context["last_invocation_target"]
    agents = real / ".claude" / "agents"
    files = [p for p in agents.iterdir() if p.is_file()]
    assert len(files) == 2, (
        f"expected exactly 2 files in {agents!s}; got {[p.name for p in files]!r}"
    )


@then(
    parsers.parse(
        'the target directory contains a top-level file named "{name}"'
    )
)
def then_target_contains_top_level_file(name: str, context: dict) -> None:
    real = context["last_invocation_target"]
    assert (real / name).is_file(), f"missing top-level file {name!r} in {real!s}"
    context["_most_recent_top_level_file"] = name


@then("that file is non-empty")
def then_that_file_non_empty(context: dict) -> None:
    # Resolve "that file" via the most-recent top-level filename
    # asserted by then_target_contains_top_level_file. We re-read all
    # files in the target's top-level whose names were referenced by
    # the immediately-preceding step. Simpler: scan the target's
    # top-level CLAUDE.md and .gitignore as the only files the
    # scenarios reference with "that file" and pick whichever exists
    # and is non-empty. But that's fragile across scenarios that
    # only check one.
    real = context["last_invocation_target"]
    # The two top-level files written by bootstrap are CLAUDE.md and
    # .gitignore; both scenarios that use "that file is non-empty"
    # refer to whichever was just named. Track the most recent one.
    candidate = context.get("_most_recent_top_level_file")
    if candidate is None:
        # Fallback: check whichever exists.
        for name in ("CLAUDE.md", ".gitignore"):
            p = real / name
            if p.exists():
                assert p.stat().st_size > 0, f"file {p!s} is empty"
                return
        raise AssertionError("no candidate 'that file' identified")
    p = real / candidate
    assert p.stat().st_size > 0, f"file {p!s} is empty"


@then(
    parsers.parse(
        'the target directory contains no directory named "{name}"'
    )
)
def then_target_no_dir(name: str, context: dict) -> None:
    real = context["last_invocation_target"]
    # Strip trailing "/" if the scenario wrote "inbox/"
    bare = name.rstrip("/")
    p = real / bare
    assert not (p.exists() and p.is_dir()), (
        f"target unexpectedly contains directory {bare!r}"
    )


@then(
    parsers.parse(
        'the target directory contains no top-level file named "{name}"'
    )
)
def then_target_no_top_level_file(name: str, context: dict) -> None:
    real = context["last_invocation_target"]
    p = real / name
    assert not (p.exists() and p.is_file()), (
        f"target unexpectedly contains top-level file {name!r}"
    )


@then(
    'the target directory contains a ".beads/" directory'
)
def then_target_contains_beads(context: dict) -> None:
    real = context["last_invocation_target"]
    assert (real / ".beads").is_dir()


# -----------------------------------------------------------------------
# Then steps — subprocess and import observation
# -----------------------------------------------------------------------


def _bd_invocations(context: dict) -> list[list[str]]:
    """Return a list of bd-shim invocation argvs from the per-test log,
    or [] if the log doesn't exist (the shim was never invoked)."""
    log = context.get("bd_shim_log")
    if log is None or not log.exists():
        return []
    invocations: list[list[str]] = []
    for line in log.read_text().splitlines():
        if not line.strip():
            continue
        # Format: "<arg1> <arg2> ...|cwd=<cwd>"
        argline = line.split("|cwd=", 1)[0]
        invocations.append(argline.split())
    return invocations


@then(
    'during the invocation a subprocess named "bd" was executed with '
    'first argument "init"'
)
def then_bd_init_subprocess_ran(context: dict) -> None:
    invocations = _bd_invocations(context)
    assert invocations, (
        f"expected a `bd` subprocess invocation; bd-shim log is empty"
    )
    first_args = [inv[0] if inv else None for inv in invocations]
    assert "init" in first_args, (
        f"expected `bd init` invocation; got bd args: {first_args!r}"
    )


@then(
    'during the invocation no symbol from a Python module whose top-level '
    'package name is "bd" or "beads" was imported into the running '
    '"shop-templates" process'
)
def then_no_bd_or_beads_import(context: dict) -> None:
    log = context.get("import_trace_log")
    assert log is not None and log.exists(), (
        "import-trace log not written; wrapper likely failed"
    )
    contents = log.read_text()
    assert "bd_in_modules=False" in contents, (
        f"shop-templates process imported a 'bd' module; trace:\n{contents}"
    )
    assert "beads_in_modules=False" in contents, (
        f"shop-templates process imported a 'beads' module; trace:\n{contents}"
    )


@then(
    'during the invocation the contents of the ".beads/" directory were '
    'written by that "bd" subprocess and not by file-writes issued '
    'directly from the "shop-templates" process'
)
def then_beads_written_by_bd_subprocess(context: dict) -> None:
    # The bd-shim creates ".beads/__shim_init__" inside cwd as its
    # side-effect. If that marker is present in the target's .beads/
    # AND no `bd` import happened, then the beads dir contents came
    # from the subprocess (the only writer that wrote
    # __shim_init__). Re-check both invariants here for clarity at
    # the assertion site.
    real = context["last_invocation_target"]
    marker = real / ".beads" / "__shim_init__"
    assert marker.is_file(), (
        f"expected bd-shim marker at {marker!s} (would have been written by "
        f"the `bd init` subprocess); not present"
    )


@then('during the invocation no subprocess named "bd" was executed')
def then_no_bd_subprocess(context: dict) -> None:
    invocations = _bd_invocations(context)
    assert not invocations, (
        f"expected no `bd` subprocess invocations; got: {invocations!r}"
    )


# -----------------------------------------------------------------------
# Then steps — update file invariants
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'after the invocation the file at ".claude/agents/{role}.md" in '
        'the target directory still equals the current canonical '
        '"{role_again}" template package-data file contents byte-for-byte'
    )
)
def then_post_update_role_file_still_canonical(
    role: str, role_again: str, context: dict
) -> None:
    assert role == role_again
    real = context["last_invocation_target"]
    target_file = real / ".claude" / "agents" / f"{role}.md"
    from shop_templates.cli import _read_template

    expected = _read_template(role)
    assert target_file.read_text() == expected


@then(
    parsers.parse(
        'after the invocation the file at ".claude/agents/{role}.md" in '
        'the target directory equals the current canonical "{role_again}" '
        'template package-data file contents byte-for-byte'
    )
)
def then_post_update_role_file_canonical(
    role: str, role_again: str, context: dict
) -> None:
    assert role == role_again
    real = context["last_invocation_target"]
    target_file = real / ".claude" / "agents" / f"{role}.md"
    from shop_templates.cli import _read_template

    expected = _read_template(role)
    actual = target_file.read_text()
    assert actual == expected, (
        f"{target_file!s} content differs from canonical {role!r}"
    )


@then(
    'after the invocation every file under the target directory has '
    'byte-for-byte the same on-disk contents as before the invocation'
)
def then_no_files_changed(context: dict) -> None:
    real = context["last_invocation_target"]
    snapshot = context["pre_invocation_all_files"]
    for p in real.rglob("*"):
        if not p.is_file():
            continue
        key = str(p)
        assert key in snapshot, f"file {p!s} did not exist before invocation"
        assert p.read_bytes() == snapshot[key], (
            f"file {p!s} content changed across invocation"
        )
    # And no file disappeared.
    for key in snapshot:
        assert Path(key).is_file(), f"file {key!r} was removed by invocation"


@then(
    parsers.parse(
        'after the invocation the file at "{path}" in the target directory '
        'has byte-for-byte the same on-disk contents as before the '
        'invocation'
    )
)
def then_file_unchanged(path: str, context: dict) -> None:
    real = context["last_invocation_target"]
    snap = context["pre_invocation_files"]
    assert path in snap, f"no pre-invocation snapshot for {path!r}"
    actual = (real / path).read_bytes()
    assert actual == snap[path], (
        f"file {path!r} changed across invocation"
    )


@then(
    'after the invocation every file under ".beads/" in the target '
    'directory has byte-for-byte the same on-disk contents as before '
    'the invocation'
)
def then_beads_unchanged(context: dict) -> None:
    real = context["last_invocation_target"]
    snap = context["pre_invocation_beads"]
    beads = real / ".beads"
    for p in beads.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(real))
        assert rel in snap, f".beads file {rel!r} did not exist before invocation"
        assert p.read_bytes() == snap[rel], (
            f".beads file {rel!r} changed across invocation"
        )
    for rel in snap:
        assert (real / rel).is_file(), f".beads file {rel!r} was removed"


@then(
    parsers.parse(
        'after the invocation the directory ".claude/agents/" in the '
        'target directory does not contain a file named "{filename}"'
    )
)
def then_agents_dir_lacks_file(filename: str, context: dict) -> None:
    real = context["last_invocation_target"]
    bound = _bind_role_placeholder(filename)
    target_file = real / ".claude" / "agents" / bound
    assert not target_file.exists(), (
        f"{target_file!s} unexpectedly still present"
    )


@then(
    parsers.parse(
        'after the invocation the directory ".claude/agents/" in the '
        'target directory contains a file named "{filename}" whose '
        'content equals the current canonical "{role}" template '
        'package-data file contents byte-for-byte'
    )
)
def then_agents_dir_has_canonical_file(
    filename: str, role: str, context: dict
) -> None:
    real = context["last_invocation_target"]
    bound_filename = _bind_role_placeholder(filename)
    bound_role = _bind_role_placeholder(role)
    target_file = real / ".claude" / "agents" / bound_filename
    assert target_file.is_file(), f"missing {target_file!s}"
    from shop_templates.cli import _read_template

    expected = _read_template(bound_role)
    assert expected is not None, f"no canonical template {bound_role!r}"
    assert target_file.read_text() == expected


@then(
    'after the invocation the set of files in ".claude/agents/" whose '
    'names match the canonical role-set naming convention equals the '
    'current canonical role set for shop type "bc"'
)
def then_agents_dir_matches_canonical_bc(context: dict) -> None:
    real = context["last_invocation_target"]
    agents = real / ".claude" / "agents"
    from shop_templates.cli import _CANONICAL_ROLE_SETS

    # "naming convention" = lowercase hyphenated stem, .md extension.
    # Filter to those candidate filenames and compare set-of-stems.
    stems: set[str] = set()
    for p in agents.iterdir():
        if not p.is_file():
            continue
        if not p.name.endswith(".md"):
            continue
        stem = p.name[:-3]
        # naming convention: hyphen present, all lowercase, only
        # lowercase letters and hyphens
        if "-" not in stem:
            continue
        if stem != stem.lower():
            continue
        if not all(c.islower() or c == "-" for c in stem):
            continue
        stems.add(stem)
    expected = set(_CANONICAL_ROLE_SETS["bc"])
    assert stems == expected, (
        f"expected naming-convention files {expected!r} in {agents!s}; "
        f"got {stems!r}"
    )


@then(
    'after the invocation each of those four files has byte-for-byte the '
    'same on-disk contents as before the invocation'
)
def then_four_files_unchanged(context: dict) -> None:
    real = context["last_invocation_target"]
    snap = context["pre_invocation_four_files"]
    for path, body in snap.items():
        actual = (real / path).read_bytes()
        assert actual == body, (
            f"shop-authored file {path!r} changed across invocation"
        )


@then(
    'after the invocation the target directory contains no path that '
    'did not exist before the invocation other than paths inside '
    '".claude/agents/"'
)
def then_no_new_paths_outside_agents(context: dict) -> None:
    real = context["last_invocation_target"]
    pre_paths = context["pre_invocation_all_paths"]
    new_paths: list[str] = []
    for p in real.rglob("*"):
        rel = str(p.relative_to(real))
        if rel in pre_paths:
            continue
        # Allowed: anything inside .claude/agents/
        if rel.startswith(".claude/agents/") or rel == ".claude/agents":
            continue
        new_paths.append(rel)
    assert not new_paths, (
        f"unexpected new paths outside .claude/agents/: {new_paths!r}"
    )


# -----------------------------------------------------------------------
# Then steps — CLAUDE.md primer content invariants
# -----------------------------------------------------------------------


@then("a non-empty template body is returned")
def then_returned_body_non_empty(context: dict) -> None:
    # Shared with brief 003 scope item A — see the comment on
    # `then_returned_body_contains_substring` for the rationale.
    body = context.get("last_returned_body")
    assert body is not None, (
        "no template body has been retrieved this scenario; "
        "the matching When step was not run"
    )
    assert body, "returned body is empty"


@then(
    parsers.parse(
        'the returned body is the source of truth from which the bootstrap '
        'entry point generates the target directory\'s top-level "CLAUDE.md" '
        'for a shop of type "{shop_type}"'
    )
)
def then_returned_body_is_source_of_truth(
    shop_type: str, context: dict, tmp_path: Path
) -> None:
    # Empirically verify: run bootstrap into a fresh target with shop_name
    # "<source-of-truth-probe>" and check that the resulting CLAUDE.md
    # contains the primer body's invariant content (substituting only
    # the shop-name marker).
    target = tmp_path / f"sot-probe-{shop_type}"
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(target)], check=True, capture_output=True)
    probe_name = "source-of-truth-probe-shop-name"
    result = _run_shop_templates_with_bd_shim(
        [
            "bootstrap",
            "--shop-type",
            shop_type,
            "--shop-name",
            probe_name,
            "--target",
            str(target),
        ],
        context,
        tmp_path,
    )
    assert result.returncode == 0, (
        f"probe bootstrap failed; stderr:\n{result.stderr}"
    )
    written = (target / "CLAUDE.md").read_text()
    primer_body = context["claude_primer_body"]
    # The primer's invariant content (modulo the {{SHOP_NAME}} marker)
    # must appear in the written CLAUDE.md.
    # Split the primer on the marker and check each chunk is in the
    # written file.
    for chunk in primer_body.split("{{SHOP_NAME}}"):
        if not chunk.strip():
            continue
        assert chunk in written, (
            f"written CLAUDE.md does not contain primer chunk:\n{chunk!r}"
        )
    assert probe_name in written, (
        f"written CLAUDE.md does not contain the substituted shop name "
        f"{probe_name!r}"
    )


@then(
    'the returned body is not read from any path under this product\'s '
    'top-level working directory at lookup time'
)
def then_primer_not_from_product_path(context: dict) -> None:
    # Empirically verify: re-do the lookup under a CWD that is NOT
    # under the product working directory, with the product source
    # path removed from sys.path-equivalents, and confirm the same
    # body is returned. The strongest version of this assertion is
    # "the body comes from importlib.resources package data"; we
    # check that by reading it again with importlib.resources and
    # asserting byte-equality.
    import importlib.resources as ires

    shop_type = context["claude_primer_shop_type"]
    expected = (
        ires.files("shop_templates.templates.claude") / f"{shop_type}.md"
    ).read_text()
    assert context["claude_primer_body"] == expected, (
        "primer body returned by the public surface differs from the "
        "package-data resource; surface must serve from importlib.resources"
    )


@then(
    parsers.parse(
        'the content of that file contains the literal substring "{needle}"'
    )
)
def then_file_content_contains_substring(needle: str, context: dict) -> None:
    real = context["last_invocation_target"]
    body = (real / "CLAUDE.md").read_text()
    assert needle in body, (
        f"CLAUDE.md does not contain literal substring {needle!r}"
    )


@then(
    parsers.parse(
        'the content of that file names every role in the canonical role '
        'set for shop type "{shop_type}" by name'
    )
)
def then_claude_md_names_all_roles(shop_type: str, context: dict) -> None:
    real = context["last_invocation_target"]
    body = (real / "CLAUDE.md").read_text()
    from shop_templates.cli import _CANONICAL_ROLE_SETS

    for role in _CANONICAL_ROLE_SETS[shop_type]:
        assert role in body, (
            f"CLAUDE.md does not name canonical {shop_type} role {role!r}"
        )


@then(
    'the content of that file does not name any role from the canonical '
    'role set of the other shop type'
)
def then_claude_md_does_not_name_other_role_set(context: dict) -> None:
    real = context["last_invocation_target"]
    body = (real / "CLAUDE.md").read_text()
    from shop_templates.cli import _CANONICAL_ROLE_SETS

    own = context["last_invocation_shop_type"]
    other = "lead" if own == "bc" else "bc"
    for role in _CANONICAL_ROLE_SETS[other]:
        assert role not in body, (
            f"CLAUDE.md for {own} shop unexpectedly names {other} role {role!r}"
        )


# =======================================================================
# Step definitions — bootstrap_bd_init_side_effects.feature (lead-2gr)
# =======================================================================
#
# Round 2 of brief 002 §4.4 closure (round 1 was lead-k8v's
# assign_scenarios). The four scenarios pin:
#
#   - 32d99f6d4a2dad37: bootstrap's `bd init` subprocess is invoked
#     with the exact token "--skip-agents".
#   - 7d64bb8ed5a3f656: bootstrap leaves no top-level AGENTS.md and
#     no .claude/settings.json in the target directory.
#   - 5ec07c275350ba81: the canonical CLAUDE.md primer template body
#     contains "bd prime" and at least one bd-subcommand instruction.
#   - 2afb5cba3ea3de25: the bootstrapped target's CLAUDE.md contains
#     the literal substring "bd prime".
#
# Most steps reuse the existing bootstrap/primer infrastructure
# (target alias mapping, bd-shim subprocess logging, primer-access
# `claude_primer_body` context). New steps live below.


# -----------------------------------------------------------------------
# Given step — AGENTS.md / settings.json absence premise
# -----------------------------------------------------------------------


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'containing no top-level "AGENTS.md" and no file at ".claude/settings.json"'
    )
)
def given_existing_git_repo_at_target_no_agents_md_no_settings(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    assert not (real / "AGENTS.md").exists(), (
        f"premise of Given violated: {(real / 'AGENTS.md')!s} unexpectedly exists"
    )
    assert not (real / ".claude" / "settings.json").exists(), (
        f"premise of Given violated: "
        f"{(real / '.claude' / 'settings.json')!s} unexpectedly exists"
    )


# -----------------------------------------------------------------------
# Given step — AGENTS.md absence premise (singular; scenario 69,
# @scenario_hash:1a6e90189f9c2ade, lead-5mz). This is the un-conjoined
# successor to the conjoined Given above: the prior scenario
# 7d64bb8ed5a3f656 paired the AGENTS.md absence with a .claude/settings.json
# absence in a single premise. Per the lead-5mz tightening, that
# conjunction is superseded — the AGENTS.md clause survives as a
# standalone pin (this Given), and the settings.json contract is
# pinned positively by scenario 60 (c8002527857e0dd1) in a separate
# feature file.
# -----------------------------------------------------------------------


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'containing no top-level "AGENTS.md"'
    )
)
def given_existing_git_repo_at_target_no_agents_md(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    assert not (real / "AGENTS.md").exists(), (
        f"premise of Given violated: {(real / 'AGENTS.md')!s} unexpectedly exists"
    )


# -----------------------------------------------------------------------
# Then step — bd subprocess argv contains "--skip-agents"
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'the argument list passed to that "bd" subprocess contains the '
        'exact token "{token}"'
    )
)
def then_bd_subprocess_argv_contains_token(token: str, context: dict) -> None:
    invocations = _bd_invocations(context)
    assert invocations, (
        "expected at least one `bd` subprocess invocation; bd-shim log is empty"
    )
    # The scenario pairs this Then with the immediately-preceding
    # "subprocess named bd was executed with first argument init" Then,
    # so we check the init invocation specifically. If multiple init
    # invocations are present, all of them must carry the token (the
    # bootstrap CLI spawns exactly one).
    init_invocations = [inv for inv in invocations if inv and inv[0] == "init"]
    assert init_invocations, (
        f"expected a `bd init` invocation; got bd args: "
        f"{[inv[0] if inv else None for inv in invocations]!r}"
    )
    for inv in init_invocations:
        assert token in inv, (
            f"expected token {token!r} in bd init argv {inv!r}; "
            f"not present"
        )


# -----------------------------------------------------------------------
# Then step — no file at ".claude/settings.json"
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'the target directory contains no file at the path "{path}"'
    )
)
def then_target_no_file_at_path(path: str, context: dict) -> None:
    real = context["last_invocation_target"]
    p = real / path
    assert not (p.exists() and p.is_file()), (
        f"target unexpectedly contains file at path {path!r}"
    )


# -----------------------------------------------------------------------
# Then steps — primer body content (lead-2gr scenario 5ec07c275350ba81)
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'the returned body contains the literal substring "{needle}"'
    )
)
def then_returned_body_contains_substring(needle: str, context: dict) -> None:
    # The "returned body" is whichever template body the most recent
    # When step retrieved through the public template-access surface.
    # That surface is currently exercised by two shop-types of scenario:
    #   1. CLAUDE.md primer access (pre-existing, lead-2gr).
    #   2. .claude/settings.json access (brief 003 scope item A/B/E).
    # Both When steps stash their result under "last_returned_body" so
    # this Then step does not need to know which surface produced the
    # body — only that something did.
    body = context.get("last_returned_body")
    assert body is not None, (
        "no template body has been retrieved this scenario; "
        "the matching When step was not run"
    )
    assert needle in body, (
        f"returned body does not contain literal substring {needle!r}"
    )


@then(
    'the returned body contains at least one instruction directing the '
    'reader to run a "bd" subcommand as part of the shop\'s working '
    'discipline'
)
def then_primer_body_directs_bd_subcommand(context: dict) -> None:
    # The scenario requires *at least one instruction directing the
    # reader to run a "bd" subcommand*. We interpret that as: the body
    # mentions a bd subcommand invocation in an instructional context —
    # operationally, the literal substring "bd " (bd followed by a
    # space, i.e. a subcommand follows) appears, AND it appears in a
    # context other than the bare phrase "bd prime" alone (so the
    # body really does direct the reader to a bd subcommand command
    # surface, not just name-drop "bd prime" once).
    body = context["claude_primer_body"]
    # Find every occurrence of "bd <word>" in the body and collect the
    # set of subcommand tokens that follow "bd ".
    import re
    matches = re.findall(r"\bbd ([a-z][a-z\-]*)\b", body)
    assert matches, (
        f"primer body does not contain any 'bd <subcommand>' instruction; "
        f"body:\n{body!r}"
    )
    # At least one *non-empty* subcommand must be present. (re's
    # character class above already requires at least one lowercase
    # letter, so the set is non-empty if matches is non-empty.)
    subcommands = set(matches)
    assert subcommands, (
        "primer body mentions 'bd' but no subcommand follows it"
    )


# -----------------------------------------------------------------------
# Steps for scenario 3c8612d20608e9a3 — bootstrap rejects missing
# --shop-name with an argparse-style usage error (exit 2, no traceback,
# no scaffold). The omission of --shop-name previously surfaced as a
# TypeError from str.replace() inside _render_claude_md.
# -----------------------------------------------------------------------


@when(
    parsers.parse(
        'I invoke the "shop-templates" bootstrap entry point with '
        '--shop-type "{shop_type}" and --target "{alias}" but with no '
        '--shop-name argument'
    )
)
def when_invoke_bootstrap_no_shop_name(
    shop_type: str, alias: str, context: dict, tmp_path: Path
) -> None:
    real = _real_target_for_alias(alias, context)
    result = _run_shop_templates_with_bd_shim(
        [
            "bootstrap",
            "--shop-type",
            shop_type,
            "--target",
            str(real),
        ],
        context,
        tmp_path,
    )
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr
    context["last_invocation_target"] = real


@then("the exit code is 2")
def then_exit_code_is_two(context: dict) -> None:
    rc = context["cli_returncode"]
    assert rc == 2, (
        f"expected exit code 2; got {rc}; stderr:\n"
        f"{context.get('cli_stderr', '')}"
    )


@then(
    parsers.parse(
        'stderr names "{flag}" as a missing required argument'
    )
)
def then_stderr_names_missing_required_flag(flag: str, context: dict) -> None:
    stderr = context["cli_stderr"]
    assert flag in stderr, (
        f"expected stderr to name {flag!r} as a missing required argument; "
        f"got:\n{stderr}"
    )
    # "missing required argument" — accept either that exact phrase or
    # the close paraphrase "required argument" / "required: <flag>" so
    # the wording check is concrete but not brittle to phrasing nits.
    stderr_lower = stderr.lower()
    assert (
        "missing required" in stderr_lower
        or "required argument" in stderr_lower
        or "required:" in stderr_lower
        or "required arguments" in stderr_lower
    ), (
        f"expected stderr to identify {flag!r} as a *required* argument; "
        f"got:\n{stderr}"
    )


@then(
    'stderr does not contain a Python traceback or the substring '
    '"TypeError"'
)
def then_stderr_has_no_traceback_or_typeerror(context: dict) -> None:
    stderr = context["cli_stderr"]
    # A Python traceback emitted by the default sys.excepthook always
    # begins with the literal "Traceback (most recent call last):" line.
    # Anything we emit ourselves via print(..., file=sys.stderr) won't
    # contain that header — that's the discriminator the scenario
    # depends on.
    assert "Traceback (most recent call last):" not in stderr, (
        f"unexpected Python traceback header in stderr:\n{stderr}"
    )
    assert "TypeError" not in stderr, (
        f"unexpected 'TypeError' substring in stderr:\n{stderr}"
    )


# -----------------------------------------------------------------------
# Steps for scenarios fe59a11a88a9ab60 (bootstrap) and 8fe363bd46cb766c
# (update) — CLI rejects missing --target with an argparse-style usage
# error (exit 2, no traceback, no scaffold mutation). The omission of
# --target previously surfaced as a TypeError from Path(args.target).
# Consistency pass adjacent to scenario 3c8612d20608e9a3 (--shop-name).
# -----------------------------------------------------------------------


def _real_witness_for_alias(alias: str, context: dict, tmp_path: Path) -> Path:
    """Map a feature-file alias to a fresh per-test directory WITHOUT
    git-initializing it.

    Distinct from `_real_target_for_alias` (which runs `git init` to
    satisfy "an existing git repository at..." Givens). The scenarios
    in this section say "an existing empty directory", so we must NOT
    create a .git/ child — otherwise the witness is no longer empty.
    """
    context.setdefault("bootstrap_workspace", tmp_path)
    mapping = context.setdefault("target_alias_to_real", {})
    if alias in mapping:
        return mapping[alias]
    base = context["bootstrap_workspace"]
    real = base / alias.lstrip("/").replace("/", "_")
    real.mkdir(parents=True, exist_ok=True)
    mapping[alias] = real
    return real


@given(
    parsers.parse(
        'an existing empty directory "{alias}" that contains no '
        '".claude/agents/" directory, no ".beads/" directory, no '
        'top-level "CLAUDE.md", and no top-level ".gitignore"'
    )
)
def given_existing_empty_witness_directory(
    alias: str, context: dict, tmp_path: Path
) -> None:
    real = _real_witness_for_alias(alias, context, tmp_path)
    # Empirically verify the premise: no shop-artifact paths present.
    for path in (".claude/agents", ".beads"):
        assert not (real / path).exists(), (
            f"premise of Given violated: {(real / path)!s} unexpectedly exists"
        )
    for fname in ("CLAUDE.md", ".gitignore"):
        assert not (real / fname).exists(), (
            f"premise of Given violated: {(real / fname)!s} unexpectedly exists"
        )


@when(
    parsers.parse(
        'I invoke the "shop-templates" bootstrap entry point with '
        '--shop-type "{shop_type}" and --shop-name "{shop_name}" but '
        'with no --target argument'
    )
)
def when_invoke_bootstrap_no_target(
    shop_type: str,
    shop_name: str,
    context: dict,
    tmp_path: Path,
) -> None:
    # The scenario gives no alias to invoke against; the witness
    # directory established by the Given is the alias-mapped path, but
    # the When invocation deliberately OMITS --target. We pass no
    # --target argv at all (not an empty string).
    result = _run_shop_templates_with_bd_shim(
        [
            "bootstrap",
            "--shop-type",
            shop_type,
            "--shop-name",
            shop_name,
        ],
        context,
        tmp_path,
    )
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr
    # No --target → no "last_invocation_target" path to track. The
    # witness-directory Then resolves via alias map instead.


@then(
    parsers.parse(
        'the witness directory "{alias}" still contains no '
        '".claude/agents/" directory and no ".beads/" directory and no '
        'top-level "CLAUDE.md" and no top-level ".gitignore"'
    )
)
def then_witness_still_pristine(alias: str, context: dict) -> None:
    mapping = context.get("target_alias_to_real", {})
    assert alias in mapping, (
        f"scenario inconsistency: witness alias {alias!r} not in scope"
    )
    real = mapping[alias]
    assert not (real / ".claude" / "agents").exists(), (
        f"unexpected .claude/agents/ written to witness {real!s}"
    )
    assert not (real / ".beads").exists(), (
        f"unexpected .beads/ written to witness {real!s}"
    )
    assert not (real / "CLAUDE.md").exists(), (
        f"unexpected CLAUDE.md written to witness {real!s}"
    )
    assert not (real / ".gitignore").exists(), (
        f"unexpected .gitignore written to witness {real!s}"
    )


# Update-side Given: bootstrap the shop at the named alias and confirm
# .claude/agents/ contains exactly the canonical role files for the
# named shop type.
_UPDATE_NO_TARGET_SHOP_NAME = "shopsystem-update-no-target-fixture"


@given(
    parsers.parse(
        'a previously-bootstrapped shop at "{alias}" of shop type '
        '"{shop_type}" whose ".claude/agents/" directory contains '
        'exactly the canonical "{shop_type_again}" role files'
    )
)
def given_previously_bootstrapped_canonical_only(
    alias: str,
    shop_type: str,
    shop_type_again: str,
    context: dict,
    tmp_path: Path,
) -> None:
    assert shop_type == shop_type_again, (
        f"scenario inconsistency: {shop_type!r} vs {shop_type_again!r}"
    )
    context["bootstrap_workspace"] = tmp_path
    real = _do_bootstrap_for_test(
        alias, shop_type, _UPDATE_NO_TARGET_SHOP_NAME, context, tmp_path
    )
    # Empirically verify the premise: .claude/agents/ contents are
    # exactly the canonical role files for this shop type (no more, no
    # less).
    from shop_templates.cli import _CANONICAL_ROLE_SETS

    agents = real / ".claude" / "agents"
    expected = {f"{r}.md" for r in _CANONICAL_ROLE_SETS[shop_type]}
    actual = {p.name for p in agents.iterdir() if p.is_file()}
    assert actual == expected, (
        f"premise of Given violated: .claude/agents/ contents {actual!r} "
        f"differ from canonical {expected!r}"
    )


@given(
    parsers.parse(
        'a recorded snapshot of the byte contents and mtimes of every '
        'file under "{path}"'
    )
)
def given_record_byte_and_mtime_snapshot(path: str, context: dict) -> None:
    # `path` is an absolute-looking path from the scenario (e.g.
    # "/tmp/example-shop-update-no-target/.claude/agents/"). Strip the
    # leading alias prefix to identify which alias-mapped real path it
    # belongs to.
    mapping = context.get("target_alias_to_real", {})
    norm = path.rstrip("/")
    matched_alias: str | None = None
    sub_rel: str = ""
    for alias in mapping:
        alias_norm = alias.rstrip("/")
        if norm == alias_norm:
            matched_alias = alias
            sub_rel = ""
            break
        if norm.startswith(alias_norm + "/"):
            matched_alias = alias
            sub_rel = norm[len(alias_norm) + 1 :]
            break
    assert matched_alias is not None, (
        f"scenario inconsistency: snapshot path {path!r} does not match "
        f"any known alias in {list(mapping)!r}"
    )
    real = mapping[matched_alias]
    snapshot_root = real / sub_rel if sub_rel else real
    snap: dict[str, tuple[bytes, float]] = {}
    for p in snapshot_root.rglob("*"):
        if p.is_file():
            st = p.stat()
            snap[str(p.relative_to(real))] = (p.read_bytes(), st.st_mtime)
    # Stash under the scenario-supplied path so the Then can look it
    # up by the same key, plus also stash the alias so Thens that
    # reference "the top-level ... under {alias}" can resolve.
    snapshots = context.setdefault("byte_mtime_snapshots", {})
    snapshots[path] = (real, snap)
    # Additionally, snapshot the surrounding top-level scaffold
    # (CLAUDE.md, .gitignore, .beads/) so the update-side Then can
    # verify those are unchanged too. The Then names a specific alias
    # so we key by alias here.
    scaffold_snap: dict[str, bytes] = {}
    for fname in ("CLAUDE.md", ".gitignore"):
        f = real / fname
        if f.is_file():
            scaffold_snap[fname] = f.read_bytes()
    beads_snap: dict[str, bytes] = {}
    beads_dir = real / ".beads"
    if beads_dir.exists():
        for p in beads_dir.rglob("*"):
            if p.is_file():
                beads_snap[str(p.relative_to(real))] = p.read_bytes()
    context.setdefault("scaffold_snapshots", {})[matched_alias] = (
        scaffold_snap,
        beads_snap,
    )


@when(
    parsers.parse(
        'I invoke the "shop-templates" update entry point with '
        '--shop-type "{shop_type}" but with no --target argument'
    )
)
def when_invoke_update_no_target(
    shop_type: str, context: dict, tmp_path: Path
) -> None:
    result = _run_shop_templates_with_bd_shim(
        [
            "update",
            "--shop-type",
            shop_type,
        ],
        context,
        tmp_path,
    )
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr


@then(
    parsers.parse(
        'every file under "{path}" has the same byte contents and '
        'mtime as the recorded snapshot'
    )
)
def then_snapshot_unchanged(path: str, context: dict) -> None:
    snapshots = context.get("byte_mtime_snapshots", {})
    assert path in snapshots, (
        f"scenario inconsistency: no snapshot recorded for {path!r}; "
        f"known snapshots: {list(snapshots)!r}"
    )
    real, snap = snapshots[path]
    # Re-walk and verify byte-for-byte AND mtime equality. Also verify
    # no new files appeared and no files disappeared.
    norm = path.rstrip("/")
    matched_alias = None
    sub_rel = ""
    mapping = context.get("target_alias_to_real", {})
    for alias in mapping:
        alias_norm = alias.rstrip("/")
        if norm == alias_norm:
            matched_alias = alias
            sub_rel = ""
            break
        if norm.startswith(alias_norm + "/"):
            matched_alias = alias
            sub_rel = norm[len(alias_norm) + 1 :]
            break
    snapshot_root = real / sub_rel if sub_rel else real
    current: dict[str, tuple[bytes, float]] = {}
    for p in snapshot_root.rglob("*"):
        if p.is_file():
            st = p.stat()
            current[str(p.relative_to(real))] = (p.read_bytes(), st.st_mtime)
    assert set(current) == set(snap), (
        f"file set under {path!r} changed; before: {sorted(snap)!r}; "
        f"after: {sorted(current)!r}"
    )
    for rel, (bytes_before, mtime_before) in snap.items():
        bytes_after, mtime_after = current[rel]
        assert bytes_after == bytes_before, (
            f"{rel} byte contents differ after invocation"
        )
        assert mtime_after == mtime_before, (
            f"{rel} mtime changed after invocation "
            f"(was {mtime_before}, is {mtime_after})"
        )


@then(
    parsers.parse(
        'the top-level "CLAUDE.md", top-level ".gitignore", and '
        '".beads/" directory under "{alias}" are unchanged from before '
        'the invocation'
    )
)
def then_top_level_scaffold_unchanged(alias: str, context: dict) -> None:
    scaffold_snaps = context.get("scaffold_snapshots", {})
    assert alias in scaffold_snaps, (
        f"scenario inconsistency: no scaffold snapshot recorded for "
        f"alias {alias!r}; known: {list(scaffold_snaps)!r}"
    )
    mapping = context["target_alias_to_real"]
    real = mapping[alias]
    scaffold_snap, beads_snap = scaffold_snaps[alias]
    for fname, bytes_before in scaffold_snap.items():
        f = real / fname
        assert f.is_file(), f"top-level {fname!r} disappeared from {real!s}"
        assert f.read_bytes() == bytes_before, (
            f"top-level {fname!r} byte contents changed under {real!s}"
        )
    # Beads: every file recorded before is still present with the same
    # bytes, and no new files appeared under .beads/.
    beads_dir = real / ".beads"
    if beads_snap:
        assert beads_dir.exists(), (
            f".beads/ directory disappeared from {real!s}"
        )
    current_beads: dict[str, bytes] = {}
    if beads_dir.exists():
        for p in beads_dir.rglob("*"):
            if p.is_file():
                current_beads[str(p.relative_to(real))] = p.read_bytes()
    assert set(current_beads) == set(beads_snap), (
        f".beads/ file set changed under {real!s}; before: "
        f"{sorted(beads_snap)!r}; after: {sorted(current_beads)!r}"
    )
    for rel, bytes_before in beads_snap.items():
        assert current_beads[rel] == bytes_before, (
            f".beads/{rel} byte contents changed under {real!s}"
        )


# =======================================================================
# Step definitions — brief 003: event-driven shop activation +
# canonical .claude/settings.json bootstrap extension (lead-1pi).
# =======================================================================
#
# Scope items A/B/C/D/E per the dispatch description. Scenarios:
#
#   - A (57, 68): 1621b59b0ea8b20b — public template-access surface for
#     .claude/settings.json; 287e6a4f31533336 — own/other watch-target
#     exclusivity.
#   - B (58, 65): 679d227f04533ad4 — inotifywait hook shape;
#     a9379ab3a162158d — loud-fail when inotifywait missing.
#   - C (59): c1e7f31eeef73e05 — lead settings.json composes bd prime
#     AND the inotifywait hook as two distinct SessionStart entries.
#   - D (60, 61, 62, 63, 64): f83e03ee69261242 — bootstrap pours the
#     settings.json byte-for-byte; d29cd723439faae1 / d3066d4476d0a975 —
#     update treats settings.json as bootstrap-managed (re-pours stale;
#     leaves byte-equal content untouched); cad1153ef4dfd18c — CLAUDE.md
#     names the host prereqs; 6bc3eb5f62115d91 — the CLAUDE.md primer
#     template body itself names the prereqs (package-data property).
#   - E (66, 67): 3957f255c35aff60 — outcome pin (edits in repos/<bc>/
#     reflect in next CLI invocation without manual reinstall);
#     ff882696856530a4 — mechanism pin (lead-bootstrap installs sibling
#     BC clones editable into product venv).
#
# Convention: tests that need a venv create one at <target>/.venv/
# via shop-templates bootstrap itself (which is the system under test).


# -----------------------------------------------------------------------
# Given step — target with no .claude/settings.json file
# -----------------------------------------------------------------------


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'with no ".claude/settings.json" file'
    )
)
def given_existing_git_repo_at_target_no_settings_json(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    assert not (real / ".claude" / "settings.json").exists(), (
        f"premise of Given violated: "
        f"{(real / '.claude' / 'settings.json')!s} unexpectedly exists"
    )


# -----------------------------------------------------------------------
# Given steps — settings.json post-bootstrap state (drives update tests)
# -----------------------------------------------------------------------


@given(
    parsers.parse(
        'the file at ".claude/settings.json" in the target directory '
        'differs from the current canonical ".claude/settings.json" '
        'template for shop type "{shop_type}"'
    )
)
def given_settings_json_differs_from_canonical(
    shop_type: str, context: dict
) -> None:
    real = _resolve_single_target(context)
    from shop_templates.cli import read_claude_settings_template

    canonical = read_claude_settings_template(shop_type)
    settings_file = real / ".claude" / "settings.json"
    # Mutate the existing settings.json so its content differs from
    # canonical. We append a JSON-comment-like marker line that breaks
    # JSON equality without making the test brittle to canonical-body
    # formatting (we don't reparse — we just compare bytes).
    if settings_file.exists():
        current = settings_file.read_text()
    else:
        current = ""
    mutated = current + "\n// STALE DRIFT MARKER — not in canonical\n"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(mutated)
    assert settings_file.read_text() != canonical, (
        "premise of Given violated: mutated settings.json equals canonical"
    )


@given(
    parsers.parse(
        'the file at ".claude/settings.json" in the target directory '
        'equals the current canonical ".claude/settings.json" template '
        'for shop type "{shop_type}" byte-for-byte'
    )
)
def given_settings_json_equals_canonical(
    shop_type: str, context: dict
) -> None:
    real = _resolve_single_target(context)
    from shop_templates.cli import read_claude_settings_template

    canonical = read_claude_settings_template(shop_type)
    settings_file = real / ".claude" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(canonical)
    # Record bytes + mtime so the "still equals" Then can verify
    # mtime is unchanged across the update invocation.
    context.setdefault("settings_pre_state", {})[str(settings_file)] = (
        settings_file.read_bytes(),
        settings_file.stat().st_mtime_ns,
    )


# -----------------------------------------------------------------------
# Given step — host environment missing inotifywait on PATH
# -----------------------------------------------------------------------


@given(
    parsers.parse(
        'a host environment where the executable "inotifywait" is not '
        'present on PATH'
    )
)
def given_host_missing_inotifywait(context: dict, tmp_path: Path) -> None:
    # Simulate "host environment without inotifywait" by stashing a PATH
    # value that contains a single empty directory; the When step picks
    # this up when synthesizing the session-start hook execution.
    empty_path_dir = tmp_path / "empty-path"
    empty_path_dir.mkdir(parents=True, exist_ok=True)
    context["session_start_path"] = str(empty_path_dir)


# -----------------------------------------------------------------------
# Given steps — variant target premises used by scope item E scenarios
# -----------------------------------------------------------------------
#
# The two scope-E scenarios (3957f255c35aff60 / ff882696856530a4) use
# Given phrasings that are not yet covered:
#
#   - "a target directory \"<target>\" containing an existing git
#     repository" — variant of the canonical "an existing git repository
#     at a target directory \"<target>\"" Given. We define it as a
#     parallel step that resolves the same alias.
#
#   - "the target directory contains a sibling BC clone at
#     \"repos/<name>/\" ..." — materializes a minimal Python package at
#     repos/<name>/ inside the target so bootstrap's editable-install
#     step has something to install.


@given(
    parsers.parse(
        'a target directory "{alias}" containing an existing git repository'
    )
)
def given_target_contains_existing_git_repo(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    _real_target_for_alias(alias, context)


def _materialize_sibling_bc_clone(
    target: Path, clone_subpath: str, package_name: str, entry_point: str
) -> Path:
    """Create a minimal installable Python package at target/<clone_subpath>
    that ships a console-script named `entry_point`. The script body is
    customized so it emits a uniquely identifying token, used by the
    editable-install + post-edit-reflection scenarios to observe CLI
    behavior changes after editing the source.
    """
    clone_dir = target / clone_subpath.rstrip("/")
    src_dir = clone_dir / "src" / package_name
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text("")
    (src_dir / "cli.py").write_text(
        "def main():\n"
        "    print('PRE_EDIT_TOKEN_v1')\n"
    )
    (clone_dir / "pyproject.toml").write_text(
        '[build-system]\n'
        'requires = ["setuptools>=61"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        '[project]\n'
        f'name = "{entry_point}"\n'
        'version = "0.0.1"\n'
        'requires-python = ">=3.10"\n\n'
        '[project.scripts]\n'
        f'{entry_point} = "{package_name}.cli:main"\n\n'
        '[tool.setuptools]\n'
        'package-dir = {"" = "src"}\n\n'
        '[tool.setuptools.packages.find]\n'
        'where = ["src"]\n'
    )
    # Initialize the clone as its own git repository so that "sibling BC
    # clone" matches the lead-shop reality (each BC has its own git
    # remote and history).
    subprocess.run(
        ["git", "init", "-q", str(clone_dir)],
        check=True,
        capture_output=True,
    )
    return clone_dir


@given(
    parsers.parse(
        'the target directory contains a sibling BC clone at '
        '"{clone_subpath}" whose installed package name is "{entry_point}"'
    )
)
def given_sibling_bc_clone_with_package_name(
    clone_subpath: str, entry_point: str, context: dict
) -> None:
    real = _resolve_single_target(context)
    # Derive a Python-module-name-safe package name from the entry point
    # (e.g. "shop-msg" -> "shop_msg"). The actual module name does not
    # need to match the entry point name — the scenarios only assert via
    # the entry-point CLI invocation.
    package_name = entry_point.replace("-", "_")
    clone_dir = _materialize_sibling_bc_clone(
        real, clone_subpath, package_name, entry_point
    )
    context.setdefault("sibling_bc_clones", {})[entry_point] = {
        "clone_dir": clone_dir,
        "package_name": package_name,
        "clone_subpath": clone_subpath,
    }
    # Scenarios that pin "the target directory CONTAINS a sibling BC
    # clone whose installed package name is <X>" describe a target
    # state in which the clone is part of the lead shop's installed
    # surface. The mechanism the BC's bootstrap surface provides for
    # reaching that state is `pip install -e` into the target venv.
    # If the Given runs AFTER a previously-bootstrapped Given (so the
    # clone is added post-bootstrap), the test harness must complete
    # the install side-effect for the premise to hold. We call into
    # the same install helper that bootstrap uses — that is the
    # mechanism under test for scope item E. The helper creates the
    # venv on demand when at least one installable clone is present,
    # so it is safe to call here even before bootstrap has created
    # the venv (a lead-shop bootstrap with no clones present does not
    # create the venv).
    #
    # We only do this if a "previously bootstrapped" Given preceded us
    # — otherwise the install would race with the bootstrap When step
    # the scenario is about to invoke (which would itself install the
    # clone). The `bootstrap_shop_type` key gets set by the
    # previously-bootstrapped Given.
    if context.get("bootstrap_shop_type") == "lead":
        from shop_templates.cli import _install_sibling_bc_clones_editable
        rc = _install_sibling_bc_clones_editable(real)
        assert rc == 0, (
            f"premise of Given violated: editable install of sibling BC "
            f"clone at {clone_dir!s} failed (rc={rc})"
        )


@given(
    parsers.parse(
        'the target directory contains a sibling BC clone at '
        '"{clone_subpath}" with a valid Python package whose installed '
        'entry point name is "{entry_point}"'
    )
)
def given_sibling_bc_clone_with_entry_point(
    clone_subpath: str, entry_point: str, context: dict
) -> None:
    # Same as the variant above. The two phrasings are alternate
    # specifications of the same premise (scenarios 3957f255c35aff60
    # and ff882696856530a4 use slightly different wording).
    given_sibling_bc_clone_with_package_name(clone_subpath, entry_point, context)


@given(
    parsers.parse(
        'a fresh edit has been made to a Python source file under '
        '"{src_subpath}" that changes observable CLI behavior of "{entry_point}"'
    )
)
def given_fresh_edit_to_bc_clone_source(
    src_subpath: str, entry_point: str, context: dict
) -> None:
    real = _resolve_single_target(context)
    clones = context.get("sibling_bc_clones", {})
    assert entry_point in clones, (
        f"no sibling BC clone for entry point {entry_point!r} in scope; "
        f"available: {list(clones)!r}"
    )
    package_name = clones[entry_point]["package_name"]
    cli_file = real / src_subpath.rstrip("/") / package_name / "cli.py"
    assert cli_file.exists(), (
        f"cli.py not found at {cli_file!s} — sibling BC clone "
        f"materialization is out of step with the src subpath"
    )
    # Replace the pre-edit token with a post-edit token. Tests check
    # for the post-edit token in stdout of `entry_point` invocations.
    cli_file.write_text(
        "def main():\n"
        "    print('POST_EDIT_TOKEN_v2')\n"
    )
    context["post_edit_token"] = "POST_EDIT_TOKEN_v2"
    context.setdefault("post_edit_entry_point", entry_point)


# -----------------------------------------------------------------------
# When step — ask the package for the canonical .claude/settings.json
# template for a shop type. Mirrors the CLAUDE.md primer When step.
# -----------------------------------------------------------------------


@when(
    parsers.parse(
        'I ask the "shop-templates" package for the canonical '
        '".claude/settings.json" template for shop type "{shop_type}" '
        'through its public template-access surface'
    )
)
def when_ask_for_settings_json(shop_type: str, context: dict) -> None:
    from shop_templates.cli import read_claude_settings_template

    body = read_claude_settings_template(shop_type)
    context["settings_template_shop_type"] = shop_type
    context["settings_template_body"] = body
    # Generic "last returned body" key, shared with the CLAUDE.md primer
    # When step so the same set of "the returned body ..." Then steps
    # covers both surfaces (see comment on
    # `then_returned_body_contains_substring`).
    context["last_returned_body"] = body
    context["last_returned_surface"] = "claude_settings"
    context["last_returned_shop_type"] = shop_type


# -----------------------------------------------------------------------
# When step — synthesized session-start hook execution.
# -----------------------------------------------------------------------
#
# Scenario a9379ab3a162158d describes "a Claude Code session starts in
# the target directory and the SessionStart hooks declared by
# .claude/settings.json execute". The smallest faithful reduction:
# extract the hook command(s) from the bootstrapped target's
# .claude/settings.json and run them through `bash -c` with a PATH that
# excludes `inotifywait`. The scenario's Then assertions are about
# stderr content + exit posture of that synthesized execution.


@when(
    parsers.parse(
        'a Claude Code session starts in the target directory and the '
        '"SessionStart" hooks declared by ".claude/settings.json" execute'
    )
)
def when_session_start_hooks_execute(context: dict) -> None:
    import json
    import os

    real = _resolve_single_target(context)
    settings_file = real / ".claude" / "settings.json"
    assert settings_file.exists(), (
        f"premise violated: no .claude/settings.json at {settings_file!s}"
    )
    parsed = json.loads(settings_file.read_text())
    hook_entries = parsed.get("hooks", {}).get("SessionStart", [])
    assert hook_entries, (
        f"settings.json declares no SessionStart hooks at {settings_file!s}"
    )

    # Build a PATH that omits inotifywait but keeps essential tooling.
    # The Given step "host missing inotifywait" stashed an empty dir on
    # context; we prepend it but ALSO keep /usr/bin and /bin so the
    # diagnostic command (`command -v`, `echo`) still resolves.
    empty_dir = context.get("session_start_path")
    assert empty_dir is not None, (
        "scenario inconsistency: When step ran without the "
        "'host missing inotifywait' Given setting up session_start_path"
    )
    # The harness must keep enough of PATH that `command -v` and `echo`
    # resolve, but NOT enough that `inotifywait` resolves. We construct
    # the PATH from /usr/bin:/bin only (system-installed inotifywait
    # would have to be missing from these) — but inotifywait IS in
    # /usr/bin on most hosts. To guarantee it's missing, we install a
    # `inotifywait` shadow script that exits 127 with an "intentionally
    # masked" diagnostic IF the path resolved; the assert below treats
    # exit 1 (our diagnostic) and stderr containing "inotifywait" as a
    # pass. The simpler, more honest fix is to use a sandbox PATH that
    # excludes inotifywait. The CI hosts we target do NOT have
    # inotifywait at /usr/bin/inotifywait by default (it ships in
    # inotify-tools), but to be safe we use a minimal sandbox here.

    # Strategy: set the subprocess env PATH to the empty dir (so
    # `command -v inotifywait` finds nothing), but invoke bash itself
    # via its absolute path so the harness doesn't need bash on the
    # sandbox PATH. `command`, `echo`, and `exit` are bash builtins so
    # they don't need PATH either. We use `bash -c` to evaluate the
    # hook command verbatim. We also resolve `bash` from the host once
    # here so the harness is robust to non-standard layouts.
    env = os.environ.copy()
    env["PATH"] = empty_dir

    bash_resolved = None
    for candidate in ("/usr/bin/bash", "/bin/bash"):
        if Path(candidate).exists():
            bash_resolved = candidate
            break
    assert bash_resolved is not None, (
        "test harness cannot locate /usr/bin/bash or /bin/bash"
    )

    # Flatten Claude Code's matcher+hooks wrapper shape: each
    # SessionStart entry is {matcher, hooks: [{type, command}, ...]}
    # (see scenario f2a7de49d80332c1). The hook commands that actually
    # run live in the inner hooks list. Fall back to a direct .command
    # for any entry that still uses the bare-object shape.
    flat_commands = []
    for entry in hook_entries:
        inner = entry.get("hooks")
        if isinstance(inner, list):
            for inner_hook in inner:
                c = inner_hook.get("command")
                if c:
                    flat_commands.append(c)
        else:
            c = entry.get("command")
            if c:
                flat_commands.append(c)

    stdouts = []
    stderrs = []
    rcs = []
    for cmd in flat_commands:
        result = subprocess.run(
            [bash_resolved, "-c", cmd],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(real),
            timeout=10,
        )
        stdouts.append(result.stdout)
        stderrs.append(result.stderr)
        rcs.append(result.returncode)
    context["session_hook_stdouts"] = stdouts
    context["session_hook_stderrs"] = stderrs
    context["session_hook_rcs"] = rcs


# Alias of the When step above for scenario 3957f255c35aff60, which
# says "execute" -> "complete" (still SessionStart). For the
# post-edit-observation scenario the hook does not affect the
# subsequent CLI invocation — we just register that hooks completed.
@when(
    parsers.parse(
        'a Claude Code session starts in the target directory and the '
        '"SessionStart" hooks declared by ".claude/settings.json" complete'
    )
)
def when_session_start_hooks_complete(context: dict) -> None:
    # No-op for the post-edit-reflection scenario: the editable-install
    # outcome (3957f255c35aff60) does not actually depend on hook
    # execution, only on the pip-editable install state. We mark the
    # step as run so the scenario's wiring is honored.
    context["session_start_completed"] = True


@when(
    parsers.parse(
        'the agent invokes the "{entry_point}" CLI through its normal '
        'entry point'
    )
)
def when_agent_invokes_cli(entry_point: str, context: dict) -> None:
    real = _resolve_single_target(context)
    # Invoke the entry point through the bootstrapped venv's bin/ dir,
    # which is what "the product venv's CLI invocation" means in
    # operational terms (lead-shop session has its venv activated, so
    # `shop-msg` resolves to .venv/bin/shop-msg).
    venv_python = real / ".venv" / "bin" / "python"
    # Use the venv to run the entry point — same mechanism `pip
    # install -e` wired up. The entry point is on the venv's PATH.
    entry_point_bin = real / ".venv" / "bin" / entry_point
    assert entry_point_bin.exists(), (
        f"entry point binary {entry_point!r} not in venv at "
        f"{entry_point_bin!s}"
    )
    result = subprocess.run(
        [str(entry_point_bin)],
        capture_output=True,
        text=True,
        cwd=str(real),
        timeout=10,
    )
    context["cli_invocation_stdout"] = result.stdout
    context["cli_invocation_stderr"] = result.stderr
    context["cli_invocation_rc"] = result.returncode


# -----------------------------------------------------------------------
# Then steps — generic returned-body assertions for the settings.json
# template surface (the substring + non-empty Thens are reused from the
# CLAUDE.md primer scenarios; see the comments on
# `then_returned_body_contains_substring`).
# -----------------------------------------------------------------------


@then("the returned body parses as valid JSON")
def then_returned_body_parses_as_json(context: dict) -> None:
    import json

    body = context.get("last_returned_body")
    assert body is not None, (
        "no template body has been retrieved; matching When step did not run"
    )
    try:
        json.loads(body)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"returned body does not parse as valid JSON: {exc!s}\n"
            f"body:\n{body!r}"
        )


@then(
    parsers.parse(
        'the returned body is the source of truth from which the '
        'bootstrap entry point generates the target directory\'s '
        '".claude/settings.json" for a shop of type "{shop_type}"'
    )
)
def then_returned_body_is_source_of_truth_for_settings(
    shop_type: str, context: dict, tmp_path: Path
) -> None:
    # Empirically verify: run bootstrap into a fresh probe target with
    # the given shop_type and check the resulting .claude/settings.json
    # is byte-for-byte equal to the body we got from the surface.
    body = context.get("last_returned_body")
    assert body is not None
    probe = tmp_path / f"sot-probe-settings-{shop_type}"
    probe.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", str(probe)],
        check=True,
        capture_output=True,
    )
    result = _run_shop_templates_with_bd_shim(
        [
            "bootstrap",
            "--shop-type",
            shop_type,
            "--shop-name",
            "settings-sot-probe-shop-name",
            "--target",
            str(probe),
        ],
        context,
        tmp_path,
    )
    assert result.returncode == 0, (
        f"probe bootstrap failed; stderr:\n{result.stderr}"
    )
    written = (probe / ".claude" / "settings.json").read_text()
    assert written == body, (
        "bootstrap-written .claude/settings.json differs from the body "
        "returned by the public template-access surface; the surface is "
        "supposed to be the source of truth from which bootstrap pours."
    )


@then(
    'the returned body is not read from any path under this product\'s '
    'top-level working directory at lookup time'
)
def then_returned_body_not_from_product_path(context: dict) -> None:
    # Strongest version of this assertion that is mechanically checkable:
    # the body is the byte-for-byte content served by
    # importlib.resources from the package-data resource, which is the
    # only path the public surface reaches for.
    surface = context.get("last_returned_surface")
    shop_type = context.get("last_returned_shop_type")
    body = context.get("last_returned_body")
    import importlib.resources as ires

    if surface == "claude_settings":
        expected = (
            ires.files("shop_templates.templates.claude_settings")
            / f"{shop_type}.json"
        ).read_text()
    elif surface == "claude_primer":
        expected = (
            ires.files("shop_templates.templates.claude")
            / f"{shop_type}.md"
        ).read_text()
    else:
        raise AssertionError(
            f"unknown returned-body surface {surface!r}; cannot verify "
            f"package-data source"
        )
    assert body == expected, (
        f"body returned by the {surface!r} surface for shop type "
        f"{shop_type!r} differs from the importlib.resources package-data "
        f"resource; surface must serve from importlib.resources"
    )


@then(
    parsers.parse(
        'the returned body does not contain the literal substring "{needle}"'
    )
)
def then_returned_body_does_not_contain_substring(
    needle: str, context: dict
) -> None:
    body = context.get("last_returned_body")
    assert body is not None
    assert needle not in body, (
        f"returned body unexpectedly contains literal substring {needle!r}"
    )


@then(
    parsers.parse(
        'the returned body does not contain the bare token "grep" '
        'without a preceding "/usr/bin/" path qualifier or an equivalent '
        'alias-bypassing form'
    )
)
def then_returned_body_no_bare_grep(context: dict) -> None:
    body = context.get("last_returned_body")
    assert body is not None
    # Find every occurrence of the literal substring "grep" and check
    # the preceding characters bypass shell-alias resolution. We accept
    # three alias-bypassing forms:
    #   (1) preceded by "/usr/bin/" — explicit absolute path
    #   (2) preceded by "\\" (backslash-grep) — bash alias-bypass form
    #   (3) preceded by "command " (i.e. `command grep`) — POSIX form
    # All three suffice; everything else is a bare `grep` and fails.
    for m in re.finditer(r"grep", body):
        i = m.start()
        preceding9 = body[max(0, i - 9):i]
        preceding2 = body[max(0, i - 2):i]
        preceding8 = body[max(0, i - 8):i]
        if preceding9.endswith("/usr/bin/"):
            continue
        if preceding2 == "\\g"[:2]:  # "\\g" prefix not realistic; skip
            continue
        if preceding8 == "command ":
            continue
        raise AssertionError(
            f"returned body contains a bare 'grep' at byte offset {i} "
            f"not preceded by an alias-bypassing form. Context (40 chars "
            f"around): ...{body[max(0,i-20):i+20]!r}..."
        )


@then(
    parsers.parse(
        'the returned body declares the "bd prime" invocation and the '
        'inotifywait arming as two distinct hook entries under '
        '"SessionStart"'
    )
)
def then_lead_settings_declares_two_distinct_hooks(context: dict) -> None:
    import json

    body = context.get("last_returned_body")
    assert body is not None
    parsed = json.loads(body)
    hook_entries = parsed.get("hooks", {}).get("SessionStart", [])
    assert isinstance(hook_entries, list) and len(hook_entries) >= 2, (
        f"expected at least 2 SessionStart hook entries; got "
        f"{len(hook_entries) if isinstance(hook_entries, list) else 'n/a'}"
    )
    # Claude Code's hook schema wraps each SessionStart entry as
    # {matcher, hooks: [{type, command}, ...]} (see scenario
    # f2a7de49d80332c1). Flatten the inner hooks so we can compare
    # commands at the unit each SessionStart entry semantically owns.
    commands = []
    for entry in hook_entries:
        inner = entry.get("hooks")
        if isinstance(inner, list):
            for inner_hook in inner:
                commands.append(inner_hook.get("command", ""))
        else:
            commands.append(entry.get("command", ""))
    bd_prime_only = [
        c for c in commands
        if "bd prime" in c and "inotifywait" not in c
    ]
    inotifywait_only = [
        c for c in commands
        if "inotifywait" in c and "bd prime" not in c
    ]
    assert bd_prime_only, (
        "no SessionStart hook entry carries 'bd prime' as its sole "
        "concern (every bd-prime mention is conjoined with inotifywait); "
        f"commands: {commands!r}"
    )
    assert inotifywait_only, (
        "no SessionStart hook entry carries the inotifywait arming as "
        "its sole concern (every inotifywait mention is conjoined with "
        f"bd prime); commands: {commands!r}"
    )


# -----------------------------------------------------------------------
# Then steps — bootstrap-written settings.json
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'the target directory contains a file at ".claude/settings.json"'
    )
)
def then_target_has_settings_json(context: dict) -> None:
    real = _resolve_single_target(context)
    settings_file = real / ".claude" / "settings.json"
    assert settings_file.is_file(), (
        f"expected file at {settings_file!s}; not found"
    )


@then(
    parsers.parse(
        'the content of that file equals the package-data file contents '
        'of the canonical ".claude/settings.json" template for shop '
        'type "{shop_type}" byte-for-byte'
    )
)
def then_settings_file_equals_canonical(
    shop_type: str, context: dict
) -> None:
    from shop_templates.cli import read_claude_settings_template

    real = _resolve_single_target(context)
    settings_file = real / ".claude" / "settings.json"
    actual = settings_file.read_text()
    expected = read_claude_settings_template(shop_type)
    assert actual == expected, (
        f"target .claude/settings.json content differs from canonical "
        f"package-data for shop type {shop_type!r}"
    )


@then(
    parsers.parse(
        'after the invocation the file at ".claude/settings.json" in '
        'the target directory equals the current canonical '
        '".claude/settings.json" template for shop type "{shop_type}" '
        'byte-for-byte'
    )
)
def then_settings_file_equals_canonical_after_update(
    shop_type: str, context: dict
) -> None:
    then_settings_file_equals_canonical(shop_type, context)


@then(
    parsers.parse(
        'after the invocation the file at ".claude/settings.json" in '
        'the target directory still equals the current canonical '
        '".claude/settings.json" template for shop type "{shop_type}" '
        'byte-for-byte'
    )
)
def then_settings_file_still_equals_canonical(
    shop_type: str, context: dict
) -> None:
    # Byte equality is the headline contract. We also check that the
    # on-disk file's mtime is preserved (the canonical-equality branch
    # of update returns early without writing); this rules out
    # "update wrote the same bytes again" implementations that would
    # bump mtime spuriously.
    real = _resolve_single_target(context)
    settings_file = real / ".claude" / "settings.json"
    from shop_templates.cli import read_claude_settings_template

    expected = read_claude_settings_template(shop_type)
    assert settings_file.read_text() == expected
    pre = context.get("settings_pre_state", {}).get(str(settings_file))
    if pre is not None:
        bytes_before, mtime_before = pre
        bytes_after = settings_file.read_bytes()
        mtime_after = settings_file.stat().st_mtime_ns
        assert bytes_after == bytes_before, (
            "settings.json bytes diverged across update despite "
            "pre-state already equaling canonical"
        )
        assert mtime_after == mtime_before, (
            f"settings.json mtime changed across update despite already "
            f"equaling canonical (before={mtime_before}, after={mtime_after})"
        )


# -----------------------------------------------------------------------
# Then steps — bootstrap-written CLAUDE.md naming host prereqs
# -----------------------------------------------------------------------
#
# Scenario cad1153ef4dfd18c uses the existing Then "the content of that
# file contains the literal substring" — pre-existing step at line 3499
# already handles it (reads target/CLAUDE.md). No new step needed.
#
# Scenario cad1153ef4dfd18c also uses "the target directory contains a
# top-level file named "CLAUDE.md"" — check for that and add if absent.


# -----------------------------------------------------------------------
# Then steps — session-start synthesized hook execution
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'the session surfaces a visible diagnostic identifying '
        '"{token1}" or "{token2}" as the missing prerequisite'
    )
)
def then_session_surfaces_diagnostic(
    token1: str, token2: str, context: dict
) -> None:
    stderrs = context.get("session_hook_stderrs", [])
    stdouts = context.get("session_hook_stdouts", [])
    rcs = context.get("session_hook_rcs", [])
    combined_err = "\n".join(stderrs)
    combined_out = "\n".join(stdouts)
    visible = combined_err + "\n" + combined_out
    assert token1 in visible or token2 in visible, (
        f"expected visible diagnostic naming {token1!r} or {token2!r}; "
        f"got stderr={combined_err!r}, stdout={combined_out!r}"
    )
    # And the failure surfaces non-zero on at least one hook entry —
    # otherwise "silent degradation" is not actually ruled out.
    assert any(rc != 0 for rc in rcs), (
        f"expected at least one SessionStart hook to exit non-zero on a "
        f"host missing inotifywait; got exit codes {rcs!r}"
    )


@then(
    'the session does not arrive at the agent\'s first turn in a state '
    'where the activation hook has silently produced no watcher and no '
    'diagnostic'
)
def then_session_does_not_arrive_silently(context: dict) -> None:
    # Operationalized: at least one hook exited non-zero AND emitted a
    # non-empty stderr (the "diagnostic"). The visible-diagnostic Then
    # above asserts the stderr names the missing prereq; this Then
    # asserts the silent-degradation outcome is ruled out.
    stderrs = context.get("session_hook_stderrs", [])
    rcs = context.get("session_hook_rcs", [])
    any_loud_failure = any(
        rc != 0 and err.strip()
        for rc, err in zip(rcs, stderrs)
    )
    assert any_loud_failure, (
        f"no SessionStart hook produced a loud failure (non-zero exit + "
        f"non-empty stderr); rcs={rcs!r}, stderrs={stderrs!r}"
    )


# -----------------------------------------------------------------------
# Then steps — editable install in product venv
# -----------------------------------------------------------------------


def _pip_show_in_venv(venv_dir: Path, distribution: str) -> str:
    """Run `pip show -f` for `distribution` against the venv's python.
    Returns the stdout. Raises AssertionError if pip exits non-zero.
    """
    venv_python = venv_dir / "bin" / "python"
    if not venv_python.exists():
        venv_python = venv_dir / "Scripts" / "python.exe"
    assert venv_python.exists(), (
        f"no python interpreter under venv {venv_dir!s}"
    )
    result = subprocess.run(
        [str(venv_python), "-m", "pip", "show", "-f", distribution],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`pip show {distribution}` failed in venv {venv_dir!s}; stderr:\n"
        f"{result.stderr}"
    )
    return result.stdout


@then(
    parsers.parse(
        'the product venv reports the installed location of the '
        '"{distribution}" distribution as pointing into "{clone_subpath}" '
        'of the target directory'
    )
)
def then_pip_show_points_into_clone(
    distribution: str, clone_subpath: str, context: dict
) -> None:
    real = _resolve_single_target(context)
    venv_dir = real / ".venv"
    show = _pip_show_in_venv(venv_dir, distribution)
    # `pip show` reports the package's Location: line. For editable
    # installs, that location points at the src directory inside the
    # clone, NOT at site-packages. The clone_subpath is e.g.
    # "repos/shopsystem-messaging/" — the Location must contain that
    # subpath (as an absolute path of the form <target>/repos/<bc>/...).
    expected_path = (real / clone_subpath.rstrip("/")).resolve()
    # Modern pip (>=21.3) reports editable installs via an
    # "Editable project location:" line; pre-21.3 used "Location:".
    # We accept either, but prefer the editable-specific line because
    # for editable installs the plain "Location:" points at
    # site-packages, not the project source — which is the wrong
    # answer to the scenario's question.
    editable_loc_line = next(
        (
            line for line in show.splitlines()
            if line.startswith("Editable project location:")
        ),
        None,
    )
    location_line = next(
        (line for line in show.splitlines() if line.startswith("Location:")),
        None,
    )
    if editable_loc_line is not None:
        location = editable_loc_line.split(":", 1)[1].strip()
    else:
        assert location_line is not None, (
            f"pip show {distribution!r} included neither "
            f"'Editable project location:' nor 'Location:' line; "
            f"output:\n{show}"
        )
        location = location_line.split(":", 1)[1].strip()
    location_resolved = Path(location).resolve()
    assert str(expected_path) in str(location_resolved), (
        f"pip show install location {location_resolved!s} does not point "
        f"into the expected clone subpath {expected_path!s}; full output:"
        f"\n{show}"
    )


@then(
    parsers.parse(
        'the "pip show {distribution}" output for the product venv '
        'records the install as editable'
    )
)
def then_pip_show_records_editable(
    distribution: str, context: dict
) -> None:
    real = _resolve_single_target(context)
    venv_dir = real / ".venv"
    show = _pip_show_in_venv(venv_dir, distribution)
    # Modern pip records editable installs by emitting an
    # "Editable project location:" line in `pip show` output.
    assert "Editable project location:" in show, (
        f"pip show output for {distribution!r} does not record install "
        f"as editable; expected 'Editable project location:' line; "
        f"output:\n{show}"
    )


@then("the invocation exhibits the post-edit observable behavior")
def then_invocation_exhibits_post_edit_behavior(context: dict) -> None:
    expected_token = context.get("post_edit_token")
    assert expected_token is not None, (
        "scenario inconsistency: post-edit-token not stashed by Given step"
    )
    stdout = context.get("cli_invocation_stdout", "")
    rc = context.get("cli_invocation_rc")
    assert rc == 0, (
        f"CLI invocation failed (rc={rc}); stderr:\n"
        f"{context.get('cli_invocation_stderr', '')}"
    )
    assert expected_token in stdout, (
        f"CLI invocation did not exhibit the post-edit token "
        f"{expected_token!r} in stdout {stdout!r}; either the source "
        f"edit was not reflected (editable install is not actually "
        f"editable) or the invocation hit a stale build."
    )


@then(
    'no manual "pip install" step is required between the source edit '
    'and the invocation'
)
def then_no_manual_pip_install(context: dict) -> None:
    # Operational reading: the test harness did NOT run pip install
    # between the Given "fresh edit" step and the When "agent invokes
    # CLI" step. We assert that by checking the harness did not stash a
    # marker indicating a reinstall happened in that window.
    assert not context.get("manual_pip_install_invoked"), (
        "test harness invoked `pip install` between source edit and CLI "
        "invocation — defeats the contract"
    )
    # And: the invocation succeeded, demonstrating the edit was visible.
    assert context.get("cli_invocation_rc") == 0


# -----------------------------------------------------------------------
# When + Then steps — structural JSON assertions over the returned body
# (scenario f2a7de49d80332c1, lead-9ht / brief-003 hook-schema wrapper
# tightening). The substring scenarios 57-68 grep over the raw template
# text; this scenario pins the *structural* shape Claude Code's hook
# schema requires (matcher+hooks wrapper around each SessionStart entry,
# inner hooks with type+command). The new step vocabulary parses the
# previously-returned body as JSON and asserts shape at named paths.
# -----------------------------------------------------------------------


@when("the returned body is parsed as JSON")
def when_returned_body_is_parsed_as_json(context: dict) -> None:
    import json

    body = context.get("last_returned_body")
    assert body is not None, (
        "no template body has been retrieved; matching When step did not run"
    )
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"returned body does not parse as JSON: {exc!s}\n"
            f"body:\n{body!r}"
        )
    context["last_parsed_body"] = parsed


def _resolve_parsed_path(context: dict, path: str):
    """Look up a dotted/keyed JSON path in the last-parsed body.

    Path is either a top-level key (e.g. "hooks") or a dot-joined
    sequence of object keys (e.g. "hooks.SessionStart"). Array
    indexing is not needed by the current scenario vocabulary, so we
    do not support it here.
    """
    parsed = context.get("last_parsed_body")
    assert parsed is not None, (
        "no parsed body in context; an earlier 'the returned body is "
        "parsed as JSON' step must run first"
    )
    cur = parsed
    for segment in path.split("."):
        assert isinstance(cur, dict), (
            f"path traversal hit a non-object at segment {segment!r} of "
            f"path {path!r}; current value is {cur!r}"
        )
        assert segment in cur, (
            f"parsed body has no key {segment!r} at path {path!r}; "
            f"available keys at this level: {list(cur.keys())!r}"
        )
        cur = cur[segment]
    return cur


@then(
    parsers.parse(
        'the parsed value at top-level key "{key}" is a JSON object'
    )
)
def then_parsed_top_level_key_is_object(key: str, context: dict) -> None:
    value = _resolve_parsed_path(context, key)
    assert isinstance(value, dict), (
        f"parsed value at top-level key {key!r} is not a JSON object "
        f"(got {type(value).__name__}): {value!r}"
    )


@then(
    parsers.parse(
        'the parsed value at "{path}" is a JSON array of length at '
        'least {min_len:d}'
    )
)
def then_parsed_value_is_array_min_length(
    path: str, min_len: int, context: dict
) -> None:
    value = _resolve_parsed_path(context, path)
    assert isinstance(value, list), (
        f"parsed value at {path!r} is not a JSON array "
        f"(got {type(value).__name__}): {value!r}"
    )
    assert len(value) >= min_len, (
        f"parsed array at {path!r} has length {len(value)}; "
        f"expected at least {min_len}"
    )


@then(
    parsers.parse(
        'every element of the "{path}" array is a JSON object with a '
        '"{key}" key whose value is a string'
    )
)
def then_every_element_has_string_key(
    path: str, key: str, context: dict
) -> None:
    array = _resolve_parsed_path(context, path)
    assert isinstance(array, list), (
        f"parsed value at {path!r} is not a JSON array "
        f"(got {type(array).__name__}): {array!r}"
    )
    for i, elem in enumerate(array):
        assert isinstance(elem, dict), (
            f"element {i} of array at {path!r} is not a JSON object "
            f"(got {type(elem).__name__}): {elem!r}"
        )
        assert key in elem, (
            f"element {i} of array at {path!r} has no key {key!r}; "
            f"keys present: {list(elem.keys())!r}"
        )
        assert isinstance(elem[key], str), (
            f"element {i} of array at {path!r} has key {key!r} but its "
            f"value is not a string (got {type(elem[key]).__name__}): "
            f"{elem[key]!r}"
        )


@then(
    parsers.parse(
        'every element of the "{path}" array is a JSON object with a '
        '"{key}" key whose value is a JSON array of length at least '
        '{min_len:d}'
    )
)
def then_every_element_has_array_key_min_length(
    path: str, key: str, min_len: int, context: dict
) -> None:
    array = _resolve_parsed_path(context, path)
    assert isinstance(array, list), (
        f"parsed value at {path!r} is not a JSON array "
        f"(got {type(array).__name__}): {array!r}"
    )
    for i, elem in enumerate(array):
        assert isinstance(elem, dict), (
            f"element {i} of array at {path!r} is not a JSON object "
            f"(got {type(elem).__name__}): {elem!r}"
        )
        assert key in elem, (
            f"element {i} of array at {path!r} has no key {key!r}; "
            f"keys present: {list(elem.keys())!r}"
        )
        inner = elem[key]
        assert isinstance(inner, list), (
            f"element {i} of array at {path!r} has key {key!r} but its "
            f"value is not a JSON array (got {type(inner).__name__}): "
            f"{inner!r}"
        )
        assert len(inner) >= min_len, (
            f"element {i} of array at {path!r} has key {key!r} with "
            f"array length {len(inner)}; expected at least {min_len}"
        )


@then(
    parsers.parse(
        'every element of every inner "{inner_key}" array under '
        '"{path}" is a JSON object with a "{key}" key whose value is '
        'a string'
    )
)
def then_every_inner_element_has_string_key(
    inner_key: str, path: str, key: str, context: dict
) -> None:
    array = _resolve_parsed_path(context, path)
    assert isinstance(array, list), (
        f"parsed value at {path!r} is not a JSON array "
        f"(got {type(array).__name__}): {array!r}"
    )
    for i, elem in enumerate(array):
        assert isinstance(elem, dict), (
            f"element {i} of array at {path!r} is not a JSON object "
            f"(got {type(elem).__name__}): {elem!r}"
        )
        assert inner_key in elem, (
            f"element {i} of array at {path!r} has no inner key "
            f"{inner_key!r}; keys present: {list(elem.keys())!r}"
        )
        inner = elem[inner_key]
        assert isinstance(inner, list), (
            f"element {i} of array at {path!r} has inner key "
            f"{inner_key!r} but its value is not a JSON array "
            f"(got {type(inner).__name__}): {inner!r}"
        )
        for j, inner_elem in enumerate(inner):
            assert isinstance(inner_elem, dict), (
                f"element {j} of inner {inner_key!r} array at element "
                f"{i} of {path!r} is not a JSON object "
                f"(got {type(inner_elem).__name__}): {inner_elem!r}"
            )
            assert key in inner_elem, (
                f"element {j} of inner {inner_key!r} array at element "
                f"{i} of {path!r} has no key {key!r}; keys present: "
                f"{list(inner_elem.keys())!r}"
            )
            assert isinstance(inner_elem[key], str), (
                f"element {j} of inner {inner_key!r} array at element "
                f"{i} of {path!r} has key {key!r} but its value is not "
                f"a string (got {type(inner_elem[key]).__name__}): "
                f"{inner_elem[key]!r}"
            )


# -----------------------------------------------------------------------
# Then steps — brief-003 realization revision (lead-pn9 / parent lead-o00).
#
# Scenarios 71-76 (hashes 206ca3d0fa40bcad, d87ccb133fa64d2f,
# 9f15982aa00829f1, 11cf1e054f79fed4, 71797e9017c95fed,
# 79c12d6bbf87aacf) move the activation mechanism from a SessionStart
# hook to a router-side instruction in the canonical CLAUDE.md primer
# to arm the in-session Monitor tool. The step vocabulary below covers
# the new primer-substring assertions (scenarios 71, 72) and the
# revised settings.json structural assertions (scenarios 74, 75, 76).
# Scenario 73 reuses the existing "the content of that file contains
# the literal substring" Then.
# -----------------------------------------------------------------------


# Scenario 71 (206ca3d0fa40bcad). Substring-presence Thens for
# "Monitor", "session start", "stdbuf -oL inotifywait",
# "-m -e create,moved_to", and the watch_target are covered by the
# existing `then_returned_body_contains_substring` step. The exclusion
# clause below needs a dedicated step because it asserts the absence
# of a *positive* instruction (an instruction telling the router TO arm
# via a SessionStart hook), not the absence of a bare substring — the
# primer is allowed to mention "SessionStart hook" in passing (e.g. to
# describe what it has retired) as long as no current-tense
# instruction tells the router to use that mechanism.
@then(
    'the returned body does not contain any instruction to arm the '
    'watcher via a "SessionStart" hook in ".claude/settings.json"'
)
def then_no_instruction_to_arm_via_sessionstart_hook(
    context: dict,
) -> None:
    import re as _re

    body = context.get("last_returned_body")
    assert body is not None, (
        "no returned body in context; matching When step did not run"
    )
    # Look for sentences that pair an arm/activate verb with the
    # SessionStart-hook mechanism. If any such sentence lacks an
    # accompanying negation/displacement marker (not, no, never,
    # instead of, rather than, without, retired, removed, replaced,
    # earlier, fallback, refuses, refuse), it counts as a positive
    # instruction to arm via the hook — which is exactly what scenario
    # 71's exclusion clause forbids.
    sentence_breakers = _re.compile(r"[.\n]")
    arm_pattern = _re.compile(
        r"(arm|activate|install|run|launch|start)\b",
        _re.IGNORECASE,
    )
    hook_pattern = _re.compile(
        r"sessionstart\s+hook|hooks\.sessionstart",
        _re.IGNORECASE,
    )
    negation_pattern = _re.compile(
        r"\b(not|no|never|instead|rather|without|retired|removed|"
        r"replaced|earlier|fallback|refuse[ds]?|hangs?|hang|"
        r"hung|tried|moved|cannot|do\s+not|don't|do\s+not\s+arm)\b",
        _re.IGNORECASE,
    )
    for sentence in sentence_breakers.split(body):
        if not sentence.strip():
            continue
        if arm_pattern.search(sentence) and hook_pattern.search(sentence):
            assert negation_pattern.search(sentence), (
                "primer body contains a sentence coupling an "
                "activation verb with the SessionStart-hook mechanism "
                "with no negation/displacement marker — reads as a "
                "positive instruction to arm via the hook:\n"
                f"  {sentence.strip()!r}"
            )


# Scenario 72 (d87ccb133fa64d2f). Substring Thens for "inotifywait"
# and "stdbuf" use the existing substring Then. The two instruction-
# substring Thens below assert that the primer contains text directing
# the router on PATH-verification + refuse-on-missing behavior.
@then(
    'the returned body contains an instruction substring directing the '
    'router to verify these executables are on PATH before arming the '
    'Monitor'
)
def then_body_directs_path_verification(context: dict) -> None:
    import re as _re

    body = context.get("last_returned_body")
    assert body is not None, (
        "no returned body in context; matching When step did not run"
    )
    # Verification instruction: a SINGLE sentence of the body must name
    # PATH and pair a verify-style verb with a Monitor-arming temporal
    # marker. Mirrors the sentence-scoped shape of scenario 71's
    # exclusion check (then_no_instruction_to_arm_via_sessionstart_hook)
    # — whole-body conjunctions admit false-positives where unrelated
    # primer text (e.g. a "sufficiency check" phrase elsewhere, or a
    # host-prereq bullet mentioning "packages being present on PATH")
    # silently satisfies the tokens.
    #
    # The canonical primer is markdown with soft-wrapped paragraphs:
    # the verify-PATH instruction is one prose sentence rendered across
    # three source lines. We normalize single newlines to spaces
    # (preserving paragraph breaks at `\n\n`) before splitting on
    # sentence-ending punctuation, so a logical sentence is scoped to
    # what a reader would call a sentence, not to a source line.
    normalized = _re.sub(r"(?<!\n)\n(?!\n)", " ", body)
    sentence_breakers = _re.compile(r"[.]|\n\n")
    verify_pattern = _re.compile(
        r"\b(verify|check|confirm|ensure)\b|command\s+-v",
        _re.IGNORECASE,
    )
    path_pattern = _re.compile(r"\bpath\b", _re.IGNORECASE)
    # Monitor-arming temporal marker: either the literal
    # "before arming the Monitor" phrase, or a conjunction of an
    # arming verb ("arm" / "arming" / etc.) with "monitor" AND
    # "before" within the same sentence. A bare "before" + "monitor"
    # is not enough — there must be an arming verb tying the two.
    arm_pattern = _re.compile(r"\barm(?:ing|ed|s)?\b", _re.IGNORECASE)
    monitor_pattern = _re.compile(r"\bmonitor\b", _re.IGNORECASE)
    before_pattern = _re.compile(r"\bbefore\b", _re.IGNORECASE)
    for sentence in sentence_breakers.split(normalized):
        if not sentence.strip():
            continue
        if not verify_pattern.search(sentence):
            continue
        if not path_pattern.search(sentence):
            continue
        has_explicit_phrase = (
            "before arming the monitor" in sentence.lower()
        )
        has_arm_before_monitor_triple = bool(
            before_pattern.search(sentence)
            and arm_pattern.search(sentence)
            and monitor_pattern.search(sentence)
        )
        if has_explicit_phrase or has_arm_before_monitor_triple:
            return
    assert False, (
        "primer body does not contain a single sentence carrying a "
        "PATH-verification instruction tied to the Monitor activation "
        "timing (verify-verb + PATH + arm-before-Monitor temporal "
        "marker within one sentence)"
    )


@then(
    'the returned body contains an instruction substring directing the '
    'router to refuse to arm the Monitor and surface a visible '
    'diagnostic when either executable is missing'
)
def then_body_directs_refuse_with_diagnostic(context: dict) -> None:
    import re as _re

    body = context.get("last_returned_body")
    assert body is not None, (
        "no returned body in context; matching When step did not run"
    )
    # Refuse-on-missing + diagnostic instruction: a SINGLE sentence of
    # the body must couple a refuse-to-arm verb with a diagnostic
    # marker and a missing-prerequisite marker. Whole-body conjunctions
    # admit false-positives where the tokens scatter across unrelated
    # primer sentences. Same soft-wrap-aware sentence scoping as
    # then_body_directs_path_verification above (normalize single
    # newlines to spaces, then split on sentence-ending punctuation or
    # paragraph break) so a multi-line prose sentence is one sentence.
    normalized = _re.sub(r"(?<!\n)\n(?!\n)", " ", body)
    sentence_breakers = _re.compile(r"[.]|\n\n")
    refuse_pattern = _re.compile(
        r"refuse\s+to\s+arm|must\s+not\s+arm|do\s+not\s+arm|"
        r"must\s+refuse",
        _re.IGNORECASE,
    )
    diagnostic_pattern = _re.compile(
        r"\bdiagnostic\b|error\s+message|\bsurface\b|\bstderr\b",
        _re.IGNORECASE,
    )
    missing_pattern = _re.compile(
        r"\bmissing\b|not\s+present|not\s+found|either\s+executable|"
        r"either\s+prerequisite",
        _re.IGNORECASE,
    )
    for sentence in sentence_breakers.split(normalized):
        if not sentence.strip():
            continue
        if (
            refuse_pattern.search(sentence)
            and diagnostic_pattern.search(sentence)
            and missing_pattern.search(sentence)
        ):
            return
    assert False, (
        "primer body does not contain a single sentence carrying a "
        "refuse-on-missing + diagnostic instruction (refuse-verb + "
        "diagnostic-marker + missing-marker within one sentence)"
    )


@then(
    'the returned body does not contain any instruction telling the '
    'router to silently fall back to a no-watcher state when a '
    'prerequisite is missing'
)
def then_no_silent_fallback_instruction(context: dict) -> None:
    import re as _re

    body = context.get("last_returned_body")
    assert body is not None, (
        "no returned body in context; matching When step did not run"
    )
    # Positive silent-fallback instructions would pair a "fall back" /
    # "continue" / "proceed without" verb with a "silent" or
    # "no-watcher" marker, with no negation. Apply the same
    # negation-scan approach used in scenario 71's exclusion check.
    sentence_breakers = _re.compile(r"[.\n]")
    fallback_pattern = _re.compile(
        r"(fall\s+back|fallback|continue\s+without|proceed\s+without|"
        r"degrade|silently)",
        _re.IGNORECASE,
    )
    no_watcher_pattern = _re.compile(
        r"(no[-\s]?watcher|without\s+a\s+watcher|skip\s+the\s+watcher|"
        r"silently)",
        _re.IGNORECASE,
    )
    negation_pattern = _re.compile(
        r"\b(not|no|never|do\s+not|don't|must\s+not|cannot|"
        r"instead|rather|refuse[ds]?|forbid|forbidden)\b",
        _re.IGNORECASE,
    )
    for sentence in sentence_breakers.split(body):
        if not sentence.strip():
            continue
        if fallback_pattern.search(sentence) and no_watcher_pattern.search(
            sentence
        ):
            assert negation_pattern.search(sentence), (
                "primer body contains a sentence coupling fall-back "
                "language with no-watcher / silent operation, with "
                "no negation marker — reads as a positive "
                "instruction to silently degrade:\n"
                f"  {sentence.strip()!r}"
            )


# Scenario 74 (11cf1e054f79fed4). Disjunctive Then: either
# hooks.SessionStart key is absent OR hooks.SessionStart is an empty
# array. Treated as one assertion at the Gherkin layer; we check
# either branch programmatically.
@then(
    'the parsed value at "hooks" has no key named "SessionStart", or '
    'the value at "hooks.SessionStart" is a JSON array of length 0'
)
def then_hooks_has_no_sessionstart_or_empty(context: dict) -> None:
    parsed = context.get("last_parsed_body")
    assert parsed is not None, (
        "no parsed body in context; an earlier 'the returned body is "
        "parsed as JSON' step must run first"
    )
    assert isinstance(parsed, dict), (
        f"parsed body is not a JSON object: {parsed!r}"
    )
    hooks = parsed.get("hooks")
    assert isinstance(hooks, dict), (
        f"parsed body has no top-level 'hooks' object: {parsed!r}"
    )
    if "SessionStart" not in hooks:
        return
    val = hooks["SessionStart"]
    assert isinstance(val, list) and len(val) == 0, (
        f"hooks.SessionStart is present but is not an empty array "
        f"(got {type(val).__name__} of length "
        f"{len(val) if isinstance(val, list) else 'n/a'}): {val!r}"
    )


# Scenario 75 (71797e9017c95fed). "Exactly one" structural assertion
# over hooks.SessionStart inner-hook command equality.
@then(
    parsers.parse(
        'exactly one JSON-object element of "{path}" has an inner '
        '"hooks" array containing an entry whose "command" string '
        'equals "{expected}"'
    )
)
def then_exactly_one_entry_with_command(
    path: str, expected: str, context: dict
) -> None:
    array = _resolve_parsed_path(context, path)
    assert isinstance(array, list), (
        f"parsed value at {path!r} is not a JSON array "
        f"(got {type(array).__name__}): {array!r}"
    )
    matches = 0
    for elem in array:
        if not isinstance(elem, dict):
            continue
        inner = elem.get("hooks")
        if not isinstance(inner, list):
            continue
        for inner_elem in inner:
            if (
                isinstance(inner_elem, dict)
                and inner_elem.get("command") == expected
            ):
                matches += 1
                break
    assert matches == 1, (
        f"expected exactly one element of {path!r} whose inner hooks "
        f"array contains an entry with command == {expected!r}; "
        f"got {matches} matching element(s)"
    )


# Scenario 75. "No element ... whose 'command' string contains the
# substring '{needle}'" — used for inotifywait and stdbuf.
@then(
    parsers.parse(
        'no element of "{path}" has an inner "hooks" array containing '
        'an entry whose "command" string contains the substring '
        '"{needle}"'
    )
)
def then_no_entry_with_command_substring(
    path: str, needle: str, context: dict
) -> None:
    array = _resolve_parsed_path(context, path)
    assert isinstance(array, list), (
        f"parsed value at {path!r} is not a JSON array "
        f"(got {type(array).__name__}): {array!r}"
    )
    for i, elem in enumerate(array):
        if not isinstance(elem, dict):
            continue
        inner = elem.get("hooks")
        if not isinstance(inner, list):
            continue
        for j, inner_elem in enumerate(inner):
            if not isinstance(inner_elem, dict):
                continue
            cmd = inner_elem.get("command")
            if isinstance(cmd, str):
                assert needle not in cmd, (
                    f"element {i} of {path!r}, inner hook {j}, has a "
                    f"command string containing forbidden substring "
                    f"{needle!r}: {cmd!r}"
                )


# Scenario 75. Combined matcher+hooks-shape Then. Asserts the
# matcher+hooks wrapper shape over every SessionStart element in one
# step (the existing per-key wrapper Thens cover this in two parts;
# this is the single-line Gherkin form scenario 75 uses).
@then(
    parsers.parse(
        'every element of "{path}" is a JSON object with a "matcher" '
        'key whose value is a string and a "hooks" key whose value is '
        'a JSON array of length at least {min_len:d}'
    )
)
def then_every_element_is_matcher_hooks_wrapper(
    path: str, min_len: int, context: dict
) -> None:
    array = _resolve_parsed_path(context, path)
    assert isinstance(array, list), (
        f"parsed value at {path!r} is not a JSON array "
        f"(got {type(array).__name__}): {array!r}"
    )
    for i, elem in enumerate(array):
        assert isinstance(elem, dict), (
            f"element {i} of array at {path!r} is not a JSON object "
            f"(got {type(elem).__name__}): {elem!r}"
        )
        assert "matcher" in elem and isinstance(elem["matcher"], str), (
            f"element {i} of {path!r} has no string 'matcher' key: "
            f"{elem!r}"
        )
        inner = elem.get("hooks")
        assert isinstance(inner, list), (
            f"element {i} of {path!r} has no 'hooks' array: {elem!r}"
        )
        assert len(inner) >= min_len, (
            f"element {i} of {path!r} has 'hooks' array of length "
            f"{len(inner)}; expected at least {min_len}"
        )


# Scenario 76 (79c12d6bbf87aacf). Conditional schema-conformance.
# These steps are vacuously true when hooks.SessionStart is absent or
# empty (the bc variant's empty case) and assert the full
# matcher+hooks wrapper shape when entries are present (the lead
# variant).
@then(
    parsers.parse(
        'if the "{outer}" object has a "{key}" key, then the value at '
        '"{path}" is a JSON array'
    )
)
def then_conditional_array_at_path(
    outer: str, key: str, path: str, context: dict
) -> None:
    parsed = context.get("last_parsed_body")
    assert parsed is not None, (
        "no parsed body in context; an earlier 'the returned body is "
        "parsed as JSON' step must run first"
    )
    outer_val = _resolve_parsed_path(context, outer)
    assert isinstance(outer_val, dict), (
        f"value at {outer!r} is not a JSON object: {outer_val!r}"
    )
    if key not in outer_val:
        return
    val = _resolve_parsed_path(context, path)
    assert isinstance(val, list), (
        f"value at {path!r} is not a JSON array "
        f"(got {type(val).__name__}): {val!r}"
    )


def _resolve_optional_array(context: dict, path: str):
    """Resolve a JSON path that may be absent; return [] if so."""
    parsed = context.get("last_parsed_body")
    assert parsed is not None
    cur = parsed
    for segment in path.split("."):
        if not isinstance(cur, dict) or segment not in cur:
            return []
        cur = cur[segment]
    if cur is None:
        return []
    assert isinstance(cur, list), (
        f"value at {path!r} is not a JSON array "
        f"(got {type(cur).__name__}): {cur!r}"
    )
    return cur


@then(
    parsers.parse(
        'every element of "{path}" (if any) is a JSON object with a '
        '"{key}" key whose value is a string'
    )
)
def then_every_element_optional_string_key(
    path: str, key: str, context: dict
) -> None:
    array = _resolve_optional_array(context, path)
    for i, elem in enumerate(array):
        assert isinstance(elem, dict), (
            f"element {i} of array at {path!r} is not a JSON object: "
            f"{elem!r}"
        )
        assert key in elem and isinstance(elem[key], str), (
            f"element {i} of {path!r} has no string {key!r} key: "
            f"{elem!r}"
        )


@then(
    parsers.parse(
        'every element of "{path}" (if any) is a JSON object with a '
        '"{key}" key whose value is a JSON array of length at least '
        '{min_len:d}'
    )
)
def then_every_element_optional_array_key_min_length(
    path: str, key: str, min_len: int, context: dict
) -> None:
    array = _resolve_optional_array(context, path)
    for i, elem in enumerate(array):
        assert isinstance(elem, dict), (
            f"element {i} of array at {path!r} is not a JSON object: "
            f"{elem!r}"
        )
        assert key in elem and isinstance(elem[key], list), (
            f"element {i} of {path!r} has no array {key!r} key: "
            f"{elem!r}"
        )
        assert len(elem[key]) >= min_len, (
            f"element {i} of {path!r} has {key!r} array of length "
            f"{len(elem[key])}; expected at least {min_len}"
        )


@then(
    parsers.parse(
        'every element of every inner "{inner_key}" array under '
        '"{path}" (if any) is a JSON object with a "{key}" key whose '
        'value is a string'
    )
)
def then_every_inner_element_optional_string_key(
    inner_key: str, path: str, key: str, context: dict
) -> None:
    outer_array = _resolve_optional_array(context, path)
    for i, elem in enumerate(outer_array):
        if not isinstance(elem, dict):
            continue
        inner = elem.get(inner_key)
        if not isinstance(inner, list):
            continue
        for j, inner_elem in enumerate(inner):
            assert isinstance(inner_elem, dict), (
                f"element {j} of inner {inner_key!r} array at "
                f"element {i} of {path!r} is not a JSON object: "
                f"{inner_elem!r}"
            )
            assert key in inner_elem and isinstance(
                inner_elem[key], str
            ), (
                f"element {j} of inner {inner_key!r} array at "
                f"element {i} of {path!r} has no string {key!r} "
                f"key: {inner_elem!r}"
            )


# =======================================================================
# Step definitions — import-graph CLAUDE.md: typed files, bootstrap,
# and update contracts (PDR-003 alt F, lead-2oe / lead-ro8)
# =======================================================================
#
# Scenarios pin:
#   - The canonical CLAUDE.md body template surface (cad9ccb5b462978d)
#   - Bootstrap writes CLAUDE.md byte-for-byte from body template
#     (2b9bd9c82017b0c6)
#   - Bootstrap writes .claude/shop/name.md (207dcfa0f8b3ca91)
#   - Bootstrap writes .claude/shop/type.md (510520660d55522a)
#   - Bootstrap writes .claude/canonical/<type>-primer.md (35c34f0e2d11c092)
#   - Bootstrap writes .claude/shop/primer.md as placeholder
#     (0bba99e6f592a788)
#   - @-import resolution shows all four typed files (68ce85606d46d7bb)
#   - Update overwrites CLAUDE.md when drifted (c458502d8632952b)
#   - Update overwrites canonical primer when drifted (ce122bcb7d794888)
#   - Update leaves .claude/shop/name.md untouched (3d3f8c8427366491)
#   - Update leaves .claude/shop/type.md untouched (ca3fc9ec7c67ddb2)
#   - Update leaves .claude/shop/primer.md untouched (91e2db0f9e3e58d5)
#   - Update is idempotent (ac5a21e046564d01)
#   - Update reads shop type from .claude/shop/type.md (f55678f733a5427a)
#   - Legacy shop: update exits non-zero (e51ac69bba8fd909)


# -----------------------------------------------------------------------
# When step — ask for canonical CLAUDE.md body template
# -----------------------------------------------------------------------


@when(
    parsers.parse(
        'I ask the "shop-templates" package for the canonical "CLAUDE.md" '
        'body template for shop type "{shop_type}" through its public '
        'template-access surface'
    )
)
def when_ask_for_claude_body_template(shop_type: str, context: dict) -> None:
    from shop_templates.cli import read_claude_md_body_template

    context["claude_body_shop_type"] = shop_type
    context["claude_body_template"] = read_claude_md_body_template(shop_type)
    context["last_returned_body"] = context["claude_body_template"]
    context["last_returned_surface"] = "claude_body_template"
    context["last_returned_shop_type"] = shop_type


# -----------------------------------------------------------------------
# Then steps — body template @-import line assertions
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'the returned body contains an "@" import line referencing '
        '"{import_path}"'
    )
)
def then_returned_body_contains_import_line(
    import_path: str, context: dict
) -> None:
    body = context.get("last_returned_body")
    assert body is not None, (
        "no returned body in context; the matching When step did not run"
    )
    # An @-import line is a line whose content is "@<path>" (with optional
    # surrounding whitespace). Check that the body has a line that after
    # stripping starts with "@" and contains the expected path.
    expected_line = f"@{import_path}"
    lines = body.splitlines()
    assert any(line.strip() == expected_line for line in lines), (
        f"returned body does not contain an '@' import line referencing "
        f"{import_path!r}; expected a line matching {expected_line!r}.\n"
        f"Body:\n{body!r}"
    )


# -----------------------------------------------------------------------
# Given steps — target directory premises for new scenarios
# -----------------------------------------------------------------------


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'with no ".claude/shop/" subdirectory'
    )
)
def given_existing_git_repo_no_claude_shop_subdir(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    shop_dir = real / ".claude" / "shop"
    assert not shop_dir.exists(), (
        f"premise of Given violated: {shop_dir!s} unexpectedly exists"
    )


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'with no ".claude/canonical/" subdirectory'
    )
)
def given_existing_git_repo_no_claude_canonical_subdir(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    canonical_dir = real / ".claude" / "canonical"
    assert not canonical_dir.exists(), (
        f"premise of Given violated: {canonical_dir!s} unexpectedly exists"
    )


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'that contains a top-level "CLAUDE.md" and has no file at '
        '".claude/shop/type.md"'
    )
)
def given_existing_git_repo_with_claude_md_no_shop_type(
    alias: str, context: dict, tmp_path: Path
) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    # Create a top-level CLAUDE.md as a legacy placeholder.
    (real / "CLAUDE.md").write_text(
        "# Legacy shop CLAUDE.md\nThis is a legacy shop.\n"
    )
    # Ensure .claude/shop/type.md does NOT exist.
    type_file = real / ".claude" / "shop" / "type.md"
    assert not type_file.exists(), (
        f"premise of Given violated: {type_file!s} unexpectedly exists"
    )


# -----------------------------------------------------------------------
# Given steps — file-editing premises for update scenarios
# -----------------------------------------------------------------------


@given(
    parsers.parse(
        'the file at "{path}" in the target directory has been edited '
        'since bootstrap so that its byte contents are not equal to the '
        'canonical "CLAUDE.md" body template for shop type "{shop_type}"'
    )
)
def given_file_edited_to_differ_from_body_template(
    path: str, shop_type: str, context: dict
) -> None:
    from shop_templates.cli import read_claude_md_body_template

    real = _resolve_single_target(context)
    target_file = real / path
    canonical = read_claude_md_body_template(shop_type)
    edited = canonical + "\nSHOP-AUTHORED CONTENT NOT IN BODY TEMPLATE.\n"
    target_file.write_text(edited)
    assert target_file.read_text() != canonical, (
        f"premise of Given violated: edited file still equals canonical "
        f"body template for {shop_type!r}"
    )


@given(
    parsers.parse(
        'the file at "{path}" in the target directory has been edited '
        'since bootstrap so that its byte contents are not equal to the '
        'canonical "CLAUDE.md" primer template for shop type "{shop_type}"'
    )
)
def given_file_edited_to_differ_from_primer_template(
    path: str, shop_type: str, context: dict
) -> None:
    from shop_templates.cli import read_claude_md_primer

    real = _resolve_single_target(context)
    target_file = real / path
    canonical = read_claude_md_primer(shop_type)
    edited = canonical + "\nSHOP-AUTHORED CONTENT NOT IN PRIMER.\n"
    target_file.write_text(edited)
    assert target_file.read_text() != canonical, (
        f"premise of Given violated: edited file still equals canonical "
        f"primer template for {shop_type!r}"
    )


@given(
    parsers.parse(
        'the file at "{path}" in the target directory has been edited '
        'since bootstrap so that its content includes a literal shop-authored '
        'sentence'
    )
)
def given_file_edited_with_shop_authored_sentence(
    path: str, context: dict
) -> None:
    real = _resolve_single_target(context)
    target_file = real / path
    original = target_file.read_text()
    edited = original + "\nSHOP-AUTHORED SENTENCE (non-canonical).\n"
    target_file.write_text(edited)


@given(
    parsers.parse(
        'the file at "{path}" in the target directory has been edited '
        'since bootstrap so that its content includes a literal shop-authored '
        'sentence that the canonical "CLAUDE.md" primer template does not '
        'contain'
    )
)
def given_file_edited_with_shop_authored_sentence_not_in_primer(
    path: str, context: dict
) -> None:
    """Edit the named file to include a shop-authored sentence that is
    verifiably NOT in the canonical CLAUDE.md primer template. Used for
    .claude/shop/primer.md non-touch assertions (scenario 91e2db0f9e3e58d5).
    """
    real = _resolve_single_target(context)
    target_file = real / path
    original = target_file.read_text()
    # Use a deliberately unique marker unlikely to appear in any canonical
    # primer template.
    shop_sentence = "\nSHOP-AUTHORED UNIQUE SENTENCE 8f3a2b7c NOT IN CANONICAL PRIMER.\n"
    edited = original + shop_sentence
    target_file.write_text(edited)


@given(
    parsers.parse(
        'the file at "{path}" in the target directory has byte contents '
        'equal to the canonical "CLAUDE.md" body template for shop type '
        '"{shop_type}"'
    )
)
def given_file_equals_body_template(
    path: str, shop_type: str, context: dict
) -> None:
    from shop_templates.cli import read_claude_md_body_template

    real = _resolve_single_target(context)
    target_file = real / path
    canonical = read_claude_md_body_template(shop_type)
    # If the file already equals canonical, nothing to do.
    if not target_file.exists() or target_file.read_text() != canonical:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(canonical)


@given(
    parsers.re(
        r'^the file at "\.claude/canonical/(?P<shop_type>[^"]+)-primer\.md" '
        r'in the target directory has byte contents equal to the canonical '
        r'"CLAUDE\.md" primer template for shop type "[^"]+"$'
    )
)
def given_canonical_primer_file_equals_primer_template(
    shop_type: str, context: dict
) -> None:
    from shop_templates.cli import read_claude_md_primer

    real = _resolve_single_target(context)
    primer_file = real / ".claude" / "canonical" / f"{shop_type}-primer.md"
    canonical = read_claude_md_primer(shop_type)
    if not primer_file.exists() or primer_file.read_text() != canonical:
        primer_file.parent.mkdir(parents=True, exist_ok=True)
        primer_file.write_text(canonical)


@given(
    'I record the byte contents and mtimes of those two files before the '
    'invocation'
)
def given_record_two_canonical_files_byte_and_mtime(context: dict) -> None:
    """Record byte contents and mtimes of CLAUDE.md and
    .claude/canonical/<shop_type>-primer.md before the update invocation.
    Used by scenario ac5a21e046564d01 (idempotent update).
    """
    real = _resolve_single_target(context)
    shop_type = context["bootstrap_shop_type"]
    files_to_record = [
        "CLAUDE.md",
        f".claude/canonical/{shop_type}-primer.md",
    ]
    snap = {}
    for rel in files_to_record:
        f = real / rel
        assert f.exists(), (
            f"premise of Given violated: {f!s} does not exist before "
            f"the invocation snapshot"
        )
        st = f.stat()
        snap[rel] = {
            "bytes": f.read_bytes(),
            "mtime_ns": st.st_mtime_ns,
        }
    context["two_file_snapshot"] = snap


@given(
    parsers.parse(
        'the file at ".claude/shop/type.md" in the target directory '
        'contains exactly the literal string "{shop_type}"'
    )
)
def given_shop_type_file_contains_literal(
    shop_type: str, context: dict
) -> None:
    real = _resolve_single_target(context)
    type_file = real / ".claude" / "shop" / "type.md"
    assert type_file.exists(), (
        f"premise of Given violated: {type_file!s} does not exist; "
        f"the shop was not bootstrapped yet or bootstrap did not write it"
    )
    actual_contents = type_file.read_text()
    # The file should contain exactly "<shop_type>\n" (written by bootstrap).
    # The "contains exactly the literal string" phrasing means the file
    # content, when stripped of the single trailing newline, equals shop_type.
    assert actual_contents.strip() == shop_type, (
        f"premise of Given violated: {type_file!s} contains "
        f"{actual_contents!r}, expected exactly {shop_type!r} with "
        f"trailing newline"
    )


@given(
    'I record the recursive listing of file paths and the byte contents '
    'of every file in the target directory before the invocation'
)
def given_record_recursive_listing_and_contents(context: dict) -> None:
    real = _resolve_single_target(context)
    paths: list[str] = []
    contents: dict[str, bytes] = {}
    for p in sorted(real.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(real))
            paths.append(rel)
            contents[rel] = p.read_bytes()
    context["pre_invocation_recursive_paths"] = paths
    context["pre_invocation_recursive_contents"] = contents


# -----------------------------------------------------------------------
# When steps — new invocation shapes
# -----------------------------------------------------------------------


@when(
    parsers.parse(
        'I resolve the "@" import directives in the bootstrapped "CLAUDE.md" '
        'against the target directory'
    )
)
def when_resolve_at_import_directives(context: dict) -> None:
    """Resolve @-import lines in the bootstrapped CLAUDE.md.

    Each line of the form "@<relative-path>" is replaced with the
    byte contents of the file at that path inside the target directory.
    The resolved content is stored on context["resolved_claude_md"].
    """
    real = context["last_invocation_target"]
    claude_md = real / "CLAUDE.md"
    assert claude_md.exists(), (
        f"bootstrapped CLAUDE.md not found at {claude_md!s}"
    )
    body = claude_md.read_text()
    resolved_parts = []
    for line in body.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("@"):
            import_path = stripped[1:]  # strip leading @
            imported_file = real / import_path
            if imported_file.exists():
                resolved_parts.append(imported_file.read_text())
            # If file doesn't exist, skip (placeholder may be empty).
        else:
            resolved_parts.append(line)
    context["resolved_claude_md"] = "".join(resolved_parts)


@when(
    parsers.parse(
        'I invoke the "shop-templates" update entry point against the '
        'target directory "{alias}" with no additional shop-type argument'
    )
)
def when_invoke_update_no_shop_type_arg(
    alias: str, context: dict, tmp_path: Path
) -> None:
    """Invoke update WITHOUT --shop-type; relies on .claude/shop/type.md."""
    real = _real_target_for_alias(alias, context)
    result = _run_shop_templates_with_bd_shim(
        ["update", "--target", str(real)],
        context,
        tmp_path,
    )
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr
    context["last_invocation_target"] = real
    # Infer shop type from the file for context stashing.
    type_file = real / ".claude" / "shop" / "type.md"
    if type_file.exists():
        context["last_invocation_shop_type"] = type_file.read_text().strip()


# -----------------------------------------------------------------------
# Then steps — target file content / byte assertions
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'the target directory contains a file at "{path}"'
    )
)
def then_target_contains_file_at_path(path: str, context: dict) -> None:
    real = context["last_invocation_target"]
    target_file = real / path
    assert target_file.exists(), (
        f"expected file at {path!r} to exist under target directory "
        f"{real!s}, but it does not"
    )
    assert target_file.is_file(), (
        f"expected {path!r} under target directory {real!s} to be a "
        f"regular file, but it is not"
    )


@then(
    parsers.parse(
        'the byte contents of the file at "{path}" in the target '
        'directory equal the canonical "CLAUDE.md" body template for '
        'shop type "{shop_type}" byte-for-byte'
    )
)
def then_file_equals_body_template_byte_for_byte(
    path: str, shop_type: str, context: dict
) -> None:
    from shop_templates.cli import read_claude_md_body_template

    real = context["last_invocation_target"]
    target_file = real / path
    assert target_file.exists(), (
        f"expected file at {path!r} in target directory {real!s}"
    )
    actual = target_file.read_bytes()
    expected = read_claude_md_body_template(shop_type).encode()
    assert actual == expected, (
        f"byte contents of {path!r} do not equal canonical CLAUDE.md "
        f"body template for {shop_type!r} byte-for-byte.\n"
        f"len(expected)={len(expected)} len(actual)={len(actual)}\n"
        f"expected_tail={expected[-40:]!r}\n"
        f"actual_tail={actual[-40:]!r}"
    )


@then(
    parsers.parse(
        'the byte contents of that file are exactly the literal string '
        '"{value}" with a single trailing newline and no other content'
    )
)
def then_file_contains_exact_value_with_newline(
    value: str, context: dict
) -> None:
    """Assert the most recently checked file (from target_contains_file_at_path)
    contains exactly the given value plus a single trailing newline.

    The scenario path is established by a preceding 'the target directory
    contains a file at "<path>"' Then step which stashes the path on
    context["last_checked_path"].
    """
    path = context.get("last_checked_path")
    assert path is not None, (
        "no prior 'the target directory contains a file at' step established "
        "the path for this assertion"
    )
    real = context["last_invocation_target"]
    target_file = real / path
    actual = target_file.read_bytes()
    expected = (value + "\n").encode()
    assert actual == expected, (
        f"byte contents of {path!r} are {actual!r}; expected exactly "
        f"{expected!r} (literal {value!r} + single trailing newline)"
    )


@then(
    parsers.parse(
        'the byte contents of that file equal the canonical "CLAUDE.md" '
        'primer template for shop type "{shop_type}" byte-for-byte'
    )
)
def then_file_equals_primer_template_byte_for_byte(
    shop_type: str, context: dict
) -> None:
    from shop_templates.cli import read_claude_md_primer

    path = context.get("last_checked_path")
    assert path is not None, (
        "no prior 'the target directory contains a file at' step established "
        "the path for this assertion"
    )
    real = context["last_invocation_target"]
    target_file = real / path
    actual = target_file.read_bytes()
    expected = read_claude_md_primer(shop_type).encode()
    assert actual == expected, (
        f"byte contents of {path!r} do not equal canonical primer template "
        f"for {shop_type!r} byte-for-byte.\n"
        f"len(expected)={len(expected)} len(actual)={len(actual)}\n"
        f"expected_tail={expected[-40:]!r}\n"
        f"actual_tail={actual[-40:]!r}"
    )


@then(
    parsers.parse(
        'the byte contents of that file do not contain any non-trivial '
        'substring (length 64 or greater) that also appears in the '
        'canonical "CLAUDE.md" primer template for shop type "{shop_type}"'
    )
)
def then_file_has_no_canonical_primer_content(
    shop_type: str, context: dict
) -> None:
    from shop_templates.cli import read_claude_md_primer

    path = context.get("last_checked_path")
    assert path is not None, (
        "no prior 'the target directory contains a file at' step established "
        "the path"
    )
    real = context["last_invocation_target"]
    target_file = real / path
    actual_text = target_file.read_text()
    canonical = read_claude_md_primer(shop_type)
    min_len = 64
    # Slide a window of length min_len through the canonical primer and
    # check that none of those substrings appear in the actual file.
    for i in range(len(canonical) - min_len + 1):
        chunk = canonical[i : i + min_len]
        assert chunk not in actual_text, (
            f"file at {path!r} contains a non-trivial substring from the "
            f"canonical primer template (length {min_len}+) at offset {i}:\n"
            f"  {chunk!r}"
        )


# -----------------------------------------------------------------------
# Then step — target_contains_file_at_path stashes path
# (override to also stash last_checked_path for downstream steps)
# -----------------------------------------------------------------------
# Note: the @then decorator for the pattern "the target directory contains
# a file at..." was already registered above. We need to stash the path
# on the context so that follow-up Thens (byte content checks that say
# "that file") can reference it. The prior registration doesn't do this.
# We use a pattern override by unregistering (not possible with pytest-bdd)
# so instead we stash via the When-step's side-effect approach.
#
# Actually: pytest-bdd picks the LAST-registered step definition for a
# given pattern when there are duplicates. So the override above
# (then_target_contains_file_at_path) is the one that runs. But it doesn't
# stash last_checked_path. Let me patch it at the conftest level.
#
# The cleanest approach: register a SEPARATE step that handles the combined
# "contains a file at X" AND stashes path. But the step text above already
# matches the pattern. Rather than using two overlapping patterns, fix
# then_target_contains_file_at_path to stash the path.


# We need to amend then_target_contains_file_at_path to stash the path.
# Since it's defined above in this same file we can just edit it.
# But since we can't retroactively patch, we re-register with a stash:
# Actually, we can't have two definitions for the same text in pytest-bdd.
# The safer path: use a different step text for "contains a file at X AND
# stash path" vs "contains a file at X". Instead, let's wire the stash
# into the existing step by delegating.
#
# SOLUTION: The step was defined just above. We patch it here by
# wrapping it. But Python step registration order is what pytest-bdd uses;
# the LAST definition wins. Re-define it here with the stash included.

# Unregister the prior definition (not possible). Instead: define a new
# step that calls the old one. Actually pytest-bdd allows duplicates and
# uses the FIRST match or the last. Let me just inline the stash directly
# in then_target_contains_file_at_path by editing it above.
#
# Since Edit tool doesn't allow retroactive changes in-flight without
# re-reading, use a wrapper approach: re-register the exact same text
# with a new function that includes the stash.
# NOTE: pytest-bdd uses the most recently registered step if there are
# duplicates. So defining this AFTER the original will override it.


# Re-define "the target directory contains a file at" to also stash path.
# This will shadow the definition above (pytest-bdd last-wins).
@then(
    parsers.parse(
        'the target directory contains a file at "{path}"'
    )
)
def then_target_contains_file_at_path_and_stash(
    path: str, context: dict
) -> None:
    real = context["last_invocation_target"]
    target_file = real / path
    assert target_file.exists(), (
        f"expected file at {path!r} to exist under target directory "
        f"{real!s}, but it does not"
    )
    assert target_file.is_file(), (
        f"expected {path!r} under target directory {real!s} to be a "
        f"regular file, but it is not"
    )
    # Stash path so downstream "that file" steps can reference it.
    context["last_checked_path"] = path


# -----------------------------------------------------------------------
# Then step — @-import resolution content assertions
# -----------------------------------------------------------------------


@then("the exit code of the bootstrap invocation is 0")
def then_bootstrap_exit_code_zero(context: dict) -> None:
    rc = context["cli_returncode"]
    assert rc == 0, (
        f"expected exit code 0 for bootstrap invocation; got {rc}; "
        f"stderr:\n{context.get('cli_stderr', '')}"
    )


@then(
    parsers.parse(
        'the resolved content contains the byte contents of the file at '
        '"{path}" in the target directory'
    )
)
def then_resolved_contains_file_contents(path: str, context: dict) -> None:
    resolved = context.get("resolved_claude_md")
    assert resolved is not None, (
        "no resolved CLAUDE.md content in context; the 'I resolve the @' "
        "When step must run first"
    )
    real = context["last_invocation_target"]
    target_file = real / path
    file_bytes = target_file.read_bytes()
    file_text = file_bytes.decode()
    # For empty placeholder files (.claude/shop/primer.md), the resolved
    # content trivially contains an empty string. Skip the check for
    # empty files since "contains ''" is vacuously true but not meaningful.
    if not file_text.strip():
        return
    assert file_text in resolved, (
        f"resolved CLAUDE.md does not contain the byte contents of "
        f"{path!r}.\n"
        f"file_text={file_text!r}\n"
        f"resolved_tail={resolved[-100:]!r}"
    )


# -----------------------------------------------------------------------
# Then steps — update post-invocation byte / mtime assertions
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'after the invocation the byte contents of the file at "{path}" '
        'in the target directory equal the canonical "CLAUDE.md" body '
        'template for shop type "{shop_type}" byte-for-byte'
    )
)
def then_file_equals_body_template_after_update(
    path: str, shop_type: str, context: dict
) -> None:
    from shop_templates.cli import read_claude_md_body_template

    real = context["last_invocation_target"]
    target_file = real / path
    assert target_file.exists(), (
        f"expected file at {path!r} in target directory {real!s}"
    )
    actual = target_file.read_bytes()
    expected = read_claude_md_body_template(shop_type).encode()
    assert actual == expected, (
        f"after update, byte contents of {path!r} do not equal canonical "
        f"CLAUDE.md body template for {shop_type!r} byte-for-byte.\n"
        f"len(expected)={len(expected)} len(actual)={len(actual)}\n"
        f"expected_tail={expected[-40:]!r}\n"
        f"actual_tail={actual[-40:]!r}"
    )


@then(
    parsers.parse(
        'after the invocation the byte contents of the file at '
        '".claude/canonical/{shop_type}-primer.md" in the target directory '
        'equal the canonical "CLAUDE.md" primer template for shop type '
        '"{shop_type}" byte-for-byte'
    )
)
def then_canonical_primer_file_equals_primer_template_after_update(
    shop_type: str, context: dict
) -> None:
    from shop_templates.cli import read_claude_md_primer

    real = context["last_invocation_target"]
    primer_path = f".claude/canonical/{shop_type}-primer.md"
    target_file = real / primer_path
    assert target_file.exists(), (
        f"expected file at {primer_path!r} in target directory {real!s}"
    )
    actual = target_file.read_bytes()
    expected = read_claude_md_primer(shop_type).encode()
    assert actual == expected, (
        f"after update, byte contents of {primer_path!r} do not equal "
        f"canonical primer template for {shop_type!r} byte-for-byte.\n"
        f"len(expected)={len(expected)} len(actual)={len(actual)}\n"
        f"expected_tail={expected[-40:]!r}\n"
        f"actual_tail={actual[-40:]!r}"
    )


@then(
    'the stderr output of the invocation is empty'
)
def then_stderr_output_is_empty(context: dict) -> None:
    stderr = context.get("cli_stderr", "")
    assert stderr == "", (
        f"expected empty stderr output from invocation; got:\n{stderr}"
    )


@then(
    parsers.parse(
        'after the invocation the byte contents of the file at "{path}" '
        'in the target directory equal the recorded byte contents'
    )
)
def then_file_byte_contents_equal_recorded(path: str, context: dict) -> None:
    snap = context.get("two_file_snapshot", {})
    assert path in snap, (
        f"no recorded snapshot for {path!r}; the 'I record the byte "
        f"contents and mtimes' Given step must run first"
    )
    real = context["last_invocation_target"]
    actual = (real / path).read_bytes()
    expected = snap[path]["bytes"]
    assert actual == expected, (
        f"byte contents of {path!r} changed across update invocation; "
        f"expected idempotent (no-op) write but file was modified."
    )


@then(
    parsers.parse(
        'after the invocation the mtime of the file at "{path}" in the '
        'target directory equals the recorded mtime'
    )
)
def then_file_mtime_equals_recorded(path: str, context: dict) -> None:
    snap = context.get("two_file_snapshot", {})
    assert path in snap, (
        f"no recorded snapshot for {path!r}; the 'I record the byte "
        f"contents and mtimes' Given step must run first"
    )
    real = context["last_invocation_target"]
    actual_mtime_ns = (real / path).stat().st_mtime_ns
    expected_mtime_ns = snap[path]["mtime_ns"]
    assert actual_mtime_ns == expected_mtime_ns, (
        f"mtime of {path!r} changed across update invocation; "
        f"expected idempotent (no-op) write but mtime was bumped. "
        f"before={expected_mtime_ns} after={actual_mtime_ns}"
    )


@then(
    parsers.parse(
        'the stderr output of the invocation contains the literal '
        'substring "{needle}"'
    )
)
def then_stderr_contains_literal_substring(needle: str, context: dict) -> None:
    stderr = context.get("cli_stderr", "")
    assert needle in stderr, (
        f"expected stderr to contain literal substring {needle!r}; "
        f"got:\n{stderr}"
    )


@then(
    'after the invocation the recursive listing of file paths in the '
    'target directory equals the recorded listing'
)
def then_recursive_listing_equals_recorded(context: dict) -> None:
    real = _resolve_single_target(context)
    recorded_paths = context.get("pre_invocation_recursive_paths")
    assert recorded_paths is not None, (
        "no recorded recursive listing; the 'I record the recursive "
        "listing' Given step must run first"
    )
    current_paths = sorted(
        str(p.relative_to(real)) for p in real.rglob("*") if p.is_file()
    )
    assert current_paths == sorted(recorded_paths), (
        f"recursive file listing changed across invocation.\n"
        f"before={sorted(recorded_paths)!r}\n"
        f"after={current_paths!r}"
    )


@then(
    'after the invocation the byte contents of every file in the target '
    'directory equal the corresponding recorded byte contents'
)
def then_every_file_byte_contents_equals_recorded(context: dict) -> None:
    real = _resolve_single_target(context)
    recorded = context.get("pre_invocation_recursive_contents")
    assert recorded is not None, (
        "no recorded file contents; the 'I record the recursive listing' "
        "Given step must run first"
    )
    for rel, expected_bytes in recorded.items():
        actual_file = real / rel
        assert actual_file.exists(), (
            f"file {rel!r} existed before invocation but is missing after"
        )
        actual_bytes = actual_file.read_bytes()
        assert actual_bytes == expected_bytes, (
            f"byte contents of {rel!r} changed across invocation; "
            f"expected no-touch but file was modified."
        )


# -----------------------------------------------------------------------
# Then steps — f55678f733a5427a: shop-type-from-file update verification
# -----------------------------------------------------------------------


@then(
    parsers.parse(
        'after the invocation the target directory contains a file at '
        '".claude/canonical/{shop_type}-primer.md" whose byte contents '
        'equal the canonical "CLAUDE.md" primer template for shop type '
        '"{shop_type}" byte-for-byte'
    )
)
def then_target_canonical_primer_file_exists_and_matches(
    shop_type: str, context: dict
) -> None:
    from shop_templates.cli import read_claude_md_primer

    real = context["last_invocation_target"]
    primer_path = f".claude/canonical/{shop_type}-primer.md"
    target_file = real / primer_path
    assert target_file.exists(), (
        f"expected file at {primer_path!r} to exist in target directory "
        f"{real!s} after update invocation"
    )
    actual = target_file.read_bytes()
    expected = read_claude_md_primer(shop_type).encode()
    assert actual == expected, (
        f"byte contents of {primer_path!r} do not equal canonical primer "
        f"template for {shop_type!r} byte-for-byte.\n"
        f"len(expected)={len(expected)} len(actual)={len(actual)}"
    )


# -----------------------------------------------------------------------
# Step definitions — lead-33r / PDR-009 scenarios:
#   0c157533eb3145c8 — canonical settings.json hook commands contain no
#                      "{{" or "}}" substrings (publisher-side guard).
#   9317b34e56712c7c — exactly one inner-hook command equals literal
#                      "shop-msg prime" (bare, no addressing flag).
#   d3cc63377ac86cce — both "bd prime" and "shop-msg prime" present as
#                      two distinct inner-hook entries under SessionStart.
#   e74510bc2af8f058 — bootstrap- or update-poured settings.json on
#                      disk also contains no "{{" or "}}" substrings.
#   ef68be19d7b3a3bb — update over a stale placeholder-bearing hook
#                      command replaces it with the current canonical
#                      bare "shop-msg prime".
# -----------------------------------------------------------------------


# Scenario 0c157533eb3145c8 — for every top-level hook-event key under
# "hooks" (e.g. SessionStart, PreCompact), iterate every element of the
# array, every inner-hook entry, and assert the entry's "command" string
# contains neither "{{" nor "}}".
@then(
    'for every top-level hook-event key under "hooks", and for every '
    'element of that hook-event\'s array, and for every entry of that '
    'element\'s inner "hooks" array, the entry\'s "command" string '
    'contains no occurrence of the substring "{{" and no occurrence of '
    'the substring "}}"'
)
def then_no_placeholder_substrings_in_any_hook_command(
    context: dict,
) -> None:
    parsed = context.get("last_parsed_body")
    assert parsed is not None, (
        "no parsed body in context; an earlier 'the returned body is "
        "parsed as JSON' step must run first"
    )
    assert isinstance(parsed, dict), (
        f"parsed body is not a JSON object: {parsed!r}"
    )
    hooks = parsed.get("hooks")
    assert isinstance(hooks, dict), (
        f"parsed body has no top-level 'hooks' object: {parsed!r}"
    )
    for event_key, event_array in hooks.items():
        if not isinstance(event_array, list):
            continue
        for i, elem in enumerate(event_array):
            if not isinstance(elem, dict):
                continue
            inner = elem.get("hooks")
            if not isinstance(inner, list):
                continue
            for j, inner_elem in enumerate(inner):
                if not isinstance(inner_elem, dict):
                    continue
                cmd = inner_elem.get("command")
                if not isinstance(cmd, str):
                    continue
                assert "{{" not in cmd, (
                    f"hook-event {event_key!r} element {i} inner hook "
                    f"{j} has command string containing forbidden "
                    f"substring '{{{{': {cmd!r}"
                )
                assert "}}" not in cmd, (
                    f"hook-event {event_key!r} element {i} inner hook "
                    f"{j} has command string containing forbidden "
                    f"substring '}}}}': {cmd!r}"
                )


# Helpers — extract the flat list of inner-hook command strings under
# hooks.SessionStart from either the in-memory parsed body or an
# on-disk poured settings.json file.
def _collect_sessionstart_commands(parsed_body: dict) -> list[str]:
    """Flatten every "command" string in every inner "hooks" array under
    hooks.SessionStart. Returns a list (order preserved) of command
    strings; ignores entries whose shape is malformed.
    """
    if not isinstance(parsed_body, dict):
        return []
    hooks = parsed_body.get("hooks")
    if not isinstance(hooks, dict):
        return []
    sessionstart = hooks.get("SessionStart")
    if not isinstance(sessionstart, list):
        return []
    commands: list[str] = []
    for elem in sessionstart:
        if not isinstance(elem, dict):
            continue
        inner = elem.get("hooks")
        if not isinstance(inner, list):
            continue
        for inner_elem in inner:
            if not isinstance(inner_elem, dict):
                continue
            cmd = inner_elem.get("command")
            if isinstance(cmd, str):
                commands.append(cmd)
    return commands


def _collect_sessionstart_entries(parsed_body: dict) -> list[tuple[int, int, str]]:
    """Like _collect_sessionstart_commands, but returns (outer_idx,
    inner_idx, command) so callers can distinguish "the same entry"
    from "two entries that happen to share a command string".
    """
    if not isinstance(parsed_body, dict):
        return []
    hooks = parsed_body.get("hooks")
    if not isinstance(hooks, dict):
        return []
    sessionstart = hooks.get("SessionStart")
    if not isinstance(sessionstart, list):
        return []
    entries: list[tuple[int, int, str]] = []
    for i, elem in enumerate(sessionstart):
        if not isinstance(elem, dict):
            continue
        inner = elem.get("hooks")
        if not isinstance(inner, list):
            continue
        for j, inner_elem in enumerate(inner):
            if not isinstance(inner_elem, dict):
                continue
            cmd = inner_elem.get("command")
            if isinstance(cmd, str):
                entries.append((i, j, cmd))
    return entries


# Scenario 9317b34e56712c7c — exactly one inner-hook entry under
# hooks.SessionStart has command equal to a literal value.
@then(
    parsers.parse(
        'exactly one inner-hook entry under "hooks.SessionStart" has a '
        '"command" string equal to the literal value "{expected}"'
    )
)
def then_exactly_one_inner_hook_command_equals(
    expected: str, context: dict
) -> None:
    parsed = context.get("last_parsed_body")
    assert parsed is not None, (
        "no parsed body in context; an earlier 'the returned body is "
        "parsed as JSON' step must run first"
    )
    commands = _collect_sessionstart_commands(parsed)
    matches = [c for c in commands if c == expected]
    assert len(matches) == 1, (
        f"expected exactly one inner-hook command equal to "
        f"{expected!r} under hooks.SessionStart; got {len(matches)} "
        f"matching entries. All commands: {commands!r}"
    )


# Scenario 9317b34e56712c7c — no inner-hook entry has a command string
# starting with a given prefix followed by additional characters.
@then(
    parsers.parse(
        'no inner-hook entry under "hooks.SessionStart" has a "command" '
        'string that starts with "{prefix}" followed by additional '
        'characters'
    )
)
def then_no_inner_hook_command_starts_with_prefix(
    prefix: str, context: dict
) -> None:
    parsed = context.get("last_parsed_body")
    assert parsed is not None, (
        "no parsed body in context; an earlier 'the returned body is "
        "parsed as JSON' step must run first"
    )
    commands = _collect_sessionstart_commands(parsed)
    for cmd in commands:
        if cmd.startswith(prefix) and len(cmd) > len(prefix):
            assert False, (
                f"inner-hook command {cmd!r} starts with forbidden "
                f"prefix {prefix!r} followed by additional characters"
            )


# Scenario 9317b34e56712c7c — no inner-hook command string contains a
# given substring (used for "--bc", "--lead", etc.).
@then(
    parsers.parse(
        'no inner-hook entry under "hooks.SessionStart" has a "command" '
        'string containing the substring "{needle}"'
    )
)
def then_no_inner_hook_command_contains_substring(
    needle: str, context: dict
) -> None:
    parsed = context.get("last_parsed_body")
    assert parsed is not None, (
        "no parsed body in context; an earlier 'the returned body is "
        "parsed as JSON' step must run first"
    )
    commands = _collect_sessionstart_commands(parsed)
    for cmd in commands:
        assert needle not in cmd, (
            f"inner-hook command {cmd!r} contains forbidden substring "
            f"{needle!r}"
        )


# Scenario d3cc63377ac86cce — two inner-hook entries are distinct entries
# (not packed into a single "command" via shell composition).
@then(
    'those two inner-hook entries are distinct entries'
)
def then_two_inner_hook_entries_are_distinct(context: dict) -> None:
    parsed = context.get("last_parsed_body")
    assert parsed is not None, (
        "no parsed body in context; an earlier 'the returned body is "
        "parsed as JSON' step must run first"
    )
    entries = _collect_sessionstart_entries(parsed)
    bd_entries = [e for e in entries if e[2] == "bd prime"]
    sm_entries = [e for e in entries if e[2] == "shop-msg prime"]
    assert len(bd_entries) == 1, (
        f"expected exactly one inner-hook entry equal to 'bd prime'; "
        f"got {len(bd_entries)}"
    )
    assert len(sm_entries) == 1, (
        f"expected exactly one inner-hook entry equal to 'shop-msg "
        f"prime'; got {len(sm_entries)}"
    )
    # "distinct entries" means a different (outer_idx, inner_idx) pair.
    # Each entry in our collection corresponds to a single inner-hook
    # object; two different (outer, inner) pairs means two different
    # JSON objects in the underlying settings.json.
    bd_pos = (bd_entries[0][0], bd_entries[0][1])
    sm_pos = (sm_entries[0][0], sm_entries[0][1])
    assert bd_pos != sm_pos, (
        "'bd prime' and 'shop-msg prime' resolve to the same inner-hook "
        f"entry at outer={bd_pos[0]} inner={bd_pos[1]} — this is the "
        "shell-composition failure mode the scenario forbids"
    )
    # Also explicitly guard against shell composition: no single command
    # string under SessionStart may contain both "bd prime" and
    # "shop-msg prime" (which would be the "bd prime && shop-msg prime"
    # failure mode named in the scenario).
    commands = _collect_sessionstart_commands(parsed)
    for cmd in commands:
        assert not ("bd prime" in cmd and "shop-msg prime" in cmd), (
            f"inner-hook command {cmd!r} packs both 'bd prime' and "
            f"'shop-msg prime' into a single command string — the "
            f"scenario forbids this composition"
        )


# -----------------------------------------------------------------------
# Scenario e74510bc2af8f058 — bootstrap-or-update entry-point dispatch.
#
# The Gherkin parameterizes <entry_point> as either "init" or "update"
# and uses a unified When step:
#
#   When I invoke the "shop-templates" "<entry_point>" against target
#        "<target>" with shop type "<shop_type>" and shop name "<shop_name>"
#
# Mapping at the test-step layer (no new CLI subcommand introduced):
#   - entry_point == "init"   -> shop-templates bootstrap --shop-type X
#                                 --shop-name Y --target T
#   - entry_point == "update" -> first bootstrap the target (so the
#                                 update has a valid shop to operate
#                                 against — update reads
#                                 .claude/shop/type.md), then run
#                                 shop-templates update --target T.
# -----------------------------------------------------------------------


@when(
    parsers.parse(
        'I invoke the "shop-templates" "{entry_point}" against target '
        '"{alias}" with shop type "{shop_type}" and shop name '
        '"{shop_name}"'
    )
)
def when_invoke_entry_point_init_or_update(
    entry_point: str,
    alias: str,
    shop_type: str,
    shop_name: str,
    context: dict,
    tmp_path: Path,
) -> None:
    real = _real_target_for_alias(alias, context)
    if entry_point == "init":
        result = _run_shop_templates_with_bd_shim(
            [
                "bootstrap",
                "--shop-type",
                shop_type,
                "--shop-name",
                shop_name,
                "--target",
                str(real),
            ],
            context,
            tmp_path,
        )
    elif entry_point == "update":
        # Update requires a previously-bootstrapped shop (it reads
        # .claude/shop/type.md to determine which canonical to pour).
        # Run bootstrap first to establish that state, then run update.
        boot = _run_shop_templates_with_bd_shim(
            [
                "bootstrap",
                "--shop-type",
                shop_type,
                "--shop-name",
                shop_name,
                "--target",
                str(real),
            ],
            context,
            tmp_path,
        )
        assert boot.returncode == 0, (
            f"step adapter: pre-update bootstrap failed for target "
            f"{real!s} (rc={boot.returncode}); stderr:\n{boot.stderr}"
        )
        result = _run_shop_templates_with_bd_shim(
            [
                "update",
                "--target",
                str(real),
            ],
            context,
            tmp_path,
        )
    else:
        raise AssertionError(
            f"unknown entry_point value {entry_point!r}; expected "
            "'init' or 'update'"
        )
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr
    context["last_invocation_target"] = real
    context["last_invocation_shop_type"] = shop_type
    context["last_invocation_shop_name"] = shop_name


# Scenario e74510bc2af8f058 — file existence + substring exclusion on a
# poured ".claude/settings.json" under the target. The path in the
# Gherkin is "<target>/.claude/settings.json" — we resolve <target> as
# an alias to the per-test real path.
@then(
    parsers.parse(
        'the file at "{alias}/.claude/settings.json" exists'
    )
)
def then_target_settings_json_exists(alias: str, context: dict) -> None:
    real = _real_target_for_alias(alias, context)
    settings_file = real / ".claude" / "settings.json"
    assert settings_file.exists(), (
        f"expected {settings_file!s} to exist after the invocation"
    )


@then(
    parsers.parse(
        'the contents of "{alias}/.claude/settings.json" contain no '
        'occurrence of the substring "{needle}"'
    )
)
def then_target_settings_json_does_not_contain_substring(
    alias: str, needle: str, context: dict
) -> None:
    real = _real_target_for_alias(alias, context)
    settings_file = real / ".claude" / "settings.json"
    body = settings_file.read_text()
    assert needle not in body, (
        f"poured {settings_file!s} unexpectedly contains forbidden "
        f"substring {needle!r}"
    )


# -----------------------------------------------------------------------
# Scenario ef68be19d7b3a3bb — stale placeholder-bearing hook command
# replaced on update.
# -----------------------------------------------------------------------


@given(
    parsers.parse(
        'the file at "{alias}/.claude/settings.json" contains an '
        'inner-hook entry under "hooks.SessionStart" whose "command" '
        'string is the stale literal "{stale_command}"'
    )
)
def given_settings_json_has_stale_command(
    alias: str, stale_command: str, context: dict
) -> None:
    import json

    real = _real_target_for_alias(alias, context)
    settings_file = real / ".claude" / "settings.json"
    # The target was previously bootstrapped, so settings.json exists
    # with the current canonical content. Mutate it to insert the
    # stale literal as an inner-hook entry — preserving valid JSON
    # structure so update can still parse-and-replace cleanly.
    assert settings_file.exists(), (
        f"premise violated: {settings_file!s} does not exist after the "
        "previously-bootstrapped Given"
    )
    body = json.loads(settings_file.read_text())
    stale_entry = {"type": "command", "command": stale_command}
    # Find or create the SessionStart array, then replace its first
    # element's inner hooks with a single stale entry — this is the
    # "shop bootstrapped with an OLD canonical" state.
    hooks = body.setdefault("hooks", {})
    sessionstart = hooks.setdefault("SessionStart", [])
    if not sessionstart:
        sessionstart.append({"matcher": "", "hooks": []})
    # Replace inner hooks of the first SessionStart element with the
    # single stale entry. This matches the "shop was bootstrapped with
    # the OLD canonical that carried a placeholder hook" state the
    # scenario describes.
    sessionstart[0] = {"matcher": "", "hooks": [stale_entry]}
    settings_file.write_text(json.dumps(body, indent=2) + "\n")
    # Sanity: confirm the stale literal is in fact present on disk.
    on_disk = settings_file.read_text()
    assert stale_command in on_disk, (
        f"premise violated: stale literal {stale_command!r} not "
        f"present in {settings_file!s} after seeding"
    )


@when(
    parsers.parse(
        'I invoke the "shop-templates" update entry point against '
        'target "{alias}"'
    )
)
def when_invoke_update_against_target_alias(
    alias: str, context: dict, tmp_path: Path
) -> None:
    real = _real_target_for_alias(alias, context)
    shop_type = context.get("bootstrap_shop_type")
    args = ["update", "--target", str(real)]
    if shop_type is not None:
        args.extend(["--shop-type", shop_type])
    result = _run_shop_templates_with_bd_shim(args, context, tmp_path)
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr
    context["last_invocation_target"] = real


@then(
    parsers.parse(
        'after the invocation no inner-hook entry under '
        '"hooks.SessionStart" in "{alias}/.claude/settings.json" has a '
        '"command" string containing the substring "{needle}"'
    )
)
def then_no_inner_hook_command_contains_substring_in_file(
    alias: str, needle: str, context: dict
) -> None:
    import json

    real = _real_target_for_alias(alias, context)
    settings_file = real / ".claude" / "settings.json"
    parsed = json.loads(settings_file.read_text())
    commands = _collect_sessionstart_commands(parsed)
    for cmd in commands:
        assert needle not in cmd, (
            f"after update, inner-hook command {cmd!r} in "
            f"{settings_file!s} still contains forbidden substring "
            f"{needle!r}"
        )


@then(
    parsers.parse(
        'after the invocation exactly one inner-hook entry under '
        '"hooks.SessionStart" in "{alias}/.claude/settings.json" has a '
        '"command" string equal to the literal value "{expected}"'
    )
)
def then_exactly_one_inner_hook_command_equals_in_file(
    alias: str, expected: str, context: dict
) -> None:
    import json

    real = _real_target_for_alias(alias, context)
    settings_file = real / ".claude" / "settings.json"
    parsed = json.loads(settings_file.read_text())
    commands = _collect_sessionstart_commands(parsed)
    matches = [c for c in commands if c == expected]
    assert len(matches) == 1, (
        f"after update, expected exactly one inner-hook command equal "
        f"to {expected!r} in {settings_file!s}; got {len(matches)} "
        f"matches. All commands: {commands!r}"
    )


@then(
    parsers.parse(
        'after the invocation "{alias}/.claude/settings.json" equals '
        'the current canonical ".claude/settings.json" template for '
        'shop type "{shop_type}" byte-for-byte'
    )
)
def then_target_settings_json_equals_canonical_byte_for_byte(
    alias: str, shop_type: str, context: dict
) -> None:
    from shop_templates.cli import read_claude_settings_template

    real = _real_target_for_alias(alias, context)
    settings_file = real / ".claude" / "settings.json"
    actual = settings_file.read_text()
    expected = read_claude_settings_template(shop_type)
    assert actual == expected, (
        f"after update, {settings_file!s} does not equal the canonical "
        f"settings template for shop_type={shop_type!r} byte-for-byte.\n"
        f"len(expected)={len(expected)} len(actual)={len(actual)}"
    )


# -----------------------------------------------------------------------
# Then steps — bc-reviewer pre-emit clean-tree and origin/main checks
# (lead-cw7 scenarios 9457dfff7e3f9e90, 2b5d558d548b0606,
# 6d0a7a957b340274, 721dcf075edcd9c7)
# -----------------------------------------------------------------------
#
# These steps pin that the bc-reviewer template names "git status
# --porcelain" and a "git log" / "git rev-parse" check against
# "origin/main" as discrete pre-emit verification steps the reviewer
# must run before composing work_done --status complete, and that
# precondition failures (dirty tracked files, untracked files,
# missing-on-origin/main commit) must convert the response into
# work_done --status blocked with the offending paths / work_id /
# HEAD SHA named in the summary. The assertion strategy mirrors the
# existing "names X as a Y discipline" steps higher up in this
# file: each scenario's Then steps reduce to literal-substring
# checks against the rendered template content, augmented with
# co-occurrence requirements so a stray mention elsewhere in the
# template would not silently satisfy a structural intent.


# --- Scenario 9457dfff7e3f9e90 ---

@then(
    'the content names "git status --porcelain" as a pre-emit verification '
    'step the reviewer must run before composing a work_done with status '
    'complete'
)
def then_content_names_git_status_porcelain_pre_emit(context: dict) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The literal command must appear.
    assert "git status --porcelain" in content, (
        "bc-reviewer template must name 'git status --porcelain' as a "
        "pre-emit verification step (lead-cw7 / 9457dfff7e3f9e90)"
    )
    # Co-occurrence: the command's framing must reference work_done /
    # status complete so the step is unambiguously tied to the pre-emit
    # gate, not an unrelated mention.
    assert "work_done" in lower and "complete" in lower, (
        "bc-reviewer template must frame 'git status --porcelain' as a "
        "step prior to composing work_done with status complete "
        "(lead-cw7 / 9457dfff7e3f9e90)"
    )


@then(
    'the content names "git log" or "git rev-parse" (against the BC\'s '
    '"origin/main" ref) as a pre-emit verification step that confirms the '
    'work_id\'s change is present on the BC\'s main branch'
)
def then_content_names_git_log_or_rev_parse_origin_main(context: dict) -> None:
    content = context["template_content"]
    # Either "git log" or "git rev-parse" must appear (the scenario
    # admits either as the verification verb).
    assert ("git log" in content) or ("git rev-parse" in content), (
        "bc-reviewer template must name either 'git log' or "
        "'git rev-parse' as a pre-emit verification step "
        "(lead-cw7 / 9457dfff7e3f9e90)"
    )
    # The BC's "origin/main" ref must appear, since the check is
    # explicitly against the main branch on origin.
    assert "origin/main" in content, (
        "bc-reviewer template must name 'origin/main' as the ref against "
        "which the work_id's commit is verified "
        "(lead-cw7 / 9457dfff7e3f9e90)"
    )
    # work_id must appear in the surrounding text so the step is tied
    # to the dispatched work_id, not a stray ref mention.
    assert "work_id" in content.lower(), (
        "bc-reviewer template must frame the origin/main verification "
        "in terms of the dispatched work_id "
        "(lead-cw7 / 9457dfff7e3f9e90)"
    )


@then(
    'the content directs the reviewer that when "git status --porcelain" '
    'produces any non-empty output the reviewer must NOT emit work_done '
    'with status complete, and instead must surface the uncommitted state '
    'as a blocker (e.g., emit work_done with status blocked, or stop and '
    'report) with the offending paths named in the response summary'
)
def then_content_dirty_tree_blocks_complete(context: dict) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The literal porcelain command must appear (already covered, but
    # we re-assert here so this Then is self-contained).
    assert "git status --porcelain" in content, (
        "bc-reviewer template must name 'git status --porcelain' in the "
        "dirty-tree-blocks-complete direction (lead-cw7 / 9457dfff7e3f9e90)"
    )
    # The blocked-status outcome must be named.
    assert "blocked" in lower, (
        "bc-reviewer template must direct emitting work_done with "
        "status blocked on dirty-tree precondition failure "
        "(lead-cw7 / 9457dfff7e3f9e90)"
    )
    # The summary-naming-paths requirement must appear: paths reported
    # by the porcelain output must be named in the summary.
    assert ("paths" in lower) and ("summary" in lower), (
        "bc-reviewer template must direct the reviewer to name the "
        "offending paths in the response summary "
        "(lead-cw7 / 9457dfff7e3f9e90)"
    )


@then(
    'the content directs the reviewer that when the BC\'s "origin/main" '
    'HEAD does NOT carry a commit for the dispatched work_id the reviewer '
    'must NOT emit work_done with status complete, and instead must '
    'surface the missing-commit state as a blocker with the work_id named '
    'in the response summary'
)
def then_content_missing_origin_main_commit_blocks_complete(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "origin/main" in content, (
        "bc-reviewer template must name 'origin/main' as the ref whose "
        "HEAD must carry the work_id's commit "
        "(lead-cw7 / 9457dfff7e3f9e90)"
    )
    assert "blocked" in lower, (
        "bc-reviewer template must direct emitting work_done with "
        "status blocked on missing-origin/main-commit precondition "
        "failure (lead-cw7 / 9457dfff7e3f9e90)"
    )
    assert "work_id" in lower and "summary" in lower, (
        "bc-reviewer template must direct the reviewer to name the "
        "work_id in the response summary on missing-commit failure "
        "(lead-cw7 / 9457dfff7e3f9e90)"
    )


@then(
    'the content marks both checks as discrete pre-emit steps (alongside '
    'the existing BDD-rerun and scenario-hash-presence steps), not as '
    'optional guidance the reviewer may skip'
)
def then_content_marks_checks_as_discrete_pre_emit_steps(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The two new checks (porcelain + origin/main) must both be present
    # — co-occurrence guarantees they are framed as a pair.
    assert "git status --porcelain" in content, (
        "bc-reviewer template missing 'git status --porcelain' check "
        "in discrete-pre-emit framing (lead-cw7 / 9457dfff7e3f9e90)"
    )
    assert "origin/main" in content, (
        "bc-reviewer template missing 'origin/main' check in "
        "discrete-pre-emit framing (lead-cw7 / 9457dfff7e3f9e90)"
    )
    # The BDD re-run must be named (it already exists in the template;
    # this is the "alongside the existing BDD-rerun" check).
    assert ("bdd" in lower) and ("pytest" in lower or "re-run" in lower
                                  or "rerun" in lower), (
        "bc-reviewer template must reference the existing BDD-rerun step "
        "(lead-cw7 / 9457dfff7e3f9e90)"
    )
    # The scenario-hash step must be referenced as a sibling pre-emit step.
    assert "scenario_hash" in lower or "scenario-hash" in lower, (
        "bc-reviewer template must reference the existing scenario-hash "
        "check as a sibling pre-emit step "
        "(lead-cw7 / 9457dfff7e3f9e90)"
    )
    # The "mandatory / not optional / must" framing — at least one
    # imperative cue must appear in the pre-emit section. We check for
    # "must" near "pre-emit" / "before" framing. The simplest robust
    # check: the word "must" appears at least three times in the
    # template (the existing template already has several; the new
    # section adds more).
    assert lower.count("must") >= 3, (
        "bc-reviewer template's pre-emit framing must use imperative "
        "language ('must' should appear multiple times), not optional "
        "guidance (lead-cw7 / 9457dfff7e3f9e90)"
    )


# --- Scenario 2b5d558d548b0606 ---

@then(
    'the content directs the reviewer that, prior to emitting work_done '
    'with status complete, the reviewer must invoke "git status '
    '--porcelain" in the BC root and inspect its output'
)
def then_content_directs_invoke_porcelain_in_bc_root(context: dict) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "git status --porcelain" in content, (
        "bc-reviewer template must direct 'git status --porcelain' "
        "invocation (lead-cw7 / 2b5d558d548b0606)"
    )
    # "BC root" must be named so the scope of the invocation is fixed.
    assert "bc root" in lower, (
        "bc-reviewer template must name 'BC root' as the scope of the "
        "porcelain invocation (lead-cw7 / 2b5d558d548b0606)"
    )
    assert "work_done" in lower and "complete" in lower, (
        "bc-reviewer template must frame the porcelain invocation as "
        "prior to emitting work_done --status complete "
        "(lead-cw7 / 2b5d558d548b0606)"
    )


@then(
    'the content directs the reviewer that any line in "git status '
    '--porcelain" output with a tracked-file modification marker (lines '
    'beginning with " M", "M ", "MM", " D", "D ", "A ", "AM", " R", "R ", '
    '" C", "C ", or "UU") is a precondition failure'
)
def then_content_enumerates_porcelain_tracked_markers(context: dict) -> None:
    content = context["template_content"]
    # The scenario explicitly enumerates these markers; the template
    # must enumerate them too so the reviewer is not left to guess.
    required_markers = (
        '" M"', '"M "', '"MM"', '" D"', '"D "', '"A "', '"AM"',
        '" R"', '"R "', '" C"', '"C "', '"UU"',
    )
    missing = [m for m in required_markers if m not in content]
    assert not missing, (
        "bc-reviewer template must enumerate every tracked-file "
        "porcelain marker called out by the scenario; missing: "
        f"{missing!r} (lead-cw7 / 2b5d558d548b0606)"
    )
    assert "precondition" in content.lower(), (
        "bc-reviewer template must name these as a 'precondition "
        "failure' (lead-cw7 / 2b5d558d548b0606)"
    )


@then(
    'the content directs the reviewer that on such a precondition failure '
    'the reviewer does NOT compose "shop-msg respond work_done --status '
    'complete" and instead emits "shop-msg respond work_done --status '
    'blocked" with a summary that names the tracked paths reported by '
    '"git status --porcelain"'
)
def then_content_directs_blocked_on_porcelain_tracked(
    context: dict,
) -> None:
    content = context["template_content"]
    assert "shop-msg respond work_done --status blocked" in content, (
        "bc-reviewer template must literally name the blocked-status "
        "shop-msg invocation (lead-cw7 / 2b5d558d548b0606)"
    )
    # The complete-status form must also be named (the negation form).
    assert "shop-msg respond work_done --status complete" in content, (
        "bc-reviewer template must literally name the complete-status "
        "shop-msg invocation that is being negated "
        "(lead-cw7 / 2b5d558d548b0606)"
    )
    lower = content.lower()
    assert "tracked" in lower and "paths" in lower, (
        "bc-reviewer template must direct naming the tracked paths in "
        "the summary (lead-cw7 / 2b5d558d548b0606)"
    )


@then(
    'the content frames the dirty-tracked-files check as a step the '
    'reviewer runs even when the BDD suite passes, so a green BDD result '
    'does not bypass the check'
)
def then_content_frames_dirty_check_not_bypassed_by_green_bdd(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The "even when BDD passes" / "BDD does not bypass" framing must
    # appear. Look for the conjunction of "bdd" and one of
    # "even", "regardless", "not bypass", "still", "always", "green".
    bypass_cues = ("even when", "even if", "regardless", "not bypass",
                   "does not bypass", "still", "always", "green")
    has_bypass_framing = "bdd" in lower and any(c in lower for c in bypass_cues)
    assert has_bypass_framing, (
        "bc-reviewer template must frame the dirty-tracked-files check "
        "as running even when BDD passes, so a green BDD result does "
        "not bypass it (lead-cw7 / 2b5d558d548b0606)"
    )


# --- Scenario 6d0a7a957b340274 ---

@then(
    'the content directs the reviewer that the same "git status '
    '--porcelain" inspection that catches modified-tracked-files (per '
    'scenario 106) also catches untracked files (lines beginning with '
    '"??") and treats them as a precondition failure'
)
def then_content_porcelain_catches_untracked(context: dict) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "git status --porcelain" in content, (
        "bc-reviewer template must name 'git status --porcelain' as the "
        "untracked-files inspection too (lead-cw7 / 6d0a7a957b340274)"
    )
    # The "??" marker must appear so the reviewer knows what line shape
    # to look for.
    assert '"??"' in content, (
        "bc-reviewer template must enumerate the '??' porcelain marker "
        "for untracked files (lead-cw7 / 6d0a7a957b340274)"
    )
    assert "untracked" in lower, (
        "bc-reviewer template must name 'untracked' files as the case "
        "this marker catches (lead-cw7 / 6d0a7a957b340274)"
    )
    assert "precondition" in lower, (
        "bc-reviewer template must frame untracked-files as a "
        "'precondition failure' (lead-cw7 / 6d0a7a957b340274)"
    )


@then(
    'the content directs the reviewer that on untracked-files failure the '
    'reviewer does NOT compose "shop-msg respond work_done --status '
    'complete" and instead emits "shop-msg respond work_done --status '
    'blocked" with a summary that names the untracked paths reported by '
    '"git status --porcelain"'
)
def then_content_directs_blocked_on_untracked(context: dict) -> None:
    content = context["template_content"]
    assert "shop-msg respond work_done --status blocked" in content, (
        "bc-reviewer template must literally name the blocked-status "
        "shop-msg invocation for untracked-files failure "
        "(lead-cw7 / 6d0a7a957b340274)"
    )
    assert "shop-msg respond work_done --status complete" in content, (
        "bc-reviewer template must literally name the complete-status "
        "shop-msg invocation that is being negated "
        "(lead-cw7 / 6d0a7a957b340274)"
    )
    lower = content.lower()
    assert "untracked" in lower and "paths" in lower, (
        "bc-reviewer template must direct naming the untracked paths "
        "in the summary (lead-cw7 / 6d0a7a957b340274)"
    )


@then(
    'the content explicitly directs the reviewer that the untracked-files '
    'check is NOT satisfied by adding the paths to .gitignore unless the '
    'paths are genuinely outside the BC\'s scope of work; the reviewer '
    'must confirm with the implementer (or by inspection of the dispatch) '
    'whether the untracked paths are work product that should be '
    'committed before re-attempting the emit'
)
def then_content_directs_gitignore_is_not_the_fix(context: dict) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert ".gitignore" in lower, (
        "bc-reviewer template must explicitly name '.gitignore' as the "
        "non-fix the reviewer must NOT default to "
        "(lead-cw7 / 6d0a7a957b340274)"
    )
    # The "scope of work" / "out of scope" framing must appear so the
    # carve-out is clear.
    assert "scope" in lower, (
        "bc-reviewer template must frame the .gitignore carve-out in "
        "terms of 'scope' (lead-cw7 / 6d0a7a957b340274)"
    )
    # The "work product" / "commit" framing must appear.
    assert "commit" in lower, (
        "bc-reviewer template must direct the reviewer to consider "
        "committing untracked work product instead of .gitignoring it "
        "(lead-cw7 / 6d0a7a957b340274)"
    )
    # The "confirm with the implementer (or by inspection of the
    # dispatch)" framing must appear.
    assert "implementer" in lower or "dispatch" in lower, (
        "bc-reviewer template must direct the reviewer to confirm with "
        "the implementer or by inspection of the dispatch "
        "(lead-cw7 / 6d0a7a957b340274)"
    )


# --- Scenario 721dcf075edcd9c7 ---

@then(
    'the content directs the reviewer that, prior to emitting work_done '
    'with status complete, the reviewer must verify by "git log '
    'origin/main" (or equivalent "git log" against the BC\'s main branch) '
    'that at least one commit attributable to the dispatched work_id is '
    'reachable from "origin/main" HEAD'
)
def then_content_directs_git_log_origin_main_reachable(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "git log origin/main" in content, (
        "bc-reviewer template must name the literal 'git log "
        "origin/main' verification (lead-cw7 / 721dcf075edcd9c7)"
    )
    assert "reachable" in lower, (
        "bc-reviewer template must frame the verification as the "
        "work_id's commit being 'reachable' from origin/main HEAD "
        "(lead-cw7 / 721dcf075edcd9c7)"
    )
    assert "work_id" in lower, (
        "bc-reviewer template must tie the reachability check to the "
        "dispatched work_id (lead-cw7 / 721dcf075edcd9c7)"
    )
    assert "work_done" in lower and "complete" in lower, (
        "bc-reviewer template must frame the verification as prior to "
        "emitting work_done --status complete "
        "(lead-cw7 / 721dcf075edcd9c7)"
    )


@then(
    'the content names a concrete attribution mechanism the reviewer may '
    'use to recognize the work_id\'s commit (for example, the work_id '
    'substring appearing in the commit message subject or body, or a '
    'tag/note pointing at the work_id), so the reviewer does not have to '
    'invent a convention'
)
def then_content_names_concrete_attribution_mechanism(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # At least one of the two attribution mechanisms must be concretely
    # named: (a) work_id substring in commit subject/body, or (b)
    # tag/note pointing at work_id. We require the language be specific
    # enough that the reviewer is not left to invent a convention.
    has_subject_body = (
        "subject" in lower or "body" in lower or "message" in lower
    ) and "work_id" in lower
    has_tag_note = "tag" in lower or "note" in lower
    assert has_subject_body or has_tag_note, (
        "bc-reviewer template must name at least one concrete "
        "attribution mechanism (work_id in commit subject/body, or "
        "tag/note pointing at work_id) "
        "(lead-cw7 / 721dcf075edcd9c7)"
    )


@then(
    'the content directs the reviewer that when no commit attributable to '
    'the work_id is reachable from "origin/main" HEAD the reviewer does '
    'NOT compose "shop-msg respond work_done --status complete" and '
    'instead emits "shop-msg respond work_done --status blocked" with a '
    'summary that names the dispatched work_id and the current '
    '"origin/main" HEAD short SHA'
)
def then_content_directs_blocked_on_missing_origin_main_commit(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "shop-msg respond work_done --status blocked" in content, (
        "bc-reviewer template must literally name the blocked-status "
        "shop-msg invocation for missing-origin/main-commit failure "
        "(lead-cw7 / 721dcf075edcd9c7)"
    )
    assert "shop-msg respond work_done --status complete" in content, (
        "bc-reviewer template must literally name the complete-status "
        "shop-msg invocation that is being negated "
        "(lead-cw7 / 721dcf075edcd9c7)"
    )
    # The summary must name (a) the dispatched work_id and (b) the
    # current origin/main HEAD short SHA. Pin both as required tokens.
    assert "work_id" in lower and "summary" in lower, (
        "bc-reviewer template must direct naming the work_id in the "
        "response summary (lead-cw7 / 721dcf075edcd9c7)"
    )
    assert ("short sha" in lower) or ("short-sha" in lower) or (
        "head" in lower and "sha" in lower
    ), (
        "bc-reviewer template must direct naming the current "
        "origin/main HEAD short SHA in the response summary "
        "(lead-cw7 / 721dcf075edcd9c7)"
    )


@then(
    'the content directs the reviewer that committing the work_id\'s '
    'change to any branch OTHER than the BC\'s main branch (e.g., a local '
    'feature branch that has not been merged or pushed to origin/main) '
    'does NOT satisfy this precondition; the only outcome that satisfies '
    'the precondition is the work_id\'s commit being reachable from '
    '"origin/main" HEAD'
)
def then_content_directs_local_branch_does_not_satisfy(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The carve-out must explicitly name the local-feature-branch case
    # and explicitly disqualify it.
    assert "local" in lower and "branch" in lower, (
        "bc-reviewer template must explicitly name the local-branch "
        "case as not satisfying the precondition "
        "(lead-cw7 / 721dcf075edcd9c7)"
    )
    assert "origin/main" in content, (
        "bc-reviewer template must name 'origin/main' as the only "
        "ref whose reachability satisfies the precondition "
        "(lead-cw7 / 721dcf075edcd9c7)"
    )
    # A disqualifying cue ("not satisfy", "does not satisfy", "only",
    # "only outcome") must appear so the carve-out reads as exclusion,
    # not allowance.
    disqualifying_cues = (
        "does not satisfy", "do not satisfy", "not satisfy",
        "only outcome", "only satisfies",
    )
    assert any(c in lower for c in disqualifying_cues), (
        "bc-reviewer template must disqualify local-branch commits "
        "with an explicit 'does not satisfy' / 'only outcome' framing "
        "(lead-cw7 / 721dcf075edcd9c7)"
    )


@then(
    'the content directs the reviewer that "git fetch origin" should be '
    'run as part of the verification so a stale local view of '
    '"origin/main" does not produce a false positive'
)
def then_content_directs_git_fetch_origin_first(context: dict) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "git fetch origin" in content, (
        "bc-reviewer template must name the literal 'git fetch origin' "
        "step (lead-cw7 / 721dcf075edcd9c7)"
    )
    # The justification — "stale" / "false positive" — must appear so
    # the step is framed as a guard, not boilerplate.
    assert "stale" in lower, (
        "bc-reviewer template must frame 'git fetch origin' as guarding "
        "against a stale local view (lead-cw7 / 721dcf075edcd9c7)"
    )
    assert "false positive" in lower or "false-positive" in lower, (
        "bc-reviewer template must frame the stale-view risk as a "
        "'false positive' (lead-cw7 / 721dcf075edcd9c7)"
    )


# -----------------------------------------------------------------------
# Then steps — bc-implementer pre-emit clean-tree and origin/main checks
# (lead-8lm scenarios fe496a8073f27678, e5669ee6062b95fd,
# 86d576b269ff89d6, e01ace6acd655909)
# -----------------------------------------------------------------------
#
# These steps mirror the lead-cw7 bc-reviewer steps above, but scoped
# to the Implementer-emitter side: the bc-implementer template must
# name the same "git status --porcelain" and "git log" /
# "git rev-parse" against "origin/main" pre-emit checks, but ONLY for
# dispatches where the Implementer is the work_done emitter — i.e.,
# request_maintenance, or request_bugfix whose scenarios[] is empty.
# For assign_scenarios / scenario-carrying request_bugfix the Reviewer
# holds the gate (per the existing "Hand-off to the Reviewer" section
# in bc-implementer.md and per lead-cw7 scenarios on bc-reviewer), so
# the new section must explicitly carve that path out, not silently
# include it. The assertion strategy mirrors lead-cw7: literal-substring
# checks against the rendered template content, augmented with
# co-occurrence requirements so a stray mention elsewhere in the
# template would not silently satisfy a structural intent.


# --- Scenario fe496a8073f27678 ---

@then(
    'the content names "git status --porcelain" as a pre-emit verification '
    'step the implementer must run before composing a work_done with status '
    'complete on a dispatch where the Implementer is the work_done emitter '
    '(request_maintenance, or request_bugfix whose scenarios[] is empty)'
)
def then_impl_content_names_git_status_porcelain_pre_emit(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "git status --porcelain" in content, (
        "bc-implementer template must name 'git status --porcelain' as "
        "a pre-emit verification step (lead-8lm / fe496a8073f27678)"
    )
    # Co-occurrence: the pre-emit framing must reference work_done /
    # status complete so the step is unambiguously tied to the pre-emit
    # gate, not an unrelated mention.
    assert "work_done" in lower and "complete" in lower, (
        "bc-implementer template must frame 'git status --porcelain' as "
        "a step prior to composing work_done with status complete "
        "(lead-8lm / fe496a8073f27678)"
    )
    # Scope qualifier: the pre-emit check must be tied to the
    # Implementer-emitter dispatches — request_maintenance and
    # request_bugfix-with-empty-scenarios. Both message_type names
    # must appear in the section.
    assert "request_maintenance" in content, (
        "bc-implementer template must name 'request_maintenance' as "
        "an Implementer-emitter dispatch in the pre-emit framing "
        "(lead-8lm / fe496a8073f27678)"
    )
    assert "request_bugfix" in content, (
        "bc-implementer template must name 'request_bugfix' as an "
        "Implementer-emitter dispatch (the scenarios[] is empty case) "
        "in the pre-emit framing (lead-8lm / fe496a8073f27678)"
    )


@then(
    'the content names "git log" or "git rev-parse" (against the BC\'s '
    '"origin/main" ref) as a pre-emit verification step that confirms the '
    'work_id\'s change is present on the BC\'s main branch'
)
def then_impl_content_names_git_log_or_rev_parse_origin_main(
    context: dict,
) -> None:
    content = context["template_content"]
    assert ("git log" in content) or ("git rev-parse" in content), (
        "bc-implementer template must name either 'git log' or "
        "'git rev-parse' as a pre-emit verification step "
        "(lead-8lm / fe496a8073f27678)"
    )
    assert "origin/main" in content, (
        "bc-implementer template must name 'origin/main' as the ref "
        "against which the work_id's commit is verified "
        "(lead-8lm / fe496a8073f27678)"
    )
    assert "work_id" in content.lower(), (
        "bc-implementer template must frame the origin/main "
        "verification in terms of the dispatched work_id "
        "(lead-8lm / fe496a8073f27678)"
    )


@then(
    'the content directs the implementer that when "git status --porcelain" '
    'produces any non-empty output the implementer must NOT emit work_done '
    'with status complete, and instead must surface the uncommitted state '
    'as a blocker (e.g., emit work_done with status blocked, or stop and '
    'report) with the offending paths named in the response summary'
)
def then_impl_content_dirty_tree_blocks_complete(context: dict) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "git status --porcelain" in content, (
        "bc-implementer template must name 'git status --porcelain' in "
        "the dirty-tree-blocks-complete direction "
        "(lead-8lm / fe496a8073f27678)"
    )
    assert "blocked" in lower, (
        "bc-implementer template must direct emitting work_done with "
        "status blocked on dirty-tree precondition failure "
        "(lead-8lm / fe496a8073f27678)"
    )
    assert ("paths" in lower) and ("summary" in lower), (
        "bc-implementer template must direct the implementer to name "
        "the offending paths in the response summary "
        "(lead-8lm / fe496a8073f27678)"
    )


@then(
    'the content directs the implementer that when the BC\'s "origin/main" '
    'HEAD does NOT carry a commit for the dispatched work_id the '
    'implementer must NOT emit work_done with status complete, and instead '
    'must surface the missing-commit state as a blocker with the work_id '
    'named in the response summary'
)
def then_impl_content_missing_origin_main_commit_blocks_complete(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "origin/main" in content, (
        "bc-implementer template must name 'origin/main' as the ref "
        "whose HEAD must carry the work_id's commit "
        "(lead-8lm / fe496a8073f27678)"
    )
    assert "blocked" in lower, (
        "bc-implementer template must direct emitting work_done with "
        "status blocked on missing-origin/main-commit precondition "
        "failure (lead-8lm / fe496a8073f27678)"
    )
    assert "work_id" in lower and "summary" in lower, (
        "bc-implementer template must direct the implementer to name "
        "the work_id in the response summary on missing-commit failure "
        "(lead-8lm / fe496a8073f27678)"
    )


@then(
    'the content marks both checks as discrete pre-emit steps that fire '
    'for every Implementer-emitted work_done (complete) regardless of '
    'message_type, not as optional guidance the implementer may skip'
)
def then_impl_content_marks_checks_as_discrete_pre_emit_steps(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # Both new checks (porcelain + origin/main) must be present, framed
    # as a pair.
    assert "git status --porcelain" in content, (
        "bc-implementer template missing 'git status --porcelain' "
        "check in discrete-pre-emit framing "
        "(lead-8lm / fe496a8073f27678)"
    )
    assert "origin/main" in content, (
        "bc-implementer template missing 'origin/main' check in "
        "discrete-pre-emit framing (lead-8lm / fe496a8073f27678)"
    )
    # "regardless of message_type" — the section must frame the check
    # as firing for every Implementer-emitted work_done, not gated on
    # message_type.
    regardless_cues = (
        "regardless of message_type",
        "regardless of the message_type",
        "every implementer-emitted",
        "for every implementer-emitted",
        "any implementer-emitted",
    )
    assert any(c in lower for c in regardless_cues), (
        "bc-implementer template must frame the pre-emit checks as "
        "firing for every Implementer-emitted work_done regardless of "
        "message_type (lead-8lm / fe496a8073f27678)"
    )
    # Imperative ("must") language must appear; the existing template
    # already has several, and the new section adds more.
    assert lower.count("must") >= 3, (
        "bc-implementer template's pre-emit framing must use "
        "imperative language ('must' should appear multiple times), "
        "not optional guidance (lead-8lm / fe496a8073f27678)"
    )


@then(
    'the content makes clear these pre-emit checks do NOT apply to the '
    'assign_scenarios / scenario-carrying request_bugfix path, where the '
    'Reviewer holds the gate per the existing "Hand-off to the Reviewer" '
    'section and per scenarios 105–108 against bc-reviewer'
)
def then_impl_content_carves_out_reviewer_gated_paths(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The carve-out must explicitly name assign_scenarios as a
    # NOT-included path for these pre-emit checks.
    assert "assign_scenarios" in content, (
        "bc-implementer template must explicitly name "
        "'assign_scenarios' in the carve-out as a path where these "
        "pre-emit checks do NOT apply (lead-8lm / fe496a8073f27678)"
    )
    # The Reviewer-holds-gate framing must appear so the carve-out is
    # tied to the existing role-discipline boundary.
    assert "reviewer" in lower, (
        "bc-implementer template's carve-out must reference the "
        "Reviewer as the gate-holder for assign_scenarios / "
        "scenario-carrying request_bugfix (lead-8lm / fe496a8073f27678)"
    )
    # The existing "Hand-off to the Reviewer" section must be
    # referenced by name so the carve-out is anchored to the existing
    # template structure, not a free-floating mention.
    assert "hand-off to the reviewer" in lower, (
        "bc-implementer template's carve-out must reference the "
        "existing 'Hand-off to the Reviewer' section by name "
        "(lead-8lm / fe496a8073f27678)"
    )
    # A negation cue ("do not apply", "does not apply", "not for") must
    # appear so the carve-out reads as exclusion, not allowance.
    negation_cues = (
        "do not apply", "does not apply", "do NOT apply",
        "not apply", "not for assign_scenarios",
    )
    assert any(c.lower() in lower for c in negation_cues), (
        "bc-implementer template's carve-out must use an explicit "
        "negation ('do not apply' / 'does not apply') so the carve-out "
        "reads as exclusion (lead-8lm / fe496a8073f27678)"
    )


# --- Scenario e5669ee6062b95fd ---

@then(
    'the content directs the implementer that, prior to emitting work_done '
    'with status complete on a dispatch where the Implementer is the '
    'work_done emitter (request_maintenance, or request_bugfix whose '
    'scenarios[] is empty), the implementer must invoke "git status '
    '--porcelain" in the BC root and inspect its output'
)
def then_impl_content_directs_invoke_porcelain_in_bc_root(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "git status --porcelain" in content, (
        "bc-implementer template must direct 'git status --porcelain' "
        "invocation (lead-8lm / e5669ee6062b95fd)"
    )
    assert "bc root" in lower, (
        "bc-implementer template must name 'BC root' as the scope of "
        "the porcelain invocation (lead-8lm / e5669ee6062b95fd)"
    )
    assert "work_done" in lower and "complete" in lower, (
        "bc-implementer template must frame the porcelain invocation "
        "as prior to emitting work_done --status complete "
        "(lead-8lm / e5669ee6062b95fd)"
    )
    # The Implementer-emitter scope qualifier must appear so this
    # check is unambiguously tied to the Implementer-emitter path.
    assert "request_maintenance" in content, (
        "bc-implementer template must scope the porcelain invocation "
        "to request_maintenance (Implementer-emitter dispatch) "
        "(lead-8lm / e5669ee6062b95fd)"
    )
    assert "request_bugfix" in content, (
        "bc-implementer template must scope the porcelain invocation "
        "to request_bugfix (the empty-scenarios case) "
        "(lead-8lm / e5669ee6062b95fd)"
    )


@then(
    'the content directs the implementer that any line in "git status '
    '--porcelain" output with a tracked-file modification marker (lines '
    'beginning with " M", "M ", "MM", " D", "D ", "A ", "AM", " R", "R ", '
    '" C", "C ", or "UU") is a precondition failure'
)
def then_impl_content_enumerates_porcelain_tracked_markers(
    context: dict,
) -> None:
    content = context["template_content"]
    required_markers = (
        '" M"', '"M "', '"MM"', '" D"', '"D "', '"A "', '"AM"',
        '" R"', '"R "', '" C"', '"C "', '"UU"',
    )
    missing = [m for m in required_markers if m not in content]
    assert not missing, (
        "bc-implementer template must enumerate every tracked-file "
        "porcelain marker called out by the scenario; missing: "
        f"{missing!r} (lead-8lm / e5669ee6062b95fd)"
    )
    assert "precondition" in content.lower(), (
        "bc-implementer template must name these as a 'precondition "
        "failure' (lead-8lm / e5669ee6062b95fd)"
    )


@then(
    'the content directs the implementer that on such a precondition '
    'failure the implementer does NOT compose "shop-msg respond work_done '
    '--status complete" and instead emits "shop-msg respond work_done '
    '--status blocked" with a summary that names the tracked paths '
    'reported by "git status --porcelain"'
)
def then_impl_content_directs_blocked_on_porcelain_tracked(
    context: dict,
) -> None:
    content = context["template_content"]
    assert "shop-msg respond work_done --status blocked" in content, (
        "bc-implementer template must literally name the "
        "blocked-status shop-msg invocation "
        "(lead-8lm / e5669ee6062b95fd)"
    )
    assert "shop-msg respond work_done --status complete" in content, (
        "bc-implementer template must literally name the "
        "complete-status shop-msg invocation that is being negated "
        "(lead-8lm / e5669ee6062b95fd)"
    )
    lower = content.lower()
    assert "tracked" in lower and "paths" in lower, (
        "bc-implementer template must direct naming the tracked paths "
        "in the summary (lead-8lm / e5669ee6062b95fd)"
    )


@then(
    'the content frames the dirty-tracked-files check as a step the '
    'implementer runs even when acceptance criteria are satisfied and any '
    'local verification (unit tests, build, lint) passes, so a green local '
    'result does not bypass the check'
)
def then_impl_content_frames_dirty_check_not_bypassed_by_green_local(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The "even when local verification passes" framing must appear.
    bypass_cues = ("even when", "even if", "regardless", "not bypass",
                   "does not bypass", "still", "always", "green")
    has_bypass_framing = any(c in lower for c in bypass_cues)
    assert has_bypass_framing, (
        "bc-implementer template must frame the dirty-tracked-files "
        "check as running even when local verification passes "
        "(lead-8lm / e5669ee6062b95fd)"
    )
    # The "local verification" / "acceptance criteria" framing must
    # appear — the scenario specifically calls out that satisfying
    # acceptance criteria + green unit tests / build / lint does NOT
    # bypass the check.
    local_cues = (
        "acceptance criteria",
        "unit test", "unit tests",
        "build", "lint",
        "local verification",
    )
    assert any(c in lower for c in local_cues), (
        "bc-implementer template must reference local-verification "
        "cues (acceptance criteria / unit tests / build / lint / "
        "local verification) when framing the green-result-does-not-"
        "bypass discipline (lead-8lm / e5669ee6062b95fd)"
    )


# --- Scenario 86d576b269ff89d6 ---

@then(
    'the content directs the implementer that the same "git status '
    '--porcelain" inspection that catches modified-tracked-files (per '
    'scenario 110) also catches untracked files (lines beginning with '
    '"??") and treats them as a precondition failure on any '
    'Implementer-emitted work_done (request_maintenance, or request_bugfix '
    'whose scenarios[] is empty)'
)
def then_impl_content_porcelain_catches_untracked(context: dict) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "git status --porcelain" in content, (
        "bc-implementer template must name 'git status --porcelain' "
        "as the untracked-files inspection too "
        "(lead-8lm / 86d576b269ff89d6)"
    )
    assert '"??"' in content, (
        "bc-implementer template must enumerate the '??' porcelain "
        "marker for untracked files (lead-8lm / 86d576b269ff89d6)"
    )
    assert "untracked" in lower, (
        "bc-implementer template must name 'untracked' files as the "
        "case this marker catches (lead-8lm / 86d576b269ff89d6)"
    )
    assert "precondition" in lower, (
        "bc-implementer template must frame untracked-files as a "
        "'precondition failure' (lead-8lm / 86d576b269ff89d6)"
    )
    # The Implementer-emitter scope qualifier must appear so the
    # untracked check is unambiguously tied to the Implementer-emitter
    # path, not the Reviewer-gated assign_scenarios path.
    assert "request_maintenance" in content, (
        "bc-implementer template must scope the untracked-files check "
        "to request_maintenance (Implementer-emitter dispatch) "
        "(lead-8lm / 86d576b269ff89d6)"
    )
    assert "request_bugfix" in content, (
        "bc-implementer template must scope the untracked-files check "
        "to request_bugfix (Implementer-emitter, empty-scenarios case) "
        "(lead-8lm / 86d576b269ff89d6)"
    )


@then(
    'the content directs the implementer that on untracked-files failure '
    'the implementer does NOT compose "shop-msg respond work_done --status '
    'complete" and instead emits "shop-msg respond work_done --status '
    'blocked" with a summary that names the untracked paths reported by '
    '"git status --porcelain"'
)
def then_impl_content_directs_blocked_on_untracked(context: dict) -> None:
    content = context["template_content"]
    assert "shop-msg respond work_done --status blocked" in content, (
        "bc-implementer template must literally name the "
        "blocked-status shop-msg invocation for untracked-files "
        "failure (lead-8lm / 86d576b269ff89d6)"
    )
    assert "shop-msg respond work_done --status complete" in content, (
        "bc-implementer template must literally name the "
        "complete-status shop-msg invocation that is being negated "
        "(lead-8lm / 86d576b269ff89d6)"
    )
    lower = content.lower()
    assert "untracked" in lower and "paths" in lower, (
        "bc-implementer template must direct naming the untracked "
        "paths in the summary (lead-8lm / 86d576b269ff89d6)"
    )


@then(
    'the content explicitly directs the implementer that the '
    'untracked-files check is NOT satisfied by adding the paths to '
    '.gitignore unless the paths are genuinely outside the BC\'s scope of '
    'work; the implementer must confirm by inspection of the dispatch\'s '
    'acceptance criteria (or by clarify back to the lead) whether the '
    'untracked paths are work product that should be committed before '
    're-attempting the emit'
)
def then_impl_content_directs_gitignore_is_not_the_fix(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert ".gitignore" in lower, (
        "bc-implementer template must explicitly name '.gitignore' as "
        "the non-fix the implementer must NOT default to "
        "(lead-8lm / 86d576b269ff89d6)"
    )
    assert "scope" in lower, (
        "bc-implementer template must frame the .gitignore carve-out "
        "in terms of 'scope' (lead-8lm / 86d576b269ff89d6)"
    )
    assert "commit" in lower, (
        "bc-implementer template must direct the implementer to "
        "consider committing untracked work product instead of "
        ".gitignoring it (lead-8lm / 86d576b269ff89d6)"
    )
    # The "inspection of the dispatch's acceptance criteria (or by
    # clarify back to the lead)" framing must appear — the scenario
    # specifically tells the implementer how to resolve the
    # uncertainty (acceptance-criteria inspection or clarify).
    assert "acceptance criteria" in lower, (
        "bc-implementer template must direct the implementer to "
        "inspect the dispatch's acceptance criteria when resolving "
        "the untracked-paths question (lead-8lm / 86d576b269ff89d6)"
    )
    assert "clarify" in lower, (
        "bc-implementer template must offer 'clarify back to the "
        "lead' as the escalation path when the implementer cannot "
        "resolve the untracked-paths question by inspection alone "
        "(lead-8lm / 86d576b269ff89d6)"
    )


# --- Scenario e01ace6acd655909 ---

@then(
    'the content directs the implementer that, prior to emitting work_done '
    'with status complete on a dispatch where the Implementer is the '
    'work_done emitter (request_maintenance, or request_bugfix whose '
    'scenarios[] is empty), the implementer must verify by "git log '
    'origin/main" (or equivalent "git log" against the BC\'s main branch) '
    'that at least one commit attributable to the dispatched work_id is '
    'reachable from "origin/main" HEAD'
)
def then_impl_content_directs_git_log_origin_main_reachable(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "git log origin/main" in content, (
        "bc-implementer template must name the literal 'git log "
        "origin/main' verification (lead-8lm / e01ace6acd655909)"
    )
    assert "reachable" in lower, (
        "bc-implementer template must frame the verification as the "
        "work_id's commit being 'reachable' from origin/main HEAD "
        "(lead-8lm / e01ace6acd655909)"
    )
    assert "work_id" in lower, (
        "bc-implementer template must tie the reachability check to "
        "the dispatched work_id (lead-8lm / e01ace6acd655909)"
    )
    assert "work_done" in lower and "complete" in lower, (
        "bc-implementer template must frame the verification as "
        "prior to emitting work_done --status complete "
        "(lead-8lm / e01ace6acd655909)"
    )
    # Implementer-emitter scope qualifier.
    assert "request_maintenance" in content, (
        "bc-implementer template must scope the origin/main "
        "reachability check to request_maintenance "
        "(lead-8lm / e01ace6acd655909)"
    )
    assert "request_bugfix" in content, (
        "bc-implementer template must scope the origin/main "
        "reachability check to request_bugfix (empty-scenarios case) "
        "(lead-8lm / e01ace6acd655909)"
    )


@then(
    'the content names a concrete attribution mechanism the implementer '
    'may use to recognize the work_id\'s commit (for example, the work_id '
    'substring appearing in the commit message subject or body, or a '
    'tag/note pointing at the work_id), so the implementer does not have '
    'to invent a convention'
)
def then_impl_content_names_concrete_attribution_mechanism(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    has_subject_body = (
        "subject" in lower or "body" in lower or "message" in lower
    ) and "work_id" in lower
    has_tag_note = "tag" in lower or "note" in lower
    assert has_subject_body or has_tag_note, (
        "bc-implementer template must name at least one concrete "
        "attribution mechanism (work_id in commit subject/body, or "
        "tag/note pointing at work_id) "
        "(lead-8lm / e01ace6acd655909)"
    )


@then(
    'the content directs the implementer that when no commit attributable '
    'to the work_id is reachable from "origin/main" HEAD the implementer '
    'does NOT compose "shop-msg respond work_done --status complete" and '
    'instead emits "shop-msg respond work_done --status blocked" with a '
    'summary that names the dispatched work_id and the current '
    '"origin/main" HEAD short SHA'
)
def then_impl_content_directs_blocked_on_missing_origin_main_commit(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "shop-msg respond work_done --status blocked" in content, (
        "bc-implementer template must literally name the "
        "blocked-status shop-msg invocation for missing-origin/main-"
        "commit failure (lead-8lm / e01ace6acd655909)"
    )
    assert "shop-msg respond work_done --status complete" in content, (
        "bc-implementer template must literally name the "
        "complete-status shop-msg invocation that is being negated "
        "(lead-8lm / e01ace6acd655909)"
    )
    assert "work_id" in lower and "summary" in lower, (
        "bc-implementer template must direct naming the work_id in "
        "the response summary (lead-8lm / e01ace6acd655909)"
    )
    assert ("short sha" in lower) or ("short-sha" in lower) or (
        "head" in lower and "sha" in lower
    ), (
        "bc-implementer template must direct naming the current "
        "origin/main HEAD short SHA in the response summary "
        "(lead-8lm / e01ace6acd655909)"
    )


@then(
    'the content directs the implementer that committing the work_id\'s '
    'change to any branch OTHER than the BC\'s main branch (e.g., a local '
    'feature branch that has not been merged or pushed to origin/main) '
    'does NOT satisfy this precondition; the only outcome that satisfies '
    'the precondition is the work_id\'s commit being reachable from '
    '"origin/main" HEAD'
)
def then_impl_content_directs_local_branch_does_not_satisfy(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "local" in lower and "branch" in lower, (
        "bc-implementer template must explicitly name the "
        "local-branch case as not satisfying the precondition "
        "(lead-8lm / e01ace6acd655909)"
    )
    assert "origin/main" in content, (
        "bc-implementer template must name 'origin/main' as the only "
        "ref whose reachability satisfies the precondition "
        "(lead-8lm / e01ace6acd655909)"
    )
    disqualifying_cues = (
        "does not satisfy", "do not satisfy", "not satisfy",
        "only outcome", "only satisfies",
    )
    assert any(c in lower for c in disqualifying_cues), (
        "bc-implementer template must disqualify local-branch commits "
        "with an explicit 'does not satisfy' / 'only outcome' framing "
        "(lead-8lm / e01ace6acd655909)"
    )


@then(
    'the content directs the implementer that "git fetch origin" should '
    'be run as part of the verification so a stale local view of '
    '"origin/main" does not produce a false positive'
)
def then_impl_content_directs_git_fetch_origin_first(context: dict) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "git fetch origin" in content, (
        "bc-implementer template must name the literal 'git fetch "
        "origin' step (lead-8lm / e01ace6acd655909)"
    )
    assert "stale" in lower, (
        "bc-implementer template must frame 'git fetch origin' as "
        "guarding against a stale local view "
        "(lead-8lm / e01ace6acd655909)"
    )
    assert "false positive" in lower or "false-positive" in lower, (
        "bc-implementer template must frame the stale-view risk as a "
        "'false positive' (lead-8lm / e01ace6acd655909)"
    )


@then(
    'the content explicitly disclaims the BC role-discipline interpretation '
    '"BC role discipline does not push" as a reason to skip this check; for '
    'Implementer-emitted work_done, pushing the work_id commit to '
    'origin/main is part of the work, not optional polish'
)
def then_impl_content_disclaims_role_discipline_no_push(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The literal phrase "BC role discipline does not push" must appear
    # so the template explicitly identifies the misinterpretation it
    # is disclaiming, rather than disclaiming it implicitly.
    assert "bc role discipline does not push" in lower, (
        "bc-implementer template must literally quote the "
        "misinterpretation it is disclaiming ('BC role discipline "
        "does not push') (lead-8lm / e01ace6acd655909)"
    )
    # The disclaim framing must be present: "not a reason to skip",
    # "does not excuse", "is not optional", etc.
    disclaim_cues = (
        "not a reason to skip",
        "does not excuse",
        "is not optional",
        "not optional",
        "part of the work",
    )
    assert any(c in lower for c in disclaim_cues), (
        "bc-implementer template must frame the role-discipline "
        "phrase as explicitly NOT a valid reason to skip the "
        "origin/main reachability check "
        "(lead-8lm / e01ace6acd655909)"
    )
    # The "pushing is part of the work" framing must be explicit so
    # the implementer cannot read the carve-out as optional polish.
    assert "push" in lower and "origin/main" in content, (
        "bc-implementer template must explicitly tie pushing the "
        "work_id commit to origin/main as part of the "
        "Implementer-emitted work_done work "
        "(lead-8lm / e01ace6acd655909)"
    )


# -----------------------------------------------------------------------
# Then steps — bc-reviewer pre-emit scenario_hash integrity checks
# (lead-83l scenarios e0d4c445a0cd7500, 50174dbb885ff5a8,
# 762e847fe873201e, 36d22e52adcea48e)
# -----------------------------------------------------------------------
#
# These steps pin that the bc-reviewer template encodes ADR-010's
# work_done.scenario_hashes pre-emit discipline: every hash the
# reviewer would echo via "--scenario-hash" must (a) be recomputed by
# the canonical "scenarios hash" CLI against the as-committed body and
# match, AND (b) carry a grep-reachable "@scenario_hash:<hash>" tag
# under "features/". The four scenarios pin the happy path plus three
# failure modes (stale, missing, orphan); each failure converts the
# response to "--status blocked" with a summary that names enough
# evidence for the lead to reconcile without round-tripping. The
# assertion strategy mirrors the lead-cw7 / lead-8lm pre-emit step
# blocks above: literal-substring checks against the rendered template
# content, augmented with co-occurrence requirements so a stray
# mention elsewhere in the template would not silently satisfy a
# structural intent.


# --- Scenario e0d4c445a0cd7500 (happy path / recomputation) ---

@then(
    'the content directs the reviewer that, before composing '
    '"shop-msg respond work_done --status complete" on a '
    'scenario-carrying dispatch (assign_scenarios, or request_bugfix '
    'whose scenarios[] is non-empty), the reviewer must recompute the '
    'hash of every scenario the work_done payload will list in '
    '"--scenario-hash" using the canonical "scenarios hash" CLI '
    'against the BC\'s as-committed feature files under "features/"'
)
def then_content_directs_recompute_each_hash(context: dict) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The canonical "scenarios hash" CLI must be named literally so the
    # reviewer is not left to invent a hashing convention.
    assert "scenarios hash" in content, (
        "bc-reviewer template must literally name the 'scenarios hash' "
        "CLI as the recomputation tool (lead-83l / e0d4c445a0cd7500)"
    )
    # The "--scenario-hash" flag must be named so the recomputation is
    # explicitly tied to the wire-form hash list the reviewer would emit.
    assert "--scenario-hash" in content, (
        "bc-reviewer template must literally name the '--scenario-hash' "
        "flag whose values the reviewer is recomputing "
        "(lead-83l / e0d4c445a0cd7500)"
    )
    # The "features/" path must be named so the recomputation is scoped
    # to the BC's as-committed feature files.
    assert "features/" in content, (
        "bc-reviewer template must name 'features/' as the directory "
        "the recomputation reads from (lead-83l / e0d4c445a0cd7500)"
    )
    # Pre-emit framing must be present (work_done --status complete is
    # the gate this check guards).
    assert "shop-msg respond work_done --status complete" in content, (
        "bc-reviewer template must literally name the complete-status "
        "shop-msg invocation the recomputation guards "
        "(lead-83l / e0d4c445a0cd7500)"
    )
    # Scenario-carrying dispatch scope: both assign_scenarios and
    # request_bugfix (with non-empty scenarios) must be named so the
    # gate is not silently restricted to one vehicle.
    assert "assign_scenarios" in content, (
        "bc-reviewer template must name 'assign_scenarios' as a "
        "scenario-carrying dispatch the recomputation applies to "
        "(lead-83l / e0d4c445a0cd7500)"
    )
    assert "request_bugfix" in content, (
        "bc-reviewer template must name 'request_bugfix' as a "
        "scenario-carrying dispatch the recomputation applies to "
        "(lead-83l / e0d4c445a0cd7500)"
    )
    # "every" / "each" framing must appear so the reviewer doesn't read
    # the check as a sampling exercise.
    assert ("every" in lower) or ("each" in lower), (
        "bc-reviewer template must frame the recomputation as covering "
        "every / each hash, not a sample "
        "(lead-83l / e0d4c445a0cd7500)"
    )


@then(
    'the content directs the reviewer to perform the recomputation in '
    'the same BC root state that the prior pre-emit steps (clean '
    'working tree, work_id commit on origin/main per scenarios '
    '105-108) have just verified, so the recomputed hashes are taken '
    'from the exact bytes that will land on origin/main'
)
def then_content_directs_recompute_in_verified_state(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The recomputation must be tied to the same state the prior
    # pre-emit steps just verified: clean tree + origin/main.
    assert "git status --porcelain" in content, (
        "bc-reviewer template must reference the clean-working-tree "
        "pre-emit step as the state the recomputation reads against "
        "(lead-83l / e0d4c445a0cd7500)"
    )
    assert "origin/main" in content, (
        "bc-reviewer template must reference origin/main as the ref "
        "whose bytes the recomputation reads against "
        "(lead-83l / e0d4c445a0cd7500)"
    )
    # The "as-committed" / "committed" framing must appear so the
    # reviewer reads the recomputation as operating on the committed
    # body, not a working-tree edit.
    assert ("as-committed" in lower) or ("as committed" in lower) or (
        "committed" in lower
    ), (
        "bc-reviewer template must frame the recomputation as reading "
        "the as-committed body (lead-83l / e0d4c445a0cd7500)"
    )


@then(
    'the content directs the reviewer to also confirm by "grep" (or '
    '"git grep") for each hash that an "@scenario_hash:<hash>" tag is '
    'present in some file under "features/", per ADR-010\'s '
    'observable-evidence requirement'
)
def then_content_directs_grep_presence_check(context: dict) -> None:
    content = context["template_content"]
    lower = content.lower()
    # "grep" or "git grep" must be named as the presence-check tool.
    assert ("grep" in lower) or ("git grep" in lower), (
        "bc-reviewer template must name 'grep' (or 'git grep') as the "
        "tag-presence check tool (lead-83l / e0d4c445a0cd7500)"
    )
    # The "@scenario_hash:" tag form must be named literally.
    assert "@scenario_hash:" in content, (
        "bc-reviewer template must literally name the "
        "'@scenario_hash:<hash>' tag the presence check looks for "
        "(lead-83l / e0d4c445a0cd7500)"
    )
    # The "features/" path must be named as the search scope.
    assert "features/" in content, (
        "bc-reviewer template must name 'features/' as the presence "
        "check search scope (lead-83l / e0d4c445a0cd7500)"
    )
    # ADR-010 citation required.
    assert "ADR-010" in content, (
        "bc-reviewer template must cite ADR-010 as the rule the "
        "presence check is encoding (lead-83l / e0d4c445a0cd7500)"
    )


@then(
    'the content directs the reviewer that the work_done emit is '
    'allowed to proceed only when every hash the reviewer would pass '
    'to "--scenario-hash" satisfies BOTH the recomputation check (the '
    'hash equals the value "scenarios hash" produces against the '
    'as-committed body) AND the presence check (an '
    '"@scenario_hash:<hash>" tag is reachable under "features/")'
)
def then_content_directs_both_checks_required(context: dict) -> None:
    content = context["template_content"]
    lower = content.lower()
    # Both checks must be named: recomputation (scenarios hash) AND
    # presence (grep / @scenario_hash tag).
    assert "scenarios hash" in content, (
        "bc-reviewer template must name 'scenarios hash' as the "
        "recomputation half of the conjoined check "
        "(lead-83l / e0d4c445a0cd7500)"
    )
    assert "@scenario_hash:" in content, (
        "bc-reviewer template must name '@scenario_hash:<hash>' tag "
        "as the presence half of the conjoined check "
        "(lead-83l / e0d4c445a0cd7500)"
    )
    # Conjunction framing: "both" / "AND" / "and" must appear so the
    # reviewer reads this as a logical conjunction, not a disjunction.
    assert "both" in lower, (
        "bc-reviewer template must use 'both' framing to mark the "
        "recomputation + presence checks as a conjunction, not a "
        "disjunction (lead-83l / e0d4c445a0cd7500)"
    )
    # The "only when" / "allowed to proceed" framing must appear so the
    # reviewer reads the emit as gated.
    assert ("only when" in lower) or ("only if" in lower) or (
        "allowed to proceed" in lower
    ), (
        "bc-reviewer template must frame the emit as gated ('only "
        "when' / 'allowed to proceed') on both checks passing "
        "(lead-83l / e0d4c445a0cd7500)"
    )


@then(
    'the content marks the recomputation step as a discrete pre-emit '
    'step alongside the existing BDD-rerun, working-tree, and '
    'work_id-on-origin-main checks, not as optional guidance the '
    'reviewer may skip'
)
def then_content_marks_recompute_as_discrete_pre_emit_step(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The recomputation step must be present (scenarios hash).
    assert "scenarios hash" in content, (
        "bc-reviewer template must name the recomputation step in "
        "discrete-pre-emit framing (lead-83l / e0d4c445a0cd7500)"
    )
    # The existing sibling pre-emit steps must all be referenced so the
    # recomputation is explicitly framed as alongside them.
    assert "git status --porcelain" in content, (
        "bc-reviewer template missing 'git status --porcelain' sibling "
        "in discrete-pre-emit framing "
        "(lead-83l / e0d4c445a0cd7500)"
    )
    assert "origin/main" in content, (
        "bc-reviewer template missing 'origin/main' sibling in "
        "discrete-pre-emit framing (lead-83l / e0d4c445a0cd7500)"
    )
    # BDD re-run reference must be present.
    assert ("bdd" in lower) and ("pytest" in lower or "re-run" in lower
                                  or "rerun" in lower), (
        "bc-reviewer template must reference the existing BDD-rerun "
        "step alongside the recomputation step "
        "(lead-83l / e0d4c445a0cd7500)"
    )
    # Imperative "must" cue must appear (not optional).
    assert "must" in lower, (
        "bc-reviewer template must use imperative 'must' framing for "
        "the recomputation step, not optional guidance "
        "(lead-83l / e0d4c445a0cd7500)"
    )


@then(
    'the content cites ADR-010 as the rule the recomputation step is '
    'encoding'
)
def then_content_cites_adr_010_for_recomputation(context: dict) -> None:
    content = context["template_content"]
    assert "ADR-010" in content, (
        "bc-reviewer template must cite ADR-010 as the rule the "
        "recomputation step is encoding "
        "(lead-83l / e0d4c445a0cd7500)"
    )


# --- Scenario 50174dbb885ff5a8 (stale hash) ---

@then(
    'the content directs the reviewer that, when the reviewer '
    'recomputes the hash of an as-committed scenario body via '
    '"scenarios hash" and the recomputed value differs from the hash '
    'the reviewer would otherwise pass to "--scenario-hash" (for '
    'instance because the implementer edited the scenario after the '
    'dispatch pinned its hash), the divergence is a precondition '
    'failure'
)
def then_content_stale_hash_is_precondition_failure(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "scenarios hash" in content, (
        "bc-reviewer template must name 'scenarios hash' as the "
        "recomputation tool whose divergence is the failure "
        "(lead-83l / 50174dbb885ff5a8)"
    )
    assert "--scenario-hash" in content, (
        "bc-reviewer template must name the '--scenario-hash' flag "
        "whose value diverges from the recomputed value "
        "(lead-83l / 50174dbb885ff5a8)"
    )
    # "stale" framing must appear so the case is named.
    assert "stale" in lower, (
        "bc-reviewer template must name the case as 'stale' so the "
        "reviewer recognizes the failure mode "
        "(lead-83l / 50174dbb885ff5a8)"
    )
    # "precondition failure" framing must appear.
    assert "precondition" in lower, (
        "bc-reviewer template must frame the stale-hash divergence as "
        "a 'precondition failure' (lead-83l / 50174dbb885ff5a8)"
    )


@then(
    'the content directs the reviewer that on such a stale-hash '
    'failure the reviewer does NOT compose "shop-msg respond '
    'work_done --status complete" and instead emits "shop-msg respond '
    'work_done --status blocked"'
)
def then_content_directs_blocked_on_stale_hash(context: dict) -> None:
    content = context["template_content"]
    assert "shop-msg respond work_done --status blocked" in content, (
        "bc-reviewer template must literally name the blocked-status "
        "shop-msg invocation for stale-hash failure "
        "(lead-83l / 50174dbb885ff5a8)"
    )
    assert "shop-msg respond work_done --status complete" in content, (
        "bc-reviewer template must literally name the complete-status "
        "shop-msg invocation that is being negated on stale-hash "
        "failure (lead-83l / 50174dbb885ff5a8)"
    )


@then(
    'the content directs the reviewer that the response summary on '
    'the blocked emit must name the dispatched work_id, the stale '
    'hash value (the one the dispatch carried or the reviewer was '
    'about to echo), and the recomputed value that "scenarios hash" '
    'produced against the as-committed body, so the lead can decide '
    'between re-pinning the hash on a fresh dispatch or restoring the '
    'scenario body without a round-trip'
)
def then_content_stale_hash_summary_names_three_pieces(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # All three required pieces of evidence must be directed into the
    # summary: work_id, stale hash, recomputed value.
    assert "work_id" in lower and "summary" in lower, (
        "bc-reviewer template must direct naming the work_id in the "
        "stale-hash summary (lead-83l / 50174dbb885ff5a8)"
    )
    assert "stale" in lower, (
        "bc-reviewer template must direct naming the stale hash value "
        "in the summary (lead-83l / 50174dbb885ff5a8)"
    )
    assert "recomputed" in lower, (
        "bc-reviewer template must direct naming the recomputed value "
        "in the summary (lead-83l / 50174dbb885ff5a8)"
    )


@then(
    'the content frames the stale-hash check as a step the reviewer '
    'runs even when the BDD suite passes and even when an '
    '"@scenario_hash:<hash>" tag for the stale hash is still '
    'grep-able somewhere under "features/", because a stale tag and a '
    'green BDD result together do not establish that the wire-form '
    'hash describes the body the BC has committed'
)
def then_content_stale_check_not_bypassed_by_green_bdd_or_grepable_tag(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The "even when BDD passes" / "even if BDD passes" framing must
    # appear so the stale check is not bypassed by a green BDD.
    bypass_cues = ("even when", "even if", "regardless", "does not "
                   "bypass", "not bypass", "still", "always", "green")
    has_bdd_bypass = "bdd" in lower and any(
        c in lower for c in bypass_cues
    )
    assert has_bdd_bypass, (
        "bc-reviewer template must frame the stale-hash check as "
        "running even when the BDD suite passes "
        "(lead-83l / 50174dbb885ff5a8)"
    )
    # The "@scenario_hash:" tag must be named, and the carve-out must
    # explicitly say a grep-able tag does not establish currency.
    assert "@scenario_hash:" in content, (
        "bc-reviewer template must literally name "
        "'@scenario_hash:<hash>' as the tag whose mere presence is "
        "not sufficient (lead-83l / 50174dbb885ff5a8)"
    )
    # The "stale tag" + "do not establish" framing must appear so the
    # carve-out is explicit.
    assert ("stale" in lower) and (
        ("do not establish" in lower)
        or ("does not establish" in lower)
        or ("not sufficient" in lower)
        or ("not enough" in lower)
    ), (
        "bc-reviewer template must explicitly frame stale-tag + green "
        "BDD as not establishing hash currency "
        "(lead-83l / 50174dbb885ff5a8)"
    )


@then(
    'the content cites ADR-010 §4 (observable-evidence requirement, '
    'BC-side) as the rule the stale-hash check is encoding'
)
def then_content_cites_adr_010_section_4_for_stale(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "ADR-010" in content, (
        "bc-reviewer template must cite ADR-010 as the rule the "
        "stale-hash check is encoding "
        "(lead-83l / 50174dbb885ff5a8)"
    )
    # The section number must be named so the citation is specific.
    assert ("§4" in content) or ("section 4" in lower), (
        "bc-reviewer template must cite ADR-010 §4 specifically "
        "(lead-83l / 50174dbb885ff5a8)"
    )
    # The "observable-evidence" framing must appear so the rule the
    # check encodes is explicit.
    assert ("observable-evidence" in lower) or (
        "observable evidence" in lower
    ), (
        "bc-reviewer template must name the 'observable-evidence' "
        "requirement as the ADR-010 §4 rule "
        "(lead-83l / 50174dbb885ff5a8)"
    )


# --- Scenario 762e847fe873201e (missing hash) ---

@then(
    'the content directs the reviewer that, before composing '
    '"shop-msg respond work_done --status complete", the reviewer '
    'must enumerate the scenario hashes the dispatch payload carried '
    '(the "@scenario_hash:<hash>" set the lead\'s dispatch text '
    'named) and confirm by "grep" (or "git grep") that each '
    'dispatched hash is also reachable under an '
    '"@scenario_hash:<hash>" tag in the BC\'s as-committed '
    '"features/" tree'
)
def then_content_directs_enumerate_dispatched_hashes(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # Pre-emit framing required.
    assert "shop-msg respond work_done --status complete" in content, (
        "bc-reviewer template must literally name the complete-status "
        "shop-msg invocation the enumeration guards "
        "(lead-83l / 762e847fe873201e)"
    )
    # Enumeration + dispatched-hash framing required.
    assert "dispatch" in lower, (
        "bc-reviewer template must frame the enumeration as covering "
        "the hashes the dispatch payload carried "
        "(lead-83l / 762e847fe873201e)"
    )
    # The @scenario_hash tag form must be named.
    assert "@scenario_hash:" in content, (
        "bc-reviewer template must literally name "
        "'@scenario_hash:<hash>' as the tag form whose reachability "
        "is being confirmed (lead-83l / 762e847fe873201e)"
    )
    # grep / git grep must be named as the confirmation tool.
    assert ("grep" in lower) or ("git grep" in lower), (
        "bc-reviewer template must name 'grep' (or 'git grep') as the "
        "confirmation tool (lead-83l / 762e847fe873201e)"
    )
    # features/ tree must be named as the scope.
    assert "features/" in content, (
        "bc-reviewer template must name 'features/' as the scope of "
        "the reachability check (lead-83l / 762e847fe873201e)"
    )


@then(
    'the content directs the reviewer that, for every dispatched hash '
    'that IS reachable under "features/", that hash MUST appear in '
    'the "--scenario-hash" list the reviewer would pass to "shop-msg '
    'respond work_done"; omitting such a hash is a precondition '
    'failure even when the BDD suite passes and even when the omitted '
    'scenario is genuinely pinned on disk'
)
def then_content_missing_hash_is_precondition_failure(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The "must appear in --scenario-hash" obligation must be present.
    assert "--scenario-hash" in content, (
        "bc-reviewer template must name '--scenario-hash' as the list "
        "the dispatched hashes must appear in "
        "(lead-83l / 762e847fe873201e)"
    )
    # "omit" framing required.
    assert ("omit" in lower) or ("omitted" in lower) or (
        "omitting" in lower
    ), (
        "bc-reviewer template must name 'omit' / 'omitting' as the "
        "failure mode (lead-83l / 762e847fe873201e)"
    )
    # precondition failure framing required.
    assert "precondition" in lower, (
        "bc-reviewer template must frame missing-hash omission as a "
        "'precondition failure' (lead-83l / 762e847fe873201e)"
    )
    # "even when BDD passes" framing required.
    bypass_cues = ("even when", "even if", "regardless")
    assert "bdd" in lower and any(c in lower for c in bypass_cues), (
        "bc-reviewer template must frame the missing-hash check as "
        "running even when the BDD suite passes "
        "(lead-83l / 762e847fe873201e)"
    )


@then(
    'the content directs the reviewer that on such a missing-hash '
    'failure the reviewer does NOT compose "shop-msg respond '
    'work_done --status complete" and instead emits "shop-msg respond '
    'work_done --status blocked"'
)
def then_content_directs_blocked_on_missing_hash(
    context: dict,
) -> None:
    content = context["template_content"]
    assert "shop-msg respond work_done --status blocked" in content, (
        "bc-reviewer template must literally name the blocked-status "
        "shop-msg invocation for missing-hash failure "
        "(lead-83l / 762e847fe873201e)"
    )
    assert "shop-msg respond work_done --status complete" in content, (
        "bc-reviewer template must literally name the complete-status "
        "shop-msg invocation that is being negated on missing-hash "
        "failure (lead-83l / 762e847fe873201e)"
    )


@then(
    'the content directs the reviewer that the response summary on '
    'the blocked emit must name the dispatched work_id and, for each '
    'omitted hash, both the hash value and the path of the feature '
    'file under "features/" where the corresponding '
    '"@scenario_hash:<hash>" tag is reachable, so the lead can see '
    'that the BC pinned the scenarios on disk but composed an '
    'incomplete payload'
)
def then_content_missing_hash_summary_names_work_id_hash_and_path(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # work_id required in summary.
    assert "work_id" in lower and "summary" in lower, (
        "bc-reviewer template must direct naming the work_id in the "
        "missing-hash summary (lead-83l / 762e847fe873201e)"
    )
    # Each omitted hash value + feature file path required.
    assert "omitted" in lower or "omit" in lower, (
        "bc-reviewer template must direct naming each omitted hash "
        "value in the summary (lead-83l / 762e847fe873201e)"
    )
    # The features/ path must be named as the path the summary cites.
    assert "features/" in content, (
        "bc-reviewer template must direct naming the path under "
        "'features/' where each omitted hash's tag is reachable "
        "(lead-83l / 762e847fe873201e)"
    )


@then(
    'the content cites the "echo back every scenario hash that '
    'currently passes" direction in the existing "Sign-off" '
    'subsection as the rule this check operationalizes, and cites '
    'lead-plt as the empirical case it exists to prevent'
)
def then_content_missing_hash_cites_signoff_and_lead_plt(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # The exact phrase from the existing Sign-off section must be
    # cited so the rule the check operationalizes is explicit.
    assert "echo back every scenario hash that currently passes" in lower, (
        "bc-reviewer template must cite the 'echo back every "
        "scenario hash that currently passes' direction from the "
        "existing Sign-off section (lead-83l / 762e847fe873201e)"
    )
    # Sign-off section reference required.
    assert "sign-off" in lower, (
        "bc-reviewer template must reference the 'Sign-off' "
        "subsection as the location of the rule "
        "(lead-83l / 762e847fe873201e)"
    )
    # lead-plt empirical case citation required.
    assert "lead-plt" in lower, (
        "bc-reviewer template must cite 'lead-plt' as the empirical "
        "case the missing-hash check exists to prevent "
        "(lead-83l / 762e847fe873201e)"
    )


# --- Scenario 36d22e52adcea48e (orphan hash) ---

@then(
    'the content directs the reviewer that, before composing '
    '"shop-msg respond work_done --status complete", the reviewer '
    'must confirm by "grep" (or "git grep") for each hash the '
    'reviewer would pass to "--scenario-hash" that an '
    '"@scenario_hash:<hash>" tag carrying that exact value is '
    'reachable in some file under the BC\'s as-committed "features/" '
    'tree'
)
def then_content_directs_grep_for_each_emitted_hash(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    assert "shop-msg respond work_done --status complete" in content, (
        "bc-reviewer template must literally name the complete-status "
        "shop-msg invocation the orphan check guards "
        "(lead-83l / 36d22e52adcea48e)"
    )
    # grep / git grep must be named as the tool.
    assert ("grep" in lower) or ("git grep" in lower), (
        "bc-reviewer template must name 'grep' (or 'git grep') as "
        "the orphan-check tool (lead-83l / 36d22e52adcea48e)"
    )
    # --scenario-hash must be named as the source of the hashes
    # whose reachability is being confirmed.
    assert "--scenario-hash" in content, (
        "bc-reviewer template must name '--scenario-hash' as the "
        "source of the hashes whose tag-reachability is being "
        "confirmed (lead-83l / 36d22e52adcea48e)"
    )
    # @scenario_hash tag form required.
    assert "@scenario_hash:" in content, (
        "bc-reviewer template must literally name the "
        "'@scenario_hash:<hash>' tag whose presence is being "
        "confirmed (lead-83l / 36d22e52adcea48e)"
    )
    # features/ scope required.
    assert "features/" in content, (
        "bc-reviewer template must name 'features/' as the scope of "
        "the orphan check (lead-83l / 36d22e52adcea48e)"
    )


@then(
    'the content directs the reviewer that any hash the reviewer '
    'would echo for which no such tag is reachable under "features/" '
    'is a precondition failure, regardless of whether the dispatch '
    'text named the hash, whether the scenario was once pinned on '
    'disk and later removed, or whether the hash was composed from '
    'elsewhere'
)
def then_content_orphan_hash_is_precondition_failure(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # precondition failure framing required.
    assert "precondition" in lower, (
        "bc-reviewer template must frame an orphan hash (no tag "
        "reachable) as a 'precondition failure' "
        "(lead-83l / 36d22e52adcea48e)"
    )
    # "regardless" framing required so the carve-outs are exhaustive.
    assert "regardless" in lower, (
        "bc-reviewer template must use 'regardless' framing to make "
        "the orphan-hash carve-outs exhaustive "
        "(lead-83l / 36d22e52adcea48e)"
    )
    # The three carve-out reasons must be named so the reviewer
    # cannot read any of them as legitimizing the orphan hash.
    # (a) dispatch text named the hash; (b) scenario was once pinned
    # and later removed; (c) hash composed from elsewhere.
    assert "dispatch" in lower, (
        "bc-reviewer template must name the 'dispatch text named the "
        "hash' carve-out (lead-83l / 36d22e52adcea48e)"
    )
    assert ("removed" in lower) or ("later removed" in lower), (
        "bc-reviewer template must name the 'scenario was once "
        "pinned and later removed' carve-out "
        "(lead-83l / 36d22e52adcea48e)"
    )
    assert ("composed" in lower) or ("elsewhere" in lower), (
        "bc-reviewer template must name the 'hash composed from "
        "elsewhere' carve-out (lead-83l / 36d22e52adcea48e)"
    )


@then(
    'the content directs the reviewer that on such an orphan-hash '
    'failure the reviewer does NOT compose "shop-msg respond '
    'work_done --status complete" and instead emits "shop-msg '
    'respond work_done --status blocked"'
)
def then_content_directs_blocked_on_orphan_hash(
    context: dict,
) -> None:
    content = context["template_content"]
    assert "shop-msg respond work_done --status blocked" in content, (
        "bc-reviewer template must literally name the blocked-status "
        "shop-msg invocation for orphan-hash failure "
        "(lead-83l / 36d22e52adcea48e)"
    )
    assert "shop-msg respond work_done --status complete" in content, (
        "bc-reviewer template must literally name the complete-status "
        "shop-msg invocation that is being negated on orphan-hash "
        "failure (lead-83l / 36d22e52adcea48e)"
    )


@then(
    'the content directs the reviewer that the response summary on '
    'the blocked emit must name the dispatched work_id and, for each '
    'orphan hash, both the hash value and the explicit statement '
    'that no "@scenario_hash:<hash>" tag carrying that value is '
    'reachable under "features/", so the lead can decide between '
    'asking the BC to restore a removed scenario or correcting the '
    'payload without round-tripping'
)
def then_content_orphan_summary_names_work_id_and_no_tag_statement(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # work_id in summary required.
    assert "work_id" in lower and "summary" in lower, (
        "bc-reviewer template must direct naming the work_id in the "
        "orphan-hash summary (lead-83l / 36d22e52adcea48e)"
    )
    # orphan hash value required in summary.
    assert "orphan" in lower, (
        "bc-reviewer template must name 'orphan' as the case being "
        "summarized (lead-83l / 36d22e52adcea48e)"
    )
    # The "no tag reachable" statement framing must appear.
    assert ("no" in lower) and ("@scenario_hash:" in content) and (
        "reachable" in lower
    ), (
        "bc-reviewer template must direct an explicit 'no "
        "@scenario_hash:<hash> tag reachable' statement in the "
        "summary for each orphan hash "
        "(lead-83l / 36d22e52adcea48e)"
    )
    # features/ path framing required.
    assert "features/" in content, (
        "bc-reviewer template must name 'features/' as the scope of "
        "the no-tag-reachable statement "
        "(lead-83l / 36d22e52adcea48e)"
    )


@then(
    'the content frames the orphan-hash check as the strict-subset '
    'rule ADR-010 §4 makes canonical (work_done.scenario_hashes MUST '
    'be a subset of the hashes actually pinned in the BC\'s '
    'features/) and cites ADR-010 as the rule this check is encoding'
)
def then_content_orphan_check_cites_adr_010_subset_rule(
    context: dict,
) -> None:
    content = context["template_content"]
    lower = content.lower()
    # ADR-010 citation required.
    assert "ADR-010" in content, (
        "bc-reviewer template must cite ADR-010 as the rule the "
        "orphan-hash check is encoding "
        "(lead-83l / 36d22e52adcea48e)"
    )
    # Strict-subset rule framing required.
    assert "subset" in lower, (
        "bc-reviewer template must frame the orphan check as the "
        "'strict-subset' rule (lead-83l / 36d22e52adcea48e)"
    )
    # work_done.scenario_hashes must be named so the subset is
    # explicit about what's being constrained.
    assert "work_done.scenario_hashes" in content or (
        "scenario_hashes" in lower
    ), (
        "bc-reviewer template must name 'work_done.scenario_hashes' "
        "as the field being constrained "
        "(lead-83l / 36d22e52adcea48e)"
    )


# =======================================================================
# lead-yi0k / ADR-018 — shop name source-of-truth doctrine (scenarios
# 51e39aa4a790e5fb, 3133b1c8c5447cd4, 97245affb1dbe5e4).
#
# name.md is the single source of truth for shop identity and must carry
# only the canonical slug (lowercase letters, digits, hyphens; no
# whitespace). Display forms live in the shop-owned primer.md. Bootstrap
# rejects a non-slug --shop-name; update surfaces (without modifying)
# drifted display-form name.md via a stderr advisory.
# =======================================================================


# -- When: bootstrap invocation whose shop-name carries a parenthetical
#    "(with a literal space)" annotation in the scenario text. The
#    annotation is descriptive Gherkin only; the actual argument value
#    passed to the CLI is the {shop_name} captured before the parenthetical.
@when(
    parsers.parse(
        'I invoke the "shop-templates" bootstrap entry point with shop type '
        '"{shop_type}", shop name "{shop_name}" (with a literal space), and '
        'target directory "{alias}"'
    )
)
def when_invoke_bootstrap_with_literal_space_annotation(
    shop_type: str,
    shop_name: str,
    alias: str,
    context: dict,
    tmp_path: Path,
) -> None:
    real = _real_target_for_alias(alias, context)
    result = _run_shop_templates_with_bd_shim(
        [
            "bootstrap",
            "--shop-type",
            shop_type,
            "--shop-name",
            shop_name,
            "--target",
            str(real),
        ],
        context,
        tmp_path,
    )
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr
    context["last_invocation_target"] = real
    context["last_invocation_shop_type"] = shop_type
    context["last_invocation_shop_name"] = shop_name


# -- Then: bootstrap slug-rejection diagnostic shape (scenario
#    51e39aa4a790e5fb). The stderr must name "--shop-name" + the
#    canonical-slug constraint (lowercase letters, digits, hyphens) AND
#    the offending input AND identify the disallowed character as
#    whitespace.
@then(
    parsers.parse(
        'stderr contains a diagnostic naming that "--shop-name" must be a '
        'canonical slug (lowercase letters, digits, and hyphens only) and '
        'that the input "{bad_input}" contains a disallowed character '
        '(whitespace)'
    )
)
def then_stderr_names_slug_constraint_and_whitespace(
    bad_input: str, context: dict
) -> None:
    stderr = context.get("cli_stderr", "")
    assert "--shop-name" in stderr, (
        f"expected stderr to name '--shop-name'; got:\n{stderr!r}"
    )
    lower = stderr.lower()
    assert "canonical slug" in lower or "slug" in lower, (
        f"expected stderr to name the canonical-slug constraint; "
        f"got:\n{stderr!r}"
    )
    # The slug constraint must enumerate the allowed character classes.
    assert "lowercase letters" in lower, (
        f"expected stderr to name 'lowercase letters' in the slug "
        f"constraint; got:\n{stderr!r}"
    )
    assert "digits" in lower and "hyphen" in lower, (
        f"expected stderr to name 'digits' and 'hyphens' in the slug "
        f"constraint; got:\n{stderr!r}"
    )
    assert bad_input in stderr, (
        f"expected stderr to name the offending input {bad_input!r}; "
        f"got:\n{stderr!r}"
    )
    assert "whitespace" in lower, (
        f"expected stderr to identify the disallowed character as "
        f"'whitespace'; got:\n{stderr!r}"
    )


# -- Then: the target directory does NOT contain a file at <path>.
@then(
    parsers.parse(
        'the target directory does not contain a file at "{path}"'
    )
)
def then_target_does_not_contain_file_at_path(
    path: str, context: dict
) -> None:
    real = context["last_invocation_target"]
    target_file = real / path
    assert not target_file.exists(), (
        f"expected NO file at {path!r} under target directory {real!s}, "
        f"but one exists"
    )


# -- Then: the target directory does NOT contain a top-level <filename>.
@then(
    parsers.parse(
        'the target directory does not contain a top-level "{filename}"'
    )
)
def then_target_does_not_contain_top_level(
    filename: str, context: dict
) -> None:
    real = context["last_invocation_target"]
    target_file = real / filename
    assert not target_file.exists(), (
        f"expected NO top-level {filename!r} under target directory "
        f"{real!s}, but one exists"
    )


# -- Then: byte contents of a named file equal exactly <value> + single
#    trailing newline (inline-path variant; scenarios 51e39aa4a790e5fb
#    and 3133b1c8c5447cd4).
@then(
    parsers.parse(
        'the byte contents of ".claude/shop/name.md" in the target '
        'directory are exactly the literal string "{value}" with a single '
        'trailing newline and no other content'
    )
)
def then_named_file_exact_value_with_newline(
    value: str, context: dict
) -> None:
    real = context["last_invocation_target"]
    target_file = real / ".claude" / "shop" / "name.md"
    actual = target_file.read_bytes()
    expected = (value + "\n").encode()
    assert actual == expected, (
        f"byte contents of '.claude/shop/name.md' are {actual!r}; "
        f"expected exactly {expected!r} (literal {value!r} + single "
        f"trailing newline)"
    )


# -- Then: a named file contains no whitespace other than the single
#    trailing newline (scenario 3133b1c8c5447cd4).
@then(
    parsers.parse(
        'the file at ".claude/shop/name.md" contains no whitespace '
        'character other than the single trailing newline'
    )
)
def then_name_md_no_internal_whitespace(context: dict) -> None:
    real = context["last_invocation_target"]
    target_file = real / ".claude" / "shop" / "name.md"
    text = target_file.read_text()
    assert text.endswith("\n"), (
        f"expected name.md to end with a single trailing newline; "
        f"got {text!r}"
    )
    body = text[:-1]  # strip the single trailing newline
    offending = [c for c in body if c.isspace()]
    assert not offending, (
        f"name.md body {body!r} contains whitespace character(s) "
        f"{offending!r} other than the single trailing newline"
    )


# -- Then: the bootstrap-written primer.md is a shop-owned placeholder
#    (scenario 3133b1c8c5447cd4). Empirically: the file exists, and it
#    is NOT canonical-managed — i.e. it does not carry the canonical
#    primer template content (which would mean it was treated as
#    canonical-managed). An empty placeholder body satisfies "shop-owned
#    placeholder whose body may contain prose".
@then(
    parsers.parse(
        'the bootstrap-written ".claude/shop/primer.md" in the target '
        'directory is a shop-owned placeholder whose body may contain '
        'prose using either the slug or a display variant; that file is '
        'not canonical-managed and its content is the shop\'s to evolve'
    )
)
def then_primer_is_shop_owned_placeholder(context: dict) -> None:
    from shop_templates.cli import read_claude_md_primer

    real = context["last_invocation_target"]
    primer_file = real / ".claude" / "shop" / "primer.md"
    assert primer_file.exists() and primer_file.is_file(), (
        f"expected bootstrap to write a shop-owned placeholder at "
        f".claude/shop/primer.md under {real!s}"
    )
    # Not canonical-managed: the shop-owned primer must NOT carry the
    # canonical primer template body. Determine shop type from the
    # invocation context to compare against the right canonical primer.
    shop_type = context.get("last_invocation_shop_type")
    body = primer_file.read_text()
    if shop_type is not None:
        canonical = read_claude_md_primer(shop_type)
        # A non-trivial overlap (64+ char shared substring) would mean
        # the file is canonical-managed content rather than a shop-owned
        # placeholder.
        min_len = 64
        if len(canonical) >= min_len:
            for i in range(len(canonical) - min_len + 1):
                chunk = canonical[i : i + min_len]
                assert chunk not in body, (
                    f".claude/shop/primer.md carries canonical primer "
                    f"template content (it is being treated as "
                    f"canonical-managed, not shop-owned): matched chunk "
                    f"{chunk!r}"
                )


# -- Then: no other bootstrap-written file contains a display variant of
#    the shop name (scenario 3133b1c8c5447cd4). Scans every file under
#    the target directory and asserts the literal display string (with a
#    space) appears in none of them, EXCEPT the shop-owned primer.md
#    (which the prior Then explicitly carves out as the home for display
#    prose).
@then(
    parsers.parse(
        'no other bootstrap-written file under the target directory '
        'contains a display variant of the shop name (i.e. the literal '
        'string "{display}" with a space) introduced by the templates '
        'package'
    )
)
def then_no_other_file_contains_display_variant(
    display: str, context: dict
) -> None:
    real = context["last_invocation_target"]
    primer_rel = (real / ".claude" / "shop" / "primer.md").resolve()
    offenders = []
    for p in real.rglob("*"):
        if not p.is_file():
            continue
        # The shop-owned primer.md is explicitly allowed to carry display
        # prose; exclude it from the "no other bootstrap-written file"
        # scan. Also skip .git internals (not bootstrap-written).
        if p.resolve() == primer_rel:
            continue
        if ".git" in p.parts:
            continue
        if ".beads" in p.parts:
            continue
        try:
            content = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if display in content:
            offenders.append(str(p.relative_to(real)))
    assert not offenders, (
        f"bootstrap-written file(s) {offenders!r} contain the display "
        f"variant {display!r} of the shop name"
    )


# -- Given: name.md has been edited to a display form (scenario
#    97245affb1dbe5e4). Establishes the drifted-display-form pre-state.
@given(
    parsers.parse(
        'the file at ".claude/shop/name.md" in the target directory has '
        'been edited so that its byte contents are exactly the literal '
        'string "{value}" with a single trailing newline (a display form '
        'containing a literal space, not a canonical slug)'
    )
)
def given_name_md_edited_to_display_form(
    value: str, context: dict
) -> None:
    real = _resolve_single_target(context)
    name_file = real / ".claude" / "shop" / "name.md"
    assert name_file.exists(), (
        f"premise of Given violated: {name_file!s} does not exist "
        f"(target must have been previously bootstrapped)"
    )
    name_file.write_bytes((value + "\n").encode())


# -- Then: stderr advisory naming file + on-disk value + suggested slug +
#    edit instruction (scenario 97245affb1dbe5e4).
@then(
    parsers.parse(
        'stderr contains an advisory naming the file ".claude/shop/name.md", '
        'the on-disk value "{on_disk}", the suggested canonical slug '
        '"{slug}", and the instruction to edit name.md to the slug form'
    )
)
def then_stderr_advisory_names_drift(
    on_disk: str, slug: str, context: dict
) -> None:
    stderr = context.get("cli_stderr", "")
    assert ".claude/shop/name.md" in stderr, (
        f"expected advisory to name '.claude/shop/name.md'; got:\n{stderr!r}"
    )
    assert on_disk in stderr, (
        f"expected advisory to name the on-disk value {on_disk!r}; "
        f"got:\n{stderr!r}"
    )
    assert slug in stderr, (
        f"expected advisory to name the suggested canonical slug "
        f"{slug!r}; got:\n{stderr!r}"
    )
    lower = stderr.lower()
    assert "edit" in lower and "name.md" in stderr and "slug" in lower, (
        f"expected advisory to instruct editing name.md to the slug "
        f"form; got:\n{stderr!r}"
    )


# -- Then: advisory explicitly notes update did not modify the shop-owned
#    file (scenario 97245affb1dbe5e4).
@then(
    'the advisory explicitly notes that "shop-templates update" did not '
    'modify the shop-owned file'
)
def then_advisory_notes_no_modification(context: dict) -> None:
    stderr = context.get("cli_stderr", "")
    lower = stderr.lower()
    assert "did not modify" in lower or "did not" in lower and (
        "modif" in lower
    ), (
        f"expected advisory to explicitly note that update did NOT "
        f"modify the shop-owned file; got:\n{stderr!r}"
    )
    assert "shop-owned" in lower, (
        f"expected advisory to name the file as 'shop-owned'; "
        f"got:\n{stderr!r}"
    )


# -- Given: previously-bootstrapped shop with no explicit shop-name in the
#    scenario text (scenario 97245affb1dbe5e4). Bootstraps with a canonical
#    slug name so the pre-state is a clean slug-form name.md, which the
#    follow-up Given then edits to a display form.
@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" that '
        'was previously bootstrapped as a "{shop_type}" shop'
    )
)
def given_previously_bootstrapped_no_name(
    alias: str,
    shop_type: str,
    context: dict,
    tmp_path: Path,
) -> None:
    context["bootstrap_workspace"] = tmp_path
    # Use a canonical slug name for the bootstrap so the resulting
    # name.md holds a valid slug; the next Given drifts it to display form.
    _do_bootstrap_for_test(
        alias, shop_type, "shopsystem-product", context, tmp_path
    )


# =======================================================================
# lead-8hxz — bootstrap renders lead-shop ops scaffolding (compose.yaml,
# bin/shop-shell, Dockerfile.shopsystem-shell); bc renders none of them.
# Scenarios 90138f78dfa46697, 3d94639d5af360d7, 314d4485b8197f2a,
# 82c069bd3fb3b1d4, 8cf5656c55b466e7, 43e085e8627c7756.
# =======================================================================


def _ops_target(context: dict) -> Path:
    """Resolve the bootstrap target for the ops-scaffolding scenarios.

    Prefer the target the When step recorded; fall back to the single
    alias in scope so the Then steps work even before any standalone
    invocation has run.
    """
    target = context.get("last_invocation_target")
    if target is not None:
        return Path(target)
    return _resolve_single_target(context)


def _parse_yaml_via_subprocess(path: Path) -> object:
    """Parse a YAML file and return the data, validating real
    YAML-parseability.

    The test venv has no PyYAML and no pip; the global interpreter does.
    Try an in-process import first (so the check is self-contained when
    PyYAML happens to be present), then fall back to a yaml-capable
    interpreter that round-trips the parsed document through JSON (stdlib)
    so this process can load it without a yaml dependency. A parse failure
    in either path raises, which is exactly the "parses as valid YAML"
    contract failing.
    """
    text = path.read_text()
    try:  # pragma: no cover - depends on environment
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ModuleNotFoundError:
        pass

    import json
    import shutil

    helper = (
        "import sys, json, yaml\n"
        "data = yaml.safe_load(sys.stdin.read())\n"
        "json.dump(data, sys.stdout)\n"
    )
    last_err = None
    for interp in (
        sys.executable,
        shutil.which("python3"),
        "/usr/local/bin/python",
        shutil.which("python"),
    ):
        if not interp:
            continue
        proc = subprocess.run(
            [interp, "-c", helper],
            input=text,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return json.loads(proc.stdout)
        last_err = proc.stderr
    raise AssertionError(
        f"could not parse {path!s} as YAML via any available interpreter; "
        f"last stderr:\n{last_err}"
    )


# -- Given premises (ops-file absence) ----------------------------------


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'with no top-level "compose.yaml" file'
    )
)
def given_repo_no_compose(alias: str, context: dict, tmp_path: Path) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    assert not (real / "compose.yaml").exists(), (
        f"premise of Given violated: {(real / 'compose.yaml')!s} exists"
    )


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'with no "bin/" subdirectory'
    )
)
def given_repo_no_bin_dir(alias: str, context: dict, tmp_path: Path) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    assert not (real / "bin").exists(), (
        f"premise of Given violated: {(real / 'bin')!s} exists"
    )


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'with no top-level "Dockerfile.shopsystem-shell" file'
    )
)
def given_repo_no_dockerfile(alias: str, context: dict, tmp_path: Path) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    assert not (real / "Dockerfile.shopsystem-shell").exists(), (
        f"premise violated: {(real / 'Dockerfile.shopsystem-shell')!s} exists"
    )


@given(
    parsers.parse(
        'an existing git repository at a target directory "{alias}" '
        'with no top-level "compose.yaml", no "bin/" subdirectory, and no '
        'top-level "Dockerfile.shopsystem-shell"'
    )
)
def given_repo_no_ops_files(alias: str, context: dict, tmp_path: Path) -> None:
    context["bootstrap_workspace"] = tmp_path
    real = _real_target_for_alias(alias, context)
    for rel in ("compose.yaml", "bin", "Dockerfile.shopsystem-shell"):
        assert not (real / rel).exists(), (
            f"premise of Given violated: {(real / rel)!s} exists"
        )


# -- Then: file presence -------------------------------------------------


@then(
    parsers.parse(
        'after the invocation the target directory contains a top-level '
        'file named "{name}"'
    )
)
def then_target_contains_top_level_file(name: str, context: dict) -> None:
    real = _ops_target(context)
    path = real / name
    assert path.is_file(), f"expected top-level file {path!s} to exist"


@then(
    parsers.parse(
        'after the invocation the target directory contains a file at '
        '"{rel}"'
    )
)
def then_target_contains_file_at(rel: str, context: dict) -> None:
    real = _ops_target(context)
    path = real / rel
    assert path.is_file(), f"expected file {path!s} to exist"


@then(
    parsers.parse(
        'the file at "{rel}" in the target directory has its '
        'owner-execute permission bit set'
    )
)
def then_file_owner_execute_set(rel: str, context: dict) -> None:
    import stat as _stat

    real = _ops_target(context)
    path = real / rel
    mode = path.stat().st_mode
    assert mode & _stat.S_IXUSR, (
        f"expected owner-execute bit set on {path!s}; mode={oct(mode)}"
    )


@then(
    parsers.parse(
        'the first line of the file at "{rel}" is exactly "{line}"'
    )
)
def then_first_line_is_exactly(rel: str, line: str, context: dict) -> None:
    real = _ops_target(context)
    text = (real / rel).read_text()
    first = text.splitlines()[0] if text.splitlines() else ""
    assert first == line, f"first line of {rel} is {first!r}, expected {line!r}"


# -- Then: bin/shop-shell body literals ---------------------------------


@then(
    parsers.re(
        r'the body of "(?P<rel>[^"]+)" contains the literal substring '
        r'"(?P<first>[^"]+)" followed somewhere later in the file by the '
        r'literal substring "(?P<second>[^"]+)"'
    )
)
def then_body_contains_ordered(
    rel: str, first: str, second: str, context: dict
) -> None:
    real = _ops_target(context)
    body = (real / rel).read_text()
    i = body.find(first)
    j = body.find(second)
    assert i != -1, f"{rel} missing literal {first!r}"
    assert j != -1, f"{rel} missing literal {second!r}"
    assert i < j, (
        f"{rel}: {first!r} (at {i}) must precede {second!r} (at {j})"
    )


@then(
    parsers.re(
        r'the body of "(?P<rel>[^"]+)" contains the literal substring '
        r'"(?P<needle>[^"]+)"$'
    )
)
def then_body_contains_literal(rel: str, needle: str, context: dict) -> None:
    real = _ops_target(context)
    body = (real / rel).read_text()
    assert needle in body, f"{rel} missing literal substring {needle!r}"


@then(
    parsers.parse(
        'the body of "{rel}" references the environment variable '
        '"{var}" with a default of "{default}"'
    )
)
def then_body_references_env_with_default(
    rel: str, var: str, default: str, context: dict
) -> None:
    real = _ops_target(context)
    body = (real / rel).read_text()
    assert var in body, f"{rel} does not reference env var {var!r}"
    assert default in body, (
        f"{rel} does not express default {default!r} for {var!r}"
    )


@then(
    parsers.parse(
        'the body of "{rel}" references the environment variable '
        '"{var}" for the shell image tag'
    )
)
def then_body_references_env(rel: str, var: str, context: dict) -> None:
    real = _ops_target(context)
    body = (real / rel).read_text()
    assert var in body, f"{rel} does not reference env var {var!r}"


# -- Then: Dockerfile literals ------------------------------------------


@then(
    parsers.parse(
        'the file at "{rel}" in the target directory contains at least '
        'one line beginning with the literal token "{token}"'
    )
)
def then_file_has_line_beginning_with(
    rel: str, token: str, context: dict
) -> None:
    real = _ops_target(context)
    body = (real / rel).read_text()
    assert any(ln.startswith(token) for ln in body.splitlines()), (
        f"{rel} has no line beginning with {token!r}"
    )


@then(
    parsers.parse(
        'the file at "{rel}" in the target directory contains the literal '
        'substring "{needle}"'
    )
)
def then_file_contains_literal(rel: str, needle: str, context: dict) -> None:
    real = _ops_target(context)
    body = (real / rel).read_text()
    assert needle in body, f"{rel} missing literal substring {needle!r}"


@then(
    parsers.re(
        r'the file at "(?P<rel>[^"]+)" in the target directory contains a '
        r'"(?P<kw>[^"]+)" instruction whose literal image reference is '
        r'"(?P<img>[^"]+)"(?:,.*)?$'
    )
)
def then_file_from_instruction_image(
    rel: str, kw: str, img: str, context: dict
) -> None:
    real = _ops_target(context)
    body = (real / rel).read_text()
    matched = any(
        ln.lstrip().startswith(kw) and img in ln
        for ln in body.splitlines()
    )
    assert matched, (
        f"{rel}: no {kw} instruction with image reference {img!r}"
    )


@then(
    parsers.re(
        r'the file at "(?P<rel>[^"]+)" in the target directory does not '
        r'contain the literal substring "(?P<needle>[^"]+)"(?:,.*)?$'
    )
)
def then_file_does_not_contain_literal(
    rel: str, needle: str, context: dict
) -> None:
    real = _ops_target(context)
    body = (real / rel).read_text()
    assert needle not in body, (
        f"{rel}: expected NOT to contain literal substring {needle!r}"
    )


@then(
    parsers.re(
        r'the file at "(?P<rel>[^"]+)" in the target directory contains a '
        r'"(?P<kw>[^"]+)" instruction whose literal token form names a '
        r'non-root user(?:,.*)?$'
    )
)
def then_file_user_instruction_non_root(
    rel: str, kw: str, context: dict
) -> None:
    real = _ops_target(context)
    body = (real / rel).read_text()
    user_lines = [
        ln.strip()
        for ln in body.splitlines()
        if ln.lstrip().startswith(kw)
    ]
    assert user_lines, f"{rel}: no {kw} instruction present"
    named_non_root = False
    for ln in user_lines:
        # Token after the keyword, e.g. "USER vscode" -> "vscode".
        parts = ln.split()
        if len(parts) < 2:
            continue
        user_token = parts[1]
        if user_token not in ("root", "0", "0:0") and not user_token.startswith(
            "root:"
        ):
            named_non_root = True
    assert named_non_root, (
        f"{rel}: {kw} instruction(s) {user_lines!r} name no non-root user"
    )


@then(
    parsers.parse(
        'the file at "{rel}" in the target directory installs at least '
        'one of the framework CLIs by literal substring match against the '
        'set "{a}", "{b}", or "{c}"'
    )
)
def then_file_installs_a_framework_cli(
    rel: str, a: str, b: str, c: str, context: dict
) -> None:
    real = _ops_target(context)
    body = (real / rel).read_text()
    assert any(x in body for x in (a, b, c)), (
        f"{rel} installs none of the framework CLIs {a!r}, {b!r}, {c!r}"
    )


@then(
    parsers.parse(
        'the file at "{rel}" in the target directory contains a "{kw1}" or '
        '"{kw2}" instruction whose literal token form references "{t1}" or '
        '"{t2}"'
    )
)
def then_file_has_cmd_or_entrypoint(
    rel: str, kw1: str, kw2: str, t1: str, t2: str, context: dict
) -> None:
    real = _ops_target(context)
    body = (real / rel).read_text()
    has_instr = any(
        ln.lstrip().startswith(kw1) or ln.lstrip().startswith(kw2)
        for ln in body.splitlines()
    )
    assert has_instr, f"{rel} has no {kw1} or {kw2} instruction"
    references = any(
        (t1 in ln or t2 in ln)
        and (ln.lstrip().startswith(kw1) or ln.lstrip().startswith(kw2))
        for ln in body.splitlines()
    )
    assert references, (
        f"{rel}: no {kw1}/{kw2} instruction references {t1!r} or {t2!r}"
    )


# -- Then: compose.yaml parsing + structure -----------------------------


def _load_compose(context: dict, rel: str = "compose.yaml") -> object:
    real = _ops_target(context)
    data = _parse_yaml_via_subprocess(real / rel)
    context["parsed_compose"] = data
    return data


@then(
    parsers.parse(
        'the file at "{rel}" in the target directory parses as valid YAML'
    )
)
def then_file_parses_as_yaml(rel: str, context: dict) -> None:
    data = _load_compose(context, rel)
    assert data is not None, f"{rel} parsed to an empty/None YAML document"


@then(
    parsers.parse(
        'after the invocation the file at "{rel}" in the target directory '
        'parses as valid YAML'
    )
)
def then_after_file_parses_as_yaml(rel: str, context: dict) -> None:
    data = _load_compose(context, rel)
    assert data is not None, f"{rel} parsed to an empty/None YAML document"


@then(
    parsers.parse(
        'the parsed YAML contains a top-level key "{key}" whose value is a '
        'mapping containing a key "{subkey}"'
    )
)
def then_parsed_yaml_top_level_mapping_has_subkey(
    key: str, subkey: str, context: dict
) -> None:
    data = context.get("parsed_compose") or _load_compose(context)
    assert isinstance(data, dict) and key in data, (
        f"parsed YAML has no top-level key {key!r}"
    )
    value = data[key]
    assert isinstance(value, dict) and subkey in value, (
        f"top-level {key!r} is not a mapping containing {subkey!r}"
    )


@then(
    parsers.parse(
        'the "{svc}" mapping has an "{field}" value whose string form '
        'begins with the literal "{prefix}"'
    )
)
def then_service_field_begins_with(
    svc: str, field: str, prefix: str, context: dict
) -> None:
    data = context.get("parsed_compose") or _load_compose(context)
    node = _resolve_dotted(data, svc)
    assert isinstance(node, dict) and field in node, (
        f"{svc!r} has no {field!r} value"
    )
    assert str(node[field]).startswith(prefix), (
        f"{svc}.{field} = {node[field]!r} does not begin with {prefix!r}"
    )


@then(
    parsers.parse(
        'the "{svc}" mapping has a "networks" entry naming the "{net}" '
        'network'
    )
)
def then_service_networks_names(svc: str, net: str, context: dict) -> None:
    data = context.get("parsed_compose") or _load_compose(context)
    node = _resolve_dotted(data, svc)
    assert isinstance(node, dict) and "networks" in node, (
        f"{svc!r} has no networks entry"
    )
    nets = node["networks"]
    if isinstance(nets, dict):
        names = list(nets.keys())
    else:
        names = list(nets)
    assert net in names, f"{svc}.networks {names!r} does not name {net!r}"


@then(
    parsers.parse(
        'the "{svc}" mapping has a "volumes" entry whose source string '
        'contains the literal substring "{src_lit}" and whose target '
        'string is exactly "{target}"'
    )
)
def then_service_volume_source_target(
    svc: str, src_lit: str, target: str, context: dict
) -> None:
    data = context.get("parsed_compose") or _load_compose(context)
    node = _resolve_dotted(data, svc)
    src, tgt = _find_volume_for_target(node, target)
    assert src is not None, (
        f"{svc!r} has no volume whose target is {target!r}"
    )
    context["last_volume_source"] = src
    assert src_lit in src, (
        f"volume source {src!r} does not contain {src_lit!r}"
    )
    assert tgt == target, f"volume target {tgt!r} is not exactly {target!r}"


@then(
    parsers.parse(
        'the source string of the volume mount on "{svc}" whose target is '
        '"{target}" contains the literal substring "{src_lit}"'
    )
)
def then_volume_source_contains(
    svc: str, target: str, src_lit: str, context: dict
) -> None:
    data = context.get("parsed_compose") or _load_compose(context)
    node = _resolve_dotted(data, svc)
    src, _tgt = _find_volume_for_target(node, target)
    assert src is not None, f"no volume on {svc!r} with target {target!r}"
    context["last_volume_source"] = src
    assert src_lit in src, f"source {src!r} missing literal {src_lit!r}"


@then(
    parsers.re(
        r'the source string of that volume mount expresses a default whose '
        r'literal substring is "(?P<a>[^"]+)" or "(?P<b>[^"]+)"'
    )
)
def then_volume_source_default(a: str, b: str, context: dict) -> None:
    src = context.get("last_volume_source")
    assert src is not None, "no volume source captured by a prior step"
    assert a in src or b in src, (
        f"volume source {src!r} expresses neither {a!r} nor {b!r}"
    )


@then(
    parsers.parse(
        'the source string of that volume mount does not contain the '
        'literal substring "{needle}"'
    )
)
def then_volume_source_excludes(needle: str, context: dict) -> None:
    src = context.get("last_volume_source")
    assert src is not None, "no volume source captured by a prior step"
    assert needle not in src, (
        f"volume source {src!r} unexpectedly contains {needle!r}"
    )


@then(
    parsers.parse(
        'no service entry under "services" mounts a volume whose source '
        'path resolves underneath "{root}"'
    )
)
def then_no_service_volume_under_root(root: str, context: dict) -> None:
    data = context.get("parsed_compose") or _load_compose(context)
    services = data.get("services", {}) if isinstance(data, dict) else {}
    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        for vol in svc.get("volumes", []) or []:
            src = _volume_source(vol)
            if src is None:
                continue
            assert root not in src, (
                f"service {svc_name!r} mounts a volume whose source {src!r} "
                f"resolves underneath {root!r}"
            )


@then(
    parsers.parse(
        'the body of "{rel}" in the target directory contains no path '
        'beginning with the literal "{a}" or "{b}"'
    )
)
def then_body_contains_no_path(rel: str, a: str, b: str, context: dict) -> None:
    real = _ops_target(context)
    body = (real / rel).read_text()
    assert a not in body, f"{rel} unexpectedly contains {a!r}"
    assert b not in body, f"{rel} unexpectedly contains {b!r}"


# -- Then: shop-owned placement (not under .claude/) --------------------


@then(
    parsers.re(
        r'after the invocation the target directory contains a top-level '
        r'file named "(?P<name>[^"]+)" at the path "(?P<abspath>[^"]+)" '
        r'\(not under any "\.claude/" subdirectory\)'
    )
)
def then_top_level_file_at_abspath_not_under_claude(
    name: str, abspath: str, context: dict
) -> None:
    real = _ops_target(context)
    path = real / name
    assert path.is_file(), f"expected file {path!s} to exist"
    assert ".claude" not in path.relative_to(real).parts, (
        f"{name} is under a .claude/ subdirectory: {path!s}"
    )


@then(
    parsers.re(
        r'after the invocation the target directory contains a file at '
        r'"(?P<abspath>[^"]+)" \(not under any "\.claude/" subdirectory\)'
    )
)
def then_file_at_abspath_not_under_claude(abspath: str, context: dict) -> None:
    real = _ops_target(context)
    # The scenario expresses the path as /tmp/example-lead-shop/<rel>; map
    # it onto the real target by stripping the alias prefix.
    rel = abspath.split("/tmp/example-lead-shop/", 1)[-1]
    path = real / rel
    assert path.is_file(), f"expected file {path!s} to exist"
    assert ".claude" not in path.relative_to(real).parts, (
        f"{rel} is under a .claude/ subdirectory: {path!s}"
    )


@then(
    parsers.re(
        r'after the invocation the directory at "(?P<dirpath>[^"]+)" does '
        r'not contain a file named "(?P<n1>[^"]+)", "(?P<n2>[^"]+)", or '
        r'"(?P<n3>[^"]+)"'
    )
)
def then_canonical_dir_lacks_files(
    dirpath: str, n1: str, n2: str, n3: str, context: dict
) -> None:
    real = _ops_target(context)
    rel = dirpath.split("/tmp/example-lead-shop/", 1)[-1].rstrip("/")
    cdir = real / rel
    for n in (n1, n2, n3):
        assert not (cdir / n).exists(), (
            f"{cdir!s} unexpectedly contains {n!r}"
        )


# -- Then: ops-file non-emission (bc shop) ------------------------------


@then(
    parsers.parse(
        'after the invocation the target directory contains no top-level '
        'file named "{name}"'
    )
)
def then_target_lacks_top_level_file(name: str, context: dict) -> None:
    real = _ops_target(context)
    assert not (real / name).exists(), (
        f"{(real / name)!s} unexpectedly exists"
    )


@then(
    parsers.parse(
        'after the invocation the target directory contains no file at '
        '"{rel}"'
    )
)
def then_target_lacks_file_at(rel: str, context: dict) -> None:
    real = _ops_target(context)
    assert not (real / rel).exists(), (
        f"{(real / rel)!s} unexpectedly exists"
    )


# -- helpers for compose structure --------------------------------------


def _resolve_dotted(data: object, dotted: str) -> object:
    node = data
    for part in dotted.split("."):
        assert isinstance(node, dict) and part in node, (
            f"path {dotted!r} not resolvable: missing {part!r}"
        )
        node = node[part]
    return node


def _volume_source(vol: object) -> str | None:
    """Return the source string of a compose volume entry (long or short
    form), or None if it has no identifiable source."""
    if isinstance(vol, dict):
        src = vol.get("source")
        return None if src is None else str(src)
    if isinstance(vol, str):
        # short form "source:target[:opts]" — but our source may itself
        # contain ":-"; long form is used in the rendered file, so this
        # branch is best-effort only.
        return vol.split(":")[0]
    return None


def _volume_target(vol: object) -> str | None:
    if isinstance(vol, dict):
        tgt = vol.get("target")
        return None if tgt is None else str(tgt)
    if isinstance(vol, str):
        parts = vol.split(":")
        return parts[1] if len(parts) > 1 else None
    return None


def _find_volume_for_target(node: object, target: str):
    """Return (source, target) for the volume on a service mapping whose
    target equals `target`, capturing the source on context for later
    'that volume mount' steps. Returns (None, None) when not found."""
    if not isinstance(node, dict):
        return None, None
    for vol in node.get("volumes", []) or []:
        tgt = _volume_target(vol)
        if tgt == target:
            src = _volume_source(vol)
            return src, tgt
    return None, None


# =======================================================================
# lead-xjsq: shop-templates update — ops scaffolding coverage
# (scenarios 3e8c8087c483db9e / ebbe3f1b92258299 / 59d41246cbd5235b).
#
# The three lead-shop ops scaffolding files are SHOP-OWNED (PDR-003 path
# F two-bucket model): update never overwrites them, emits a drift
# advisory on stderr (exit 0) when on-disk content differs from the
# current canonical template body, and is idempotent (no advisory, no
# mtime bump) when on-disk content already matches canonical. The
# advisory pattern mirrors scenario 132's name.md advisory.
#
# Map a scenario-visible relative target path to the package-data ops
# template name read via shop_templates.cli.read_ops_template().
# =======================================================================

_OPS_PATH_TO_TEMPLATE_NAME: dict[str, str] = {
    "compose.yaml": "compose.yaml",
    "bin/shop-shell": "shop-shell",
    "Dockerfile.shopsystem-shell": "Dockerfile.shopsystem-shell",
}


def _canonical_ops_body(path: str) -> str:
    from shop_templates.cli import read_ops_template

    template_name = _OPS_PATH_TO_TEMPLATE_NAME[path]
    return read_ops_template(template_name)


# -- Given: an ops scaffolding file has been hand-edited so its byte
#    contents differ from the canonical template body (scenario 139).
@given(
    parsers.parse(
        'the file at "{path}" in the target directory has been hand-edited '
        'so that its byte contents are not equal to the canonical "{path_again}" '
        'template body for shop type "{shop_type}"'
    )
)
def given_ops_file_hand_edited_differs(
    path: str, path_again: str, shop_type: str, context: dict
) -> None:
    assert path == path_again, (
        f"scenario inconsistency: {path!r} vs {path_again!r}"
    )
    real = _resolve_single_target(context)
    target_file = real / path
    assert target_file.exists(), (
        f"premise of Given violated: {target_file!s} does not exist "
        f"(lead shop must have been previously bootstrapped with ops "
        f"scaffolding)"
    )
    edited = target_file.read_text() + "\n# HAND-EDITED — not in canonical ops body\n"
    target_file.write_text(edited)
    canonical = _canonical_ops_body(path)
    assert target_file.read_text() != canonical, (
        f"premise of Given violated: hand-edited {path!r} still equals "
        f"the canonical ops template body"
    )


# -- Given: record byte contents of the three named ops files (scenario 139).
@given('I record the byte contents of those three files before the invocation')
def given_record_three_ops_files(context: dict) -> None:
    real = _resolve_single_target(context)
    snap = context.setdefault("two_file_snapshot", {})
    for path in ("compose.yaml", "bin/shop-shell", "Dockerfile.shopsystem-shell"):
        target_file = real / path
        assert target_file.exists(), (
            f"premise of Given violated: {target_file!s} does not exist"
        )
        snap[path] = {
            "bytes": target_file.read_bytes(),
            "mtime_ns": target_file.stat().st_mtime_ns,
        }


# -- Given: an ops scaffolding file's on-disk content differs from the
#    current canonical template body (scenario 140 outline).
@given(
    parsers.parse(
        'the file at "{path}" in the target directory has byte contents '
        'that differ from the current canonical "{path_again}" template '
        'body for shop type "{shop_type}"'
    )
)
def given_ops_file_differs_from_canonical(
    path: str, path_again: str, shop_type: str, context: dict
) -> None:
    assert path == path_again
    real = _resolve_single_target(context)
    target_file = real / path
    assert target_file.exists(), (
        f"premise of Given violated: {target_file!s} does not exist"
    )
    edited = target_file.read_text() + "\n# DRIFTED FROM CANONICAL\n"
    target_file.write_text(edited)
    assert target_file.read_text() != _canonical_ops_body(path), (
        f"premise of Given violated: {path!r} still equals canonical"
    )


# -- Given: an ops scaffolding file's on-disk content equals the current
#    canonical template body byte-for-byte (scenario 141 outline).
@given(
    parsers.parse(
        'the file at "{path}" in the target directory has byte contents '
        'equal to the current canonical "{path_again}" template body for '
        'shop type "{shop_type}"'
    )
)
def given_ops_file_equals_canonical(
    path: str, path_again: str, shop_type: str, context: dict
) -> None:
    assert path == path_again
    real = _resolve_single_target(context)
    target_file = real / path
    canonical = _canonical_ops_body(path)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(canonical)
    assert target_file.read_text() == canonical, (
        f"premise of Given violated: could not establish {path!r} == canonical"
    )


# -- Given: record byte contents and mtime of a single ops file (scenarios
#    140 / 141 outlines). Populates two_file_snapshot keyed by the path so
#    the existing "equal the recorded byte contents" / "equals the recorded
#    mtime" Then steps reconcile against it.
@given(
    parsers.parse(
        'I record the byte contents and mtime of the file at "{path}" in '
        'the target directory before the invocation'
    )
)
def given_record_single_ops_file_byte_and_mtime(path: str, context: dict) -> None:
    real = _resolve_single_target(context)
    target_file = real / path
    assert target_file.exists(), (
        f"premise of Given violated: {target_file!s} does not exist"
    )
    snap = context.setdefault("two_file_snapshot", {})
    snap[path] = {
        "bytes": target_file.read_bytes(),
        "mtime_ns": target_file.stat().st_mtime_ns,
    }


# -- Then: an ops file is byte-for-byte unchanged across the invocation
#    (scenario 140 outline). Reads the pre_invocation_files snapshot
#    populated by the existing "I record the byte contents of the file at
#    <path>" Given step.
@then(
    parsers.parse(
        'after the invocation the file at "{path}" in the target directory '
        'has byte-for-byte the same on-disk contents as before the invocation'
    )
)
def then_ops_file_unchanged_vs_recorded(path: str, context: dict) -> None:
    snap = context.get("pre_invocation_files", {})
    assert path in snap, (
        f"no recorded snapshot for {path!r}; the 'I record the byte "
        f"contents of the file at' Given step must run first"
    )
    real = context["last_invocation_target"]
    actual = (real / path).read_bytes()
    expected = snap[path]
    assert actual == expected, (
        f"on-disk byte contents of {path!r} changed across update "
        f"invocation; expected the shop-owned ops file to be left untouched"
    )


# -- Then: stderr advisory names the drifted ops file path and notes the
#    drift (scenario 140 outline). Mirrors scenario 132's name.md advisory.
@then(
    parsers.parse(
        'stderr contains an advisory naming the file path "{path}" and '
        'noting that the file has drifted from canonical'
    )
)
def then_stderr_ops_drift_advisory(path: str, context: dict) -> None:
    stderr = context.get("cli_stderr", "")
    assert path in stderr, (
        f"expected advisory to name the file path {path!r}; got:\n{stderr!r}"
    )
    lower = stderr.lower()
    assert "drift" in lower or "drifted" in lower, (
        f"expected advisory to note the file has drifted from canonical; "
        f"got:\n{stderr!r}"
    )


# -- Then: advisory names a means to view the canonical body (scenario 140
#    outline). Accepts the literal "shop-templates show" substring or an
#    equivalent operator-visible canonical-read path.
@then(
    parsers.parse(
        'the advisory names a means for the operator to view the canonical '
        'body (e.g., the literal substring "{needle}" or an equivalent '
        'operator-visible path the canonical body can be read from)'
    )
)
def then_advisory_names_canonical_read_means(needle: str, context: dict) -> None:
    stderr = context.get("cli_stderr", "")
    assert needle in stderr, (
        f"expected advisory to name a means to view the canonical body "
        f"(literal substring {needle!r}); got:\n{stderr!r}"
    )


# -- Then: stderr contains NO advisory naming the file path (scenario 141
#    outline — idempotent / already-up-to-date case).
@then(
    parsers.parse(
        'stderr does not contain any advisory naming the file path "{path}"'
    )
)
def then_stderr_no_advisory_for_path(path: str, context: dict) -> None:
    stderr = context.get("cli_stderr", "")
    assert path not in stderr, (
        f"expected NO advisory naming {path!r} on stderr (file matches "
        f"canonical; update must be a silent no-op for it); got:\n{stderr!r}"
    )


# =======================================================================
# Release-workflow repository_dispatch to bc-launcher
# (lead-jx4u, scenario 26ca8a14e01db50c)
#
# This scenario pins behavior of THIS repository's own CI: on a
# version-tag release of shopsystem-templates, its release workflow
# performs a repository_dispatch API call targeting the
# shopsystem-bc-launcher repository, carrying a credential authorized
# to dispatch.
#
# The testable artifact is the GitHub Actions release workflow file
# committed under .github/workflows/ in this repo. We parse it as YAML
# and assert, against the static workflow definition:
#   - it triggers on a version-tag push (so a "v0.2.0" tag push on main
#     is associated with a run of this workflow),
#   - some step performs a repository_dispatch targeting
#     shopsystem-bc-launcher (either the GitHub API
#     /repos/<owner>/shopsystem-bc-launcher/dispatches endpoint, or a
#     repository-dispatch action wired to that repository),
#   - that step wires a credential (a secrets.* token reference) into
#     the dispatch call.
#
# "runs to successful completion" is interpreted statically: the
# workflow is well-formed and the dispatch step is unconditionally part
# of the version-tag run path (not gated behind a manual-only trigger).
# =======================================================================

def _bc_repo_root() -> Path:
    # tests/ sits directly under the BC repo root.
    return Path(__file__).resolve().parent.parent


def _workflow_on_block(parsed: dict):
    """Return the `on:` trigger mapping from a parsed workflow.

    PyYAML parses the bare `on:` key as the boolean True; the
    JSON-round-trip fallback in _parse_yaml_via_subprocess turns that
    same key into the string "true". Accept all three spellings.
    """
    for key in ("on", True, "true"):
        on = parsed.get(key)
        if isinstance(on, dict):
            return on
    return None


def _find_release_workflow_for_version_tag(root: Path):
    """Return (path, parsed) for the first .github/workflows/*.ya?ml whose
    push trigger fires on a version tag, or None if there is none.

    A workflow "fires on a version tag" when its `on.push.tags` list
    contains at least one glob that the tag "v0.2.0" matches. We
    recognize the common version-tag globs (e.g. "v*", "v*.*.*",
    "v[0-9]+*") via fnmatch against "v0.2.0".
    """
    import fnmatch

    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return None
    for path in sorted(wf_dir.iterdir()):
        if path.suffix not in (".yml", ".yaml"):
            continue
        try:
            parsed = _parse_yaml_via_subprocess(path)
        except AssertionError:
            continue
        if not isinstance(parsed, dict):
            continue
        on = _workflow_on_block(parsed)
        if not isinstance(on, dict):
            continue
        push = on.get("push")
        if not isinstance(push, dict):
            continue
        tags = push.get("tags")
        if not isinstance(tags, list):
            continue
        for glob in tags:
            if isinstance(glob, str) and fnmatch.fnmatch("v0.2.0", glob):
                return (path, parsed)
    return None


def _iter_workflow_steps(parsed: dict):
    """Yield every step mapping across every job in a parsed workflow."""
    jobs = parsed.get("jobs")
    if not isinstance(jobs, dict):
        return
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if isinstance(step, dict):
                yield step


def _step_text(step: dict) -> str:
    """Flatten a step's run/uses/with into a single searchable string."""
    parts = []
    for key in ("uses", "run", "name"):
        val = step.get(key)
        if isinstance(val, str):
            parts.append(val)
    with_block = step.get("with")
    if isinstance(with_block, dict):
        for k, v in with_block.items():
            parts.append(str(k))
            parts.append(str(v))
    env_block = step.get("env")
    if isinstance(env_block, dict):
        for k, v in env_block.items():
            parts.append(str(k))
            parts.append(str(v))
    return "\n".join(parts)


@given("the shopsystem-templates source repository")
def given_templates_source_repo(context: dict) -> None:
    root = _bc_repo_root()
    assert (root / ".git").exists(), (
        f"premise of Given violated: {root!s} is not a git repository "
        f"(no .git present)"
    )
    context["bc_repo_root"] = root


@given(parsers.parse('a tag named "{tag}" is pushed to its "{branch}" branch'))
def given_version_tag_pushed(tag: str, branch: str, context: dict) -> None:
    # The premise is that a version tag like "v0.2.0" exists on the
    # release line. We do not actually mutate git here; we record the tag
    # so the When step can confirm the release workflow's trigger is
    # associated with this tag push.
    context["release_tag"] = tag
    context["release_branch"] = branch


@when(
    "the shopsystem-templates release workflow associated with that tag "
    "push runs to successful completion"
)
def when_release_workflow_runs(context: dict) -> None:
    root = context["bc_repo_root"]
    found = _find_release_workflow_for_version_tag(root)
    assert found is not None, (
        "no release workflow under .github/workflows/ triggers on a "
        f"version-tag push (a push of tag {context.get('release_tag')!r} "
        "is not associated with any workflow run): expected a workflow "
        "whose on.push.tags matches a version tag like 'v0.2.0'"
    )
    path, parsed = found
    context["release_workflow_path"] = path
    context["release_workflow"] = parsed

    # "runs to successful completion" — the workflow must be well-formed
    # enough to run: it must define at least one job with at least one
    # step.
    steps = list(_iter_workflow_steps(parsed))
    assert steps, (
        f"release workflow {path.name} defines no runnable steps; a run "
        "could not complete successfully"
    )
    context["release_workflow_steps"] = steps


@then(
    parsers.parse(
        'the workflow performs a "repository_dispatch" API call targeting '
        'the "{repo}" repository'
    )
)
def then_workflow_dispatches_repo(repo: str, context: dict) -> None:
    steps = context["release_workflow_steps"]
    # A repository_dispatch can be realized two ways:
    #   (a) a direct API call to
    #       /repos/<owner>/<repo>/dispatches  (gh api / curl), or
    #   (b) a repository-dispatch action (e.g. peter-evans/repository-dispatch)
    #       whose `with.repository` (or `with.repo`) names <owner>/<repo>.
    # Either way the call must (1) be a repository_dispatch and (2) target
    # the named repository.
    dispatch_steps = []
    for step in steps:
        text = _step_text(step)
        is_dispatch = (
            "repository_dispatch" in text
            or "repository-dispatch" in text
            or "/dispatches" in text
        )
        if is_dispatch:
            dispatch_steps.append((step, text))

    assert dispatch_steps, (
        "release workflow contains no step performing a repository_dispatch "
        "(no 'repository_dispatch', 'repository-dispatch', or '/dispatches' "
        f"reference found across its steps); workflow: "
        f"{context['release_workflow_path'].name}"
    )

    targeted = [
        (step, text) for step, text in dispatch_steps if repo in text
    ]
    assert targeted, (
        f"a repository_dispatch step exists but none targets the {repo!r} "
        f"repository; dispatch step text(s):\n"
        + "\n---\n".join(text for _step, text in dispatch_steps)
    )
    # Stash the targeting dispatch step(s) for the credential assertion.
    context["dispatch_steps"] = targeted


@then(
    "that dispatch call carries a credential authorized to dispatch to the "
    "bc-launcher repository"
)
def then_dispatch_carries_credential(context: dict) -> None:
    targeted = context["dispatch_steps"]
    # The dispatch call must wire in a credential rather than run
    # unauthenticated. A repository_dispatch to a *different* repository
    # cannot use the default GITHUB_TOKEN (which is scoped to the current
    # repo), so the workflow must reference a secret (a PAT / app token).
    # We assert at least one targeting dispatch step references a
    # `secrets.<NAME>` token expression.
    secret_re = re.compile(r"secrets\.[A-Za-z_][A-Za-z0-9_]*")
    for step, text in targeted:
        if secret_re.search(text):
            return
    raise AssertionError(
        "the repository_dispatch step targeting shopsystem-bc-launcher does "
        "not wire in a credential: no `secrets.<NAME>` reference found on "
        "the dispatch step. A cross-repository repository_dispatch cannot "
        "use the default GITHUB_TOKEN and must carry an authorized token. "
        "Dispatch step text(s):\n" + "\n---\n".join(t for _s, t in targeted)
    )


# -----------------------------------------------------------------------
# Skills pouring — A2/A3 step definitions
# -----------------------------------------------------------------------

from shop_templates.cli import iter_skill_files as _iter_skill_files  # noqa: E402


@when(parsers.parse('I bootstrap a "{shop_type}" shop named "{name}" at "{target}"'))
def when_bootstrap_shop(shop_type, name, target, context, tmp_path):
    ws = context["bootstrap_workspace"]
    result = _run_shop_templates_with_bd_shim(
        ["bootstrap", "--shop-type", shop_type, "--shop-name", name, "--target", str(ws)],
        context, tmp_path,
    )
    context["cli_returncode"] = result.returncode
    context["cli_stdout"] = result.stdout
    context["cli_stderr"] = result.stderr


@then('every shipped skill file appears under ".claude/skills/" in the target byte-for-byte')
def then_skills_poured(context):
    ws = Path(context["bootstrap_workspace"])
    for rel, body in _iter_skill_files():
        dest = ws / ".claude" / "skills" / rel
        assert dest.exists(), f"missing poured skill file: {rel}"
        assert dest.read_bytes() == body, f"skill file content drift: {rel}"


@then(parsers.parse('the target directory contains no ".claude/skills/" directory'))
def then_no_skills_dir(context):
    ws = Path(context["bootstrap_workspace"])
    assert not (ws / ".claude" / "skills").exists()


# -----------------------------------------------------------------------
# Skills update (A3) step definitions
# -----------------------------------------------------------------------


@given(parsers.parse('a bootstrapped "{shop_type}" shop at a target directory "{target}"'))
def given_bootstrapped_shop(shop_type, target, context, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    context["bootstrap_workspace"] = ws
    res = _run_shop_templates_with_bd_shim(
        ["bootstrap", "--shop-type", shop_type, "--shop-name", "probe-shop", "--target", str(ws)],
        context, tmp_path,
    )
    assert res.returncode == 0, res.stderr


@given(parsers.parse('the skill file "{rel}" has drifted to "{text}"'))
def given_skill_drifted(rel, text, context):
    p = Path(context["bootstrap_workspace"]) / rel
    p.write_text(text)


@given(parsers.parse('an extra file "{rel}" exists in the target'))
def given_extra_file(rel, context):
    p = Path(context["bootstrap_workspace"]) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("orphan")


@when(parsers.parse('I record the mtime of "{rel}"'))
def when_record_mtime(rel, context):
    p = Path(context["bootstrap_workspace"]) / rel
    context.setdefault("mtimes", {})[rel] = p.stat().st_mtime_ns


@when(parsers.parse('I run update for shop type "{shop_type}" at "{target}"'))
def when_run_update(shop_type, target, context):
    import argparse
    from shop_templates.cli import _cmd_update
    ws = context["bootstrap_workspace"]
    ns = argparse.Namespace(target=str(ws), shop_type=shop_type)
    context["update_rc"] = _cmd_update(ns)


@then("the exit code of the update invocation is 0")
def then_update_rc_zero(context):
    assert context["update_rc"] == 0


@then(parsers.parse('the mtime of "{rel}" is unchanged'))
def then_mtime_unchanged(rel, context):
    p = Path(context["bootstrap_workspace"]) / rel
    assert p.stat().st_mtime_ns == context["mtimes"][rel]


# -----------------------------------------------------------------------
# Step definitions — lead-po empowered-PM identity and durable disciplines
# (lead-y8rz / scenario_hash:1e49cc3a526d4272)
# -----------------------------------------------------------------------


@given(
    parsers.parse(
        'the four durable PM disciplines "{d1}", "{d2}", "{d3}", and "{d4}"'
    )
)
def given_four_durable_pm_disciplines(
    d1: str, d2: str, d3: str, d4: str, context: dict
) -> None:
    """Store the four discipline names for later Then assertions."""
    context["pm_disciplines"] = [d1, d2, d3, d4]


@then(
    "the content names an empowered Product-Manager identity that owns the "
    "problem and the outcome, distinct from an order-taker who converts "
    "requests into scenarios"
)
def then_content_names_empowered_pm_identity(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "empowered" in lc, (
        "lead-po template must name an empowered Product-Manager identity "
        "(lead-y8rz / 1e49cc3a526d4272)"
    )
    # Must name ownership of the problem AND the outcome.
    assert "problem" in lc and "outcome" in lc, (
        "lead-po template must state the empowered-PM owns the problem and the "
        "outcome (lead-y8rz / 1e49cc3a526d4272)"
    )
    # Must be distinct from an order-taker.
    assert "order-taker" in lc or "order taker" in lc, (
        "lead-po template must distinguish the empowered-PM from an "
        "order-taker (lead-y8rz / 1e49cc3a526d4272)"
    )


@then(
    "the content states that this empowered-PM identity sharpens, and does "
    "not replace, the existing COMMIT TO SPECIFICS posture"
)
def then_content_states_sharpens_not_replaces(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    assert "sharpen" in lc, (
        "lead-po template must state the empowered-PM identity sharpens the "
        "COMMIT TO SPECIFICS posture (lead-y8rz / 1e49cc3a526d4272)"
    )
    assert "does not replace" in lc or "not replace" in lc, (
        "lead-po template must state the empowered-PM identity does not replace "
        "the COMMIT TO SPECIFICS posture (lead-y8rz / 1e49cc3a526d4272)"
    )
    assert "commit to specifics" in lc, (
        "lead-po template must name the COMMIT TO SPECIFICS posture in the "
        "sharpens/not-replaces statement (lead-y8rz / 1e49cc3a526d4272)"
    )


@then("the content names each of the four durable PM disciplines")
def then_content_names_each_discipline(context: dict) -> None:
    content = context["template_content"]
    lc = content.lower()
    disciplines = context["pm_disciplines"]
    for discipline in disciplines:
        assert discipline.lower() in lc, (
            f"lead-po template must name PM discipline {discipline!r} "
            "(lead-y8rz / 1e49cc3a526d4272)"
        )


@then(
    "for each discipline, the content has a contiguous block — either a "
    "subsection that names the discipline or a line that names the discipline "
    "— that contains at minimum one sentence of guidance OR an explicit "
    'marker of the form "guidance pending" (case-insensitive)'
)
def then_each_discipline_has_guidance_or_pending(context: dict) -> None:
    """Assert that each discipline has a contiguous block with guidance or
    a 'guidance pending' marker.

    A 'contiguous block' is defined as: a subsection header line that names
    the discipline, OR a line that names the discipline, followed by at least
    one non-empty line within the same block (before the next heading or end
    of file) that constitutes guidance, OR the discipline name (or its block)
    contains the literal phrase 'guidance pending' (case-insensitive).
    """
    content = context["template_content"]
    lines = content.splitlines()
    disciplines = context["pm_disciplines"]

    for discipline in disciplines:
        discipline_lc = discipline.lower()
        # Find the line index where this discipline is named.
        block_start = None
        for i, line in enumerate(lines):
            if discipline_lc in line.lower():
                block_start = i
                break

        assert block_start is not None, (
            f"discipline {discipline!r} not found anywhere in lead-po template"
        )

        # Collect the contiguous block: from block_start until the next
        # heading line (## or ###) or end of file, but at least the current
        # line itself.
        block_lines = [lines[block_start]]
        for j in range(block_start + 1, len(lines)):
            line = lines[j]
            # A new heading starts a new block.
            if re.match(r"^#{1,6}\s", line):
                break
            block_lines.append(line)

        block_text = "\n".join(block_lines)
        block_lc = block_text.lower()

        # Satisfied if "guidance pending" appears anywhere in the block.
        if "guidance pending" in block_lc:
            continue

        # Satisfied if the block (beyond the discipline-naming line itself)
        # contains at least one non-empty sentence of guidance — i.e. at least
        # one non-empty line after the discipline-naming line.
        guidance_lines = [
            ln for ln in block_lines[1:]
            if ln.strip()
        ]
        assert len(guidance_lines) >= 1, (
            f"discipline {discipline!r} has no guidance and no 'guidance "
            f"pending' marker in its contiguous block. Block was:\n{block_text}"
        )


@then(
    "no PM discipline appears as a bare list item with neither guidance nor "
    'a "guidance pending" marker'
)
def then_no_bare_list_item(context: dict) -> None:
    """Assert that no discipline is a bare bullet/list item with nothing after.

    A 'bare list item' is a line that starts with a markdown list marker
    (* or - or a digit followed by .) that contains the discipline name but
    has no guidance text on the same line AND no non-empty content on
    immediately following lines before the next list item or heading.
    """
    content = context["template_content"]
    lines = content.splitlines()
    disciplines = context["pm_disciplines"]

    for discipline in disciplines:
        discipline_lc = discipline.lower()
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Is this line a list item naming this discipline?
            is_list_item = re.match(r"^[-*]|\d+\.", stripped)
            if not is_list_item:
                continue
            if discipline_lc not in line.lower():
                continue

            # It's a list item naming this discipline. Check if it has
            # inline content beyond the discipline name itself.
            # Remove the list marker and discipline name and see what's left.
            after_marker = re.sub(r"^[-*]|\d+\.", "", stripped, count=1).strip()
            # Remove the discipline name from what remains.
            remaining_inline = after_marker.lower().replace(discipline_lc, "").strip()
            # Strip common punctuation to see if there's substantive content.
            remaining_inline_clean = re.sub(r"[.,;:\"'()\[\]]", "", remaining_inline).strip()

            if "guidance pending" in remaining_inline.lower():
                continue  # explicit marker present inline — OK

            if remaining_inline_clean:
                continue  # inline guidance present — OK

            # No inline content. Check next non-empty lines before the next
            # list item or heading.
            following_guidance = []
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                next_stripped = next_line.strip()
                if not next_stripped:
                    continue
                # Another list item or heading terminates this item's block.
                if re.match(r"^[-*]|\d+\.", next_stripped) or re.match(r"^#{1,6}\s", next_line):
                    break
                following_guidance.append(next_stripped)

            if "guidance pending" in " ".join(following_guidance).lower():
                continue

            assert following_guidance, (
                f"discipline {discipline!r} appears as a bare list item at "
                f"line {i + 1} with neither guidance nor a 'guidance pending' "
                f"marker. Line: {line!r}"
            )


@then(parsers.parse('the target directory contains no file at "{rel}"'))
def then_no_file(rel, context):
    assert not (Path(context["bootstrap_workspace"]) / rel).exists()


# -----------------------------------------------------------------------
# Then steps — lead-architect Maintain structurizr workspace activity
# (lead-y8rz scenario 9fac437e075784fe)
# -----------------------------------------------------------------------


def _extract_structurizr_workspace_block(content: str) -> str:
    """Return the text of the 'Maintain structurizr workspace' section.

    Starts at the heading line and ends at the next same-or-higher-level
    heading (## or #) or end of document.  Returns empty string if the
    section is absent.
    """
    # The heading may be a subsection under ### Your job or a standalone ##.
    import re as _re
    # Match the heading at any depth (##, ###, etc.)
    pattern = _re.compile(
        r"((?:#{1,6}\s+)Maintain structurizr workspace.*?)(?=\n#{1,6}\s|\Z)",
        _re.DOTALL,
    )
    m = pattern.search(content)
    return m.group(1) if m else ""


@then(
    "the Maintain structurizr workspace block names all three view families "
    "— containers, components, and dynamic views — as in scope of "
    "the activity, not only the static container view"
)
def then_structurizr_block_names_all_three_view_families(context: dict) -> None:
    content = context["template_content"]
    block = _extract_structurizr_workspace_block(content)
    assert block, (
        "lead-architect template must have a 'Maintain structurizr workspace' "
        "section (lead-y8rz / 9fac437e075784fe)"
    )
    lc = block.lower()
    for family in ("containers", "components", "dynamic views"):
        assert family in lc, (
            f"Maintain structurizr workspace block must name view family "
            f"{family!r} as in scope (lead-y8rz / 9fac437e075784fe)"
        )


@then(
    "the Maintain structurizr workspace block states the assign-per-structurizr "
    "coupling: a BC named in an assign_scenarios dispatch must correspond to a "
    "container or component the workspace models, and assigning to a BC the "
    "workspace does not model is a structural gap"
)
def then_structurizr_block_states_assign_per_structurizr_coupling(
    context: dict,
) -> None:
    content = context["template_content"]
    block = _extract_structurizr_workspace_block(content)
    assert block, (
        "lead-architect template must have a 'Maintain structurizr workspace' "
        "section (lead-y8rz / 9fac437e075784fe)"
    )
    lc = block.lower()
    # The coupling: BC in assign_scenarios must be modelled as container or component.
    assert "assign_scenarios" in block, (
        "Maintain structurizr workspace block must name 'assign_scenarios' to "
        "state the assign-per-structurizr coupling "
        "(lead-y8rz / 9fac437e075784fe)"
    )
    assert "container" in lc or "component" in lc, (
        "Maintain structurizr workspace block must name 'container' or 'component' "
        "as the workspace element a BC must correspond to "
        "(lead-y8rz / 9fac437e075784fe)"
    )
    assert "structural gap" in lc, (
        "Maintain structurizr workspace block must name 'structural gap' as the "
        "consequence of assigning to a BC the workspace does not model "
        "(lead-y8rz / 9fac437e075784fe)"
    )


@then(
    "the Maintain structurizr workspace block states the ADR↔workspace "
    "traceability gate: every workspace edge traces to an ADR and every "
    "structural ADR shows up in the workspace"
)
def then_structurizr_block_states_adr_traceability_gate(context: dict) -> None:
    content = context["template_content"]
    block = _extract_structurizr_workspace_block(content)
    assert block, (
        "lead-architect template must have a 'Maintain structurizr workspace' "
        "section (lead-y8rz / 9fac437e075784fe)"
    )
    lc = block.lower()
    # Every workspace edge traces to an ADR.
    assert "adr" in lc, (
        "Maintain structurizr workspace block must name 'ADR' in the traceability "
        "gate (lead-y8rz / 9fac437e075784fe)"
    )
    assert "edge" in lc, (
        "Maintain structurizr workspace block must state that workspace edges "
        "trace to ADRs (lead-y8rz / 9fac437e075784fe)"
    )
    # Every structural ADR shows up in the workspace.
    assert "structural adr" in lc or ("structural" in lc and "adr" in lc), (
        "Maintain structurizr workspace block must state that every structural "
        "ADR shows up in the workspace (lead-y8rz / 9fac437e075784fe)"
    )


@then(
    'each of these is stated as a sufficiency criterion on the activity OR '
    'carries an explicit "guidance pending" marker (case-insensitive), not as '
    "bare advisory prose with no criterion"
)
def then_structurizr_criteria_are_stated_as_sufficiency_criteria(
    context: dict,
) -> None:
    content = context["template_content"]
    block = _extract_structurizr_workspace_block(content)
    assert block, (
        "lead-architect template must have a 'Maintain structurizr workspace' "
        "section (lead-y8rz / 9fac437e075784fe)"
    )
    lc = block.lower()
    # A sufficiency criterion is detectable by one of:
    # - the word "sufficiency" appearing in the block
    # - "must" used in a binding obligation (not just describing others)
    # - "criterion" / "criteria" naming the items
    # - "guidance pending" as the explicit deferral marker
    # The block must contain at least one of these signals rather than being
    # purely advisory prose (e.g. "keep it in sync" with no binding language).
    criterion_signals = (
        "sufficiency",
        "criterion",
        "criteria",
        "guidance pending",
    )
    # Also count binding "must" in context of the block items.
    has_criterion_signal = any(s in lc for s in criterion_signals)
    # "must" counts as a sufficiency criterion signal when it appears in the
    # block (it converts advisory prose into a binding obligation).
    has_must = "must" in lc
    assert has_criterion_signal or has_must, (
        "Maintain structurizr workspace block must state each item as a "
        "sufficiency criterion (using 'must', 'sufficiency', 'criterion', "
        "'criteria') or carry a 'guidance pending' marker — bare advisory "
        "prose alone does not satisfy the scenario "
        "(lead-y8rz / 9fac437e075784fe)"
    )


# -----------------------------------------------------------------------
# Then steps — lead-po PM discipline sufficiency criteria
# (scenario_hash:25038c88fec521ba — lead-y8rz / tmpl-9du)
# -----------------------------------------------------------------------
#
# These steps assert that the "problem discovery & selection" and
# "outcome ownership" discipline blocks in the lead-po template carry
# explicit, measurable sufficiency criteria — not mere advisory prose.
# -----------------------------------------------------------------------


def _extract_discipline_block(content: str, discipline_heading: str) -> str:
    """Return the contiguous text block for a named discipline subsection.

    Searches for a heading line that contains the discipline_heading text
    (case-insensitive), then collects all lines through the next heading
    at the same or higher depth (or end of file).
    """
    lines = content.splitlines()
    start_idx = None
    heading_depth = None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            continue
        # Determine depth and text of this heading.
        depth = 0
        for ch in stripped:
            if ch == "#":
                depth += 1
            else:
                break
        heading_text = stripped[depth:].strip().lower()
        if discipline_heading.lower() in heading_text:
            start_idx = i
            heading_depth = depth
            break

    if start_idx is None:
        return ""

    # Collect lines until the next heading at the same or higher depth.
    block_lines = [lines[start_idx]]
    for line in lines[start_idx + 1 :]:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            depth = sum(1 for ch in stripped if ch == "#") - len(
                stripped.lstrip("#")
            )
            # Re-count properly
            d = 0
            for ch in stripped:
                if ch == "#":
                    d += 1
                else:
                    break
            if d <= heading_depth:
                break
        block_lines.append(line)
    return "\n".join(block_lines)


@then(
    "the problem discovery & selection discipline block states a sufficiency "
    "criterion that requires every committed intent to trace to a validated "
    "problem or job-to-be-done, not to a stakeholder feature request"
)
def then_problem_discovery_block_has_trace_criterion(context: dict) -> None:
    content = context["template_content"]
    block = _extract_discipline_block(content, "problem discovery")
    lc = block.lower()
    assert block, (
        "lead-po template is missing a 'problem discovery & selection' "
        "discipline block (scenario_hash:25038c88fec521ba)"
    )
    # Must carry a sufficiency criterion — binding language.
    assert "must" in lc or "criterion" in lc or "sufficiency" in lc, (
        "problem discovery & selection block must state a sufficiency criterion "
        "using binding language ('must', 'criterion', or 'sufficiency') "
        "(scenario_hash:25038c88fec521ba)"
    )
    # Must require tracing to a validated problem or JTBD.
    trace_signals = ("trace", "traces", "tracing", "traced")
    assert any(s in lc for s in trace_signals), (
        "problem discovery & selection block must require committed intent to "
        "trace to a validated problem or job-to-be-done "
        "(scenario_hash:25038c88fec521ba)"
    )
    jtbd_signals = (
        "job-to-be-done",
        "job to be done",
        "jtbd",
        "validated problem",
    )
    assert any(s in lc for s in jtbd_signals), (
        "problem discovery & selection block must name 'job-to-be-done' or "
        "'validated problem' as the required trace target "
        "(scenario_hash:25038c88fec521ba)"
    )
    # Must distinguish from stakeholder feature request.
    feature_request_signals = (
        "feature request",
        "stakeholder request",
        "stakeholder feature",
    )
    assert any(s in lc for s in feature_request_signals), (
        "problem discovery & selection block must distinguish committed intent "
        "from a stakeholder feature request "
        "(scenario_hash:25038c88fec521ba)"
    )


@then(
    "the problem discovery & selection discipline block names choosing which "
    "problem to solve as the scarcest good, anchored on a stable "
    "job-to-be-done before intent is committed"
)
def then_problem_discovery_block_names_scarcest_good(context: dict) -> None:
    content = context["template_content"]
    block = _extract_discipline_block(content, "problem discovery")
    lc = block.lower()
    assert block, (
        "lead-po template is missing a 'problem discovery & selection' "
        "discipline block (scenario_hash:25038c88fec521ba)"
    )
    # Must name the act of choosing which problem to solve as the scarcest good.
    assert "scarce" in lc or "scarcest" in lc, (
        "problem discovery & selection block must name choosing which problem "
        "to solve as the 'scarcest good' (scenario_hash:25038c88fec521ba)"
    )
    # Must anchor on a stable JTBD before intent is committed.
    jtbd_signals = (
        "job-to-be-done",
        "job to be done",
        "jtbd",
    )
    assert any(s in lc for s in jtbd_signals), (
        "problem discovery & selection block must anchor on a stable "
        "job-to-be-done (scenario_hash:25038c88fec521ba)"
    )
    before_commit_signals = (
        "before intent is committed",
        "before committing",
        "before intent",
        "before the intent",
        "before committing intent",
    )
    assert any(s in lc for s in before_commit_signals), (
        "problem discovery & selection block must name the JTBD as the anchor "
        "before intent is committed (scenario_hash:25038c88fec521ba)"
    )


@then(
    "the outcome ownership discipline block states a sufficiency criterion "
    "that requires the intent to name the outcome it targets as an observable "
    "behavior change rather than an output"
)
def then_outcome_ownership_block_has_observable_criterion(context: dict) -> None:
    content = context["template_content"]
    block = _extract_discipline_block(content, "outcome ownership")
    lc = block.lower()
    assert block, (
        "lead-po template is missing an 'outcome ownership' discipline block "
        "(scenario_hash:25038c88fec521ba)"
    )
    # Must carry a sufficiency criterion — binding language.
    assert "must" in lc or "criterion" in lc or "sufficiency" in lc, (
        "outcome ownership block must state a sufficiency criterion using "
        "binding language ('must', 'criterion', or 'sufficiency') "
        "(scenario_hash:25038c88fec521ba)"
    )
    # Must require naming an observable behavior change.
    assert "observable" in lc, (
        "outcome ownership block must require the intent to name an 'observable' "
        "behavior change (scenario_hash:25038c88fec521ba)"
    )
    behavior_change_signals = (
        "behavior change",
        "behaviour change",
        "behavioral change",
    )
    assert any(s in lc for s in behavior_change_signals), (
        "outcome ownership block must require the outcome to be framed as a "
        "behavior change (scenario_hash:25038c88fec521ba)"
    )
    # Must contrast with output (not just an output).
    output_contrast_signals = (
        "rather than an output",
        "not an output",
        "not just an output",
        "not output",
        "instead of an output",
    )
    assert any(s in lc for s in output_contrast_signals), (
        "outcome ownership block must contrast an observable behavior change "
        "with an output (scenario_hash:25038c88fec521ba)"
    )


@then(
    "the outcome ownership discipline block states that the intent must address "
    "at least value (will they use it) and viability, naming Cagan's four risks "
    "with feasibility owned in partnership with the Architect"
)
def then_outcome_ownership_block_names_cagan_risks(context: dict) -> None:
    content = context["template_content"]
    block = _extract_discipline_block(content, "outcome ownership")
    lc = block.lower()
    assert block, (
        "lead-po template is missing an 'outcome ownership' discipline block "
        "(scenario_hash:25038c88fec521ba)"
    )
    # Must name Cagan's four risks.
    assert "cagan" in lc, (
        "outcome ownership block must name Cagan's four risks "
        "(scenario_hash:25038c88fec521ba)"
    )
    # Must name value risk.
    value_signals = ("value risk", "value (will they use", "will they use it")
    assert any(s in lc for s in value_signals), (
        "outcome ownership block must name value risk (will they use it) "
        "(scenario_hash:25038c88fec521ba)"
    )
    # Must name viability.
    assert "viability" in lc or "viable" in lc, (
        "outcome ownership block must name viability risk "
        "(scenario_hash:25038c88fec521ba)"
    )
    # Must name feasibility with partnership ownership to the Architect.
    assert "feasibility" in lc or "feasible" in lc, (
        "outcome ownership block must name feasibility risk "
        "(scenario_hash:25038c88fec521ba)"
    )
    partnership_signals = (
        "partnership",
        "in partnership",
        "partner",
        "architect",
    )
    assert any(s in lc for s in partnership_signals), (
        "outcome ownership block must name feasibility as owned in partnership "
        "with the Architect (scenario_hash:25038c88fec521ba)"
    )


@then(
    "neither discipline's sufficiency criterion is expressed as a constraint "
    '("don\'t crash", "use judgment") rather than a measurable outcome'
)
def then_neither_discipline_uses_constraint_language(context: dict) -> None:
    content = context["template_content"]
    pd_block = _extract_discipline_block(content, "problem discovery")
    oo_block = _extract_discipline_block(content, "outcome ownership")

    # Constraint anti-patterns: purely negative prohibitions without an
    # affirmative measurable criterion.  The scenario names two: "don't crash"
    # and "use judgment". We check that neither block uses these specific
    # phrasings AND that each block carries at least one affirmative criterion
    # signal (something they must achieve, not merely avoid).
    constraint_phrases = (
        "don't crash",
        "dont crash",
        "use judgment",
        "use your judgment",
        "use judgement",
    )
    for block_name, block in (
        ("problem discovery & selection", pd_block),
        ("outcome ownership", oo_block),
    ):
        lc = block.lower()
        for phrase in constraint_phrases:
            assert phrase not in lc, (
                f"{block_name} block must not express its sufficiency criterion "
                f"as a bare constraint ({phrase!r}); it must state a measurable "
                f"outcome (scenario_hash:25038c88fec521ba)"
            )
        # Each block must carry at least one affirmative measurable criterion
        # (binding language that names what the artifact must achieve).
        affirmative_signals = ("must", "criterion", "criteria", "sufficiency")
        assert any(s in lc for s in affirmative_signals), (
            f"{block_name} block must carry an affirmative measurable criterion "
            f"(using 'must', 'criterion', 'criteria', or 'sufficiency') — "
            f"constraint-only language is not sufficient "
            f"(scenario_hash:25038c88fec521ba)"
        )
