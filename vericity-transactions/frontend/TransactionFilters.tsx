/**
 * TransactionFilters — slide-in filter panel for the transactions map layer.
 *
 * Uses Tailwind CSS + Radix UI Sheet (same deps Vericity already has).
 * Opened by the layer toggle button in the map toolbar.
 *
 * Props:
 *   open       — controlled open state
 *   onClose    — close callback
 *   filters    — current filter values (from useTransactions)
 *   setFilters — partial update function (from useTransactions)
 *   resetFilters — reset to defaults
 *   stats      — aggregate stats (shown in header)
 *   loading    — shows spinner while fetching
 *   mappableCount — number of points with coordinates
 */

import type { ReactNode } from "react";
import type { TransactionFilters as Filters, TransactionStats } from "./useTransactions";

const DISTRICTS = [
  "Āgenskalns", "Bolderāja", "Brasa", "Čiekurkalns", "Centrs", "Daugavgrīva",
  "Iļģuciems", "Imanta", "Jugla", "Kengarags", "Ķengarags", "Kleisti",
  "Mežaparks", "Mežciems", "Pļavnieki", "Purvciems", "Sarkandaugava",
  "Šampēteris", "Teika", "Torņakalns", "Vecmīlgrāvis", "Ziepniekkalns",
  "Zolitūde",
];

const CURRENT_YEAR = new Date().getFullYear();
const YEAR_OPTIONS = Array.from({ length: CURRENT_YEAR - 2021 }, (_, i) => 2022 + i);

interface Props {
  open: boolean;
  onClose: () => void;
  filters: Filters;
  setFilters: (patch: Partial<Filters>) => void;
  resetFilters: () => void;
  stats: TransactionStats | null;
  loading: boolean;
  mappableCount: number;
}

export function TransactionFilters({
  open, onClose, filters, setFilters, resetFilters, stats, loading, mappableCount,
}: Props) {
  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40"
        onClick={onClose}
        aria-hidden
      />
      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-80 bg-white shadow-xl z-50 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <div>
              <h2 className="font-semibold text-sm">Darījumi</h2>
              {stats && !loading && (
                <p className="text-xs text-gray-500 mt-0.5">
                  {mappableCount.toLocaleString("lv-LV")} punkti
                  {stats.median_price_sqm
                    ? ` · mediāna ${stats.median_price_sqm.toLocaleString("lv-LV")} €/m²`
                    : ""}
                </p>
              )}
              {loading && <p className="text-xs text-gray-400 mt-0.5">Ielādē…</p>}
            </div>
            <button
              className="text-gray-400 hover:text-gray-700 p-1 rounded"
              aria-label="Aizvērt"
              onClick={onClose}
            >
              ✕
            </button>
          </div>

          {/* Stats bar */}
          {stats && !loading && (
            <div className="grid grid-cols-3 divide-x border-b text-center text-xs py-2">
              <div className="px-2">
                <div className="font-semibold text-sm">
                  {stats.total_count.toLocaleString("lv-LV")}
                </div>
                <div className="text-gray-500">Darījumi</div>
              </div>
              <div className="px-2">
                <div className="font-semibold text-sm">
                  {stats.median_price
                    ? `${(stats.median_price / 1000).toFixed(0)}k €`
                    : "—"}
                </div>
                <div className="text-gray-500">Mediānā cena</div>
              </div>
              <div className="px-2">
                <div className="font-semibold text-sm">
                  {stats.avg_area_apt ? `${stats.avg_area_apt.toFixed(0)} m²` : "—"}
                </div>
                <div className="text-gray-500">Vid. platība</div>
              </div>
            </div>
          )}

          {/* Filters */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">

            {/* Rooms */}
            <FilterSection label="Istabas">
              <div className="flex gap-1.5 flex-wrap">
                {[undefined, 1, 2, 3, 4, 5].map(r => (
                  <button
                    key={r ?? "all"}
                    onClick={() => setFilters({ rooms: r })}
                    className={`px-3 py-1 rounded text-xs font-medium border transition-colors ${
                      filters.rooms === r
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
                    }`}
                  >
                    {r === undefined ? "Visas" : r === 5 ? "5+" : r}
                  </button>
                ))}
              </div>
            </FilterSection>

            {/* District */}
            <FilterSection label="Rajons">
              <select
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-blue-400"
                value={filters.district ?? ""}
                onChange={e => setFilters({ district: e.target.value || undefined })}
              >
                <option value="">Visi rajoni</option>
                {DISTRICTS.map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </FilterSection>

            {/* Year range */}
            <FilterSection label="Gads">
              <div className="flex gap-2">
                <select
                  className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-blue-400"
                  value={filters.year_from ?? ""}
                  onChange={e => setFilters({ year_from: e.target.value ? Number(e.target.value) : undefined })}
                >
                  <option value="">No</option>
                  {YEAR_OPTIONS.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
                <select
                  className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-blue-400"
                  value={filters.year_to ?? ""}
                  onChange={e => setFilters({ year_to: e.target.value ? Number(e.target.value) : undefined })}
                >
                  <option value="">Līdz</option>
                  {YEAR_OPTIONS.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
            </FilterSection>

            {/* Price range */}
            <FilterSection label="Cena (€)">
              <div className="flex gap-2">
                <input
                  type="number"
                  placeholder="No"
                  className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-blue-400"
                  value={filters.price_min ?? ""}
                  onChange={e => setFilters({ price_min: e.target.value ? Number(e.target.value) : undefined })}
                />
                <input
                  type="number"
                  placeholder="Līdz"
                  className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-blue-400"
                  value={filters.price_max ?? ""}
                  onChange={e => setFilters({ price_max: e.target.value ? Number(e.target.value) : undefined })}
                />
              </div>
            </FilterSection>

            {/* Area range */}
            <FilterSection label="Platība (m²)">
              <div className="flex gap-2">
                <input
                  type="number"
                  placeholder="No"
                  className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-blue-400"
                  value={filters.area_min ?? ""}
                  onChange={e => setFilters({ area_min: e.target.value ? Number(e.target.value) : undefined })}
                />
                <input
                  type="number"
                  placeholder="Līdz"
                  className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:border-blue-400"
                  value={filters.area_max ?? ""}
                  onChange={e => setFilters({ area_max: e.target.value ? Number(e.target.value) : undefined })}
                />
              </div>
            </FilterSection>

            {/* Limit */}
            <FilterSection label={`Rādīt punktus (${filters.limit})`}>
              <input
                type="range"
                min={50}
                max={1000}
                step={50}
                className="w-full accent-blue-600"
                value={filters.limit}
                onChange={e => setFilters({ limit: Number(e.target.value) })}
              />
              <div className="flex justify-between text-xs text-gray-400 mt-0.5">
                <span>50</span><span>1 000</span>
              </div>
            </FilterSection>

          </div>

          {/* Footer */}
          <div className="px-4 py-3 border-t">
            <button
              onClick={resetFilters}
              className="w-full py-1.5 text-xs text-gray-600 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
            >
              Atiestatīt filtrus
            </button>
          </div>
      </div>
    </>
  );
}

// ── Helper ────────────────────────────────────────────────────────────────────

function FilterSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-700 mb-1.5">{label}</label>
      {children}
    </div>
  );
}
