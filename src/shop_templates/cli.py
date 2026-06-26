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
import os
import re
import subprocess
import sys
import zlib
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
# The canonical LEAD skill-group — a package-data subtree DISTINCT from the BC
# skill tree (_SKILLS_PKG). A "lead" shop pours ONLY this group into
# .claude/skills/; a "bc" shop pours the BC tree. They never mix. (lead-5mr5,
# scenarios 75f86e53/c20785332/cc520034/f75eb04e/e803b4c9/4a008549/a14e5a0a.)
_LEAD_SKILLS_PKG = "shop_templates.templates.lead_skills"
# The shopsystem-starter forkable-repo BODY — a package-data subtree carrying
# the standalone "Use this template" repo's artifacts (compose.yaml,
# bin/bootstrap, .env.example, README.md). Unlike templates/ops/ (the
# poured-into-a-lead-shop variant), the starter body ships UNSUBSTITUTED:
# there is no product slug at "Use this template" time, so it carries no
# render-time placeholders. This BC renders the body as package data only; the
# GitHub repo creation / template-repository marking is a separate lead action
# (tmpl-3ch / lead-v0m7, PDR-019 U1, ADR-040 D1/D3, briefs/012 §2).
_STARTER_PKG = "shop_templates.templates.starter"

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


def iter_lead_skill_files():
    """Yield (relative_posix_path, content_bytes) for every file under the
    canonical LEAD skill-group package-data tree, recursively. Relative path
    rooted at templates/lead_skills/ (e.g. "bring-up-bc/SKILL.md"). Served from
    importlib.resources package data — never read from a filesystem path under
    the product working directory.

    This is the lead analogue of iter_skill_files(): the lead skill-group is a
    separate canonical-managed surface that lead bootstrap pours into
    .claude/skills/ and `shop-templates update` mirrors+prunes for lead shops.
    (lead-5mr5.)"""
    root = files(_LEAD_SKILLS_PKG)

    def _walk(node, prefix):
        for child in node.iterdir():
            rel = child.name if prefix == "" else f"{prefix}/{child.name}"
            if child.is_dir():
                yield from _walk(child, rel)
            elif child.is_file():
                yield rel, child.read_bytes()

    yield from _walk(root, "")


def iter_starter_files():
    """Yield (relative_posix_path, content_bytes) for every file in the
    shopsystem-starter forkable-repo BODY, recursively. Relative path rooted at
    templates/starter/ (e.g. "compose.yaml", "bin/bootstrap"). Served from
    importlib.resources package data — never read from a filesystem path under
    the product working directory.

    The starter body is the standalone, lead-owned "Use this template" repo's
    artifacts; this BC renders the body as package data only. Unlike the ops
    scaffolding, the starter body ships UNSUBSTITUTED (no product slug exists at
    "Use this template" time). (tmpl-3ch / lead-v0m7, PDR-019 U1.)"""
    root = files(_STARTER_PKG)

    def _walk(node, prefix):
        for child in node.iterdir():
            rel = child.name if prefix == "" else f"{prefix}/{child.name}"
            if child.is_dir():
                yield from _walk(child, rel)
            elif child.is_file():
                yield rel, child.read_bytes()

    yield from _walk(root, "")


def read_starter_file(rel: str) -> str:
    """Return the named shopsystem-starter body file's text from package data.

    `rel` is a posix-relative path rooted at templates/starter/ (e.g.
    "compose.yaml", "bin/bootstrap", ".env.example", "README.md"). Served from
    importlib.resources package data; raises FileNotFoundError if no such file.
    The starter body ships unsubstituted, so the returned text is the exact
    committed body (no placeholder rendering). (tmpl-3ch / lead-v0m7.)"""
    resource = files(_STARTER_PKG)
    for part in rel.split("/"):
        resource = resource / part
    return resource.read_text()


def canonical_skill_group(shop_type: str) -> tuple[tuple[str, bytes], ...]:
    """Return the canonical skill-group for a shop type as the public
    template-access surface: a tuple of (member_name, SKILL.md bytes), one per
    skill-group member, served from package data byte-for-byte.

    Parallel to read_claude_md_primer / canonical_role_set: a pure pass-through
    over package data, never a filesystem read under the product working
    directory. The "lead" group is the canonical LEAD skill-group
    (bring-up-bc, create-bc); the "bc" group is the BC skill tree. (lead-5mr5,
    scenario c207853320920de7.)"""
    if shop_type not in _CANONICAL_ROLE_SETS:
        raise ValueError(
            f"unknown shop type {shop_type!r}; accepted values: "
            f"{', '.join(_SHOP_TYPES)}"
        )
    iterator = iter_lead_skill_files if shop_type == "lead" else iter_skill_files
    members: dict[str, bytes] = {}
    for rel, body in iterator():
        # Each member is the top-level directory carrying a SKILL.md.
        head, _, tail = rel.partition("/")
        if tail == "SKILL.md":
            members[head] = body
    return tuple(sorted(members.items()))


# -----------------------------------------------------------------------
# Lead-shop ops scaffolding (PDR-003 path F — shop-owned, NOT canonical).
#
# Per lead-8hxz / PDR-020 slice 2 (scenarios 90138f78dfa46697,
# 82c069bd3fb3b1d4, 43e085e8627c7756, plus converged 03f1256aefc7fad4 /
# 5e42381f435397f2 / 5730de0b80aa6a0b / 82c3a716143014a6): bootstrap of a
# "lead" shop renders a top-level compose.yaml and an executable bin/shop-shell
# (the THIN bc-container-delegating wrapper) from package data under
# templates/ops/. Per PDR-020 the dedicated shell image and its
# Dockerfile.<slug>-shell are RETIRED — bin/shop-shell launches an ephemeral
# product-neutral bc-base instead, so no shell Dockerfile is written.
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
    # lead-csas (scenarios 5c0a34a0b9ad1be7 / e430bb96e91b89ab): the
    # cross-BC scenario-completion reconciliation view. Poured executable
    # under bin/ for "lead" shops only; a "bc" shop never renders it (the
    # aggregate composes the lead's own bead ledger, invisible inside a
    # bc-launcher container — ADR-018). Shop-owned starter content, never
    # under .claude/canonical/.
    ("shop-scenario-completion", "bin/shop-scenario-completion", True),
    # lead-w87b (WS-2): the agent-vault broker provisioning + expiry-advisory
    # scripts. Poured executable under bin/ for "lead" shops, product-scoped
    # via {{OPS_SLUG}} so each renders against its own compose-defined broker
    # (<slug>-agent-vault) — no shopsystem-*/fleet literals. provision is the
    # one human-gated Claude-OAuth dashboard paste (ADR-026 D4); check is the
    # non-fatal 30-day GitHub-PAT expiry probe bin/shop-shell calls at startup
    # (`bin/agent-vault-check || true`). Shop-owned, never under .claude/.
    ("agent-vault-provision", "bin/agent-vault-provision", True),
    ("agent-vault-check", "bin/agent-vault-check", True),
    # lead-9s46 (WS-2): the Claude-OAuth proposal approval tool. provision
    # leaves ONE human step — approving the CLAUDE_OAUTH proposal with the real
    # token — and previously printed a docker-exec string the adopter had to
    # hand-edit. This lead-only executable removes that friction: it
    # auto-resolves the broker/vault/proposal from the same {{OPS_SLUG}}-derived
    # coordinates provision uses and runs the scoped approve. Product-neutral.
    ("agent-vault-approve-claude", "bin/agent-vault-approve-claude", True),
)


def read_ops_template(name: str) -> str:
    """Return the named lead-shop ops template body from package data.

    Loaded via importlib.resources from templates/ops/; never read from a
    filesystem path under the product working directory. The returned
    string is the RAW (placeholder-bearing) source of truth from which
    bootstrap renders a lead shop's compose.yaml / bin/shop-shell. To obtain
    the rendered, product-scoped body use `render_ops_template(name, slug)`.
    """
    return (files(_TEMPLATES_PKG) / "ops" / name).read_text()


def _ops_slug(shop_name: str) -> str:
    """Return the product slug the ops scaffolding is scoped to.

    The ops slug is the bootstrap `--shop-name` (already the canonical
    shop-identity slug) with a single trailing `-product` suffix stripped,
    so `shopsystem-product` -> `shopsystem` and `dummyco-product` ->
    `dummyco`. A name without that suffix is used verbatim. This is the
    SAME slug source the rest of bootstrap reads (`.claude/shop/name.md`,
    scenario 4e99a6abbc57b884 / ADR-018): name.md is the single source of
    truth for shop identity, and the ops generification derives every
    `<product>-*` literal from it — it introduces no new identity source.
    """
    suffix = "-product"
    if shop_name.endswith(suffix) and len(shop_name) > len(suffix):
        return shop_name[: -len(suffix)]
    return shop_name


def _ops_postgres_host_port(slug: str) -> int:
    """Return a deterministic, product-distinct default postgres HOST port
    for a slug.

    Derivation: 5432 + crc32(slug) % 1000, giving each product a stable
    host port in [5432, 6431] so a second product does not collide on the
    published port with a running fleet. The rendered compose makes this an
    env-overridable default (`${<SLUG_UPPER>_POSTGRES_PORT:-<derived>}`),
    so an operator can still pin it explicitly.
    """
    return 5432 + (zlib.crc32(slug.encode("utf-8")) % 1000)


def _ops_vault_api_host_port(slug: str) -> int:
    """Return a deterministic, product-distinct default agent-vault broker
    API HOST port for a slug.

    Mirrors `_ops_postgres_host_port`: 14321 + crc32(slug) % 1000, giving each
    product a stable host port in [14321, 15320] so a second product does not
    collide on the published broker API port with a running fleet. The broker
    CONTAINER API port stays fixed at 14321; only the published HOST default
    is slug-derived (and env-overridable via `<SLUG_UPPER>_VAULT_API_PORT`).
    """
    return 14321 + (zlib.crc32(("vault-api:" + slug).encode("utf-8")) % 1000)


def _ops_vault_proxy_host_port(slug: str) -> int:
    """Return a deterministic, product-distinct default agent-vault broker
    PROXY HOST port for a slug.

    Mirrors `_ops_postgres_host_port`: 14322 + crc32(slug) % 1000. The broker
    CONTAINER proxy port stays fixed at 14322 (the `HTTPS_PROXY=<broker>:14322`
    target bin/shop-shell wires, scenario 5335c39eb06f7493); only the published
    HOST default is slug-derived (env-overridable via
    `<SLUG_UPPER>_VAULT_PROXY_PORT`).
    """
    return 14322 + (zlib.crc32(("vault-proxy:" + slug).encode("utf-8")) % 1000)


def render_ops_template(name: str, slug: str) -> str:
    """Return the named ops template body rendered for a product slug.

    Substitutes the ops placeholders ({{OPS_SLUG}}, {{OPS_SLUG_UPPER}},
    {{OPS_POSTGRES_PORT}}) using the same plain placeholder-substitution
    mechanism the rest of bootstrap uses — every `<product>-*` literal in
    the rendered ops/ derives from `slug`. Only the literal `{{OPS_*}}`
    tokens are replaced, so docker `{{...}}` Go-template format strings in
    the template body are left intact.
    """
    body = read_ops_template(name)
    upper = slug.upper().replace("-", "_")
    body = body.replace("{{OPS_SLUG_UPPER}}", upper)
    body = body.replace("{{OPS_SLUG}}", slug)
    body = body.replace("{{OPS_POSTGRES_PORT}}", str(_ops_postgres_host_port(slug)))
    body = body.replace("{{OPS_VAULT_API_PORT}}", str(_ops_vault_api_host_port(slug)))
    body = body.replace(
        "{{OPS_VAULT_PROXY_PORT}}", str(_ops_vault_proxy_host_port(slug))
    )
    return body


def _ops_target_rel(rel_path: str, slug: str) -> str:
    """Return the on-disk relative target for an ops file, product-scoped.

    Per PDR-020 the dedicated shell image and its Dockerfile.<slug>-shell are
    retired, so every converged ops file keeps its fixed path (no slug-derived
    target filename remains). `slug` is retained for signature stability and
    future product-scoped target derivation.
    """
    return rel_path


def _skill_iterator_for(shop_type: str):
    """Return the package-data skill iterator for a shop type. A "lead" shop
    owns the canonical LEAD skill-group (templates/lead_skills/); a "bc" shop
    owns the BC skill tree (templates/skills/). (lead-5mr5.)"""
    return iter_lead_skill_files if shop_type == "lead" else iter_skill_files


def _pour_skills(target: Path, iterator=iter_skill_files) -> None:
    """Mirror a skills package-data tree into <target>/.claude/skills/.

    `iterator` selects which canonical skill set is poured — the BC skill tree
    (default) or the LEAD skill-group — so a lead shop pours its own group and a
    bc shop pours the BC tree."""
    skills_root = target / ".claude" / "skills"
    for rel, body in iterator():
        dest = skills_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)


def _mirror_skills(target: Path, iterator=iter_skill_files) -> None:
    """Mirror a skills package-data tree into <target>/.claude/skills/: re-pour
    drifted/missing (idempotent on byte-equality), remove managed files no
    longer shipped, prune empty dirs.

    Pruning is scoped to CANONICAL-MANAGED MEMBERS ONLY (lead-1e8d, supersedes
    scenario 159 / hash d29c551ef3f58dc9): a top-level skill directory
    "<name>/" is subject to pruning IFF "<name>" is a member of the canonical
    skill-group this mirror manages. Files and empty dirs under an unmanaged
    (e.g. experimentally-adopted) member-name directory are NEVER pruned, so
    such directories survive a mirror byte-for-byte.

    `iterator` selects the canonical skill set (BC tree or LEAD group) so update
    mirrors the set that matches the shop type."""
    skills_root = target / ".claude" / "skills"
    shipped = dict(iterator())
    for rel, body in shipped.items():
        dest = skills_root / rel
        if dest.exists() and dest.read_bytes() == body:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
    if skills_root.exists():
        # Canonical-managed member names: the top-level skill dirs this mirror
        # owns. Only paths under one of these are eligible for pruning; a
        # directory whose name is not a managed member (unmanaged/experimental)
        # is left untouched.
        managed_members = {rel.split("/", 1)[0] for rel in shipped}
        shipped_abs = {skills_root / rel for rel in shipped}

        def _is_under_managed_member(path: Path) -> bool:
            rel_parts = path.relative_to(skills_root).parts
            return bool(rel_parts) and rel_parts[0] in managed_members

        for path in sorted(skills_root.rglob("*")):
            if (
                path.is_file()
                and path not in shipped_abs
                and _is_under_managed_member(path)
            ):
                path.unlink()
        for path in sorted(skills_root.rglob("*"), reverse=True):
            if (
                path.is_dir()
                and _is_under_managed_member(path)
                and not any(path.iterdir())
            ):
                path.rmdir()


def _render_lead_ops_scaffolding(target: Path, slug: str) -> None:
    """Render the lead-shop ops files into the target directory, scoped to
    the product `slug`.

    Writes the top-level compose.yaml and the bin/ ops tools (shop-shell,
    shop-scenario-completion, agent-vault-provision, agent-vault-check, each
    with its owner-execute bit set), plus the .env.example scaffold and the
    footing script — all shop-owned, none under .claude/, every `<product>-*`
    literal derived from `slug`. Caller gates this on shop_type == "lead".

    No shell Dockerfile is emitted: the shop-shell convergence retired the
    `Dockerfile.<slug>-shell` render (PDR-020 / ADR-028), and `_LEAD_OPS_FILES`
    carries no shell-Dockerfile entry.
    """
    for template_name, rel_path, executable in _LEAD_OPS_FILES:
        body = render_ops_template(template_name, slug)
        dest = target / _ops_target_rel(rel_path, slug)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body)
        if executable:
            mode = dest.stat().st_mode
            # Set the owner-execute bit (scenario 3d94639d5af360d7).
            dest.chmod(mode | 0o100)
    _render_lead_env_example(target, slug)
    _render_lead_ops_coordinates(target, slug)
    _render_lead_footing_script(target, slug)


# The top-level .env.example scaffold (lead-llc1, scenario d8b53704e6e2584).
# This is DELIBERATELY rendered OUTSIDE the six-file `_LEAD_OPS_FILES`
# ops-tool enumeration (scenario cb1e585684ff4a14 pins exactly six ops-tool
# files). It is an additive top-level scaffold carrying placeholder-only
# broker credentials the rendered compose.yaml / bin/shop-shell consume
# (AGENT_VAULT_MASTER_PASSWORD, AGENT_VAULT_ADDR, AGENT_VAULT_TOKEN), so
# `cp .env.example .env` is executable as written. It is never under
# .claude/, and never enumerated alongside the six ops-tool files.
_LEAD_ENV_EXAMPLE_TEMPLATE = ".env.example"


def _render_lead_env_example(target: Path, slug: str) -> None:
    """Render the top-level placeholder-only .env.example for a lead shop.

    Additive to the six-file ops-tool set: rendered through the same
    placeholder-substitution mechanism (so {{OPS_SLUG}} comments stay
    slug-clean) but NOT part of `_LEAD_OPS_FILES`. Every value is a
    placeholder; no real secret material is written.
    """
    body = render_ops_template(_LEAD_ENV_EXAMPLE_TEMPLATE, slug)
    dest = target / ".env.example"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body)


# The lead-shop footing bootstrap script (tmpl-obj, scenario
# e69c18dd25104b5e). Like .env.example above, this is DELIBERATELY rendered
# OUTSIDE the six-file `_LEAD_OPS_FILES` ops-tool enumeration (scenario
# cb1e585684ff4a14 pins exactly six ops-tool files). It is the third member
# of the "starter compose, script, and .env.example" grouping the footing
# scenario names: an additive, shop-owned bin/footing the operator runs ONCE
# in a freshly forked "<slug>-lead" repo to reach SOLID FOOTING (bring up
# postgres + agent-vault, pour the lead structure via `shop-templates
# bootstrap`, create the <slug>-lead-beads repo, wire the git + beads
# remotes, prove footing with a `git push` + `bd dolt push`) and STOP there
# (no product Discovery, no BC creation). Product-scoped via {{OPS_SLUG}};
# never under .claude/; never enumerated alongside the six ops-tool files.
_LEAD_FOOTING_TEMPLATE = "footing"


def _render_lead_footing_script(target: Path, slug: str) -> None:
    """Render the executable top-level bin/footing for a lead shop.

    Additive to the six-file ops-tool set (NOT part of `_LEAD_OPS_FILES`):
    rendered through the same placeholder-substitution mechanism so every
    `<slug>-*` literal (the bootstrap shop name, the <slug>-lead-beads repo,
    the git/beads remotes) derives from `slug`. Written with its
    owner-execute bit set so a fresh operator can run `./bin/footing`.
    """
    body = render_ops_template(_LEAD_FOOTING_TEMPLATE, slug)
    dest = target / "bin" / "footing"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body)
    dest.chmod(dest.stat().st_mode | 0o100)


# The single-source ops-coordinates artifact (ADR-043 Phase 1, lead-0t5m).
# Like bin/footing and .env.example above, this is DELIBERATELY rendered OUTSIDE
# the six-file `_LEAD_OPS_FILES` ops-tool enumeration (it is a sourced DATA
# artifact, not a seventh ops tool — the "exactly six ops tools" scenario stays
# intact). Every bin/ ops script SOURCES bin/ops-coordinates and references its
# OPS_* variables; each derived coordinate is a defining literal here exactly
# once and a variable reference everywhere else.
_LEAD_OPS_COORDINATES_TEMPLATE = "ops-coordinates"


def _render_lead_ops_coordinates(target: Path, slug: str) -> None:
    """Render bin/ops-coordinates for a lead shop — the single source of the
    product's ops coordinates that every other bin/ ops script sources. Sourced,
    not executed (no execute bit)."""
    body = render_ops_template(_LEAD_OPS_COORDINATES_TEMPLATE, slug)
    dest = target / "bin" / "ops-coordinates"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body)


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


def _bd_init_in(target: Path, prefix: str | None = None) -> int:
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

    Per scenario 0636fba2c1445f9f (tmpl-am6, corrected re-dispatch), when
    `prefix` is given `bd init` is invoked with `--prefix <prefix>` so the
    new shop's tracker stamps issues with the product-derived prefix. This
    is bd's own contract for setting the issue prefix — it is stored under
    the hyphenated `issue-prefix` config key (`bd config get issue-prefix`),
    NOT a cosmetic `issue_prefix` YAML key bd never reads (the retired
    9e15d8cfd55b9541 approach). The `--skip-agents` flag is preserved.
    """
    # Per scenario 584e2f7352dc2a24 (lead-9s46 / WS-2): `bd init` MUST be
    # invoked with the explicit `--non-interactive` flag. The BD_NON_INTERACTIVE
    # env var ALONE is insufficient — empirically `BD_NON_INTERACTIVE=1 bd init`
    # on a TTY/stdin HANGS (reproduced: a fresh bc-lead container hung 6
    # minutes). The `--non-interactive` flag is what makes bd init non-blocking
    # on a controlling terminal; the env var is kept too (belt-and-suspenders).
    cmd = ["bd", "init", "--non-interactive", "--skip-agents"]
    if prefix is not None:
        cmd += ["--prefix", prefix]
    result = subprocess.run(
        cmd,
        cwd=str(target),
        capture_output=True,
        text=True,
        env={**os.environ, "BD_NON_INTERACTIVE": "1"},
    )
    if result.returncode != 0:
        print(
            f"shop-templates bootstrap: `bd init` failed in {target!s} "
            f"(exit {result.returncode}); stderr:\n{result.stderr}",
            file=sys.stderr,
        )
    return result.returncode


def _product_beads_remote(shop_name: str) -> str:
    """Return the product beads remote URL the new shop's bd tracker syncs to.

    Per tmpl-4k7 (PDR-019 U5 / ADR-040). The remote mirrors the convention
    this very repository's .beads/config.yaml carries — for shop name
    "shopsystem-templates" the committed sync.remote is
    "git+https://github.com/dstengle/shopsystem-templates-beads.git". The rule
    is therefore: the product beads remote is the shop's own sibling "-beads"
    repo under the same GitHub org the framework itself ships from
    (`dstengle`, the org of the shop-templates package — see README install
    URL and the ops Dockerfile base image). It introduces no new identity
    source beyond the bootstrap `--shop-name`.
    """
    return f"git+https://github.com/dstengle/{shop_name}-beads.git"


# The Dolt remote name bootstrap configures the new shop's tracker under.
# This mirrors how this very repository names its own bd Dolt remote
# (`bd dolt remote list` here reports `origin` ->
# git+https://github.com/dstengle/shopsystem-templates-beads.git), so the
# bootstrapped shop's remote naming is consistent with the framework's own.
_BD_DOLT_REMOTE_NAME = "origin"


def _configure_bd_dolt_remote(target: Path, shop_name: str) -> str:
    """Configure the new shop's bd dolt push remote via `bd dolt remote add`.

    Per scenario 0636fba2c1445f9f (tmpl-am6, corrected re-dispatch — supersedes
    the cosmetic 9e15d8cfd55b9541). The bd dolt push remote is a DB-side remote
    that bd reads only when it has been added by NAME via `bd dolt remote add
    <name> <url>` (verified against `bd dolt remote --help`); the retired
    `sync.remote` YAML key is the separate jsonl-sync remote bd does not use for
    dolt push, so writing it was cosmetic. `bd init` (invoked by `_bd_init_in`)
    initializes .beads/ but does not configure the dolt remote; bootstrap does
    that here so a freshly bootstrapped shop's `bd dolt remote list` shows the
    product remote without a manual follow-up.

    Like `_bd_init_in`, this spawns the `bd` subprocess and never imports the
    bd / beads Python internals (scenario 0c6f1c5d9bc4226e).

    Returns the configured remote URL, so the caller can run the `bd dolt push`
    smoke-test against the freshly-configured remote.
    """
    remote = _product_beads_remote(shop_name)
    add = subprocess.run(
        ["bd", "dolt", "remote", "add", _BD_DOLT_REMOTE_NAME, remote],
        cwd=str(target),
        capture_output=True,
        text=True,
    )
    if add.returncode != 0:
        print(
            f"shop-templates bootstrap: `bd dolt remote add` failed to "
            f"configure remote {_BD_DOLT_REMOTE_NAME!r} -> {remote!r} in "
            f"{target!s} (exit {add.returncode}); stderr:\n{add.stderr}",
            file=sys.stderr,
        )
        # Surface the failure to the caller via a sentinel-free contract:
        # raise so the caller's existing non-zero-exit handling kicks in.
        raise _BdConfigError(add.returncode)
    return remote


class _BdConfigError(Exception):
    """Internal: a bd config subprocess (remote add) exited non-zero.

    Carries the failing exit code so `_cmd_bootstrap` can propagate it as the
    bootstrap exit code, matching the existing "bd subprocess failed -> return
    its rc" discipline used by `_bd_init_in`.
    """

    def __init__(self, returncode: int) -> None:
        super().__init__(f"bd config subprocess exited {returncode}")
        self.returncode = returncode


def _push_credentials_available() -> bool:
    """Best-effort detection of GitHub push credentials in the environment.

    A cold INSTALL (§1) adopter typically has none. Running a live
    authenticated `bd dolt push` then BLOCKS waiting for git authentication,
    stalling the whole cold-bootstrap. We detect the common token signals so
    bootstrap can DEFER the push (offline, non-fatal) instead of hanging.
    Returns True when a GitHub token is present in the environment.
    """
    return bool(
        os.environ.get("GH_TOKEN", "").strip()
        or os.environ.get("GITHUB_TOKEN", "").strip()
    )


def _bd_dolt_push_smoke_test(target: Path, remote: str) -> int:
    """Run a `bd dolt push` smoke-test against the configured dolt remote.

    Per scenario 5ae67969a7f205d5 (corrected re-dispatch, supersedes the retired
    62eb2a8b9b617f4b). The dolt push remote is configured upstream by
    `_configure_bd_dolt_remote` (`bd dolt remote add <name> <url>`, scenario
    0636fba2c1445f9f); this smoke-test proves the freshly-wired tracker can
    actually reach that remote by pushing to it. On success it reports success
    (stdout) and returns 0; on a non-zero push it returns the failing exit code
    with a diagnostic on stderr that names the failed smoke-test — so a
    misconfigured or unreachable remote is caught at bootstrap time rather than
    at the first mid-work work_done emission.

    The REAL `bd dolt push` contract (verified via `bd dolt push --help` /
    `bd dolt remote --help`) takes NO positional argument: a Dolt remote must
    first be CONFIGURED by NAME via `bd dolt remote add <name> <url>` (which the
    config step now owns), and only then can `bd dolt push` (which targets the
    configured/default remote) reach it.

    CRITICAL: a bare `bd dolt push` against a tracker with NO dolt remote
    configured is a no-op — real bd prints "No remote is configured — skipping"
    and EXITS 0. A bare push could therefore silently PASS the smoke-test on a
    misconfigured tracker, defeating its entire purpose. So this function first
    GUARDS the push: it reads `bd dolt remote list` and, if no dolt remote is
    configured, FAILS LOUD (returns non-zero) with a diagnostic that NAMES the
    missing dolt remote (the expected remote name and URL) — rather than running
    a push that would no-op to exit 0. Only when a remote is configured does it
    run the bare `bd dolt push` and capture its REAL exit code.

    Like `_bd_init_in`, this spawns the `bd` subprocess and never imports the
    bd / beads Python internals (scenario 0c6f1c5d9bc4226e).
    """
    # Guard: a `bd dolt push` against an unconfigured tracker no-ops and exits
    # 0, so verify a dolt remote is actually configured before trusting the
    # push's exit code. `bd dolt remote list` prints each configured remote;
    # empty output means no remote is configured.
    remote_list = subprocess.run(
        ["bd", "dolt", "remote", "list"],
        cwd=str(target),
        capture_output=True,
        text=True,
    )
    if remote_list.returncode != 0 or not remote_list.stdout.strip():
        print(
            f"shop-templates bootstrap: `bd dolt push` smoke-test FAILED — no "
            f"dolt remote is configured. The expected dolt remote "
            f"{_BD_DOLT_REMOTE_NAME!r} -> {remote!r} is missing from "
            f"`bd dolt remote list` in {target!s} "
            f"(list exit {remote_list.returncode}; stdout: "
            f"{remote_list.stdout.strip()!r}). A bare `bd dolt push` against an "
            f"unconfigured tracker no-ops and exits 0, so the missing remote "
            f"would otherwise pass silently. Configure it via "
            f"`bd dolt remote add {_BD_DOLT_REMOTE_NAME} {remote}`.",
            file=sys.stderr,
        )
        return 1

    # A remote is configured. Push to it. `bd dolt push` takes no positional
    # argument; it targets the default/configured remote.
    result = subprocess.run(
        ["bd", "dolt", "push"],
        cwd=str(target),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"shop-templates bootstrap: `bd dolt push` smoke-test failed "
            f"against the configured dolt remote {remote!r} in {target!s} "
            f"(exit {result.returncode}); stderr:\n{result.stderr}",
            file=sys.stderr,
        )
    else:
        print(
            f"shop-templates bootstrap: `bd dolt push` smoke-test success "
            f"against the configured dolt remote {remote!r}."
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

    # Pour canonical skills into .claude/skills/. A "bc" shop pours the BC skill
    # tree; a "lead" shop pours the canonical LEAD skill-group (bring-up-bc,
    # create-bc) and NOTHING else. The two sets are distinct package-data
    # subtrees and never mix. (lead-5mr5, supersedes "lead shops pour no
    # skills".)
    _pour_skills(target, _skill_iterator_for(shop_type))

    # Lead-shop ops scaffolding (PDR-003 path F — shop-owned). For a
    # "lead" shop, render the converged five-file ops set (compose.yaml,
    # bin/shop-shell, bin/shop-scenario-completion, bin/agent-vault-provision,
    # bin/agent-vault-check) at the repo top level / under bin/, NEVER under
    # .claude/, and NO dedicated shell Dockerfile (PDR-020 retires it). For a
    # "bc" shop, render NONE of them — a BC runs inside a bc-launcher container
    # and never owns its own postgres or shell image (scenarios
    # 90138f78dfa46697, 82c069bd3fb3b1d4, 43e085e8627c7756, plus converged
    # 5730de0b80aa6a0b / 82c3a716143014a6).
    if shop_type == "lead":
        _render_lead_ops_scaffolding(target, _ops_slug(shop_name))

    # Bootstrap is idempotent over an already-initialized ".beads/" (scenario
    # 5786b555ee0732bf, lead-i8u — the "wrap an existing beads workspace"
    # case, brief 002). `bd init` aborts ("Found existing Dolt database...
    # Aborting") against a target that already carries a ".beads/" directory,
    # which would fail the whole bootstrap with no scaffold written. Per
    # architect option (a), DETECT the already-initialized ".beads/" and SKIP
    # the entire bd-tracker block — `bd init`, the `bd dolt remote add`, and
    # the `bd dolt push` smoke-test — so the pre-existing ".beads/" is
    # preserved byte-for-byte (every one of those subprocesses would mutate
    # it) while the rest of the canonical scaffold above is still written;
    # exit 0. The no-".beads/" init path (scenarios 2277308ce4fb92d2 /
    # 31a044e7d2eceaf4) is precondition-disjoint and runs unchanged below.
    if not (target / ".beads").exists():
        # Initialize .beads/ via a `bd init` subprocess, stamping the
        # product-derived issue prefix via `bd init --prefix <prefix>`
        # (scenario 0636fba2c1445f9f). The prefix reuses the established
        # product-slug derivation (`_ops_slug`: the --shop-name with a single
        # trailing "-product" stripped), tracking shop identity from the
        # single source of truth. shop-templates MUST NOT import bd / beads
        # internals and MUST NOT write to .beads/ directly (scenario
        # 0c6f1c5d9bc4226e).
        rc = _bd_init_in(target, prefix=_ops_slug(shop_name))
        if rc != 0:
            return rc

        # Configure the new shop's bd dolt push remote via `bd dolt remote
        # add` (scenario 0636fba2c1445f9f, supersedes the cosmetic
        # 9e15d8cfd55b9541). This wires the tracker to the product beads
        # remote the way bd actually reads it (a DB-side dolt remote, not a
        # cosmetic YAML key); it spawns the `bd` subprocess and does not
        # import bd / beads internals.
        try:
            remote = _configure_bd_dolt_remote(target, shop_name)
        except _BdConfigError as exc:
            return exc.returncode

        # Smoke-test the freshly-wired tracker: run `bd dolt push` against the
        # configured dolt remote (scenario 5ae67969a7f205d5, supersedes the
        # retired 62eb2a8b9b617f4b). The smoke-test first guards that a dolt
        # remote is actually configured (a bare push against an unconfigured
        # tracker no-ops and exits 0), failing loud with a diagnostic naming
        # the missing remote; on a non-zero push it likewise exits non-zero —
        # so a misconfigured / unreachable remote is caught here, not at the
        # first mid-work work_done emission.
        # A cold INSTALL (§1) adopter has no GitHub push credentials, so a live
        # authenticated `bd dolt push` would block waiting for git auth and
        # stall the cold-bootstrap. Detect the missing credential and DEFER the
        # push (offline, non-fatal) with a clear diagnostic, rather than running
        # a credential-requiring live push during scaffolding (lead-3t1o).
        if not _push_credentials_available():
            print(
                "shop-templates bootstrap: no GitHub push credentials detected "
                "(GH_TOKEN / GITHUB_TOKEN unset) — the `bd dolt push` "
                f"smoke-test against {remote!r} was SKIPPED (offline); the "
                "tracker push is DEFERRED, not run, so scaffolding does not "
                "block on git authentication. Run `bd dolt push` later once "
                "push credentials are configured."
            )
        else:
            rc = _bd_dolt_push_smoke_test(target, remote)
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

    # Step 6: mirror canonical skills into .claude/skills/; re-pour
    # drifted/missing files, remove managed files no longer shipped, prune empty
    # dirs. A "bc" shop mirrors the BC skill tree; a "lead" shop mirrors the
    # canonical LEAD skill-group. (lead-5mr5.)
    _mirror_skills(target, _skill_iterator_for(shop_type))

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
    # scaffolding files. Per lead-xjsq / PDR-020 (scenarios 3c496f8858b6b033,
    # 29caed838aebe9f7, 953b2102a6924c28): the converged ops set
    # (compose.yaml, bin/shop-shell, and the bin/ ops tools) is SHOP-OWNED
    # under PDR-003 path F's two-bucket model — update NEVER overwrites them;
    # the retired shell Dockerfile is no longer part of the set (the
    # ops-scaffolding
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

    The converged ops scaffolding files (compose.yaml, bin/shop-shell, and the
    bin/ ops tools) are shop-owned: this function NEVER writes to
    them. It only inspects on-disk content against the current canonical
    ops template body RENDERED for this shop's product slug (read from
    .claude/shop/name.md — the single identity source) and, on drift,
    prints an advisory to stderr that mirrors the name.md advisory pattern
    (scenario 132). Files that match canonical, or that are absent, produce
    no advisory.
    """
    name_file = target / ".claude" / "shop" / "name.md"
    shop_name = name_file.read_text().rstrip("\n") if name_file.exists() else ""
    slug = _ops_slug(shop_name)
    for template_name, rel_path, _executable in _LEAD_OPS_FILES:
        on_disk_rel = _ops_target_rel(rel_path, slug)
        dest = target / on_disk_rel
        if not dest.exists():
            continue
        canonical_body = render_ops_template(template_name, slug)
        if dest.read_text() == canonical_body:
            continue
        print(
            f"shop-templates update: advisory — the shop-owned ops "
            f"scaffolding file {on_disk_rel} has drifted from the current "
            f"canonical template body. shop-templates update did NOT modify "
            f"the shop-owned file {on_disk_rel}. To view the current canonical "
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
