"""bc-emit `_scenario_blocks` block-delimitation conformity with the ADR-019
canonical producer (tmpl-7ti; PIN 1 @scenario_hash:ea9c1bbd9be87d72; work_id
lead-rvdl).

DEFECT (long-standing tmpl-7ti): `_scenario_blocks` accumulated every tag line
it saw into `pending_tag` and never cleared it at the `Feature:` line, so the
feature-level `@`-tag lines that precede `Feature:` (e.g.
`@bc:shopsystem-messaging @origin:adr-020`) folded INTO the first-in-file
scenario's block. `scenarios.hash.compute_scenario_hash` drops only
`@scenario_hash:` lines — it keeps `@bc:`/`@origin:` tag lines — so the folded
feature-level tag survived canonicalization and the wrapper recomputed a hash
DIFFERENT from the ADR-019 block-only canonical producer, false-refusing an
otherwise-valid emit with `classification: STALE`. Because Check 3's staleness
precondition scanned across features/, one mis-delimited first-in-file scenario
blocked EVERY `bc-emit work-done` sign-off in the repo, forcing `--force`.

This regression pins that the wrapper's blockifier AGREES with the ADR-019
block-only canonical producer — specifically for FIRST-in-file scenarios whose
feature line carries feature-level `@`-tags, the exact fold-in trap — mirroring
tests/test_scenario_hash_tag_invariant.py's use of the block-only canonical per
`shop_msg.cli._build_scenario_payload`. Both wrapper pins continue to hold
(conformance, not a re-pin):

  PIN 1 @scenario_hash:ea9c1bbd9be87d72 — the block passed to
        compute_scenario_hash is the Scenario:/Scenario Outline: keyword line
        through the last step/Examples line, EXCLUDING the Feature: line and ALL
        @-prefixed tag lines.
  PIN 2 @scenario_hash:aabbc009bad6fe86 — Check 3 is scoped to the dispatch's
        own assigned scenario set.

The two independently-confirmed demonstrations are mirrored below as fixtures:
launcher 20b7a66364a26404 (first-in-file, feature `@`-tags) and messaging
b1fbd8070695aa52 (feature line `@bc:shopsystem-messaging @origin:adr-020`).
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

import scenarios.hash as scenarios_hash
from scenarios.feature import iter_scenarios
from shop_msg.cli import _build_scenario_payload

_COMPUTE = scenarios_hash.compute_scenario_hash

# Load the module under test FROM THIS WORKTREE's source by file path (not the
# ambient editable install, which may resolve to a sibling checkout).
_BC_EMIT_SRC = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "shop_templates"
    / "bc_emit.py"
)
_spec = importlib.util.spec_from_file_location(
    "_bc_emit_blockify_under_test", _BC_EMIT_SRC
)
bc_emit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bc_emit)  # type: ignore[union-attr]


# A first-in-file scenario body (Scenario keyword line + steps, no tags).
_FIRST_BODY = (
    "  Scenario: the first-in-file scenario\n"
    "    Given an abstract address\n"
    "    When it is registered\n"
    "    Then it resolves to a concrete endpoint"
)

# A second scenario carrying its own non-@scenario_hash tag on a separate line,
# to prove per-scenario tags are excluded from the block too (not just
# feature-level ones).
_SECOND_BODY = (
    "  Scenario Outline: a second scenario with its own tag\n"
    "    Given <input>\n"
    "    When processed\n"
    "    Then <result>\n"
    "  Examples:\n"
    "    | input | result |\n"
    "    | a     | ok     |"
)


def _feature_with_feature_level_tags(first_hash: str, second_hash: str) -> str:
    """A feature file whose FEATURE line is preceded by feature-level @-tags —
    the exact fold-in trap (messaging b1fbd8070695aa52 shape)."""
    return (
        "@bc:shopsystem-messaging @origin:adr-020\n"
        "Feature: Abstract address registry\n"
        "  A short description line.\n"
        "\n"
        f"  @scenario_hash:{first_hash} @bc:shopsystem-messaging\n"
        f"{_FIRST_BODY}\n"
        "\n"
        f"  @wip\n"
        f"  @scenario_hash:{second_hash} @bc:shopsystem-messaging\n"
        f"{_SECOND_BODY}\n"
    )


def test_first_in_file_feature_tagged_scenario_recomputes_to_canonical():
    """PIN 1 conformance: the wrapper's blockifier recomputes the first-in-file
    scenario (whose feature line carries feature-level @-tags) to the SAME
    block-only canonical hash the ADR-019 producer computes — the feature-level
    @-tags are NOT folded into the block."""
    first_hash = _COMPUTE(_FIRST_BODY)
    second_hash = _COMPUTE(_SECOND_BODY)
    feature_text = _feature_with_feature_level_tags(first_hash, second_hash)

    blocks = bc_emit._scenario_blocks(feature_text)

    # One (block_text, carried) per scenario, in file order, aligned with the
    # canonical splitter iter_scenarios.
    canonical = list(iter_scenarios(feature_text))
    assert [c for _b, c in blocks] == [h for h, _t in canonical], (
        "carried hashes must match the canonical iter_scenarios association"
    )

    recomputes = [_COMPUTE(block_text) for block_text, _c in blocks]
    assert recomputes == [first_hash, second_hash], (
        "wrapper blockifier folded the Feature line / feature-level or "
        f"per-scenario @-tags into a block: recomputes={recomputes} but the "
        f"block-only canonical is {[first_hash, second_hash]}"
    )

    # Each carried on-disk tag reproduces via the wrapper's own recompute — no
    # false STALE.
    for (block_text, carried) in blocks:
        assert carried == _COMPUTE(block_text), (
            f"carried tag {carried} does not reproduce via the wrapper "
            f"blockifier recompute {_COMPUTE(block_text)}"
        )


def test_wrapper_agrees_with_build_scenario_payload_producer():
    """The wrapper blockifier agrees with the canonical producer
    `_build_scenario_payload` (the same producer
    tests/test_scenario_hash_tag_invariant.py trusts) even when the scenario is
    first-in-file under a feature-tagged Feature header."""
    with tempfile.TemporaryDirectory() as d:
        body_path = Path(d) / "body.txt"
        body_path.write_text(_FIRST_BODY + "\n")
        payload = _build_scenario_payload(
            str(body_path), "Abstract address registry", "shopsystem-messaging"
        )

    # Place the producer's exact block (with its @scenario_hash tag) first in a
    # feature file that ALSO carries feature-level tags on the pre-Feature line.
    feature_text = (
        "@bc:shopsystem-messaging @origin:adr-020\n"
        "Feature: Abstract address registry\n"
        "\n"
        f"{payload.gherkin}"
    )
    blocks = bc_emit._scenario_blocks(feature_text)
    assert len(blocks) == 1
    block_text, carried = blocks[0]
    assert carried == payload.hash, (
        f"carried {carried} != producer hash {payload.hash}"
    )
    assert _COMPUTE(block_text) == payload.hash, (
        f"wrapper recompute {_COMPUTE(block_text)} != producer hash "
        f"{payload.hash} — the feature-level tags were folded into the block"
    )


def test_check_scenario_hashes_passes_in_scope_first_in_file_feature_tagged():
    """PIN 1 + PIN 2 end-to-end: an in-scope first-in-file scenario under a
    feature-tagged Feature header PASSES Check 3 without refusing — the exact
    case that false-refused STALE all session."""
    first_hash = _COMPUTE(_FIRST_BODY)
    second_hash = _COMPUTE(_SECOND_BODY)
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        features = repo / "features"
        features.mkdir()
        (features / "abstract_address_registry_adr020.feature").write_text(
            _feature_with_feature_level_tags(first_hash, second_hash)
        )
        # The dispatch's own assigned set names the first-in-file hash. With the
        # fold-in defect this recomputed to a spurious value and refused STALE.
        bc_emit.check_scenario_hashes(repo, "lead-rvdl", [first_hash])
