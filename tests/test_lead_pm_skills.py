"""PDR-033 Wave 2 (lead-kz33): the six graduated PM skills are canonical lead
skill-group members, are poured by the lead bootstrap into
.claude/skills/<skill>/SKILL.md, and each SKILL.md names its terminal artifact
for the lead-pm mode.

Direct-unit companion to the BDD scenarios ebc6436bdbeea485 (membership +
byte-for-byte access surface) and fd2e4444df9913e2 (bootstrap pour + terminal
artifact naming) in features/lead_skill_group.feature. The mode -> skill ->
terminal-artifact map is fixed by lead-pm.md scenario 657c435f.
"""
from pathlib import Path

import pytest

from shop_templates.cli import (
    canonical_skill_group,
    iter_lead_skill_files,
    _pour_skills,
)

# skill -> the exact terminal-artifact phrase each SKILL.md must name.
GRADUATED_PM_SKILLS = {
    "discovery-dialogue": "intent record",
    "shaping": "candidate driven to shaped",
    "option-tradeoff": "PDR draft or candidate fork",
    "prioritization": "prioritization record",
    "problem-space-mapping": "problem-space map revision",
    "product-narrative": "README, site, or current-state revision",
}


@pytest.mark.parametrize("skill", sorted(GRADUATED_PM_SKILLS))
def test_graduated_skill_is_lead_group_member_with_byte_for_byte_body(skill):
    """The access surface reports each graduated PM skill as a canonical lead
    skill-group member and returns its SKILL.md package-data bytes exactly."""
    group = dict(canonical_skill_group("lead"))
    assert skill in group, (
        f"{skill!r} is not a reported canonical lead skill-group member; "
        f"members: {sorted(group)}"
    )
    shipped = dict(iter_lead_skill_files())
    rel = f"{skill}/SKILL.md"
    assert rel in shipped, f"{skill!r} ships no package-data SKILL.md"
    assert group[skill] == shipped[rel], (
        f"{skill!r} access-surface bytes differ from package data"
    )


@pytest.mark.parametrize("skill,artifact", sorted(GRADUATED_PM_SKILLS.items()))
def test_lead_pour_writes_graduated_skill_naming_terminal_artifact(
    skill, artifact, tmp_path
):
    """The lead skill-group pour writes .claude/skills/<skill>/SKILL.md and its
    body names the skill's terminal artifact for the lead-pm mode."""
    _pour_skills(tmp_path, iter_lead_skill_files)
    poured = tmp_path / ".claude" / "skills" / skill / "SKILL.md"
    assert poured.is_file(), (
        f"lead pour did not write {poured} for graduated PM skill {skill!r}"
    )
    body = poured.read_text()
    assert artifact.lower() in body.lower(), (
        f".claude/skills/{skill}/SKILL.md does not name its terminal artifact "
        f"{artifact!r} for the lead-pm mode"
    )
