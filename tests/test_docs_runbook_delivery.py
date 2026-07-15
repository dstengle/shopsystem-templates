"""Regression guard for the canonical beads Dolt schema-skew recovery runbook
shipping as shop-templates distributed package data and being delivered to
every BC via the same pour mechanism BCs already use to receive canonical
content (`shop-templates update`). (request_maintenance lead-pq9ex.)

shopsystem-bc-launcher authored `docs/runbooks/beads-schema-skew-recovery.md`
while recovering its own tracker from the fleet-wide #4259 schema-skew wall
(mechanism_observation shopsystem_bc_launcher-jbam). That runbook must stop
living in one BC's private repo and become canonical content shipped to EVERY
BC — reachable via the same importlib.resources package-data + update-pour
mechanism the skill tree, fabro skeleton, and canonical primer ride.

ACCEPTANCE CRITERIA (from the dispatch — this is what these tests prove):
  docs/runbooks/beads-schema-skew-recovery.md ships as part of
  shopsystem-templates' distributed package data, reachable by every BC via
  the same mechanism BCs already use to receive canonical docs (per
  `shop-templates show` / `shop-templates update`). No BC-specific paths
  hardcoded in the shipped content.
"""
import argparse
import tomllib
from importlib.resources import files
from pathlib import Path

from shop_templates.cli import _cmd_update, iter_doc_files, read_doc_file

# The canonical runbook's relative path, rooted at the docs package-data subtree
# (templates/docs/) AND at a BC's on-disk docs/ directory after the pour.
_RUNBOOK_REL = "runbooks/beads-schema-skew-recovery.md"

_DOCS_PKG = "shop_templates.templates.docs"

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _minimal_bc_shop(target: Path, shop_name: str = "shopsystem-templates") -> None:
    """Lay down the minimal bc-shop identity surface `update` reads."""
    shop_dir = target / ".claude" / "shop"
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "type.md").write_text("bc\n")
    (shop_dir / "name.md").write_text(f"{shop_name}\n")


def test_runbook_ships_as_distributed_package_data():
    """The runbook resolves via importlib.resources from the docs package-data
    subtree — i.e. it rides the sdist+wheel and is reachable exactly as the
    skill tree / fabro skeleton are (served from package data, never from a
    known filesystem path)."""
    resource = files(_DOCS_PKG)
    for part in _RUNBOOK_REL.split("/"):
        resource = resource / part
    assert resource.is_file(), (
        "the runbook must resolve as importlib.resources package data under "
        f"{_DOCS_PKG}/{_RUNBOOK_REL}"
    )
    body = resource.read_text()
    assert body.strip(), "the shipped runbook must be non-empty"

    # And the public read helper returns the same bytes (the read analogue of
    # read_starter_file / read_ops_template for the docs subtree).
    assert read_doc_file(_RUNBOOK_REL) == body


def test_runbook_enumerated_by_iter_doc_files():
    """The canonical docs iterator (the docs analogue of iter_skill_files /
    iter_fabro_asset_files) enumerates the runbook, so the update pour that
    walks it delivers the runbook to every BC."""
    rels = {rel for rel, _body in iter_doc_files()}
    assert _RUNBOOK_REL in rels, (
        f"iter_doc_files must enumerate {_RUNBOOK_REL}; got {sorted(rels)}"
    )


def test_runbook_declared_in_package_data():
    """pyproject declares a package-data glob covering templates/docs/** so the
    runbook actually rides the built sdist+wheel (the lead-5mr5 lesson: a
    subtree not declared in package-data pours empty in a real install)."""
    pyproject = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())
    globs = pyproject["tool"]["setuptools"]["package-data"]["shop_templates"]
    assert any(g.startswith("templates/docs/") for g in globs), (
        "pyproject [tool.setuptools.package-data] must declare a "
        f"templates/docs/ glob; got {globs}"
    )


def test_update_pours_runbook_into_bc_docs(tmp_path):
    """`shop-templates update --target <bc>` delivers the canonical runbook to
    the BC's docs/runbooks/ — the SAME pour path BCs already use to receive
    canonical content. Byte-equal to the shipped package data."""
    target = tmp_path / "bc-shop"
    target.mkdir()
    _minimal_bc_shop(target)

    poured = target / "docs" / _RUNBOOK_REL
    assert not poured.exists(), "precondition: runbook absent before update"

    rc = _cmd_update(argparse.Namespace(target=str(target), shop_type=None))
    assert rc == 0, "update must exit 0"

    assert poured.is_file(), (
        "update must pour the runbook into the BC's docs/runbooks/"
    )
    assert poured.read_text() == read_doc_file(_RUNBOOK_REL), (
        "the poured runbook must be byte-equal to the shipped package data"
    )


def test_update_leaves_shop_authored_docs_untouched(tmp_path):
    """docs/ is NOT a fully canonical-managed tree (unlike .claude/skills/):
    the docs pour writes only the canonical set and never prunes or clobbers a
    BC's own authored docs."""
    target = tmp_path / "bc-shop"
    target.mkdir()
    _minimal_bc_shop(target)

    authored = target / "docs" / "my-bc-notes.md"
    authored.parent.mkdir(parents=True, exist_ok=True)
    authored.write_text("shop-authored content\n")

    rc = _cmd_update(argparse.Namespace(target=str(target), shop_type=None))
    assert rc == 0

    assert authored.is_file(), "update must not delete shop-authored docs"
    assert authored.read_text() == "shop-authored content\n"


def test_runbook_content_covers_required_substance():
    """The shipped runbook must actually document the schema-skew wall: root
    cause, the two bd-suggested recovery traps, and the safe old-binary path —
    with the concrete schema-band coordinates from the incident."""
    body = read_doc_file(_RUNBOOK_REL).lower()

    # (a) root cause: wisps / dolt_ignore / the 0020 create migration /
    # schema_migrations / the 0047 failure site.
    assert "wisps" in body
    assert "dolt_ignore" in body
    assert "0020" in body
    assert "schema_migrations" in body
    assert "0047" in body

    # (b) why bd's own two suggested recoveries are traps.
    assert "force-push" in body or "force push" in body
    assert "bootstrap" in body

    # (c) the safe path: read the wedged remote with the OLD bd binary whose
    # max main-series migration matches the remote's schema.
    assert "v1.0.4" in body
    assert "v1.1.0" in body
    assert "v32" in body
    assert "v53" in body
    # the affected schema band.
    assert "20" in body and "46" in body


def test_runbook_content_is_shop_agnostic():
    """No BC-specific paths, names, or repos may be hardcoded in the shipped
    content — it is delivered to EVERY BC, so it must not name the BC that
    authored it or any concrete shop slug/repo."""
    body = read_doc_file(_RUNBOOK_REL)
    banned = [
        "shopsystem-bc-launcher",
        "shopsystem-templates",
        "shopsystem-product",
        "shopsystem-lead",
        "github.com/dstengle",
    ]
    for token in banned:
        assert token not in body, (
            f"shipped runbook must be shop-agnostic; found BC-specific "
            f"token {token!r}"
        )
