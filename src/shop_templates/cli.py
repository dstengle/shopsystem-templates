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
import subprocess
import sys
from importlib.resources import files
from pathlib import Path


_TEMPLATES_PKG = "shop_templates.templates"
_CLAUDE_TEMPLATES_PKG = "shop_templates.templates.claude"
_CLAUDE_SETTINGS_PKG = "shop_templates.templates.claude_settings"

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
    """Render the CLAUDE.md primer for a shop type by substituting the
    shop name. The primer must name the shop's identity (its shop_name
    and its role set) per scenario a15dac2f87549b8a.
    """
    primer = read_claude_md_primer(shop_type)
    return primer.replace("{{SHOP_NAME}}", shop_name)


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
    """
    if shop_name is None:
        print(
            f"shop-templates {command}: missing required argument: --shop-name. "
            f"Provide the shop's own name (e.g. shopsystem-messaging).",
            file=sys.stderr,
        )
        return "missing"
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

    # Top-level CLAUDE.md — render the primer with the shop's identity.
    (target / "CLAUDE.md").write_text(_render_claude_md(shop_type, shop_name))

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
    # Update requires shop_type as an explicit argument so the
    # reconciliation step (scenario 03b4e3fa31d72031) can compare the
    # current contents of .claude/agents/ against the current canonical
    # role set for the right shop type. Inferring the shop type from
    # .claude/agents/ contents is unsafe: a hand-mutated shop may have
    # zero files whose names are in either canonical set.
    err = _validate_shop_type(args.shop_type, "update")
    if err is not None:
        return 2

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
    shop_type: str = args.shop_type
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
    # already-current content is left byte-for-byte unchanged. This is
    # additive to the prior update contract: the non-touch invariant on
    # CLAUDE.md / .gitignore / .beads/ (scenarios 56a0ac7107ba5c15,
    # ca0f0a249d025267, 3f4d7d2256a97ae7, efae77e534588357) still holds.
    canonical_settings = read_claude_settings_template(shop_type)
    settings_file = target / ".claude" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    if settings_file.exists() and settings_file.read_text() == canonical_settings:
        pass  # leave byte+mtime unchanged
    else:
        settings_file.write_text(canonical_settings)

    return 0


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
