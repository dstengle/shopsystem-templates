"""shop-templates CLI entry point.

Subcommands:
    list
        Print available template names (one per line) to stdout.
    show <name>
        Print the named template's content to stdout. Exits non-zero
        with a stderr message when no template matches that name.

Templates live in the package as `templates/<name>.md` data files. The
CLI is the public boundary; dispatchers, scaffold scripts, and any
other consumer reads templates via this surface rather than by path.
"""
from __future__ import annotations

import argparse
import sys
from importlib.resources import files


_TEMPLATES_PKG = "shop_templates.templates"


def _list_template_names() -> list[str]:
    """Return the sorted list of available template names (no extension)."""
    pkg_root = files(_TEMPLATES_PKG)
    names = []
    for resource in pkg_root.iterdir():
        name = resource.name
        if name.endswith(".md"):
            names.append(name[: -len(".md")])
    return sorted(names)


def _read_template(name: str) -> str | None:
    """Return the named template's content, or None if no such template."""
    try:
        return (files(_TEMPLATES_PKG) / f"{name}.md").read_text()
    except FileNotFoundError:
        return None


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shop-templates")
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="list available template names")
    list_cmd.set_defaults(func=_cmd_list)

    show_cmd = sub.add_parser("show", help="print a named template to stdout")
    show_cmd.add_argument("name", help="template name (e.g. bc-implementer)")
    show_cmd.set_defaults(func=_cmd_show)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
