# MVP Blockers — Diagnosis & Action Plan
Version: v1 (2025-08-29)

## Diagnosis — Why progress stalls
1) **No enforced vertical slice:** You pause to perfect cross-screen “synergy” before a single end-to-end happy path exists. Result: refactors without a working spine.
2) **UI perfection early:** Reworking layout/details before logic stabilizes. Result: churn and regressions across screens.
3) **Schemas undefined (until now):** Without JSON/CSV schemas, artifacts drift and code contracts are implicit. Result: orchestration bugs and brittle “Next” gates.
4) **Env thrash & tool friction:** Conda/versions drift; PS vs. bash confusion; local scripts missing. Result: slow spin-up every session.
5) **Thread context fragmentation:** New threads lack a compact, up-to-date truth set; you restart design docs mid-flight. Result: re-deciding settled choices.
6) **PR scope too broad:** Large diffs spanning multiple concerns. Result: hard reviews, hidden regressions.
7) **No golden fixtures early:** Without tiny fixtures and smoke scripts, you overfit to real data quirks and miss fast feedback.

## What you’re *not* missing (good news)
- You now have: contracts v2, screen orchestration map, system design, build plan, and module map.
- Your instincts on HITL gates, autosave-on-Next, and single-click UX are correct—keep them.

## Action Plan — What to lock *now*
1) **Artifacts are the contract.** Adopt the provided schemas as the source of truth (below). Any screen “Next” must write them.
2) **Vertical slices over broad polish.** Deliver Slice A→E (S2→S6) sequentially; UI minimal until Slice D.
3) **Tiny fixtures + smoke scripts.** Use PS smoke scripts (included) to validate each phase without Streamlit.
4) **Versioned env & reqs.** Use the pinned requirements + Python 3.11; include one-liner PS setup in repo.
5) **Small PRs with DoD.** ≤300 LOC, single module/concern, must update tests & schemas.
6) **Decision log.** Record changes once, then stop revisiting unless broken in tests.
7) **UI baseline frozen.** Lock the UI rules in the style guide; defer redesign until MVP passes Slice E.

## Success Criteria (MVP)
- Click-through S1→S6 on fixtures in < 2 minutes; each screen writes its artifacts.
- Modeling trains ≥2 models; champion selected; optimization yields ≥1 feasible batch.
- Handoff pack (`export_pack.zip`) builds with stamped approvals.
