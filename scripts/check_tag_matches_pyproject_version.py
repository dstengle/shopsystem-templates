#!/usr/bin/env python3
"""Release-process guard: fail if a pushed version tag vX.Y.Z does not match
the [project].version in pyproject.toml.

Wired into .github/workflows/release.yml so a tag cut with a lagging
pyproject (the v0.21.0 -> 0.20.0 regression pinned by scenario 192,
88a5418db371a12a) fails the release run instead of shipping bad dist
metadata.

Usage:
    check_tag_matches_pyproject_version.py --tag v0.21.0 [--pyproject path]

Exits 0 when the tag's version (the tag with its leading "v" removed) equals
the pyproject [project].version; exits non-zero (naming both versions) on any
mismatch.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - fallback for <3.11
    import tomli as tomllib  # type: ignore


def pyproject_version(pyproject_path: Path) -> str:
    data = tomllib.loads(pyproject_path.read_text())
    return data["project"]["version"]


def tag_version(tag: str) -> str:
    if not tag.startswith("v"):
        raise SystemExit(
            f"ERROR: release tag {tag!r} does not start with 'v'; expected "
            f"a version tag like 'v0.21.0'"
        )
    return tag[1:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True,
                        help="the pushed git tag, e.g. v0.21.0")
    parser.add_argument("--pyproject", default="pyproject.toml",
                        help="path to pyproject.toml (default: ./pyproject.toml)")
    args = parser.parse_args(argv)

    expected = tag_version(args.tag)
    actual = pyproject_version(Path(args.pyproject))

    if actual != expected:
        sys.stderr.write(
            f"ERROR: release tag {args.tag} expects pyproject "
            f"[project].version {expected!r}, but pyproject.toml declares "
            f"{actual!r}. Bump pyproject to {expected} before tagging so an "
            f"install from {args.tag} reports {expected} in its dist "
            f"metadata.\n"
        )
        return 1

    sys.stdout.write(
        f"OK: release tag {args.tag} matches pyproject "
        f"[project].version {actual}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
