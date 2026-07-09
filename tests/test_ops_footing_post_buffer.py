"""Pin the durable http.postBuffer fix in the shopsystem-templates-owned
footing template (work_id: lead-x4s3; finding lead-d4ja).

The agent-vault 0.32.0 credential-injection proxy returns 413 for chunked
(Transfer-Encoding) request bodies, size-independent. git streams any push
larger than http.postBuffer (~1 MiB default) as chunked, so large dolt/git
pushes fail. Setting http.postBuffer to 1 GiB forces git to buffer and send a
single Content-Length request the proxy accepts. Footing writes ~/.gitconfig
at bootstrap fleet-wide (lead + every BC), so rendering the setting there makes
the fix DURABLE — it survives rebuild-from-image rather than living only in a
session ~/.gitconfig.

The value is exactly 1073741824 (1 GiB), matching the proxy's
MAX_REQUEST_BYTES 1 GiB request cap — a larger postBuffer would let git emit a
>1 GiB Content-Length body the proxy's request cap then rejects. The deeper
broker-image chunked-body fix stays SEPARATE (still tracked on lead-d4ja);
this pin is only the flat additive config line.

This is ADDITIVE to footing's existing scenario pins (author identity
0761c8febe333f50, out-of-band insteadOf auth 513c7a7e642541dd, footing
sequence e69c18dd25104b5e): none asserts a closed/exhaustive git-config set,
so the extra global write contradicts none of them.
"""
import re

from shop_templates.cli import render_ops_template


_POST_BUFFER_LINE = "git config --global http.postBuffer 1073741824"
_INSTEADOF_MARKER = 'git config --global url.'
# A default (shopsystem) and a non-default (dummyco) product slug: the second
# guards the "no new shopsystem literal for an arbitrary slug" clause.
_SLUGS = ("shopsystem", "dummyco")


def _footing_body(slug: str = "shopsystem") -> str:
    return render_ops_template("footing", slug)


def _code_lines(body: str) -> list[str]:
    """Non-comment, non-blank lines — what footing actually EXECUTES."""
    out = []
    for raw in body.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(raw)
    return out


def test_footing_renders_exact_post_buffer_line():
    """The rendered footing carries the EXACT postBuffer write, for every slug
    (durable across rebuild-from-image because it is in the shipped render, not
    a session-only edit)."""
    for slug in _SLUGS:
        body = _footing_body(slug)
        assert _POST_BUFFER_LINE in body, (
            f"{slug} rendered footing lacks the exact line {_POST_BUFFER_LINE!r}"
        )


def test_footing_post_buffer_value_is_exactly_one_gib():
    """The value is exactly 1073741824 (1 GiB) — matching the proxy
    MAX_REQUEST_BYTES cap — and no larger value is used."""
    body = _footing_body()
    # The postBuffer global write appears with exactly 1073741824 as its value.
    m = re.search(r"git config --global http\.postBuffer (\d+)", body)
    assert m is not None, "no `git config --global http.postBuffer <value>` write in footing"
    assert m.group(1) == "1073741824", (
        f"http.postBuffer value is {m.group(1)!r}, expected exactly '1073741824' (1 GiB); "
        f"a larger value would emit a >1 GiB Content-Length body the proxy rejects"
    )


def test_footing_post_buffer_is_a_global_config_write():
    """The postBuffer write is a GLOBAL git config write (`--global`), so it
    lands in ~/.gitconfig at bootstrap and survives rebuild-from-image — not a
    repo-local `git config` that would be lost with the checkout."""
    body = _footing_body()
    assert _POST_BUFFER_LINE in body, "exact global postBuffer line missing"
    # And it is not accidentally repo-local: no bare `git config http.postBuffer`.
    assert not re.search(r"git config http\.postBuffer", body), (
        "http.postBuffer must be written --global (to ~/.gitconfig), not repo-local"
    )


def test_footing_post_buffer_positioned_among_global_git_config_writes():
    """The postBuffer write sits alongside the other global git-config writes —
    adjacent to the existing `git config --global url."...".insteadOf` write —
    so all of footing's ~/.gitconfig writes live together, not scattered."""
    lines = _code_lines(_footing_body())
    pb_idx = next(
        (i for i, ln in enumerate(lines) if _POST_BUFFER_LINE in ln), None
    )
    io_idx = next(
        (i for i, ln in enumerate(lines) if _INSTEADOF_MARKER in ln and ".insteadOf" in ln),
        None,
    )
    assert pb_idx is not None, "postBuffer write not found among executed lines"
    assert io_idx is not None, "insteadOf global write not found among executed lines"
    assert abs(pb_idx - io_idx) == 1, (
        "the http.postBuffer global write must be immediately adjacent to the "
        f"insteadOf global write (postBuffer at code-line {pb_idx}, insteadOf at "
        f"{io_idx}); they are the fleet-wide ~/.gitconfig global writes and belong together"
    )


def test_footing_post_buffer_introduces_no_shopsystem_literal():
    """For a non-default slug (dummyco) the rendered footing carries no
    'shopsystem' literal — the additive line introduces no hardcoded product
    literal (zero-product-literal discipline)."""
    body = _footing_body("dummyco")
    assert _POST_BUFFER_LINE in body, "postBuffer line missing from dummyco render"
    assert "shopsystem" not in body.lower(), (
        "rendered dummyco footing contains a 'shopsystem' literal"
    )
