/**
 * TransactionsToggle — map toolbar button that activates the transactions layer.
 *
 * This is the integration point. Drop it inside the existing map toolbar
 * (wherever the other layer buttons / controls live).
 *
 * It owns:
 *  - the enabled toggle (layer on/off)
 *  - the filter panel open/close state
 *  - the useTransactions hook
 *  - renders TransactionsLayer (imperative ESRI) + TransactionFilters (UI)
 *
 * Usage:
 *   <TransactionsToggle view={mapViewRef.current} />
 *
 * The parent map component only needs to pass the ESRI MapView reference.
 */

import { useState } from "react";
import { useTransactions } from "./useTransactions";
import { TransactionsLayer } from "./TransactionsLayer";
import { TransactionFilters } from "./TransactionFilters";

interface Props {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  view: any;
}

export function TransactionsToggle({ view }: Props) {
  const [enabled, setEnabled] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const { transactions, stats, filters, setFilters, resetFilters, loading, error, mappableCount } =
    useTransactions(enabled);

  return (
    <>
      {/* Toggle + filter button — drop into map toolbar */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => {
            const next = !enabled;
            setEnabled(next);
            if (!next) setFiltersOpen(false);
          }}
          title="Rādīt darījumus"
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium border transition-colors ${
            enabled
              ? "bg-blue-600 text-white border-blue-600"
              : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
          }`}
        >
          {/* Simple house-sale icon using Unicode — no extra icon dep */}
          <span aria-hidden>💰</span>
          Darījumi
          {loading && <span className="ml-1 animate-spin">⟳</span>}
          {error && <span className="ml-1 text-red-300" title={error}>!</span>}
          {enabled && !loading && (
            <span className="ml-1 text-blue-200 font-normal">
              {mappableCount.toLocaleString("lv-LV")}
            </span>
          )}
        </button>

        {enabled && (
          <button
            onClick={() => setFiltersOpen(v => !v)}
            title="Filtri"
            className={`p-1.5 rounded border text-xs transition-colors ${
              filtersOpen
                ? "bg-blue-50 border-blue-400 text-blue-600"
                : "bg-white border-gray-300 text-gray-500 hover:border-blue-400"
            }`}
          >
            ⚙
          </button>
        )}
      </div>

      {/* Imperative ESRI layer — renders nothing to the DOM */}
      <TransactionsLayer view={view} transactions={transactions} visible={enabled} />

      {/* Filter side panel */}
      <TransactionFilters
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        filters={filters}
        setFilters={setFilters}
        resetFilters={resetFilters}
        stats={stats}
        loading={loading}
        mappableCount={mappableCount}
      />
    </>
  );
}
