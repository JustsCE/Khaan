/**
 * TransactionsLayer — ESRI ArcGIS JS API 4.x map layer for Vericity transactions.
 *
 * Renders transaction sale points as colour-coded circles on the existing map.
 * Colour scale: price_per_sqm (green = cheap → red = expensive).
 * Click → popup with full transaction detail.
 *
 * Props:
 *   view       — ArcGIS MapView reference (from parent map component)
 *   transactions — filtered list from useTransactions()
 *   visible    — layer toggle (true = shown)
 *
 * Deps: @arcgis/core (already a Vericity dep if ESRI maps are in use).
 */

import { useEffect, useRef } from "react";
import type { Transaction } from "./useTransactions";

// Dynamic imports — avoids SSR issues and keeps bundle splitting intact.
// ArcGIS ESM build is tree-shakeable; only what's imported is bundled.

async function getEsriModules() {
  const [
    { default: GraphicsLayer },
    { default: Graphic },
    { default: Point },
    { default: SimpleMarkerSymbol },
    { default: PopupTemplate },
  ] = await Promise.all([
    import("@arcgis/core/layers/GraphicsLayer"),
    import("@arcgis/core/Graphic"),
    import("@arcgis/core/geometry/Point"),
    import("@arcgis/core/symbols/SimpleMarkerSymbol"),
    import("@arcgis/core/PopupTemplate"),
  ]);
  return { GraphicsLayer, Graphic, Point, SimpleMarkerSymbol, PopupTemplate };
}

// ── Colour scale ──────────────────────────────────────────────────────────────

/** Map price_per_sqm → RGB hex. 1 000–6 000 EUR/m² is the Riga range. */
function priceColor(ppsm: number | null): string {
  if (ppsm === null) return "#9ca3af"; // gray for unknown

  const MIN = 1000;
  const MAX = 5500;
  const t = Math.max(0, Math.min(1, (ppsm - MIN) / (MAX - MIN)));

  // green → yellow → red
  const r = Math.round(t < 0.5 ? t * 2 * 255 : 255);
  const g = Math.round(t < 0.5 ? 200 : (1 - t) * 2 * 200);
  const b = 40;
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}

// ── Popup content ─────────────────────────────────────────────────────────────

function buildPopupContent(t: Transaction): string {
  const ppsm = t.price_per_sqm ? `${t.price_per_sqm.toLocaleString("lv-LV")} €/m²` : "—";
  const price = `${t.price.toLocaleString("lv-LV")} €`;
  const cadastreUrl = t.apt_cadastre_nr
    ? `https://www.kadastrs.lv/en/kadastrs/?searchText=${encodeURIComponent(t.apt_cadastre_nr)}`
    : null;

  return `
    <div style="font-family: sans-serif; font-size: 13px; min-width: 220px;">
      <div style="font-weight: 600; font-size: 14px; margin-bottom: 6px;">${t.room_address}</div>
      <table style="border-collapse: collapse; width: 100%;">
        <tr><td style="color:#6b7280; padding:2px 8px 2px 0">Date</td><td>${t.transaction_date}</td></tr>
        <tr><td style="color:#6b7280; padding:2px 8px 2px 0">Price</td><td style="font-weight:600">${price}</td></tr>
        <tr><td style="color:#6b7280; padding:2px 8px 2px 0">€/m²</td><td style="font-weight:600">${ppsm}</td></tr>
        <tr><td style="color:#6b7280; padding:2px 8px 2px 0">Area</td><td>${t.area_apt} m²</td></tr>
        <tr><td style="color:#6b7280; padding:2px 8px 2px 0">Rooms</td><td>${t.rooms}</td></tr>
        ${t.building_material ? `<tr><td style="color:#6b7280; padding:2px 8px 2px 0">Type</td><td>${t.building_material}</td></tr>` : ""}
        ${t.district ? `<tr><td style="color:#6b7280; padding:2px 8px 2px 0">District</td><td>${t.district}</td></tr>` : ""}
      </table>
      ${cadastreUrl ? `<a href="${cadastreUrl}" target="_blank" rel="noopener"
          style="display:inline-block; margin-top:8px; font-size:11px; color:#2563eb;">
          Kadastrs.lv ↗</a>` : ""}
    </div>
  `;
}

// ── Component ─────────────────────────────────────────────────────────────────

interface TransactionsLayerProps {
  /** ArcGIS MapView instance — passed down from the parent map component. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  view: any;
  transactions: Transaction[];
  visible: boolean;
}

export function TransactionsLayer({ view, transactions, visible }: TransactionsLayerProps) {
  // Keep a stable ref to the layer so we can update it without re-adding.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const layerRef = useRef<any>(null);

  // Create the layer once and add it to the map.
  useEffect(() => {
    if (!view) return;

    let mounted = true;

    getEsriModules().then(({ GraphicsLayer }) => {
      if (!mounted) return;

      const layer = new GraphicsLayer({
        id: "vericity-transactions",
        title: "Darījumi",
        visible,
        listMode: "show",
      });

      view.map.add(layer);
      layerRef.current = layer;
    });

    return () => {
      mounted = false;
      if (layerRef.current && view?.map) {
        view.map.remove(layerRef.current);
        layerRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  // Sync visibility.
  useEffect(() => {
    if (layerRef.current) {
      layerRef.current.visible = visible;
    }
  }, [visible]);

  // Re-render graphics whenever the transactions list changes.
  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;

    if (!visible || transactions.length === 0) {
      layer.removeAll();
      return;
    }

    getEsriModules().then(({ Graphic, Point, SimpleMarkerSymbol, PopupTemplate }) => {
      const graphics = transactions
        .filter(t => t.lat !== null && t.lng !== null)
        .map(t => {
          const point = new Point({ longitude: t.lng!, latitude: t.lat! });

          const symbol = new SimpleMarkerSymbol({
            style: "circle",
            color: priceColor(t.price_per_sqm),
            size: "9px",
            outline: { color: "#ffffff", width: 1 },
          });

          const popupTemplate = new PopupTemplate({
            title: `${t.rooms}-istabu dzīvoklis`,
            content: buildPopupContent(t),
          });

          return new Graphic({ geometry: point, symbol, popupTemplate, attributes: t });
        });

      layer.removeAll();
      layer.addMany(graphics);
    });
  }, [transactions, visible]);

  // This component is purely imperative — no DOM output.
  return null;
}
