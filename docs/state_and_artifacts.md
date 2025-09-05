Perfect—locking on `response_metric` and using `docs/ui_ux_baseline_v1_20250829.md` as the baseline theme.

Below is the **Phase 0 deliverable** you can drop directly into your repo at `docs/state_and_artifacts.md`. It freezes the in-memory state schema, artifact BOM, autoload policy, gates, and versioning so refactors don’t churn later. I kept it concise, actionably specific, and consistent with our contracts.

---

# State & Artifacts Spec (MVP v0)

**Scope:** DOE Wizard (Project 2) S1–S6.
**Goal:** Freeze the app’s in-memory state keys, artifact inventory, cross-screen dependencies, autoload behavior, and HITL gates.

## 1) Global Conventions

* **Foldering:** All session artifacts live under `artifacts/<session_slug>/`.
* **Autosave:** On every “Next” click. Screens never write outside the session folder.
* **Schema versioning:** Every JSON/CSV writer must embed `"schema_version": "<semver or date-tag>"` in its header/metadata JSON; CSVs store a sidecar JSON when needed (e.g., `model_compare.meta.json`).
* **Fingerprinting:** We maintain a **dataset fingerprint** (hash of `merged.csv`) and a **roles signature** (hash of role map + collapse spec). These ride along in downstream artifacts to detect staleness.

## 2) In-Memory State (owned by `state.py`)

```text
session_slug: str                 # unique id (timestamp + short objective token)
objective: str                    # user-entered objective (S1)
context_tag: str                  # optional free text/tags (S1)
response_metric: str              # display label carried into S4/S5 metrics
paths: dict                       # absolute paths to latest artifacts (see §3)
fingerprint:                      # for staleness checks
  dataset_hash: str               # hash(merged.csv)
  roles_signature: str            # hash(role mapping + collapse spec)
ui: dict                          # transient per-screen UI; never persisted
schema_version: str               # app-level current schema set (e.g., "2025-08-29")
```

Helpers in `state.py`:

* `get_session() -> dict`
* `save_session(state: dict) -> None`
* `autoload_latest_artifacts(session_slug: str) -> dict`
* `fingerprint_check(...) -> dict` (returns {ok: bool, reasons: list})

## 3) Artifact Bill of Materials (BOM)

We **keep** only what’s needed for audit and resume; other intermediates are derived on demand.

### S1 — Session Setup

* `session_setup.json`
  Keys: `session_slug, objective, context_tag, response_metric, schema_version, created_utc, created_local`

### S2 — Files · Join · Profile

* `merged.csv`
  Notes: canonical, row-wise merged dataset post-join/parse.
* `profile.json`
  Keys: column types, NA counts, basic stats, detected id/group/time, dataset hash, `schema_version`.

### S3 — Roles & Collapse

* `modeling_ready.csv`
  Notes: post-collapse, filtered columns, encoded as needed.
* `datacard.json`
  Keys: roles map, collapse spec, response column, variance checks, **roles\_signature**, data caveats, `schema_version`.

### S4 — Modeling & Evaluation

* `model_compare.csv`
  Columns: model\_id, family, params\_digest, CV metrics (R², MAE, RMSE), training walltime.
* `champion_bundle.json`
  Keys: model\_id, family, feature\_list, scaler/encoder params, chosen metric(s), uncertainty proxy (if any), **dataset\_hash**, **roles\_signature**, `schema_version`.

### S5 — Optimization & Next Runs

* `optimization_settings.json`
  Keys: bounds per feature, constraints (≤, =, ≥), acquisition type (EI/UCB/PI), batch size, safety thresholds (distance, feasibility), `schema_version`.
* `proposals.csv`
  Columns: proposal\_id, feature values…, acquisition\_score, feasibility\_flag, distance\_flag, notes.
* `optimization_trace.json`
  Keys: random seed, scored candidate summary, top-k audit, timestamps, `schema_version`.

### S6 — Handoff

* `handoff_summary.md`
* `run_plan.csv`
* `traveler.md`
* `export_pack.zip` (includes the above + `proposals.csv` + `optimization_settings.json`)

### Per-screen logs (rotating JSONL)

* `artifacts/<slug>/<slug>_screenN_log.jsonl` for N=1..6 (append-only events with UTC + local timestamps)

## 4) Cross-Screen Autoload (enter-screen behavior)

On each screen render:

1. Read `session_slug` from state (or prompt to pick a session).
2. `autoload_latest_artifacts(session_slug)`:

   * Locate latest prior artifacts per BOM.
   * Validate `schema_version` alignment (hard-fail with actionable message if mismatch).
   * Compare **dataset\_hash**/**roles\_signature** where applicable:

     * If mismatch, **soft-block** with HITL modal:
       “Artifacts appear stale for this screen due to changes in upstream data/roles. Recompute now or continue with stale artifacts (not recommended).”
3. Load only **paths and small metadata** into memory; lazy-load large CSVs on demand.

## 5) Gates & HITL Acknowledgments

* **S3 Gate (variance):** Response variance must be > 0. Otherwise require “Variance Acknowledgment” to proceed.
* **S4 Gate (predictive power):** Champion `R²` must be ≥ floor (configurable in constants). Otherwise require “Low-R² Acknowledgment.”
* **S5 Gate (feasible set):** If feasible set is empty, show **L0–L4 ladder** with suggestions to relax bounds/constraints. Also flag **distance\_from\_data** outliers and allow proceed only with HITL “Out-of-Hull Acknowledgment.”
* **S6 Gate (approval):** Require final approval checkbox + approver name/time stamp before exports.

## 6) Naming, Versions, and Timestamps

* **Session slug:** `YYYYMMDD_HHMMSS-<short_objective_token>`
* **CSV sidecars** (when metadata needed): `foo.csv`, `foo.meta.json`.
* **Timestamps:** Always write both `*_utc` and `*_local` (local = America/Los\_Angeles).
* **Schema version string:** single source of truth in `constants.py` (e.g., `SCHEMA_VERSION = "2025-08-29"`).

## 7) Performance Budgets (MVP)

* S2 join/profile ≤ 8s
* S4 training ≤ 60s (on synthetic dataset)
* S5 proposal generation + scoring ≤ 5s

## 8) Security & Privacy (MVP)

* No PII; files read from user-provided CSVs only.
* Artifacts directory is git-ignored and local-only by default.
* Export packs are created on explicit user action (S6).
