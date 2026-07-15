"""Regression guard for the canonical review-venv import-integrity hazard
runbook shipping as shop-templates distributed package data and being delivered
to every BC via the same pour mechanism BCs already use to receive canonical
content (`shop-templates update`). (request_maintenance lead-uzweq.)

shopsystem-bc-launcher authored `docs/runbooks/review-venv-import-integrity.md`
while investigating a TOCTOU venv-clobber incident (lead-b7gqq): a
freshly-provisioned, verified-clean review venv losing its target package and
gaining a foreign `__editable__.<pkg>-<ver>.pth` within ~1s of provisioning,
via ambient VIRTUAL_ENV honored by `pip install -e /workspace`. That runbook is
SHOP-AGNOSTIC (<pkg>/<repo>/<venv> placeholders, "Applies to any shop..."
phrasing) and must stop living in one BC's private repo and become canonical
content shipped to EVERY BC — reachable via the same importlib.resources
package-data + update-pour mechanism lead-pq9ex already established for
docs/runbooks/beads-schema-skew-recovery.md.

ACCEPTANCE CRITERIA (from the dispatch — this is what these tests prove):
  docs/runbooks/review-venv-import-integrity.md ships as part of
  shopsystem-templates' distributed package data, reachable by every BC via
  the same mechanism BCs already use to receive canonical docs (per
  `shop-templates show` / `shop-templates update`). No BC-specific paths or
  names hardcoded in the shipped content.
"""
import argparse
import tomllib
from importlib.resources import files
from pathlib import Path

from shop_templates.cli import _cmd_update, iter_doc_files, read_doc_file

# The canonical runbook's relative path, rooted at the docs package-data subtree
# (templates/docs/) AND at a BC's on-disk docs/ directory after the pour.
_RUNBOOK_REL = "runbooks/review-venv-import-integrity.md"

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

    # And the public read helper returns the same bytes.
    assert read_doc_file(_RUNBOOK_REL) == body


def test_runbook_enumerated_by_iter_doc_files():
    """The canonical docs iterator enumerates the runbook, so the update pour
    that walks it delivers the runbook to every BC."""
    rels = {rel for rel, _body in iter_doc_files()}
    assert _RUNBOOK_REL in rels, (
        f"iter_doc_files must enumerate {_RUNBOOK_REL}; got {sorted(rels)}"
    )


def test_runbook_declared_in_package_data():
    """pyproject declares a package-data glob covering templates/docs/** so the
    runbook actually rides the built sdist+wheel."""
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


def test_runbook_content_covers_required_substance():
    """The shipped runbook must actually document the venv/import-integrity
    hazards: the 4 traps (including the new TOCTOU venv-clobber) and the 3
    mitigations named in the dispatch."""
    body = read_doc_file(_RUNBOOK_REL).lower()

    # The new hazard trap: ambient VIRTUAL_ENV honored by `pip install -e` that
    # clobbers a verified-clean venv, dropping a foreign __editable__ .pth.
    assert "virtual_env" in body
    assert "__editable__" in body
    assert ".pth" in body
    assert "toctou" in body

    # The 3 mitigations.
    # (1) purge foreign __editable__*.pth after provisioning AND before each run.
    assert "purge" in body
    # (2) assert import resolution in the SAME process that runs the tests.
    assert "same process" in body
    # (3) differential experiments: assert per arm and print resolved path.
    assert "arm" in body

    # It must actually enumerate multiple hazard traps and mitigations.
    assert "trap" in body
    assert "mitigation" in body


def test_runbook_content_covers_trap_5_substance():
    """Trap 5 — the blanket purge unmasks a stale non-editable global — must
    be documented in the shipped runbook: its symptom (a --system-site-packages
    venv whose blanket glob deletes the reviewer's own pointer and silently
    resolves <pkg> from the inherited global), the 'no purge can remove it'
    mechanism (a non-editable dist-info, not a .pth), both mitigations
    (provision WITHOUT --system-site-packages; else re-point via a
    uniquely-named non-__editable__ .pth) INCLUDING the probe-established
    zz-prefix-non-precedence correction, the retained/reaffirmed Trap-4 assert
    note, and the PURGE / RE-POINT / ASSERT composite rule."""
    body = read_doc_file(_RUNBOOK_REL).lower()

    # Enumerated as a fifth hazard.
    assert "trap 5" in body
    assert "five hazard traps" in body

    # Symptom: --system-site-packages venv, blanket glob deletes the OWN
    # editable pointer, import still succeeds from the inherited global.
    assert "system-site-packages" in body
    assert "non-editable" in body

    # Mechanism: the stale global is a non-editable dist-info, not a .pth, so
    # no purge can remove it — the blanket purge unmasks it.
    assert "no purge can remove it" in body
    assert "dist-info" in body
    assert "unmasks" in body

    # Both mitigations.
    assert "without" in body  # (i) provision WITHOUT --system-site-packages
    assert "zz-" in body       # (ii) re-point via a uniquely-named .pth
    # The probe-established correction: zz- is NOT load-bearing for precedence.
    assert "not load-bearing" in body
    assert "precedence" in body
    assert "cargo-cult" in body

    # Trap 4's in-process resolution assert is retained/reaffirmed, not weakened.
    assert "retained" in body
    assert "mandatory" in body

    # The composite rule: purge, re-point, then assert.
    assert "re-point" in body
    assert "purge, re-point" in body


def test_runbook_content_is_shop_agnostic():
    """No BC-specific paths, names, or repos may be hardcoded in the shipped
    content — it is delivered to EVERY BC. In particular the line-13 gloss
    ('in this shop, bc_launcher') from the source doc must be genericized or
    dropped: the token 'bc_launcher' must be absent."""
    body = read_doc_file(_RUNBOOK_REL)
    banned = [
        "bc_launcher",
        "shopsystem-bc-launcher",
        "shopsystem-templates",
        "shopsystem-product",
        "shopsystem-lead",
        "github.com/dstengle",
        "engage.py",
    ]
    for token in banned:
        assert token not in body, (
            f"shipped runbook must be shop-agnostic; found BC-specific "
            f"token {token!r}"
        )

    # The placeholder phrasing is preserved as authored.
    assert "<pkg>" in body
    assert "<repo>" in body
    assert "<venv>" in body
