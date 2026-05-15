"""
FastAPI router: /api/v1/transactions
Integrate into the Vericity FastAPI app alongside the existing listings router.

Mount with:
    from transactions_router import router as transactions_router
    app.include_router(transactions_router, prefix="/api/v1")
"""

from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import pyodbc
import os

router = APIRouter(tags=["transactions"])


# ── DB dependency ─────────────────────────────────────────────────────────────

def get_db():
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={os.environ['INUDAT_SQL_SERVER']},1433;"
        f"DATABASE={os.environ['INUDAT_SQL_DATABASE']};"
        f"UID={os.environ['INUDAT_SQL_USER']};"
        f"PWD={os.environ['INUDAT_SQL_PASSWORD']};"
        "Encrypt=yes;TrustServerCertificate=no;"
    )
    conn = pyodbc.connect(conn_str)
    try:
        yield conn
    finally:
        conn.close()


# ── Response models ───────────────────────────────────────────────────────────

class Transaction(BaseModel):
    id:                     int
    transaction_date:       str
    price:                  float
    area_apt:               float
    rooms:                  int
    room_address:           str
    building_cadastre_nr:   Optional[str]
    apt_cadastre_nr:        Optional[str]
    property_cadastre_nr:   Optional[str]
    min_floor:              Optional[int]
    max_floor:              Optional[int]
    building_material:      Optional[str]
    building_depreciation:  Optional[float]
    area_land:              Optional[float]
    price_per_sqm:          Optional[float]
    lat:                    Optional[float]
    lng:                    Optional[float]
    district:               Optional[str]


class TransactionStats(BaseModel):
    total_count:        int
    median_price:       Optional[float]
    median_price_sqm:   Optional[float]
    avg_area_apt:       Optional[float]
    date_min:           Optional[str]
    date_max:           Optional[str]
    rooms_distribution: dict[str, int]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/transactions", response_model=list[Transaction])
def list_transactions(
    rooms:       Optional[int]   = Query(None, ge=1, le=5),
    district:    Optional[str]   = None,
    year_from:   Optional[int]   = None,
    year_to:     Optional[int]   = None,
    price_min:   Optional[float] = None,
    price_max:   Optional[float] = None,
    area_min:    Optional[float] = None,
    area_max:    Optional[float] = None,
    limit:       int             = Query(200, le=1000),
    offset:      int             = 0,
    db: pyodbc.Connection = Depends(get_db),
):
    where, params = _build_where(rooms, district, year_from, year_to, price_min, price_max, area_min, area_max)
    sql = f"""
        SELECT
            id, CONVERT(VARCHAR, transaction_date, 23) AS transaction_date,
            price, area_apt, rooms, room_address,
            building_cadastre_nr, apt_cadastre_nr, property_cadastre_nr,
            min_floor, max_floor, building_material, building_depreciation,
            area_land, price_per_sqm, lat, lng, district
        FROM dbo.transactions
        {where}
        ORDER BY transaction_date DESC
        OFFSET {offset} ROWS
        FETCH NEXT {limit} ROWS ONLY
    """
    cursor = db.cursor()
    cursor.execute(sql, params)
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


@router.get("/transactions/stats", response_model=TransactionStats)
def transaction_stats(
    rooms:       Optional[int]   = Query(None, ge=1, le=5),
    district:    Optional[str]   = None,
    year_from:   Optional[int]   = None,
    year_to:     Optional[int]   = None,
    price_min:   Optional[float] = None,
    price_max:   Optional[float] = None,
    area_min:    Optional[float] = None,
    area_max:    Optional[float] = None,
    db: pyodbc.Connection = Depends(get_db),
):
    where, params = _build_where(rooms, district, year_from, year_to, price_min, price_max, area_min, area_max)
    cursor = db.cursor()

    # Aggregate stats (COUNT, AVG, MIN, MAX — pure aggregates, no window fns)
    cursor.execute(f"""
        SELECT
            COUNT(*)                                    AS total_count,
            AVG(area_apt)                               AS avg_area_apt,
            CONVERT(VARCHAR, MIN(transaction_date), 23) AS date_min,
            CONVERT(VARCHAR, MAX(transaction_date), 23) AS date_max
        FROM dbo.transactions
        {where}
    """, params)
    row = cursor.fetchone()
    if not row or row[0] == 0:
        raise HTTPException(status_code=404, detail="No transactions match the filter")

    # Percentiles — separate query (PERCENTILE_CONT is a window fn; can't mix with aggregates)
    cursor.execute(f"""
        SELECT DISTINCT
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price)         OVER () AS median_price,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_per_sqm) OVER () AS median_price_sqm
        FROM dbo.transactions
        {where}
    """, params)
    pct = cursor.fetchone()

    # Rooms distribution
    cursor.execute(f"""
        SELECT rooms, COUNT(*) AS cnt
        FROM dbo.transactions
        {where}
        GROUP BY rooms
        ORDER BY rooms
    """, params)
    rooms_dist = {str(r[0]): r[1] for r in cursor.fetchall()}

    return {
        "total_count":        row[0],
        "median_price":       round(pct[0], 2) if pct and pct[0] else None,
        "median_price_sqm":   round(pct[1], 2) if pct and pct[1] else None,
        "avg_area_apt":       round(row[1], 2) if row[1] else None,
        "date_min":           row[2],
        "date_max":           row[3],
        "rooms_distribution": rooms_dist,
    }


@router.get("/transactions/{transaction_id}", response_model=Transaction)
def get_transaction(transaction_id: int, db: pyodbc.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
        SELECT
            id, CONVERT(VARCHAR, transaction_date, 23) AS transaction_date,
            price, area_apt, rooms, room_address,
            building_cadastre_nr, apt_cadastre_nr, property_cadastre_nr,
            min_floor, max_floor, building_material, building_depreciation,
            area_land, price_per_sqm, lat, lng, district
        FROM dbo.transactions WHERE id = ?
    """, transaction_id)
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Transaction not found")
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


# ── Query builder ─────────────────────────────────────────────────────────────

def _build_where(rooms, district, year_from, year_to, price_min, price_max, area_min, area_max):
    clauses, params = [], []
    if rooms      is not None: clauses.append("rooms = ?");                              params.append(rooms)
    if district   is not None: clauses.append("district = ?");                           params.append(district)
    if year_from  is not None: clauses.append("YEAR(transaction_date) >= ?");            params.append(year_from)
    if year_to    is not None: clauses.append("YEAR(transaction_date) <= ?");            params.append(year_to)
    if price_min  is not None: clauses.append("price >= ?");                             params.append(price_min)
    if price_max  is not None: clauses.append("price <= ?");                             params.append(price_max)
    if area_min   is not None: clauses.append("area_apt >= ?");                          params.append(area_min)
    if area_max   is not None: clauses.append("area_apt <= ?");                          params.append(area_max)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params
