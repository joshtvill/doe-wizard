"""S1 adapter: session setup helpers (pure; no I/O)."""
from utils.naming import auto_slug

def compute_slug(project_name: str, date_str: str | None = None) -> str:
    return auto_slug(project_name, date_str=date_str)

def validate_session_inputs(name: str, objective: str, response_type: str,
                            context_tag: str, response_metric: str) -> tuple[bool, list[str]]:
    errs: list[str] = []
    if not (name and name.strip()): errs.append("Session Title is required.")
    if objective not in {"Maximize", "Minimize"}: errs.append("Objective must be Maximize/Minimize.")
    if response_type not in {"Continuous", "Categorical"}: errs.append("Response Type must be Continuous/Categorical.")
    if not (context_tag and context_tag.strip()): errs.append("Context Tag is required.")
    if not (response_metric and response_metric.strip()): errs.append("Response Metric is required.")
    return (len(errs) == 0, errs)
