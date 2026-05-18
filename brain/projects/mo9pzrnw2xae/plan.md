
# Vericity Transactions — Frontend Map Layer

## Final State (2026-05-13, Round 3)

All 7 deliverables built, reviewed, and verified. Two SQL bugs fixed in Round 2. No open TODOs in code.

---

## Deliverables

| File | Status | Notes |
|------|--------|-------|
| `migration_create_transactions.sql` | Verified | Idempotent IF NOT EXISTS, computed persisted price_per_sqm, 4 indexes (date/rooms/district/cadastre) |
| `load_transactions.py` | Built | S3 → dbo.transactions, Nominatim geocoding, file cache at ~/.cache/riga-geocode.json |
| `transactions_router.py` | Fixed + Verified | 2 SQL Server bugs fixed: (1) TOP+OFFSET conflict → OFFSET/FETCH NEXT, (2) PERCENTILE_CONT mixed with aggregates → split into 2 queries |
| `frontend/useTransactions.ts` | Verified | AbortController cancel-on-refilter, correct filter state, mappableCount derived |
| `frontend/TransactionsLayer.tsx` | Verified | ESRI dynamic imports, green→red €/m² colour scale (1k–5.5k range), Latvian popup, stable layerRef pattern |
| `frontend/TransactionFilters.tsx` | Verified | Pure Tailwind (no Radix dep), 5 filter types (rooms/district/year/price/area), stats bar, reset |
| `frontend/TransactionsToggle.tsx` | Verified | Single integration point, enabled/filtersOpen state, loading + error indicators |
| `INTEGRATION.md` | Fixed | Removed false @radix-ui/react-sheet dependency claim |

---

## Integration (what Justs does to ship)

**Step 1 — Migration go-ahead (decision only):**
```bash
sqlcmd -S $INUDAT_SQL_SERVER -d $INUDAT_SQL_DATABASE -U $INUDAT_SQL_USER \
  -P $INUDAT_SQL_PASSWORD -i migration_create_transactions.sql
python3 load_transactions.py
```

**Step 2 — Wire backend (1 line in main.py):**
```python
from transactions_router import router as transactions_router
app.include_router(transactions_router, prefix="/api/v1")
```

**Step 3 — Wire frontend (2 lines in map component):**
```tsx
import { TransactionsToggle } from "./TransactionsToggle";
// in toolbar JSX:
<TransactionsToggle view={mapViewRef.current} />
```

No new dependencies. No new routes. No schema changes to existing tables.

---

## Blockers (Justs decisions only)

1. **Migration go-ahead** — Justs confirms it's OK to run on inudat
2. **Repo access** — Justs integrates locally from INTEGRATION.md, or grants goodhealth.lv SSH/git access to vericity repo

---

## Out of scope (deferred, not forgotten)

- Q4: Display-only vs. feed into valuation retraining — deferred, display-only now
- Q5: VZD licensing on public display — Justs to confirm; feature can be gated behind auth if needed
