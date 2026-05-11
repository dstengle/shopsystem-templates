# shopsystem-templates

Templates bounded context of the shopsystem. Provides the four validated
role-prompt templates used by shops in a shopsystem-aligned product:

- `lead-po` — lead-shop product owner
- `lead-architect` — lead-shop architect
- `bc-implementer` — bounded-context implementer
- `bc-reviewer` — bounded-context reviewer

Templates ship as package data inside `shop_templates/templates/`. Consumers
read them through the `shop-templates` CLI rather than by filesystem path —
the CLI is the package's public boundary.

## Install

```bash
pip install "git+https://github.com/dstengle/shopsystem-templates@v0.1.0"
```

## Usage

```bash
shop-templates list
# bc-implementer
# bc-reviewer
# lead-architect
# lead-po

shop-templates show bc-implementer
# (prints the bc-implementer role prompt to stdout)
```

`shop-templates show <name>` exits non-zero with a stderr message if no
template matches that name.

In-process consumers can also read templates via `importlib.resources`
against the `shop_templates.templates` package, but the CLI is the
documented surface.

## Naming

The repository is named `shopsystem-templates`; the Python package is
`shop_templates` and the CLI binary on `$PATH` is `shop-templates`. The
package and CLI keep their pre-extraction names per ADR-001's phase-1
"no CLI renames" rule.

## Context

Framework split rationale and sequencing:
[ADR-001](https://github.com/dstengle/ddd-product-system/blob/main/docs/shop-system/adr-001-framework-packaging.md).
