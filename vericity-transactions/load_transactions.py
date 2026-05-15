"""
Load Real Riga transactions from S3 into Azure SQL dbo.transactions.

Usage:
    python load_transactions.py [--dry-run] [--geocode]

Requires env vars:
    INUDAT_SQL_SERVER   inudat.database.windows.net
    INUDAT_SQL_DATABASE inudat
    INUDAT_SQL_USER
    INUDAT_SQL_PASSWORD
    AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY  (or instance role)
"""

import os
import io
import re
import json
import time
import argparse
import logging
from pathlib import Path

import boto3
import pandas as pd
import pyodbc
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

S3_BUCKET = "realrigafingoodhealth"
S3_KEY    = "real_riga/Transactions.xlsx"

COLUMN_MAP = {
    "transaction_date":     "transaction_date",
    "price":                "price",
    "area_apt":             "area_apt",
    "rooms":                "rooms",
    "room_address":         "room_address",
    "building_cadastre_nr": "building_cadastre_nr",
    "apt_cadastre_nr":      "apt_cadastre_nr",
    "property_cadastre_nr": "property_cadastre_nr",
    "min_floor":            "min_floor",
    "max_floor":            "max_floor",
    "building_material":    "building_material",
    "building_depreciation":"building_depreciation",
    "area_land":            "area_land",
}

INSERT_SQL = """
    INSERT INTO dbo.transactions (
        transaction_date, price, area_apt, rooms,
        room_address, building_cadastre_nr, apt_cadastre_nr, property_cadastre_nr,
        min_floor, max_floor, building_material, building_depreciation, area_land,
        lat, lng, district
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def fetch_xlsx_from_s3() -> pd.DataFrame:
    log.info("Fetching s3://%s/%s", S3_BUCKET, S3_KEY)
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
    buf = io.BytesIO(obj["Body"].read())
    df = pd.read_excel(buf, engine="openpyxl")
    log.info("Loaded %d rows, columns: %s", len(df), list(df.columns))
    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    # Lowercase column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Ensure required columns exist
    required = {"transaction_date", "price", "area_apt", "rooms", "room_address"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["transaction_date"] = pd.to_datetime(df["transaction_date"]).dt.date
    df["price"]            = pd.to_numeric(df["price"], errors="coerce")
    df["area_apt"]         = pd.to_numeric(df["area_apt"], errors="coerce")
    df["rooms"]            = pd.to_numeric(df["rooms"], errors="coerce").astype("Int64")

    # Optional columns — fill missing with None
    for col in ["building_cadastre_nr", "apt_cadastre_nr", "property_cadastre_nr",
                "min_floor", "max_floor", "building_material",
                "building_depreciation", "area_land"]:
        if col not in df.columns:
            df[col] = None

    # Geocoding placeholders — populated by geocode() if --geocode flag used
    df["lat"]      = None
    df["lng"]      = None
    df["district"] = None

    # Drop rows missing critical values
    before = len(df)
    df = df.dropna(subset=["transaction_date", "price", "area_apt", "rooms", "room_address"])
    log.info("Dropped %d rows with nulls in required fields, %d remain", before - len(df), len(df))

    return df


GEOCODE_CACHE = Path.home() / ".cache" / "riga-geocode.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_UA  = "Vericity-Geocoder/1.0 (ceplisj@gmail.com)"


def _strip_apt(address: str) -> str:
    """Strip apartment suffix from Latvian address.

    'Brīvības iela 57-12, Rīga' → 'Brīvības iela 57, Rīga'
    Handles korpuss pattern too: 'Blaumaņa 3 k.2-15' → 'Blaumaņa 3 k.2'
    """
    return re.sub(r"-\d+\b", "", address).strip().rstrip(",").strip()


def _nominatim(query: str) -> tuple:
    """Single Nominatim lookup. Returns (lat, lng, district) — all may be None."""
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "addressdetails": 1,
                    "limit": 1, "countrycodes": "lv"},
            headers={"User-Agent": NOMINATIM_UA},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None, None, None
        r = results[0]
        addr = r.get("address", {})
        # Nominatim returns Riga neighborhoods as suburb or city_district
        district = (addr.get("suburb")
                    or addr.get("city_district")
                    or addr.get("quarter")
                    or addr.get("municipality"))
        return float(r["lat"]), float(r["lon"]), district
    except Exception as exc:
        log.warning("Nominatim error for %r: %s", query, exc)
        return None, None, None


def geocode(df: pd.DataFrame) -> pd.DataFrame:
    """
    Geocode unique building addresses using Nominatim (OpenStreetMap).

    Strategy:
    - Deduplicates by building_cadastre_nr (or stripped address) before any API call.
      Thousands of apartments share the same building → fraction of the rows need geocoding.
    - Results cached to ~/.cache/riga-geocode.json — re-runs skip already-geocoded entries.
    - Rate-limited to 1 req/sec per Nominatim ToS.
    - Joins lat/lng/district back to every row after geocoding unique buildings.
    """
    GEOCODE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache: dict = {}
    if GEOCODE_CACHE.exists():
        try:
            cache = json.loads(GEOCODE_CACHE.read_text(encoding="utf-8"))
            log.info("Geocode cache: %d entries loaded from %s", len(cache), GEOCODE_CACHE)
        except Exception:
            log.warning("Could not load geocode cache — starting fresh.")

    def _row_key(row) -> str:
        """Stable lookup key: prefer cadastre nr, fall back to stripped address."""
        cad = row.get("building_cadastre_nr")
        if pd.notna(cad) and cad:
            return f"cad:{cad}"
        return f"addr:{_strip_apt(str(row['room_address']))}"

    def _row_query(row) -> str:
        """Nominatim query string — building-level address."""
        addr = _strip_apt(str(row["room_address"]))
        # Ensure Riga context is present for unambiguous lookup
        if "rīga" not in addr.lower() and "riga" not in addr.lower():
            addr = f"{addr}, Rīga, Latvija"
        return addr

    df["_geokey"]   = df.apply(_row_key, axis=1)
    df["_geoquery"] = df.apply(_row_query, axis=1)

    unique    = df[["_geokey", "_geoquery"]].drop_duplicates("_geokey")
    to_fetch  = unique[~unique["_geokey"].isin(cache)]
    cached_n  = len(unique) - len(to_fetch)

    log.info(
        "Geocoding: %d unique buildings total — %d cached, %d to fetch via Nominatim",
        len(unique), cached_n, len(to_fetch),
    )

    for i, (_, pair) in enumerate(to_fetch.iterrows(), 1):
        key, query = pair["_geokey"], pair["_geoquery"]
        lat, lng, district = _nominatim(query)
        cache[key] = {"lat": lat, "lng": lng, "district": district}
        if i % 200 == 0:
            GEOCODE_CACHE.write_text(json.dumps(cache), encoding="utf-8")
            log.info("Progress: %d/%d geocoded", i, len(to_fetch))
        time.sleep(1.1)  # Nominatim ToS: max 1 req/sec

    GEOCODE_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    log.info("Geocode cache saved: %d total entries", len(cache))

    df["lat"]      = df["_geokey"].map(lambda k: (cache.get(k) or {}).get("lat"))
    df["lng"]      = df["_geokey"].map(lambda k: (cache.get(k) or {}).get("lng"))
    df["district"] = df["_geokey"].map(lambda k: (cache.get(k) or {}).get("district"))

    geocoded_n = int(df["lat"].notna().sum())
    log.info(
        "Geocoded %d/%d rows (%.1f%%) — %d NULL (unresolved addresses)",
        geocoded_n, len(df), 100 * geocoded_n / max(len(df), 1), len(df) - geocoded_n,
    )

    return df.drop(columns=["_geokey", "_geoquery"])


def get_connection() -> pyodbc.Connection:
    server   = os.environ["INUDAT_SQL_SERVER"]
    database = os.environ["INUDAT_SQL_DATABASE"]
    user     = os.environ["INUDAT_SQL_USER"]
    password = os.environ["INUDAT_SQL_PASSWORD"]
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server},1433;DATABASE={database};"
        f"UID={user};PWD={password};"
        "Encrypt=yes;TrustServerCertificate=no;"
    )
    return pyodbc.connect(conn_str)


def truncate_and_load(df: pd.DataFrame, dry_run: bool = False) -> None:
    if dry_run:
        log.info("[DRY RUN] Would insert %d rows into dbo.transactions", len(df))
        return

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE dbo.transactions")
    log.info("Table truncated.")

    rows = [
        (
            row["transaction_date"],
            row["price"],
            row["area_apt"],
            int(row["rooms"]) if pd.notna(row["rooms"]) else None,
            row["room_address"],
            row.get("building_cadastre_nr"),
            row.get("apt_cadastre_nr"),
            row.get("property_cadastre_nr"),
            row.get("min_floor"),
            row.get("max_floor"),
            row.get("building_material"),
            row.get("building_depreciation"),
            row.get("area_land"),
            row.get("lat"),
            row.get("lng"),
            row.get("district"),
        )
        for _, row in df.iterrows()
    ]

    cursor.fast_executemany = True
    cursor.executemany(INSERT_SQL, rows)
    conn.commit()
    conn.close()
    log.info("Inserted %d rows into dbo.transactions.", len(rows))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",  action="store_true", help="Skip DB write")
    parser.add_argument("--geocode",  action="store_true", help="Run geocoding step")
    args = parser.parse_args()

    df = fetch_xlsx_from_s3()
    df = normalize(df)
    if args.geocode:
        df = geocode(df)

    truncate_and_load(df, dry_run=args.dry_run)
    log.info("Done.")


if __name__ == "__main__":
    main()
