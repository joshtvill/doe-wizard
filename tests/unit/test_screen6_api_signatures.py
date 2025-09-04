# tests/unit/test_screen6_api_signatures.py
import importlib
import inspect
from pathlib import Path


def test_screen6_public_api_shapes():
    mod = importlib.import_module("screens.handoff")

    # Ensure functions exist
    for name in ("discover_artifacts", "summarize", "compute_fingerprints", "build_bundle", "write_outputs"):
        assert hasattr(mod, name), f"missing {name}"

    # Signature checks (lightweight, aligned to current implementation)
    sig_disc = inspect.signature(mod.discover_artifacts)
    assert list(sig_disc.parameters.keys())[:2] == ["slug", "artifacts_dir"]

    sig_sum = inspect.signature(mod.summarize)
    # summarize(slug, included: Dict[str, List[str]]) -> Summary
    params_sum = list(sig_sum.parameters.keys())
    assert params_sum[0] == "slug"
    assert len(params_sum) == 2

    sig_fp = inspect.signature(mod.compute_fingerprints)
    # compute_fingerprints(inc: Dict[str, List[str]]) -> Fingerprints
    assert list(sig_fp.parameters.keys()) == ["inc"]

    sig_bundle = inspect.signature(mod.build_bundle)
    # build_bundle(slug, discovery: Discovery, summary: Summary, fingerprints: Fingerprints, ...)
    params_bundle = list(sig_bundle.parameters.keys())
    assert params_bundle[:4] == ["slug", "discovery", "summary", "fingerprints"]

    sig_write = inspect.signature(mod.write_outputs)
    # write_outputs(slug, artifacts_dir: Path, bundle: Dict, hitl_notes: Optional[str] = None)
    params_write = list(sig_write.parameters.keys())
    assert params_write[:3] == ["slug", "artifacts_dir", "bundle"]
