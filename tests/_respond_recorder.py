"""Test seam: a fake `shop-msg` that records its argv to a sentinel file.

Used as the `--respond-cmd` base for bc-emit work-done end-to-end tests so a
test can observe whether the wrapper invoked the real respond primitive — the
wrapper must NOT invoke it on any precondition refusal. argv[1] is the sentinel
path; the remaining argv (the `respond work_done ...` the wrapper appends) is
written there.
"""
import sys

sentinel = sys.argv[1]
with open(sentinel, "w") as fh:
    fh.write("\n".join(sys.argv[2:]))
sys.exit(0)
