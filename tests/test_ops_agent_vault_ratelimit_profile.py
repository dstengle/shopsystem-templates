"""Pin the AGENT_VAULT_RATELIMIT_PROFILE env knob on the agent-vault broker
service in the shopsystem-templates-owned ops compose template (work_id:
lead-1xh8, product decision brief 016).

Product posture (brief 016, David 2026-07-08, not open for re-litigation):
the credential-injection-proxy rate-limit is DISABLED BY DEFAULT, fleet-wide,
opt-in to re-enable. The rendered agent-vault service environment therefore
declares AGENT_VAULT_RATELIMIT_PROFILE with an explicit `off` default via the
`${AGENT_VAULT_RATELIMIT_PROFILE:-off}` interpolation idiom — so with the var
unset in the instance environment the effective value is `off` and
`docker compose up` emits no "variable is not set" warning for it, while any
non-off instance value overrides the default and reaches the container.

This is ADDITIVE to the existing agent-vault render pin
@scenario_hash:568e33d4d441069b (ops_agent_vault_broker_render.feature): the
AGENT_VAULT_MASTER_PASSWORD entry and every other agent-vault field are
preserved, and no new "shopsystem" literal is introduced (the block derives
its product-scoped names from the bootstrap slug).
"""
from pathlib import Path

from shop_templates.cli import render_ops_template

from test_ops_generification import _yaml_load

# A default (shopsystem) and a non-default (dummyco) product slug: the second
# guards the "no new shopsystem literal for an arbitrary slug" clause.
_SLUGS = ("shopsystem", "dummyco")

_KEY = "AGENT_VAULT_RATELIMIT_PROFILE"
_EXPECTED_FORM = "${AGENT_VAULT_RATELIMIT_PROFILE:-off}"
_MASTER_KEY = "AGENT_VAULT_MASTER_PASSWORD"


def _agent_vault_env(slug: str) -> dict:
    rendered = render_ops_template("compose.yaml", slug)
    data = _yaml_load(rendered)
    assert isinstance(data, dict), f"{slug} compose.yaml did not parse to a mapping"
    av = data["services"]["agent-vault"]
    env = av["environment"]
    if isinstance(env, list):
        env = {
            e.split("=", 1)[0]: (e.split("=", 1)[1] if "=" in e else "")
            for e in (str(x) for x in env)
        }
    assert isinstance(env, dict), f"{slug} agent-vault environment is not a mapping/list"
    return env


def test_agent_vault_env_declares_ratelimit_profile_default_off():
    """The rendered agent-vault env block declares AGENT_VAULT_RATELIMIT_PROFILE
    with the `${AGENT_VAULT_RATELIMIT_PROFILE:-off}` default (explicit off, the
    unset-effective value), matching the file's existing ${VAR:-default} idiom."""
    for slug in _SLUGS:
        env = _agent_vault_env(slug)
        assert _KEY in env, (
            f"{slug} agent-vault environment lacks {_KEY!r}: {env!r}"
        )
        assert str(env[_KEY]) == _EXPECTED_FORM, (
            f"{slug} {_KEY} value is {env[_KEY]!r}, expected {_EXPECTED_FORM!r} "
            f"so an unset instance var renders to 'off' with no compose warning"
        )


def test_ratelimit_profile_default_is_off_and_overridable():
    """The default segment of the interpolation is exactly `off` (unset => off),
    and the interpolated key equals the env var name so a non-off instance value
    overrides the default and reaches the container."""
    for slug in _SLUGS:
        val = str(_agent_vault_env(slug)[_KEY])
        # `${AGENT_VAULT_RATELIMIT_PROFILE:-off}`: `:-off` is the default arm.
        assert val.endswith(":-off}"), (
            f"{slug} {_KEY} default arm is not ':-off' (unset must yield 'off'): {val!r}"
        )
        assert _KEY in val and val.startswith("${"), (
            f"{slug} {_KEY} is not sourced from the instance environment (an "
            f"instance override must reach the container): {val!r}"
        )


def test_master_password_entry_preserved():
    """Additive change: the existing AGENT_VAULT_MASTER_PASSWORD entry, sourced
    from the instance environment, is preserved (pin 568e33d4d441069b stays
    green)."""
    for slug in _SLUGS:
        env = _agent_vault_env(slug)
        assert _MASTER_KEY in env, (
            f"{slug} agent-vault environment lost {_MASTER_KEY!r}: {env!r}"
        )
        val = str(env[_MASTER_KEY])
        assert _MASTER_KEY in val and "$" in val, (
            f"{slug} {_MASTER_KEY} is no longer instance-sourced: {val!r}"
        )


def test_ratelimit_profile_introduces_no_shopsystem_literal():
    """For a non-default slug (dummyco) the rendered agent-vault block carries
    no 'shopsystem' literal — the knob introduces no hardcoded product literal."""
    rendered = render_ops_template("compose.yaml", "dummyco")
    assert "shopsystem" not in rendered.lower(), (
        "rendered dummyco compose.yaml contains a 'shopsystem' literal"
    )
    # And the new key really is present in that non-default render.
    assert _KEY in rendered, f"{_KEY} missing from dummyco render"
