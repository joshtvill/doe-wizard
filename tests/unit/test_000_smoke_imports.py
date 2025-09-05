import importlib

def test_screens_importable():
    for mod in [
        "screens.session_setup",
        "screens.files_join_profile",
        "screens.roles_collapse",
        "screens.modeling",
        "screens.optimization",
        "screens.handoff",
    ]:
        importlib.import_module(mod)

def test_services_importable():
    for mod in [
        "services.file_io",
        "services.joiner",
        "services.profiler",
        "services.roles",
        "services.modeling_train",
        "services.modeling_select",
        "services.opt_defaults",
        "services.opt_validation",
        "services.opt_candidate_pool",
        "services.opt_scoring",
        "services.opt_distance",
        "services.artifacts",
    ]:
        importlib.import_module(mod)

def test_utils_importable():
    for mod in [
        "utils.naming",
        "utils.time",
        "utils.normalize",
        "utils.regex",
        "utils.ops",
        "utils.rng",
        "utils.jsonsafe",
    ]:
        importlib.import_module(mod)