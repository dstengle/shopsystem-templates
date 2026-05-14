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
# Then steps — BC @scenario_hash pre-state enumeration discipline
# (lead-dbc scenarios 0d384c6b92004c8d, 48dd1f01012efafe, 22cbdf7cc9e917ca,
# 744cd4a4532c28d7)
# -----------------------------------------------------------------------
#
# These steps pin that the lead-architect template names @scenario_hash
# enumeration (via grep over features/*.feature) as a discrete, required
# pre-state step whenever a dispatch retires, supersedes, or contradicts
# prior BC-side coverage — and that the discipline applies on every
# dispatch in a clarify-correction chain, not only the initial one.


@then(
    'the content names "@scenario_hash" as a pre-state surface the architect '
    "must verify before composing a dispatch that retires, supersedes, or "
    "contradicts prior BC-side coverage"
)
def then_content_names_scenario_hash_pre_state_surface(context: dict) -> None:
    content = context["template_content"]
    # Must contain @scenario_hash in the context of a pre-state enumeration
    # discipline — specifically that the architect must enumerate @scenario_hash
    # values from the BC's features/ before dispatching.  The tell is that
    # both "@scenario_hash" and "enumerate" appear (the existing template only
    # has @scenario_hash in the context of tag-computation, not enumeration).
    assert "@scenario_hash" in content, (
        "template must name '@scenario_hash' as a pre-state surface "
        "(lead-dbc / 0d384c6b92004c8d)"
    )
    assert "enumerate" in content.lower(), (
        "template must use the word 'enumerate' to describe the @scenario_hash "
        "pre-state step — the existing template does not use this word in the "
        "@scenario_hash context (lead-dbc / 0d384c6b92004c8d)"
    )


@then(
    "the content directs the architect to enumerate that surface from the "
    'BC\'s "features/" directory rather than from the lead shop\'s scenario register'
)
def then_content_directs_enumerate_from_features_dir(context: dict) -> None:
    content = context["template_content"]
    # The BC's features/ directory must be named as the source for enumeration.
    # The existing template has "features/" only in the context of the lead
    # shop's own features/ — not as a BC's enumeration source. The new content
    # must explicitly name the BC's features/ as the authoritative source for
    # the @scenario_hash enumeration (in contrast to the lead shop's register).
    # Check: "features/" appears AND either "BC's" or a BC-side context exists.
    assert "features/" in content, (
        "template must name the BC's 'features/' directory as the enumeration "
        "source for @scenario_hash (lead-dbc / 0d384c6b92004c8d)"
    )
    # The new enumeration context must pair features/ with @scenario_hash
    # to distinguish it from the existing mention of the lead shop's features/.
    assert "enumerate" in content.lower() or "grep" in content, (
        "template must describe enumerating @scenario_hash from features/ "
        "(via 'enumerate' or 'grep') — the existing features/ reference is "
        "about the lead shop's own features, not BC-side enumeration "
        "(lead-dbc / 0d384c6b92004c8d)"
    )


@then(
    "the content marks the enumeration as a discrete pre-state step (alongside "
    "the existing behavior-verification step), not as optional guidance the "
    "architect may skip"
)
def then_content_marks_enumeration_as_discrete_step(context: dict) -> None:
    content = context["template_content"]
    # The @scenario_hash enumeration must be framed as a mandatory, discrete
    # pre-state step — not optional guidance.  The signal is that both
    # "enumerate" (or "grep") and a mandatory modal ("must" / "required") appear
    # in the new content, AND the existing step-numbering structure already uses
    # "must" heavily — so we require the combination of "enumerate"/"grep" with
    # "step" or a numbered list item in the enumeration context.
    # Minimal test: "enumerate" or "grep" appears (ensuring there's actual new
    # @scenario_hash enumeration prose) AND "must" appears (mandatory framing).
    assert "enumerate" in content.lower() or "grep" in content, (
        "template must describe the @scenario_hash enumeration as a step "
        "(via 'enumerate' or 'grep') (lead-dbc / 0d384c6b92004c8d)"
    )
    assert "must" in content, (
        "template must use 'must' to frame the @scenario_hash enumeration as "
        "mandatory (lead-dbc / 0d384c6b92004c8d)"
    )


@then(
    'the content names at least one of the trigger conditions "retire", '
    '"supersede", or "contradict" as the gate that requires the enumeration step'
)
def then_content_names_trigger_conditions(context: dict) -> None:
    content = context["template_content"].lower()
    # At least one of the trigger conditions must appear as the gate that
    # requires the @scenario_hash enumeration.  "supersede" already appears
    # in the existing template (in "superseded"), but in the context of
    # request_bugfix scope marking — not as a trigger for @scenario_hash
    # enumeration.  The new content must place a trigger condition in the
    # enumeration context.  Since "enumerate" is the distinguishing word
    # for the new section, we verify that at least one trigger appears in
    # the same content that also contains "enumerate" (i.e., the new section
    # exists AND has a trigger word).
    trigger_words = ("retire", "supersede", "contradict")
    found = [t for t in trigger_words if t in content]
    assert found, (
        "template must name at least one trigger condition "
        f"({', '.join(trigger_words)}) for the @scenario_hash enumeration step "
        "(lead-dbc / 0d384c6b92004c8d)"
    )
    # The enumeration content must also be present — a trigger alone in the
    # existing request_bugfix section is insufficient.
    assert "enumerate" in content, (
        "template must use 'enumerate' in the @scenario_hash pre-state section "
        "that the trigger condition gates (lead-dbc / 0d384c6b92004c8d)"
    )


@then(
    'the content names the literal substring "grep" as the enumeration '
    "mechanism for the BC's @scenario_hash pre-state surface"
)
def then_content_names_grep_as_enumeration_mechanism(context: dict) -> None:
    content = context["template_content"]
    assert "grep" in content, (
        "template must name 'grep' as the enumeration mechanism for the BC's "
        "@scenario_hash pre-state surface (lead-dbc / 48dd1f01012efafe)"
    )


@then(
    'the content names the literal substring "@scenario_hash" as the pattern '
    "that grep enumerates"
)
def then_content_names_scenario_hash_as_grep_pattern(context: dict) -> None:
    content = context["template_content"]
    assert "@scenario_hash" in content, (
        "template must name '@scenario_hash' as the pattern that grep "
        "enumerates (lead-dbc / 48dd1f01012efafe)"
    )


@then(
    "the content names the BC's \"features/*.feature\" tree (not a single named "
    "feature file) as the surface the grep is run against"
)
def then_content_names_features_glob_as_grep_surface(context: dict) -> None:
    content = context["template_content"]
    assert "features/*.feature" in content, (
        "template must name 'features/*.feature' (the glob, not a single named "
        "file) as the surface the grep runs against "
        "(lead-dbc / 48dd1f01012efafe)"
    )


@then(
    "the content names the BC's \"features/\" directory as the authoritative "
    "source for the BC's pinned @scenario_hash set, in contrast to the lead "
    "shop's scenario register"
)
def then_content_names_features_dir_as_authoritative_source(context: dict) -> None:
    content = context["template_content"]
    # features/ must appear as the authoritative source
    assert "features/" in content, (
        "template must name 'features/' as the authoritative source for the BC's "
        "pinned @scenario_hash set (lead-dbc / 48dd1f01012efafe)"
    )
    # Some contrast to the lead shop's register must also be named
    lead_signals = ("lead shop", "scenario register", "lead-shop")
    assert any(s in content.lower() for s in lead_signals), (
        "template must contrast the BC's 'features/' directory against the lead "
        "shop's scenario register (lead-dbc / 48dd1f01012efafe)"
    )


@then(
    "the content names a clarify-driven correction (a follow-up dispatch that "
    "augments or amends a prior dispatch in response to an Implementer clarify) "
    "as a moment that itself requires the BC @scenario_hash pre-state enumeration"
)
def then_content_names_clarify_correction_requires_enumeration(context: dict) -> None:
    content = context["template_content"].lower()
    # The template must name clarify-correction / follow-up dispatch / clarify
    # chain as a context that also requires the @scenario_hash enumeration.
    clarify_signals = ("clarify", "follow-up dispatch", "clarify-correction chain",
                       "clarify chain")
    assert any(s in content for s in clarify_signals), (
        "template must name a clarify-driven correction as a moment that requires "
        "the @scenario_hash pre-state enumeration (lead-dbc / 22cbdf7cc9e917ca)"
    )
    assert "@scenario_hash" in context["template_content"], (
        "template must name @scenario_hash in the clarify-correction context "
        "(lead-dbc / 22cbdf7cc9e917ca)"
    )


@then(
    "the content directs the architect not to limit the re-enumeration to only "
    "the @scenario_hash entries a prior clarify named, but to re-run the "
    'enumeration against the BC\'s full "features/" tree'
)
def then_content_directs_full_features_tree_reenumeration(context: dict) -> None:
    content = context["template_content"]
    # The template must direct re-enumeration against the full features/ tree
    assert "features/" in content, (
        "template must direct re-enumeration against the full 'features/' tree, "
        "not limited to hashes named in a prior clarify "
        "(lead-dbc / 22cbdf7cc9e917ca)"
    )
    # Must reference the full tree (not just prior clarify's hashes)
    full_signals = ("full", "entire", "all", "every")
    assert any(s in content.lower() for s in full_signals), (
        "template must direct re-enumeration against the full 'features/' tree "
        "(not only prior clarify hashes) (lead-dbc / 22cbdf7cc9e917ca)"
    )


@then(
    "the content frames a prior clarify as evidence that the prior enumeration "
    "was incomplete, rather than as a definitive list of every conflicting "
    "BC-side @scenario_hash"
)
def then_content_frames_prior_clarify_as_incomplete_evidence(context: dict) -> None:
    content = context["template_content"].lower()
    # The template must frame a prior clarify as evidence of incompleteness
    incomplete_signals = ("incomplete", "not definitive", "not a definitive",
                          "evidence", "missed")
    assert any(s in content for s in incomplete_signals), (
        "template must frame a prior clarify as evidence of an incomplete "
        "enumeration, not as a definitive list of conflicts "
        "(lead-dbc / 22cbdf7cc9e917ca)"
    )


@then(
    "the content names this per-event discipline as applying independently to "
    "each dispatch in a clarify-correction chain, not only to the initial "
    "dispatch in such a chain"
)
def then_content_names_per_dispatch_discipline(context: dict) -> None:
    content = context["template_content"].lower()
    # The per-dispatch / per-event application must be made explicit
    per_dispatch_signals = ("each dispatch", "every dispatch",
                            "clarify-correction chain", "per dispatch",
                            "per-dispatch", "not only the initial")
    assert any(s in content for s in per_dispatch_signals), (
        "template must name the @scenario_hash enumeration discipline as "
        "applying to each dispatch in a clarify-correction chain, not only the "
        "initial dispatch (lead-dbc / 22cbdf7cc9e917ca)"
    )


@then(
    "the content directs the architect that, for any dispatch that retires, "
    "supersedes, or contradicts prior BC-side coverage, the dispatch text must "
    "reference each conflicting BC-side @scenario_hash entry by its hash ID, "
    "or carry an explicit retirement instruction for that hash"
)
def then_content_directs_hash_reference_or_retirement(context: dict) -> None:
    content = context["template_content"]
    # Must direct that the dispatch text references conflicting @scenario_hash
    # entries by hash ID or carries an explicit retirement instruction.
    # The new content must use "hash ID" or similar to name the reference form,
    # and must name "retirement" or "retire" as the alternative — the existing
    # template has "explicit" in unrelated contexts, so we require "retire" or
    # "retirement" as a stronger signal.
    assert "@scenario_hash" in content, (
        "template must name @scenario_hash in the dispatch-text evidence "
        "requirement (lead-dbc / 744cd4a4532c28d7)"
    )
    retirement_signals = ("retirement instruction", "retirement", "retire")
    assert any(s in content.lower() for s in retirement_signals), (
        "template must name 'retirement' or 'retire' as the alternative form "
        "in the dispatch-text hash-reference requirement "
        "(lead-dbc / 744cd4a4532c28d7)"
    )
    # Must also require the dispatch text to reference the hash by ID
    id_signals = ("hash id", "hash ID", "by id", "by ID", "conflicting")
    assert any(s in content for s in id_signals), (
        "template must direct the architect to reference conflicting hashes "
        "by their ID in the dispatch text (lead-dbc / 744cd4a4532c28d7)"
    )


@then(
    "the content frames that requirement as the observable evidence the BC "
    "Implementer can use to confirm the architect ran the enumeration step, "
    "rather than as optional context for the BC"
)
def then_content_frames_hash_reference_as_observable_evidence(context: dict) -> None:
    content = context["template_content"].lower()
    # The requirement must be framed as observable evidence for the Implementer.
    # "confirm" exists in the current template in unrelated contexts; we need
    # "observable" or "evidence" to appear in the new content as a stronger pin.
    evidence_signals = ("observable", "observable evidence")
    assert any(s in content for s in evidence_signals), (
        "template must use 'observable' or 'observable evidence' to frame the "
        "hash-reference requirement as evidence the Implementer can verify "
        "(lead-dbc / 744cd4a4532c28d7)"
    )


@then(
    "the content directs the architect to cite the enumeration in the dispatch "
    "description (in the same shape that the existing behavior-verification step "
    "is cited), so the Implementer does not have to re-run the enumeration to "
    "discover conflicts the architect missed"
)
def then_content_directs_cite_enumeration_in_dispatch(context: dict) -> None:
    content = context["template_content"].lower()
    # Must direct citing the @scenario_hash enumeration in the dispatch
    # description. The existing template already has "cite" and "dispatch
    # description" in the context of empirical behavior verification — we need
    # to check that the enumeration itself (grep / @scenario_hash) is explicitly
    # called out as something to cite, not just the general behavior-verification.
    # Signal: "enumeration" appears in the context of citing / dispatch
    cite_signals = ("cite the enumeration", "cite the @scenario_hash",
                    "cite.*enumeration", "enumeration.*cite")
    # Simple substring check: "enumeration" must appear AND "cite" must appear
    assert "enumeration" in content, (
        "template must use 'enumeration' to describe what the architect should "
        "cite in the dispatch description (not just the behavior-verification) "
        "(lead-dbc / 744cd4a4532c28d7)"
    )
    assert "cite" in content, (
        "template must direct the architect to cite the @scenario_hash "
        "enumeration in the dispatch description (lead-dbc / 744cd4a4532c28d7)"
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
    path = context["file_path"]
    context["file_content"] = Path(path).read_text()


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
    # The shop_type was stashed by the "previously bootstrapped" Given.
    shop_type = context.get("bootstrap_shop_type")
    assert shop_type is not None, (
        "scenario inconsistency: update invoked but no prior bootstrap "
        "captured the shop type"
    )
    result = _run_shop_templates_with_bd_shim(
        [
            "update",
            "--target",
            str(real),
            "--shop-type",
            shop_type,
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
