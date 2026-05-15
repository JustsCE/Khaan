/**
 * useTransactions — data-fetching hook for the Vericity transactions map layer.
 *
 * Drop this alongside the map component. It manages filter state, fetches from
 * /api/v1/transactions, and exposes the result + stats for the layer + panel.
 *
 * Stack: React 18, TypeScript, native fetch (no extra deps).
 */

import { useState, useEffect, useCallback, useRef } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Transaction {
  id: number;
  transaction_date: string;    // "YYYY-MM-DD"
  price: number;               // EUR
  area_apt: number;            // m²
  rooms: number;
  room_address: string;
  building_cadastre_nr: string | null;
  apt_cadastre_nr: string | null;
  property_cadastre_nr: string | null;
  min_floor: number | null;
  max_floor: number | null;
  building_material: string | null;
  building_depreciation: number | null;
  area_land: number | null;
  price_per_sqm: number | null;
  lat: number | null;
  lng: number | null;
  district: string | null;
}

export interface TransactionStats {
  total_count: number;
  median_price: number | null;
  median_price_sqm: number | null;
  avg_area_apt: number | null;
  date_min: string | null;
  date_max: string | null;
  rooms_distribution: Record<string, number>;
}

export interface TransactionFilters {
  rooms?: number;
  district?: string;
  year_from?: number;
  year_to?: number;
  price_min?: number;
  price_max?: number;
  area_min?: number;
  area_max?: number;
  limit: number;
}

const DEFAULT_FILTERS: TransactionFilters = {
  limit: 500,
};

// ── Hook ──────────────────────────────────────────────────────────────────────

interface UseTransactionsReturn {
  transactions: Transaction[];
  stats: TransactionStats | null;
  filters: TransactionFilters;
  setFilters: (patch: Partial<TransactionFilters>) => void;
  resetFilters: () => void;
  loading: boolean;
  error: string | null;
  /** Total transactions with coordinates (plottable on map) */
  mappableCount: number;
}

export function useTransactions(enabled: boolean): UseTransactionsReturn {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [stats, setStats] = useState<TransactionStats | null>(null);
  const [filters, setFiltersState] = useState<TransactionFilters>(DEFAULT_FILTERS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Cancel in-flight requests when filters change
  const abortRef = useRef<AbortController | null>(null);

  const buildQuery = useCallback((f: TransactionFilters): string => {
    const p = new URLSearchParams();
    if (f.rooms !== undefined)     p.set("rooms",     String(f.rooms));
    if (f.district !== undefined)  p.set("district",  f.district);
    if (f.year_from !== undefined) p.set("year_from", String(f.year_from));
    if (f.year_to !== undefined)   p.set("year_to",   String(f.year_to));
    if (f.price_min !== undefined) p.set("price_min", String(f.price_min));
    if (f.price_max !== undefined) p.set("price_max", String(f.price_max));
    if (f.area_min !== undefined)  p.set("area_min",  String(f.area_min));
    if (f.area_max !== undefined)  p.set("area_max",  String(f.area_max));
    p.set("limit", String(f.limit));
    return p.toString();
  }, []);

  useEffect(() => {
    if (!enabled) {
      setTransactions([]);
      setStats(null);
      return;
    }

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    const q = buildQuery(filters);

    setLoading(true);
    setError(null);

    Promise.all([
      fetch(`/api/v1/transactions?${q}`, { signal: ctrl.signal }).then(r => {
        if (!r.ok) throw new Error(`Transactions fetch failed: ${r.status}`);
        return r.json() as Promise<Transaction[]>;
      }),
      fetch(`/api/v1/transactions/stats?${q}`, { signal: ctrl.signal }).then(r => {
        if (!r.ok) throw new Error(`Stats fetch failed: ${r.status}`);
        return r.json() as Promise<TransactionStats>;
      }),
    ])
      .then(([txns, s]) => {
        setTransactions(txns);
        setStats(s);
        setLoading(false);
      })
      .catch(err => {
        if (err.name === "AbortError") return;
        setError(err.message ?? "Unknown error");
        setLoading(false);
      });

    return () => ctrl.abort();
  }, [enabled, filters, buildQuery]);

  const setFilters = useCallback((patch: Partial<TransactionFilters>) => {
    setFiltersState(prev => ({ ...prev, ...patch }));
  }, []);

  const resetFilters = useCallback(() => {
    setFiltersState(DEFAULT_FILTERS);
  }, []);

  const mappableCount = transactions.filter(t => t.lat !== null && t.lng !== null).length;

  return { transactions, stats, filters, setFilters, resetFilters, loading, error, mappableCount };
}
