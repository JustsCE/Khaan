# Vericity Transactions — Integration Guide

Backend complete. Frontend components complete. This doc is the exact playbook for wiring it in.

---

## What's ready in `~/vericity-transactions/`

| File | Status |
|------|--------|
| `migration_create_transactions.sql` | Ready — run on inudat (needs go-ahead) |
| `load_transactions.py` | Ready — loads S3 CSVs, geocodes, caches to `~/.cache/riga-geocode.json` |
| `transactions_router.py` | Ready — FastAPI router: GET /transactions, /stats, /{id} |
| `frontend/useTransactions.ts` | Ready — data hook + filter state |
| `frontend/TransactionsLayer.tsx` | Ready — ArcGIS GraphicsLayer, colour by €/m², popups in Latvian |
| `frontend/TransactionFilters.tsx` | Ready — custom Tailwind slide-in panel, filters: rooms/district/year/price/area |
| `frontend/TransactionsToggle.tsx` | Ready — the single integration point |

---

## Step 1 — Run the migration

```bash
sqlcmd -S $INUDAT_SQL_SERVER -d $INUDAT_SQL_DATABASE -U $INUDAT_SQL_USER \
  -P $INUDAT_SQL_PASSWORD -i migration_create_transactions.sql
```

Then load the data with geocoding (first run only — subsequent runs use the cache):
```bash
python3 load_transactions.py --geocode
```

> **Note:** First geocode run will take time — Nominatim rate-limits to 1 req/sec and each unique building address needs one lookup. Expect 30–90 min depending on how many distinct buildings are in the data. Results are cached to `~/.cache/riga-geocode.json`; re-runs skip already-resolved addresses. Without `--geocode`, lat/lng/district will be NULL and no points appear on the map.

---

## Step 2 — Wire the FastAPI router

In the Vericity FastAPI `main.py` (alongside the listings router):

```python
from transactions_router import router as transactions_router
app.include_router(transactions_router, prefix="/api/v1")
```

Copy `transactions_router.py` into the backend source directory.

Required env vars (same DB as listings):
```
INUDAT_SQL_SERVER=...
INUDAT_SQL_DATABASE=...
INUDAT_SQL_USER=...
INUDAT_SQL_PASSWORD=...
```

---

## Step 3 — Wire the frontend

Copy the 4 files from `frontend/` into the Vericity frontend source tree (alongside the existing map components).

Find the component that holds the ArcGIS `MapView` (likely `PropertyMap.tsx`, `MapComponent.tsx`, or similar). It will have a `useRef` holding the ESRI view and a toolbar/controls section.

Add **one import**:
```tsx
import { TransactionsToggle } from "./TransactionsToggle";
```

Add **one line** in the map toolbar JSX (wherever the other layer/control buttons live):
```tsx
<TransactionsToggle view={mapViewRef.current} />
```

That's it. The toggle owns everything: layer on/off, filter panel, data fetching, ESRI graphics.

---

## Dependencies

No new dependencies required. All 4 components use only:
- `@arcgis/core` — already in the Vericity stack
- React 18 — already in the Vericity stack
- Tailwind CSS — already in the Vericity stack

`TransactionFilters.tsx` is a custom slide-in panel using Tailwind only — no Radix UI.

---

## UI decision

The Q3 answer is: **map layer toggle** — consistent with listings UX, no new page, zero route changes. The `TransactionsToggle` button drops into the existing toolbar with a 💰 Darījumi label, activates the layer, and opens the filter panel.

---

## What's blocked until Justs decides

- Migration go-ahead → Step 1
- Repo access on goodhealth.lv → Steps 2 + 3 (or Justs integrates locally from this doc)
