# Proposals CSV — Schema

**Filename:** `/artifacts/<session_slug>/<session_slug>_proposals.csv`  
**Producer:** S5 Optimization  
**Consumer(s):** S6 Handoff (export pack), Operators, Audits  
**Rule:** File must remain **unchanged** when included in S6 export pack.

## Columns (order not enforced, names are)

1. All decision variables (one column per variable; types per bounds_snapshot)
2. `y_mean` — float (predicted mean response)
3. `y_std` — float or empty (prediction uncertainty)
4. `acq_score` — float (acquisition score used for ranking)
5. `is_safety_ok` — boolean
6. `is_novelty_ok` — boolean
7. `is_diverse` — boolean
8. `rank` — integer (1 = best)
9. `batch_id` — integer (optional; present if batched proposals)
10. `acquisition` — string (e.g., "q-EI", "EI")
11. `seed` — integer or empty

## Invariants

- All rows must validate against the **typed bounds** and categorical levels.
- `rank` is a strict total order with no duplicates.
- If `batch_id` exists, each batch is internally ranked starting at 1.

## Example (header)

pad_speed,rpm,slurry,pressure,y_mean,y_std,acq_score,is_safety_ok,is_novelty_ok,is_diverse,rank,batch_id,acquisition,seed