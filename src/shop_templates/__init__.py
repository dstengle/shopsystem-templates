"""Validated role-prompt templates for shops in the shop-system.

Templates are package data, not docs. Consume them via the `shop-templates`
CLI (or `importlib.resources` for in-process use), not by reading Markdown
at a known path. Same dogfooding rule the catalog and scenarios packages
already follow — production code crosses the package boundary through a
CLI surface, never by reading internals at a path.
"""
