"""shop-templates CLI entry point.

Subcommands:
    list
        Print available role-template names (one per line) to stdout.
    show <name>
        Print the named template's content to stdout. Exits non-zero
        with a stderr message when no template matches that name.
    bootstrap --shop-type {bc,lead} --shop-name NAME --target DIR
        Scaffold a new (existing-but-empty) shop repository at DIR:
        write the canonical role-prompt copies for the shop type under
        .claude/agents/, write a CLAUDE.md primer for the shop type,
        write a top-level .gitignore, and invoke `bd init` as a
        subprocess to initialize .beads/.
    update --target DIR --shop-type {bc,lead}
        Re-pour the bootstrap-managed agent files in DIR/.claude/agents/
        from the current canonical package data. Reconcile against the
        canonical role set for the shop type — add canonical files that
        are missing, remove managed files whose canonical template no
        longer exists. Does NOT touch CLAUDE.md, .gitignore, or .beads/.

Role-prompt templates live in the package as `templates/<name>.md` data
files. CLAUDE.md primer templates live as `templates/claude/<shop_type>.md`.
The .gitignore template lives as `templates/gitignore.template`. The CLI
is the public boundary; dispatchers, scaffold scripts, and any other
consumer reads templates via this surface rather than by path.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from importlib.resources import files
from pathlib import Path


# The canonical shop-identity slug shape (ADR-018): .claude/shop/name.md is
# the single source of truth for shop identity and must carry only the
# canonical registry slug — lowercase ASCII letters, digits, and hyphens,
# with no whitespace and no other characters. Any human-readable display
# form of the shop name lives in the shop-owned .claude/shop/primer.md,
# which is NOT canonical-managed.
_SLUG_RE = re.compile(r"^[a-z0-9-]+$")


def _is_canonical_slug(value: str) -> bool:
    """Return True iff `value` is a canonical shop-identity slug.

    A slug is one or more characters drawn only from lowercase ASCII
    letters, digits, and hyphens — no whitespace, no uppercase, no other
    punctuation. Per ADR-018 this is the only admissible content for
    .claude/shop/name.md.
    """
    return bool(_SLUG_RE.match(value))


def _suggest_slug(value: str) -> str:
    """Return a best-effort canonical-slug suggestion for a display-form name.

    Lowercases the input and replaces each run of disallowed characters
    (whitespace and any character outside [a-z0-9-]) with a single hyphen,
    then trims leading/trailing hyphens. Used only to surface a helpful
    suggestion in the drift advisory; it does NOT mutate any shop-owned
    file. For the canonical example "shopsystem product" this yields
    "shopsystem-product".
    """
    lowered = value.strip().lower()
    slugged = re.sub(r"[^a-z0-9-]+", "-", lowered)
    return slugged.strip("-")


_TEMPLATES_PKG = "shop_templates.templates"
_CLAUDE_TEMPLATES_PKG = "shop_templates.templates.claude"
_CLAUDE_BODY_TEMPLATES_PKG = "shop_templates.templates.claude_body"
_CLAUDE_SETTINGS_PKG = "shop_templates.templates.claude_settings"
_SKILLS_PKG = "shop_templates.templates.skills"

# The canonical role-set assignment per shop type. The bootstrap surface
# uses this to decide which role files to pour into .claude/agents/ for
# a freshly-bootstrapped shop, and the update surface uses it to
# reconcile an existing shop's .claude/agents/ against the current
# canonical set.
_CANONICAL_ROLE_SETS: dict[str, tuple[str, ...]] = {
    "bc": ("bc-implementer", "bc-reviewer"),
    "lead": ("lead-po", "lead-architect"),
}

_SHOP_TYPES = tuple(_CANONICAL_ROLE_SETS.keys())


# -----------------------------------------------------------------------
# Public template-access surface (importable; not just CLI-internal).
#
# Per scenario 0cce58eb573d3c91, the CLAUDE.md primer template must be
# accessible "through its public template-access surface" and must NOT
# be read from any path under the product's top-level working directory
# at lookup time — i.e., it must be served from importlib.resources
# package data, the same boundary the role-prompt templates use.
# -----------------------------------------------------------------------


def _list_template_names() -> list[str]:
    """Return the sorted list of available role-template names.

    Walks only the top-level package directory; sub-directories (e.g.
    `templates/claude/`) are skipped. This keeps `shop-templates list`
    output stable as new categories of package data (CLAUDE primers,
    gitignore template) are added.
    """
    pkg_root = files(_TEMPLATES_PKG)
    names = []
    for resource in pkg_root.iterdir():
        # `is_file()` plus `.md` suffix isolates role-prompt templates
        # from sub-directories like `templates/claude/`.
        if not resource.is_file():
            continue
        name = resource.name
        if name.endswith(".md"):
            names.append(name[: -len(".md")])
    return sorted(names)


def _read_template(name: str) -> str | None:
    """Return the named role-template's content, or None if no such template."""
    try:
        return (files(_TEMPLATES_PKG) / f"{name}.md").read_text()
    except FileNotFoundError:
        return None


def read_claude_md_primer(shop_type: str) -> str:
    """Return the canonical CLAUDE.md primer template body for a shop type.

    The body is loaded from package data via importlib.resources; it is
    never read from a filesystem path under the product working
    directory. The returned string is the source of truth from which the
    bootstrap entry point generates a target directory's top-level
    CLAUDE.md.
    """
    if shop_type not in _CANONICAL_ROLE_SETS:
        raise ValueError(
            f"unknown shop type {shop_type!r}; accepted values: "
            f"{', '.join(_SHOP_TYPES)}"
        )
    resource = files(_CLAUDE_TEMPLATES_PKG) / f"{shop_type}.md"
    return resource.read_text()


def read_claude_md_body_template(shop_type: str) -> str:
    """Return the canonical CLAUDE.md body template for a shop type.

    The body template is the file that bootstrap writes byte-for-byte as
    the target directory's top-level CLAUDE.md. It contains only @-import
    directives referencing the four typed files that bootstrap also writes
    (.claude/shop/name.md, .claude/shop/type.md,
    .claude/canonical/<shop_type>-primer.md, .claude/shop/primer.md).
    No shop-specific substitution is applied; the body is written
    byte-for-byte.

    Loaded from package data via importlib.resources; never read from a
    filesystem path under the product working directory.

    Per scenarios cad9ccb5b462978d and 2b9bd9c82017b0c6 (lead-2oe /
    PDR-003 alt F).
    """
    if shop_type not in _CANONICAL_ROLE_SETS:
        raise ValueError(
            f"unknown shop type {shop_type!r}; accepted values: "
            f"{', '.join(_SHOP_TYPES)}"
        )
    resource = files(_CLAUDE_BODY_TEMPLATES_PKG) / f"{shop_type}.md"
    return resource.read_text()


def read_gitignore_template() -> str:
    """Return the canonical top-level .gitignore template body."""
    return (files(_TEMPLATES_PKG) / "gitignore.template").read_text()


def read_claude_settings_template(shop_type: str) -> str:
    """Return the canonical ".claude/settings.json" template body for a shop type.

    Per scenarios 1621b59b0ea8b20b and family (brief 003 §A): the body is
    loaded from package data via importlib.resources; it is never read
    from a filesystem path under the product working directory. The
    returned string is the source of truth from which the bootstrap
    entry point generates a target directory's ".claude/settings.json"
    for a shop of the given type, and is also what the update entry
    point re-pours.

    Per scenarios 679d227f04533ad4, c1e7f31eeef73e05, and 287e6a4f31533336:
    the body's content discipline (SessionStart hook shape, watch
    target per shop type, the `bd prime` companion hook on lead,
    alias-bypassing grep, exclusion of the other shop type's watch
    target) is a property of the package-data file itself — this
    accessor is a pure pass-through.
    """
    if shop_type not in _CANONICAL_ROLE_SETS:
        raise ValueError(
            f"unknown shop type {shop_type!r}; accepted values: "
            f"{', '.join(_SHOP_TYPES)}"
        )
    resource = files(_CLAUDE_SETTINGS_PKG) / f"{shop_type}.json"
    return resource.read_text()


def iter_skill_files():
    """Yield (relative_posix_path, content_bytes) for every file under the
    skills package-data tree, recursively. Relative path rooted at
    templates/skills/ (e.g. "test-driven-development/SKILL.md"). Served from
    importlib.resources package data."""
    root = files(_SKILLS_PKG)

    def _walk(node, prefix):
        for child in node.iterdir():
            rel = child.name if prefix == "" else f"{prefix}/{child.name}"
            if child.is_dir():
                yield from _walk(child, rel)
            elif child.is_file():
                yield rel, child.read_bytes()

    yield from _walk(root, "")


# -----------------------------------------------------------------------
# Lead-shop ops scaffolding (PDR-003 path F — shop-owned, NOT canonical).
#
# Per lead-8hxz (scenarios 90138f78dfa46697, 3d94639d5af360d7,
# 314d4485b8197f2a, 82c069bd3fb3b1d4, 8cf5656c55b466e7, 43e085e8627c7756):
# bootstrap of a "lead" shop renders three ops files — a top-level
# compose.yaml, an executable bin/shop-shell, and a top-level
# Dockerfile.shopsystem-shell — from package data under templates/ops/.
# A "bc" shop bootstrap renders NONE of them (a BC runs inside a
# bc-launcher container and never owns its own postgres or shell image).
#
# These files are SHOP-OWNED bootstrap-time starter content: they live at
# the repo top level / under bin/, NEVER under .claude/canonical/, because
# they are not subject to the canonical-managed re-pour contract that
# .claude/canonical/ implies.
# -----------------------------------------------------------------------

_OPS_TEMPLATES_PKG = "shop_templates.templates.ops"

# Each entry maps a package-data ops template name to (relative target
# path, executable?). The relative target path is resolved against the
# bootstrap target directory; it is deliberately a top-level / bin/ path
# and never under .claude/.
_LEAD_OPS_FILES: tuple[tuple[str, str, bool], ...] = (
    ("compose.yaml", "compose.yaml", False),
    ("shop-shell", "bin/shop-shell", True),
    ("Dockerfile.shopsystem-shell", "Dockerfile.shopsystem-shell", False),
    # lead-csas (scenarios 5c0a34a0b9ad1be7 / e430bb96e91b89ab): the
    # cross-BC scenario-completion reconciliation view. Poured executable
    # under bin/ for "lead" shops only; a "bc" shop never renders it (the
    # aggregate composes the lead's own bead ledger, invisible inside a
    # bc-launcher container — ADR-018). Shop-owned starter content, never
    # under .claude/canonical/.
    ("shop-scenario-completion", "bin/shop-scenario-completion", True),
)


def read_ops_template(name: str) -> str:
    """Return the named lead-shop ops template body from package data.

    Loaded via importlib.resources from templates/ops/; never read from a
    filesystem path under the product working directory. The returned
    string is the source of truth from which bootstrap renders a lead
    shop's compose.yaml / bin/shop-shell / Dockerfile.shopsystem-shell.
    """
    return (files(_TEMPLATES_PKG) / "ops" / name).read_text()


def _pour_skills(target: Path) -> None:
    """Mirror the skills package-data tree into <target>/.claude/skills/."""
    skills_root = target / ".claude" / "skills"
    for rel, body in iter_skill_files():
        dest = skills_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)


def _mirror_skills(target: Path) -> None:
    """Mirror skills package data into <target>/.claude/skills/: re-pour
    drifted/missing (idempotent on byte-equality), remove managed files no
    longer shipped, prune empty dirs."""
    skills_root = target / ".claude" / "skills"
    shipped = dict(iter_skill_files())
    for rel, body in shipped.items():
        dest = skills_root / rel
        if dest.exists() and dest.read_bytes() == body:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
    if skills_root.exists():
        shipped_abs = {skills_root / rel for rel in shipped}
        for path in sorted(skills_root.rglob("*")):
            if path.is_file() and path not in shipped_abs:
                path.unlink()
        for path in sorted(skills_root.rglob("*"), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()


def _render_lead_ops_scaffolding(target: Path) -> None:
    """Render the three lead-shop ops files into the target directory.

    Writes compose.yaml and Dockerfile.shopsystem-shell at the top level
    and bin/shop-shell (with its owner-execute bit set) — all shop-owned,
    none under .claude/. Caller gates this on shop_type == "lead".
    """
    for template_name, rel_path, executable in _LEAD_OPS_FILES:
        body = read_ops_template(template_name)
        dest = target / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body)
        if executable:
            mode = dest.stat().st_mode
            # Set the owner-execute bit (scenario 3d94639d5af360d7).
            dest.chmod(mode | 0o100)


def canonical_role_set(shop_type: str) -> tuple[str, ...]:
    """Return the canonical role-prompt-template names for a shop type.

    The bootstrap surface treats these names as the canonical role set
    for the given shop type — both `bootstrap` (initial pour) and
    `update` (reconciliation) work from this mapping.
    """
    if shop_type not in _CANONICAL_ROLE_SETS:
        raise ValueError(
            f"unknown shop type {shop_type!r}; accepted values: "
            f"{', '.join(_SHOP_TYPES)}"
        )
    return _CANONICAL_ROLE_SETS[shop_type]


# -----------------------------------------------------------------------
# `list` / `show` subcommands — pre-existing surface.
# -----------------------------------------------------------------------


def _cmd_list(args: argparse.Namespace) -> int:
    for name in _list_template_names():
        print(name)
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    content = _read_template(args.name)
    if content is None:
        # Fall back to the lead-shop ops scaffolding templates so the drift
        # advisory emitted by `update` (lead-xjsq) can truthfully point the
        # operator at `shop-templates show <ops-template-name>` to read the
        # current canonical ops body. The `list` surface deliberately does
        # NOT enumerate these (it stays the four role names), but `show`
        # resolves them by exact name.
        ops_names = {tn for tn, _rel, _exe in _LEAD_OPS_FILES}
        if args.name in ops_names:
            sys.stdout.write(read_ops_template(args.name))
            return 0
        available = ", ".join(_list_template_names())
        print(
            f"shop-templates show: no template named {args.name!r}. Available: {available}",
            file=sys.stderr,
        )
        return 1
    # Use sys.stdout.write to preserve exact bytes (no trailing newline from print).
    sys.stdout.write(content)
    return 0


# -----------------------------------------------------------------------
# `bootstrap` subcommand
# -----------------------------------------------------------------------


def _render_claude_md(shop_type: str, shop_name: str) -> str:
    """Return the CLAUDE.md body template for a shop type.

    Under PDR-003 alt F, bootstrap writes CLAUDE.md byte-for-byte from
    the canonical body template (no shop-specific substitution into the
    file itself). The shop name is recorded separately in
    .claude/shop/name.md (scenario 207dcfa0f8b3ca91). The {{SHOP_NAME}}
    parameter is retained in the signature for call-site compatibility
    but is not used.

    Scenarios a15dac2f87549b8a and 0cce58eb573d3c91 are RETIRED (lead-ro8).
    """
    return read_claude_md_body_template(shop_type)


def _bd_init_in(target: Path) -> int:
    """Invoke `bd init` as a subprocess in the target directory.

    Per scenario 0c6f1c5d9bc4226e, .beads/ MUST be initialized by a
    subprocess named "bd" with first argument "init", NOT by importing
    bd / beads internals into the running shop-templates process and
    NOT by writing .beads/ files from shop-templates directly. This
    function is the single place where that subprocess is spawned.

    Per scenario 32d99f6d4a2dad37 (lead-2gr round 2 of lead-k8v's
    bd-init side-effect closure), `bd init` MUST be invoked with the
    `--skip-agents` flag. That flag is bd's own opt-out for the
    AGENTS.md / .claude/settings.json / CLAUDE.md-beads-block append
    that bd otherwise applies during `bd init`. The shop's canonical
    agent surface is .claude/agents/*.md alone (poured by bootstrap
    itself); bd's agent-surface generation is duplicative at best and
    contradictory at worst, so we suppress it. Verified against bd
    1.0.3: `BD_NON_INTERACTIVE=1 bd init --skip-agents --quiet` in a
    fresh probe dir produces .beads/ + .gitignore and no AGENTS.md,
    no .claude/.
    """
    result = subprocess.run(
        ["bd", "init", "--skip-agents"],
        cwd=str(target),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"shop-templates bootstrap: `bd init` failed in {target!s} "
            f"(exit {result.returncode}); stderr:\n{result.stderr}",
            file=sys.stderr,
        )
    return result.returncode


def _validate_shop_type(shop_type: str | None, command: str) -> str | None:
    """Return None if shop_type is valid; else print a usage diagnostic to
    stderr and return an error sentinel string usable by callers.

    The diagnostic shape is pinned by scenarios d6e935bca62d0039 (missing
    shop type) and 7941cdc591cd2c3b (invalid shop type): stderr names
    the offending input AND lists the accepted values "bc" and "lead".
    """
    accepted = ", ".join(f'"{s}"' for s in _SHOP_TYPES)
    if shop_type is None:
        print(
            f"shop-templates {command}: missing required argument: shop type. "
            f"Accepted values: {accepted}.",
            file=sys.stderr,
        )
        return "missing"
    if shop_type not in _CANONICAL_ROLE_SETS:
        print(
            f"shop-templates {command}: invalid shop type {shop_type!r}. "
            f"Accepted values: {accepted}.",
            file=sys.stderr,
        )
        return "invalid"
    return None


def _validate_shop_name(shop_name: str | None, command: str) -> str | None:
    """Return None if shop_name is provided; else print a usage diagnostic
    to stderr and return an error sentinel string usable by callers.

    The diagnostic shape is pinned by scenario 3c8612d20608e9a3: stderr
    names "--shop-name" as the missing required argument and emits no
    Python traceback / no "TypeError" substring. We validate manually
    (matching the in-house pattern used by `_validate_shop_type`) rather
    than letting argparse short-circuit so the error shape is ours, not
    argparse's auto-generated message.

    Per scenario 51e39aa4a790e5fb (ADR-018): the --shop-name value must
    additionally be the canonical slug form (lowercase letters, digits,
    and hyphens only; no whitespace). A non-slug --shop-name (e.g. a
    display form containing a space) is rejected here with a diagnostic
    that names "--shop-name" + the slug constraint + the offending input
    + the disallowed character class, BEFORE any scaffold is written.
    """
    if shop_name is None:
        print(
            f"shop-templates {command}: missing required argument: --shop-name. "
            f"Provide the shop's own name (e.g. shopsystem-messaging).",
            file=sys.stderr,
        )
        return "missing"
    if not _is_canonical_slug(shop_name):
        # Name the offending input and, when present, call out whitespace
        # explicitly (scenario 51e39aa4a790e5fb pins that the diagnostic
        # identifies whitespace as the disallowed character for the
        # "shopsystem product" example). Fall back to a generic
        # disallowed-character phrasing for non-whitespace violations.
        if any(c.isspace() for c in shop_name):
            disallowed = "whitespace"
        else:
            disallowed = "a disallowed character"
        print(
            f"shop-templates {command}: --shop-name must be a canonical slug "
            f"(lowercase letters, digits, and hyphens only); the input "
            f"{shop_name!r} contains {disallowed}. The slug written into "
            f".claude/shop/name.md is the single source of truth for shop "
            f"identity; any human-readable display form belongs in the "
            f"shop-owned .claude/shop/primer.md, not in name.md.",
            file=sys.stderr,
        )
        return "invalid"
    return None


def _validate_target(target: str | None, command: str) -> str | None:
    """Return None if target is provided; else print a usage diagnostic
    to stderr and return an error sentinel string usable by callers.

    The diagnostic shape is pinned by scenarios fe59a11a88a9ab60
    (bootstrap) and 8fe363bd46cb766c (update): stderr names "--target"
    as the missing required argument and emits no Python traceback / no
    "TypeError" substring. We validate manually (matching the in-house
    pattern used by `_validate_shop_type` and `_validate_shop_name`)
    rather than letting argparse short-circuit so the error shape is
    ours, not argparse's auto-generated message — and so the
    diagnostic surfaces BEFORE any Path(args.target) construction that
    would otherwise raise TypeError when target is None.
    """
    if target is None:
        print(
            f"shop-templates {command}: missing required argument: --target. "
            f"Provide the path to the target repository.",
            file=sys.stderr,
        )
        return "missing"
    return None


def _cmd_bootstrap(args: argparse.Namespace) -> int:
    # Validate shop_type early so we can emit the usage diagnostic shape
    # the scenarios pin (named offending input + list of accepted values)
    # BEFORE touching the target directory. Scenarios d6e935bca62d0039
    # and 7941cdc591cd2c3b both require "writes no scaffold" when the
    # shop type is bad.
    err = _validate_shop_type(args.shop_type, "bootstrap")
    if err is not None:
        return 2

    # Validate shop_name early for the same reason. Scenario
    # 3c8612d20608e9a3 pins exit 2 + stderr names "--shop-name" + no
    # traceback + no scaffold written when --shop-name is omitted.
    # Without this guard, args.shop_name=None propagates into
    # _render_claude_md and surfaces as a TypeError from str.replace().
    err = _validate_shop_name(args.shop_name, "bootstrap")
    if err is not None:
        return 2

    # Validate target early for the same reason. Scenario
    # fe59a11a88a9ab60 pins exit 2 + stderr names "--target" + no
    # traceback + no scaffold written when --target is omitted. Without
    # this guard, args.target=None propagates into Path() and surfaces
    # as a TypeError from pathlib.
    err = _validate_target(args.target, "bootstrap")
    if err is not None:
        return 2

    target = Path(args.target)
    shop_type: str = args.shop_type
    shop_name: str = args.shop_name

    # Pour role-prompt files into .claude/agents/.
    agents_dir = target / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for role_name in _CANONICAL_ROLE_SETS[shop_type]:
        body = _read_template(role_name)
        if body is None:
            print(
                f"shop-templates bootstrap: internal error — canonical "
                f"role template {role_name!r} not found in package data",
                file=sys.stderr,
            )
            return 1
        (agents_dir / f"{role_name}.md").write_text(body)

    # Top-level CLAUDE.md — write the canonical body template byte-for-byte.
    # Under PDR-003 alt F, CLAUDE.md is a pure @-import file; no shop-specific
    # substitution is applied (scenarios 2b9bd9c82017b0c6 and cad9ccb5b462978d).
    (target / "CLAUDE.md").write_text(_render_claude_md(shop_type, shop_name))

    # .claude/shop/name.md — literal shop name with a single trailing newline
    # and no other content (scenario 207dcfa0f8b3ca91).
    shop_dir = target / ".claude" / "shop"
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "name.md").write_text(shop_name + "\n")

    # .claude/shop/type.md — literal shop type with a single trailing newline
    # and no other content (scenario 510520660d55522a).
    (shop_dir / "type.md").write_text(shop_type + "\n")

    # .claude/canonical/<shop_type>-primer.md — canonical primer template
    # byte-for-byte from package data (scenario 35c34f0e2d11c092).
    canonical_dir = target / ".claude" / "canonical"
    canonical_dir.mkdir(parents=True, exist_ok=True)
    (canonical_dir / f"{shop_type}-primer.md").write_text(
        read_claude_md_primer(shop_type)
    )

    # .claude/shop/primer.md — shop-authored placeholder; written as an empty
    # file so the operator may populate it later. Must NOT contain canonical
    # primer text (scenario 0bba99e6f592a788).
    (shop_dir / "primer.md").write_text("")

    # Top-level .gitignore — pour the canonical template.
    (target / ".gitignore").write_text(read_gitignore_template())

    # .claude/settings.json — pour the canonical per-shop-type settings
    # template (SessionStart activation hook over the shop's inbound
    # mailbox surface). Per brief 003 scope item A (scenarios
    # 1621b59b0ea8b20b, c8002527857e0dd1, f83e03ee69261242): the
    # canonical settings template lives in package data and bootstrap
    # writes it into the target's .claude/settings.json byte-for-byte.
    claude_dir = target / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "settings.json").write_text(
        read_claude_settings_template(shop_type)
    )

    # Pour canonical skills into .claude/skills/ for bc shops only.
    # Lead shops pour no skills.
    if shop_type == "bc":
        _pour_skills(target)

    # Lead-shop ops scaffolding (PDR-003 path F — shop-owned). For a
    # "lead" shop, render the three ops files (compose.yaml,
    # bin/shop-shell, Dockerfile.shopsystem-shell) at the repo top level /
    # under bin/, NEVER under .claude/. For a "bc" shop, render NONE of
    # them — a BC runs inside a bc-launcher container and never owns its
    # own postgres or shell image (scenarios 90138f78dfa46697,
    # 3d94639d5af360d7, 314d4485b8197f2a, 82c069bd3fb3b1d4,
    # 8cf5656c55b466e7, 43e085e8627c7756).
    if shop_type == "lead":
        _render_lead_ops_scaffolding(target)

    # Initialize .beads/ via a `bd init` subprocess. shop-templates MUST
    # NOT import bd / beads internals and MUST NOT write to .beads/
    # directly (scenario 0c6f1c5d9bc4226e).
    rc = _bd_init_in(target)
    if rc != 0:
        return rc

    # Lead-shop bootstrap installs each sibling BC clone under repos/
    # editable into the product venv, per brief 003 scope item E
    # (scenarios 3957f255c35aff60 outcome pin / ff882696856530a4
    # mechanism pin). The reference realization: for each subdir of
    # target/repos/ that ships a Python package (pyproject.toml or
    # setup.py), pip-install it editable into target/.venv/.
    if shop_type == "lead":
        rc = _install_sibling_bc_clones_editable(target)
        if rc != 0:
            return rc

    return 0


def _install_sibling_bc_clones_editable(target: Path) -> int:
    """For a lead shop, install every sibling BC clone under target/repos/
    editable into target/.venv/.

    Per brief 003 scope item E (scenarios 3957f255c35aff60 /
    ff882696856530a4): on session start in a bootstrapped lead shop,
    every BC CLI installed into the product venv must resolve invocations
    to the current source tree of that BC's clone under repos/, so a
    source edit in a BC clone is reflected in the next CLI invocation
    without an intervening manual reinstall. The reference realization
    is `pip install -e` per BC-clone subdir.

    Well-defined no-op states (returns 0 silently):
      - target/repos/ does not exist (lead-shop bootstrap with no BC
        clones yet — venv creation is also a no-op here).
      - target/repos/ exists but contains no installable subdir.

    If at least one installable subdir is present, ensure the venv
    exists (creating it on demand) and install each installable subdir
    in editable mode.
    """
    repos_dir = target / "repos"
    if not repos_dir.exists() or not repos_dir.is_dir():
        return 0

    # Filter to installable subdirs first; defer venv creation until
    # we know we have at least one clone to install.
    installable_children = []
    for child in sorted(repos_dir.iterdir()):
        if not child.is_dir():
            continue
        if (
            (child / "pyproject.toml").exists()
            or (child / "setup.py").exists()
            or (child / "setup.cfg").exists()
        ):
            installable_children.append(child)

    if not installable_children:
        return 0

    venv_dir = target / ".venv"
    if not venv_dir.exists():
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(
                f"shop-templates bootstrap: failed to create venv at "
                f"{venv_dir!s} (exit {result.returncode}); stderr:\n"
                f"{result.stderr}",
                file=sys.stderr,
            )
            return result.returncode

    venv_python = venv_dir / "bin" / "python"
    if not venv_python.exists():
        # Windows or other layouts — fall back to Scripts/python.exe
        alt = venv_dir / "Scripts" / "python.exe"
        if alt.exists():
            venv_python = alt
        else:
            print(
                f"shop-templates bootstrap: cannot find venv python "
                f"interpreter under {venv_dir!s}",
                file=sys.stderr,
            )
            return 1

    for child in installable_children:
        result = subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-e", str(child)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(
                f"shop-templates bootstrap: `pip install -e {child!s}` "
                f"failed (exit {result.returncode}); stderr:\n"
                f"{result.stderr}",
                file=sys.stderr,
            )
            return result.returncode

    return 0


# -----------------------------------------------------------------------
# `update` subcommand
# -----------------------------------------------------------------------


def _cmd_update(args: argparse.Namespace) -> int:
    # Validate target early. Scenario 8fe363bd46cb766c pins exit 2 +
    # stderr names "--target" + no traceback + every file under the
    # previously-bootstrapped shop's .claude/agents/ is byte+mtime
    # identical when --target is omitted. Without this guard,
    # args.target=None propagates into Path() and surfaces as a
    # TypeError from pathlib.
    err = _validate_target(args.target, "update")
    if err is not None:
        return 2

    target = Path(args.target)

    # Resolve shop type. PDR-003 alt F: the canonical shop type is
    # recorded in .claude/shop/type.md at bootstrap time (scenario
    # f55678f733a5427a). If --shop-type is provided explicitly (backward
    # compatibility), use it. Otherwise, read from .claude/shop/type.md.
    # If neither is available (legacy shop predating PDR-003 alt F),
    # exit non-zero with a migration diagnostic (scenario e51ac69bba8fd909).
    if args.shop_type is not None:
        # Explicit --shop-type provided; validate it.
        err = _validate_shop_type(args.shop_type, "update")
        if err is not None:
            return 2
        shop_type: str = args.shop_type
    else:
        type_file = target / ".claude" / "shop" / "type.md"
        if not type_file.exists():
            print(
                f"shop-templates update: .claude/shop/type.md not found in "
                f"{target!s}. This appears to be a legacy shop that was "
                f"bootstrapped before PDR-003 alternative F. migration steps: "
                f"(1) run `shop-templates bootstrap --shop-type <type> "
                f"--shop-name <name> --target {target!s}` to re-bootstrap "
                f"with the current shop structure, or (2) manually create "
                f".claude/shop/type.md containing the shop type (bc or lead) "
                f"and re-run update.",
                file=sys.stderr,
            )
            return 2
        shop_type = type_file.read_text().strip()
        if shop_type not in _CANONICAL_ROLE_SETS:
            print(
                f"shop-templates update: .claude/shop/type.md in {target!s} "
                f"contains invalid shop type {shop_type!r}. migration steps: "
                f"update the file to contain a valid shop type (one of: "
                f"{', '.join(_SHOP_TYPES)}) and re-run update.",
                file=sys.stderr,
            )
            return 2

    agents_dir = target / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    canonical = set(_CANONICAL_ROLE_SETS[shop_type])

    # The "naming convention" for bootstrap-managed agent files is:
    # filename = <role-name>.md where <role-name> is a name in the
    # canonical role set of SOME shop type (current or historical).
    # For reconciliation we treat any .md file in .claude/agents/ as a
    # candidate managed file; if its name is in the current canonical
    # role set for this shop type it stays (and gets re-poured); if
    # its name is in NEITHER canonical role set we leave it alone
    # (shop-authored content we don't recognize); if it matches a
    # canonical name from any role set (including the other shop
    # type's set, or a name previously in this set but no longer) we
    # remove it. This satisfies scenario 03b4e3fa31d72031's "remove
    # managed files whose canonical template no longer exists" while
    # leaving shop-authored files alone.
    all_canonical_names = set()
    for rs in _CANONICAL_ROLE_SETS.values():
        all_canonical_names.update(rs)
    # A file is "managed" if its base name (sans .md) is in the
    # historical set OR is a current canonical name we're about to
    # pour. For this implementation, treat managed = any .md file
    # whose name follows the role-prompt-template naming convention,
    # which we recognize via the heuristic: name contains "-" and is
    # all lowercase ASCII. That keeps shop-authored files like
    # "TODO.md" or "NOTES.md" out.
    def _is_managed_role_name(stem: str) -> bool:
        # Recognize names of the form "<prefix>-<suffix>" where both
        # halves are ASCII lowercase letters. This matches every
        # canonical role-name pattern shipped today (bc-implementer,
        # bc-reviewer, lead-po, lead-architect) and excludes typical
        # shop-authored markdown filenames.
        if "-" not in stem:
            return False
        if stem != stem.lower():
            return False
        if not all(c.islower() or c == "-" for c in stem):
            return False
        return True

    # Step 1: remove managed files whose names are NOT in the current
    # canonical role set for this shop type.
    for child in list(agents_dir.iterdir()):
        if not child.is_file():
            continue
        if not child.name.endswith(".md"):
            continue
        stem = child.name[:-len(".md")]
        if stem in canonical:
            continue
        if _is_managed_role_name(stem):
            child.unlink()

    # Step 2: re-pour every canonical role file. If a file is already
    # byte-equal to the canonical content, leave its on-disk
    # mtime alone (scenario 264322ae65312bc7).
    for role_name in canonical:
        body = _read_template(role_name)
        if body is None:
            print(
                f"shop-templates update: internal error — canonical "
                f"role template {role_name!r} not found in package data",
                file=sys.stderr,
            )
            return 1
        target_file = agents_dir / f"{role_name}.md"
        if target_file.exists():
            current = target_file.read_text()
            if current == body:
                continue
        target_file.write_text(body)

    # Step 3: re-pour the canonical .claude/settings.json. Per scenarios
    # d29cd723439faae1 and d3066d4476d0a975: settings.json is treated as
    # bootstrap-managed (not init-only) — stale content is replaced and
    # already-current content is left byte-for-byte unchanged.
    canonical_settings = read_claude_settings_template(shop_type)
    settings_file = target / ".claude" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    if settings_file.exists() and settings_file.read_text() == canonical_settings:
        pass  # leave byte+mtime unchanged
    else:
        settings_file.write_text(canonical_settings)

    # Step 4: re-pour the top-level CLAUDE.md from the canonical body
    # template byte-for-byte. Per scenario c458502d8632952b (PDR-003 alt F):
    # update overwrites a drifted CLAUDE.md. Per scenario ac5a21e046564d01:
    # if already matching, leave byte+mtime unchanged.
    canonical_body = read_claude_md_body_template(shop_type)
    claude_md_file = target / "CLAUDE.md"
    if claude_md_file.exists() and claude_md_file.read_text() == canonical_body:
        pass  # leave byte+mtime unchanged
    else:
        claude_md_file.write_text(canonical_body)

    # Step 5: re-pour .claude/canonical/<shop_type>-primer.md from the
    # canonical primer template byte-for-byte. Per scenario ce122bcb7d794888
    # (PDR-003 alt F): update overwrites a drifted canonical primer. Per
    # scenario ac5a21e046564d01: if already matching, leave byte+mtime
    # unchanged. .claude/shop/name.md, .claude/shop/type.md, and
    # .claude/shop/primer.md are NEVER touched by update (scenarios
    # 3d3f8c8427366491, ca3fc9ec7c67ddb2, 91e2db0f9e3e58d5).
    canonical_primer = read_claude_md_primer(shop_type)
    canonical_dir = target / ".claude" / "canonical"
    canonical_dir.mkdir(parents=True, exist_ok=True)
    primer_file = canonical_dir / f"{shop_type}-primer.md"
    if primer_file.exists() and primer_file.read_text() == canonical_primer:
        pass  # leave byte+mtime unchanged
    else:
        primer_file.write_text(canonical_primer)

    # Step 6: mirror canonical skills into .claude/skills/ for bc shops;
    # re-pour drifted/missing files, remove managed files no longer shipped,
    # prune empty dirs. Lead shops own no skills.
    if shop_type == "bc":
        _mirror_skills(target)

    # Step 7: surface (without modifying) drift in .claude/shop/name.md.
    # Per scenario 97245affb1dbe5e4 (ADR-018 / ADR-007): name.md is the
    # single source of truth for shop identity and must hold the canonical
    # slug; but name.md is a SHOP-OWNED file that update must never
    # modify (scenario 3d3f8c8427366491). When its on-disk content has
    # drifted to a non-slug form (e.g. a legacy display form with a
    # space), update emits a stderr advisory naming the file, the on-disk
    # value, a suggested canonical slug, and the instruction to edit
    # name.md to slug form — and explicitly notes that update did NOT
    # modify the shop-owned file. This respects the canonical-managed vs
    # shop-owned boundary while still surfacing the drift to the operator.
    name_file = target / ".claude" / "shop" / "name.md"
    if name_file.exists():
        on_disk = name_file.read_text()
        on_disk_value = on_disk.rstrip("\n")
        if not _is_canonical_slug(on_disk_value):
            suggested = _suggest_slug(on_disk_value)
            print(
                f"shop-templates update: advisory — the shop-owned file "
                f".claude/shop/name.md contains {on_disk_value!r}, which is "
                f"not a canonical shop-identity slug (lowercase letters, "
                f"digits, and hyphens only; no whitespace). Suggested "
                f"canonical slug: {suggested!r}. Please edit "
                f".claude/shop/name.md to the slug form "
                f"(e.g. {suggested!r}); any human-readable display form "
                f"belongs in the shop-owned .claude/shop/primer.md. "
                f"shop-templates update did NOT modify the shop-owned file "
                f".claude/shop/name.md.",
                file=sys.stderr,
            )

    # Step 7: surface (without modifying) drift in the lead-shop ops
    # scaffolding files. Per lead-xjsq (scenarios 3e8c8087c483db9e,
    # ebbe3f1b92258299, 59d41246cbd5235b): compose.yaml, bin/shop-shell,
    # and Dockerfile.shopsystem-shell are SHOP-OWNED under PDR-003 path F's
    # two-bucket model — update NEVER overwrites them (the ops-scaffolding
    # analogue of scenarios 86/87/88 for .claude/shop/). When an ops file's
    # on-disk content has drifted from the current canonical ops template
    # body, update emits a stderr advisory naming the file, noting the
    # drift, explicitly noting it did NOT modify the shop-owned file, and
    # pointing the operator at the canonical body — without touching the
    # file or changing the exit code (stays 0). When an ops file already
    # matches canonical byte-for-byte, no advisory is emitted and the file
    # is left byte+mtime untouched (idempotence, the ops analogue of
    # scenario 89). BC shops own NO ops scaffolding, so this is gated on
    # shop_type == "lead".
    if shop_type == "lead":
        _advise_ops_scaffolding_drift(target)

    return 0


def _advise_ops_scaffolding_drift(target: Path) -> None:
    """Emit a non-modifying stderr drift advisory for each lead-shop ops
    scaffolding file whose on-disk content differs from canonical.

    The ops scaffolding files (compose.yaml, bin/shop-shell,
    Dockerfile.shopsystem-shell) are shop-owned: this function NEVER writes
    to them. It only inspects on-disk content against the current canonical
    ops template body and, on drift, prints an advisory to stderr that
    mirrors the name.md advisory pattern (scenario 132). Files that match
    canonical, or that are absent, produce no advisory.
    """
    for template_name, rel_path, _executable in _LEAD_OPS_FILES:
        dest = target / rel_path
        if not dest.exists():
            continue
        canonical_body = read_ops_template(template_name)
        if dest.read_text() == canonical_body:
            continue
        print(
            f"shop-templates update: advisory — the shop-owned ops "
            f"scaffolding file {rel_path} has drifted from the current "
            f"canonical template body. shop-templates update did NOT modify "
            f"the shop-owned file {rel_path}. To view the current canonical "
            f"body, run `shop-templates show {template_name}` and reconcile "
            f"the file by hand if you intend to adopt the canonical update.",
            file=sys.stderr,
        )


# -----------------------------------------------------------------------
# Argparse wiring
# -----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shop-templates")
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="list available template names")
    list_cmd.set_defaults(func=_cmd_list)

    show_cmd = sub.add_parser("show", help="print a named template to stdout")
    show_cmd.add_argument("name", help="template name (e.g. bc-implementer)")
    show_cmd.set_defaults(func=_cmd_show)

    bootstrap_cmd = sub.add_parser(
        "bootstrap",
        help="scaffold an existing repo with the canonical shop structure",
    )
    # `--shop-type` intentionally has no default. Scenario d6e935bca62d0039
    # requires that omitting it produces a non-zero exit and a usage
    # diagnostic naming the missing argument AND the accepted values.
    # We declare it as a regular optional argument (not required=True at
    # the argparse layer) so argparse does NOT short-circuit with its
    # own auto-generated "the following arguments are required:..."
    # message — we want our own diagnostic shape on stderr.
    bootstrap_cmd.add_argument(
        "--shop-type",
        choices=None,  # validate manually so error shape is ours, not argparse's
        default=None,
        help='one of "bc" or "lead"',
    )
    bootstrap_cmd.add_argument(
        "--shop-name",
        default=None,
        help="the shop's own name, e.g. shopsystem-messaging",
    )
    bootstrap_cmd.add_argument(
        "--target",
        default=None,
        help="path to the existing repository to scaffold",
    )
    bootstrap_cmd.set_defaults(func=_cmd_bootstrap)

    update_cmd = sub.add_parser(
        "update",
        help="re-pour bootstrap-managed agent files from current package data",
    )
    update_cmd.add_argument(
        "--target",
        default=None,
        help="path to the previously-bootstrapped repository",
    )
    update_cmd.add_argument(
        "--shop-type",
        default=None,
        help='one of "bc" or "lead" (must match the original bootstrap)',
    )
    update_cmd.set_defaults(func=_cmd_update)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
