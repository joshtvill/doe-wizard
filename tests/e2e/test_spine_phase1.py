from screens import session_setup, files_join_profile, roles_collapse, modeling, optimization, handoff

def _ok(d: dict) -> bool:
    return bool(d.get("valid_to_proceed", False))

def test_render_contracts():
    for mod in [session_setup, files_join_profile, roles_collapse, modeling, optimization, handoff]:
        out = mod.render()
        assert isinstance(out, dict)
        assert "valid_to_proceed" in out
        assert isinstance(_ok(out), bool)
