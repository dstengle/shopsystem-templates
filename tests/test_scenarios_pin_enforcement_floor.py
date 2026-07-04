"""ADR-056 enforcement-floor scenarios pin (work_id lead-vzxd.10, tmpl-3ip).

The bin/doctor coherence gate (ADR-047) and the bc-emit changed-feature
schema-conformity gate (ADR-042) both depend on scenarios v0.3.1 surface —
`validate --aggregate`, the 3-dimension @bc/@origin/@scenario_hash schema, the
@bc_internal exemption, and the E_STRAY_GHERKIN guard. So the shop-templates
`[project].dependencies` scenarios pin must resolve to at least v0.3.1, else a
clean install of shop-templates into a launched BC would resolve a scenarios
build that lacks the enforcement surface.
"""
from __future__ import annotations

import re
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _scenarios_pin() -> str:
    text = PYPROJECT.read_text()
    m = re.search(r'"(scenarios @ git\+[^"]+)"', text)
    assert m, f"no VCS-pinned scenarios dependency found in {PYPROJECT}"
    return m.group(1)


def test_scenarios_pin_is_at_least_v0_3_1() -> None:
    pin = _scenarios_pin()
    m = re.search(r"@v(\d+)\.(\d+)\.(\d+)", pin)
    assert m, f"scenarios pin does not carry a @vX.Y.Z tag ref: {pin!r}"
    version = tuple(int(g) for g in m.groups())
    assert version >= (0, 3, 1), (
        "the scenarios pin must be at least v0.3.1 (the ADR-056 enforcement "
        f"floor: validate --aggregate / E_STRAY_GHERKIN / 3-dimension schema); "
        f"got {pin!r}"
    )
