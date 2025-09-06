# Run Plan CSV — Schema

**Filename:** `/artifacts/<session_slug>/<session_slug>_run_plan.csv`  
**Producer:** S6 Handoff (derived from proposals)  
**Purpose:** Operator-friendly plan (units, simplified headers).  
**Rule:** Values must correspond 1:1 with proposals; only headers/units and ordering may change.

## Columns

- `Run_ID` — integer (1..N)
- Decision variables with **operator headers + units**, e.g.:
  - `Pad Speed [m/s]`
  - `Platen RPM [rpm]`
  - `Slurry Type [code]`
  - `Downforce [kPa]`
- `Expected_Response (y_mean)`
- `Uncertainty (y_std)`
- `Notes` (optional)

## Invariants

- Row count equals number of accepted proposals.
- Sorting must be documented (default: ascending `rank` from proposals).

