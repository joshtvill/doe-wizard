# System Design — CMP AI‑Guided DOE Wizard
**Version:** v1  
**Date:** 2025‑08‑29  
**Scope:** End‑to‑end architecture for a Streamlit app that ingests DOE‑style data, produces a modeling‑ready dataset, trains surrogate models, runs Bayesian optimization, and exports next‑run plans with HITL guardrails.

---

## 1) Overview

**Goal:** Deliver a production‑grade MVP that is simple, testable, and extensible. Screens (S1–S6) are thin; business logic lives in `services/`; formatting and controls in `ui/`; shared helpers in `utils/`. Artifacts (CSV/JSON/MD/ZIP) are the **single source of audit truth**; active data moves **in memory** between screens for speed.

**Key principles**
- **Contracts first:** screen‑level contracts define behavior; this design maps modules to those contracts.
- **Single‑click UX:** shared UI handlers prevent double‑submit race conditions.
- **Autosave‑on‑Next:** each screen writes minimal reproducible artifacts before routing.
- **HITL gates:** explicit acknowledgments for risky states; circuit breaker for infeasible optimization.
- **Local‑first:** no network calls by default; secure file I/O within project workspace only.

---

## 2) Architecture & Module Layout

```
repo/
  app.py                 # router/bootstrap (thin)
  constants.py           # tunables & budgets (k defaults, caps, thresholds)
  state.py               # session state schema & helpers

  screens/
    session_setup.py
    files_join_profile.py
    roles_collapse.py
    modeling.py
    optimization.py
    handoff.py

  services/
    session_setup_store.py
    file_io.py           # upload/paths, CSV read, safe writes
    joiner.py            # key‑pair joins
    profiler.py          # table/column summaries + alerts
    roles.py             # role assignment, collapse executor
    modeling_train.py    # RF/XGB/GPR, CV, metrics, diagnostics
    modeling_select.py   # champion selection, rationale
    opt_defaults.py      # k‑linked bounds from training stats
    opt_validation.py
    opt_candidate_pool.py
    opt_scoring.py       # EI/PI/UCB + greedy q‑EI, diversity
    opt_distance.py      # numeric+categorical distance
    artifacts.py         # cross‑screen read/write & export pack

  ui/
    theme.py
    blocks.py            # nav, status, headers, single‑click button
    tables.py            # data_editor wrappers, metrics tables
    dialogs.py           # forbidden interval modal, ACK modal
    downloads.py, progress.py, file_uploader.py

  utils/
    constants.py, typing_ext.py, exceptions.py
    logging.py, paths.py, naming.py, time.py, rng.py
    jsonsafe.py, normalize.py, regex.py, ops.py
    dataframe_ops.py, math_stats.py

  artifacts/             # outputs (git‑ignored)
  tests/                 # unit + golden + e2e
  docs/                  # README, USER_GUIDE, this SYSTEM_DESIGN, etc.
  .streamlit/            # theme, config
```

**Separation of concerns**
- **screens/** — orchestration only (call services, render with ui, enforce gates).
- **services/** — deterministic business logic; no Streamlit calls.
- **ui/** — consistent look/feel, navigation, preview tables, modals.
- **utils/** — pure helpers (I/O safety, logging, math, typing, exceptions).

---

## 3) Data & State Flow (S1→S6)

**In memory (fast path):** the active table and model objects pass from screen to screen.  

**On disk (audit path):** minimal artifacts are written at each **Next** for reproducibility.

### 3.1 Screen‑to‑Screen
- **S1 → S2:** `session_setup.json` (session slug, objective, response meta). In memory: session fields.
- **S2 → S3:** `profile.json` (+ optional `merged.csv`). In memory: active table (features or merged) + profile payload.
- **S3 → S4:** `modeling_ready.csv`, `datacard.json`. In memory: `collapsed_df`.
- **S4 → S5:** `model_compare.csv`, `champion_bundle.json` (+ optional `champion_model.pkl`). In memory: champion spec/handle.
- **S5 → S6:** `optimization_settings.json`, `proposals.csv`, `optimization_trace.json`. In memory: proposals DataFrame.

### 3.2 Artifact Map
| Artifact | Producer | Consumer | Purpose | Schema Ref |
|---|---|---|---|---|
| `<slug>_session_setup.json` | S1 | S2+ | Session identity & objective | `schemas/session_setup.json` |
| `<slug>_profile.json` | S2 | S3 | Table+column profile | `schemas/profile.json` |
| `<slug>_modeling_ready.csv` | S3 | S4 | Collapsed DOE dataset | CSV (tabular) |
| `<slug>_datacard.json` | S3 | S4+ | Roles, grouping keys, checks | `schemas/datacard.json` |
| `<slug>_model_compare.csv` | S4 | S5 | Model metrics table | CSV |
| `<slug>_champion_bundle.json` | S4 | S5 | Champion spec & metadata | `schemas/champion_bundle.json` |
| `<slug>_optimization_settings.json` | S5 | S6 | Optimization inputs | `schemas/optimization_settings.json` |
| `<slug>_proposals.csv` | S5 | S6 | Ranked next‑run plan | CSV |
| `<slug>_optimization_trace.json` | S5 | S6 | Audit of sampling/scoring/masking | `schemas/optimization_trace.json` |
| `<slug>_handoff_summary.md` | S6 | External | Human‑readable summary | Markdown |
| `<slug>_run_plan.csv` | S6 | External | Executable run plan | CSV |
| `<slug>_export_pack.zip` | S6 | External | Bundle for sharing | ZIP |

---

## 4) Contracts & Interfaces (high‑level)

### 4.1 Services — representative contracts (no code)
- **file_io.py** — `read_csv_smart(path) -> pd.DataFrame`, `save_artifact(obj, path) -> Path`
- **joiner.py** — `validate_keys(dfL, dfR, key_pairs) -> list[str]`, `execute_join(dfL, dfR, key_pairs, how='left') -> pd.DataFrame`
- **profiler.py** — `profile_table(df) -> dict`, `profile_columns(df) -> dict`, `detect_alerts(df) -> list`
- **roles.py** — `assign_roles(df, overrides) -> roles_map`, `execute_collapse(df, roles, grouping_keys, plan) -> pd.DataFrame`
- **modeling_train.py** — `train_rf(X,y,spec) -> model, metrics`, `train_xgb(...)`, `train_gpr(...)`, `compute_metrics(y, yhat) -> dict`
- **modeling_select.py** — `select_champion(results_df) -> champion_spec`, `generate_rationale(champion, runners_up) -> str`
- **opt_candidate_pool.py** — `sample_candidates(space, roles, constraints) -> pd.DataFrame`, `filter_candidates(pool_df, constraints, safeguards) -> pd.DataFrame`
- **opt_scoring.py** — `compute_ei(mu, sigma, best_y) -> np.ndarray`, `greedy_batch_select(scored_df, diversity_min, distance_fn) -> pd.DataFrame`
- **artifacts.py** — `load_artifact(path) -> obj/df`, `build_export_pack(paths) -> bytes`

### 4.2 UI — representative contracts
- **blocks.py** — `single_click_button(label, key) -> bool`, `status_zone(level, messages)`, `section_header(text)`
- **tables.py** — `dataframe_table(df, height=None)`, `metrics_table(scores_df)`
- **dialogs.py** — `open_acknowledge_warning_modal(msg) -> bool`

---

## 5) Orchestration per Screen (summary)

| Screen | Primary Services | Primary UI | Key Gates |
|---|---|---|---|
| **S1 Session Setup** | `session_setup_store` | `theme`, `blocks` | Required fields present |
| **S2 Files · Join · Profile** | `file_io`, `joiner`, `profiler` | `tables`, `blocks` | Valid join (if response), profile current, warnings ack |
| **S3 Roles & Collapse** | `roles`, `profiler` | `tables`, `dialogs` | ≥1 response; collapse executed if grouped; variance ack |
| **S4 Modeling** | `modeling_train`, `modeling_select`, `artifacts` | `tables`, (charts later) | ≥1 model, champion selected, quality ack |
| **S5 Optimization** | `opt_defaults`, `opt_validation`, `opt_candidate_pool`, `opt_scoring`, `opt_distance` | `tables`, `dialogs` | Valid constraints; feasible proposals; HITL L0–L2 |
| **S6 Handoff** | `artifacts` | `tables`, `downloads` | Approval checklist before export |

---

## 6) Schemas (concise)

### 6.1 `session_setup.json`
```json
{
  "schema_version": "1.0",
  "session_slug": "cmp_mrr_demo",
  "objective": "maximize",
  "response_metric": "MRR",
  "context_tag": "CMP",
  "timestamps": { "local": "...", "utc": "..." }
}
```

### 6.2 `datacard.json`
```json
{
  "schema_version": "1.0",
  "session_slug": "...",
  "responses": ["MRR"],
  "grouping_keys": ["wafer_id"],
  "features": {
    "knobs_run_varying": {"downforce": "avg", "pad_speed": "max"},
    "knobs_run_constant": ["slurry_id"],
    "usage_run_varying": {"pad_wafer_count": "last_by:time"},
    "excluded": ["timestamp"]
  },
  "checks": {"response_variance_groups": 0, "ack_response_variance": false},
  "collapsed_summary": {"n_rows": 100, "n_features": 25}
}
```

### 6.3 `champion_bundle.json`
```json
{
  "schema_version": "1.0",
  "model_type": "RF",
  "model_uid": "rf_20250829_1",
  "training_metrics": {"rmse": 12.3, "r2": 0.87},
  "feature_list": ["downforce","pad_speed","slurry_id_onehot_..."],
  "training_hash": "abc123",
  "notes": "selected by highest R², tiebreak RMSE"
}
```

(Other schema stubs: `profile.json`, `modeling_settings.json`, `optimization_settings.json`, `optimization_trace.json` — see docs/schemas.)

---

## 7) Error Handling & HITL Gates

- **Typed exceptions** in `utils/exceptions.py` (`UserInputError`, `ValidationError`, `JoinKeyError`, `ConfigError`).  

- **Surface rules:** services raise; screens catch → `ui.blocks.status_zone()` with next‑step tips.  

- **HITL acknowledgments:**  
  - S3 response variance, S4 low R², S5 near‑boundary proposals.  
  - L0–L4 framework in optimization: L0 auto pass → L4 circuit breaker (no feasible set).

---

## 8) Performance Budgets (targets)

- **S2 join+profile:** ≤ 5–8 s (100k×200)  

- **S3 collapse:** ≤ 5 s  

- **S4 training:** ≤ 30–60 s across RF/XGB/GPR (GPR autoskip threshold)  

- **S5 optimization:** candidate gen ≤ 5 s; scoring ≤ 5 s; batch build ≤ 3 s  

- **UI:** first paint < 1.5 s; progress feedback < 300 ms

If exceeded → yellow warning with mitigation tips (reduce columns, relax settings).

---

## 9) Testing Strategy

- **Unit tests (pytest):** utils/services deterministic logic.  

- **Golden files:** tiny fixtures for S2–S6; compare artifacts (CSV/JSON) byte‑wise.  

- **E2E smoke:** scripted S1→S6 on fixtures; assert artifacts written.  

- **Performance tests:** synthetic generator to validate budgets.  

- **Linters/type checks:** `ruff` + `mypy` (optional for MVP).

---

## 10) Build Order & Smoke Tests (bottom‑up)

1) **Phase 0 (Scaffold):** utils constants/exceptions/logging/paths/jsonsafe/naming; ui theme/blocks; services artifacts/session store.  

   **Smoke:** `pytest -q`; minimal app boots.
2) **Phase 1 (Data):** file_io, joiner, profiler (+ dataframe_ops/math_stats).  

   **Smoke:** CLI script prints join rate & profile alerts.
3) **Phase 2 (Roles):** roles, validation.  

   **Smoke:** CLI script prints groups, collapsed rows, variance warnings.
4) **Phase 3 (Modeling):** modeling_train, modeling_select (+ reporting minimal).  

   **Smoke:** champion table + rationale printed.
5) **Phase 4 (Optimization):** opt_defaults/validation/candidate_pool/scoring/distance.  

   **Smoke:** top‑N proposals with flags; non‑empty batch by default.
6) **Phase 5 (UI+Screens):** ui primitives, thin screens, router.  

   **Smoke:** S1→S6 clickable path on fixtures.

---

## 11) Deployment

- **Primary (free):** Streamlit Community Cloud — deploy from GitHub repo with a small **synthetic demo dataset** and canned artifacts.  

- **Backup:** HuggingFace Spaces (CPU).  

- **Local run:** `conda`/`uv` + `streamlit run app.py`.  

- **No binaries** (Windows EXE) shipped in MVP.

---

## 12) Security & Privacy

- Local‑first; explicit safe writes to `artifacts/`.  

- No outbound network calls by default.  

- MIT license by default (can adjust later).

---

## 13) Observability & Logging

- Screen logs: `screenX_log.json` with `{ts_local, ts_utc, session_slug, screen, event, level, details}`.  

- Each artifact includes timestamps and identifiers (`session_slug`, `dataset_hash`, `model_uid`).  

- Exceptions: stacktrace captured to log; user sees actionable summary.  

- Optional telemetry (off by default): event counters only.

---

## 14) Open Questions

1) Hosted demo target: Streamlit Cloud (default) vs HF Spaces?  

2) Demo dataset: synthetic CMP only, or add a small open bio‑process dataset?  

3) Telemetry: allow opt‑in anonymous counts for demo only?

---

## 15) Definition of Done (System‑level)

- Contracts S1–S6 implemented; autosave‑on‑Next artifacts produced.  

- Unit + golden + e2e tests passing; performance within budgets.  

- Hosted demo live; docs complete (README, USER_GUIDE, SYSTEM_DESIGN).  

- Version `v0.1.0` tagged; CHANGELOG updated.

---

## 16) Appendix — Risk & Mitigation (concise)

- **Double‑submit races:** shared `single_click_button()` wrapper; disable actions while running.  

- **Stale previews:** `last_execute_fingerprint` recompute gates on S2/S3/S5.  

- **Model leakage:** prefer GroupKFold path when grouping keys exist.  

- **Empty feasible set:** circuit‑breaker guidance (widen bounds, relax Δ, novelty/diversity).  

- **Schema drift:** bump `schema_version`, write migration or fail with clear message.

---

### Your Turn — Next Steps (short)
- Approve this design as the source of truth for code scaffolding.  

- Green‑light **Phase 0** (scaffold) and create tiny fixtures for S2–S5.  

- Decide hosted demo target and demo dataset choice.
