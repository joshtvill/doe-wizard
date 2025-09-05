# services/s1_adapter.py
from utils.naming import make_session_slug

def compute_slug(
    project_name: str,
    context_tag: str = "",
    objective: str = "",
    response_metric: str = "",
    date_str: str | None = None,
) -> str:
    return make_session_slug(project_name, context_tag, objective, response_metric, date_str=date_str)

def validate_session_inputs(name: str, objective: str, response_type: str,
                            context_tag: str, response_metric: str) -> tuple[bool, list[str]]:
    errs: list[str] = []
    if not (name and name.strip()): errs.append("Session Title is required.")
    if objective not in {"Maximize", "Minimize"}: errs.append("Objective must be Maximize/Minimize.")
    if response_type not in {"Continuous", "Categorical"}: errs.append("Response Type must be Continuous/Categorical.")
    if not (context_tag and context_tag.strip()): errs.append("Context Tag is required.")
    if not (response_metric and response_metric.strip()): errs.append("Response Metric is required.")
    return (len(errs) == 0, errs)
