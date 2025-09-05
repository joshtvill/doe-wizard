# UI / UX Baseline — DOE Wizard (MVP)
Version: v1 (2025-08-29)

## Purpose
Stop aesthetic churn by freezing baseline rules for MVP. Defer redesign after Slice E.

## Layout & Typography
- **Page config**: set once at app start.
- **Base font**: Streamlit default; **base size 14**; headings 20/16.
- **Grid**: two-column helper with ratios 2:1 or 1:1; avoid deep nesting.
- **Tables**: preview first **100 rows**; max height **420 px**; horizontal scroll allowed.

## Buttons & Interactions
- **Single-click wrapper** for all actions.
- **Primary button**: Execute/Next. **Secondary**: Save. **Tertiary**: Reset/Back.
- Disable buttons while tasks run; show spinner + progress.
- Place **Save** buttons **above nav** (consistent across screens).

## Status & Errors
- **Status zone** per screen (bottom, above nav bar). Messages: Success / Warning / Error with concise tips.
- Errors are actionable and reference **row/field** when applicable.
- Provide a **“Fix next”** focus action for table errors.

## Navigation
- Nav bar at bottom (below status zone, above preview); stepper indicates active screen.
- “Next” is gated only by that screen’s acceptance rules.

## Charts (later pass)
- MVP can omit plots except parity/residuals if trivial; no custom colors for now.

## Downloads & Naming
- All downloads named: `<session_slug>_<artifact>.ext`.
- No spaces; lowercase; underscores; date optional.

## Acceptance (MVP)
- Single-click everywhere; gated Next; autosave-on-Next; consistent placement of Save/Reset/Next.
