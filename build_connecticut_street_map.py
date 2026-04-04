from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX_PATH = ROOT / "index.html"
MAX_DATA_FILE_BYTES = 24_000_000
MAX_ALLOWED_FILE_BYTES = 25_000_000


@dataclass(frozen=True)
class DatasetConfig:
    slug: str
    page_title: str
    page_description: str
    hero_title: str
    hero_body: str
    dataset_label: str
    search_placeholder: str
    status_idle: str
    detail_idle: str
    usage_blurb: str
    data_path: Path
    output_paths: tuple[Path, ...]
    sibling_links: tuple[tuple[str, str], ...] = ()
    default_municipality: str | None = None
    externalize_data: bool = False
    data_asset_stem: str | None = None


DATASETS = (
    DatasetConfig(
        slug="new-haven-county",
        page_title="New Haven County Explorer | Connecticut Street Atlas",
        page_description=(
            "Interactive New Haven County street map with municipality filtering, "
            "favorites, custom pins, and demographic road overlays."
        ),
        hero_title="New Haven County Explorer",
        hero_body=(
            "A county-wide street map with town filtering, hover demographics, "
            "favorite streets, and custom pins you can save locally in your browser."
        ),
        dataset_label="New Haven County",
        search_placeholder="Search for Main Street or Whitney Avenue, then pick the right town",
        status_idle="Hover a street for details. Click a street to favorite it.",
        detail_idle="Hover or search for a road to see its block-group demographic estimates here.",
        usage_blurb=(
            "Use the town filter to narrow the map, then search or browse. "
            "Trackpad pinch or Ctrl/Cmd + wheel zooms the map. Pins are shared across atlas pages."
        ),
        data_path=ROOT / "new_haven_county_map_features_manifest.json",
        output_paths=(INDEX_PATH, ROOT / "new_haven_county_street_map.html"),
        sibling_links=(("north_haven_ct_street_map.html", "North Haven"),),
        externalize_data=True,
        data_asset_stem="new_haven_county_street_map_data",
    ),
    DatasetConfig(
        slug="north-haven",
        page_title="North Haven Explorer | Connecticut Street Atlas",
        page_description=(
            "Interactive North Haven street map with favorites, custom pins, "
            "and demographic road overlays."
        ),
        hero_title="North Haven Explorer",
        hero_body=(
            "A detailed North Haven street map with hover demographics, "
            "favorite streets, and custom pins you can save locally in your browser."
        ),
        dataset_label="North Haven",
        search_placeholder="Search for Whitney Avenue, Adeline Drive, or Ridge Road",
        status_idle="Hover a street for details. Click a street to favorite it.",
        detail_idle="Hover or search for a road to see its block-group demographic estimates here.",
        usage_blurb=(
            "Trackpad pinch or mousewheel with Ctrl/Cmd zooms the map. "
            "Click a street to favorite it. Turn on pin mode, click the map, and save a custom pin."
        ),
        data_path=ROOT / "north_haven_map_features.geojson",
        output_paths=(ROOT / "north_haven_ct_street_map.html",),
        sibling_links=(("new_haven_county_street_map.html", "New Haven County"),),
        default_municipality="North Haven",
    ),
)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>__PAGE_TITLE__</title>
    <meta name="description" content="__META_DESCRIPTION__" />
    <link
      href="https://unpkg.com/maplibre-gl@5.16.0/dist/maplibre-gl.css"
      rel="stylesheet"
    />
    <style>
      :root {
        --paper: #f5efe2;
        --paper-deep: #eadfca;
        --ink: #15324a;
        --muted: #5e7281;
        --accent: #d1495b;
        --accent-soft: rgba(209, 73, 91, 0.12);
        --favorite: #f2a541;
        --panel: rgba(255, 251, 244, 0.93);
        --panel-strong: rgba(255, 250, 241, 0.98);
      }

      * {
        box-sizing: border-box;
      }

      html,
      body {
        margin: 0;
        min-height: 100%;
        font-family: "Avenir Next", "Segoe UI", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top, rgba(255, 255, 255, 0.55), transparent 34%),
          linear-gradient(180deg, var(--paper) 0%, var(--paper-deep) 100%);
      }

      body {
        min-height: 100vh;
      }

      .app-shell {
        display: grid;
        grid-template-columns: 360px minmax(0, 1fr);
        min-height: 100vh;
      }

      .sidebar {
        position: relative;
        z-index: 2;
        display: flex;
        flex-direction: column;
        gap: 16px;
        padding: 22px 20px 24px;
        background: var(--panel);
        border-right: 1px solid rgba(21, 50, 74, 0.08);
        box-shadow: 12px 0 34px rgba(36, 42, 49, 0.06);
        overflow-y: auto;
      }

      .hero {
        padding: 18px 18px 16px;
        background: linear-gradient(145deg, rgba(255, 255, 255, 0.72), rgba(255, 247, 237, 0.9));
        border: 1px solid rgba(21, 50, 74, 0.08);
        border-radius: 22px;
        box-shadow: 0 18px 40px rgba(36, 42, 49, 0.08);
      }

      .eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 10px;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(21, 50, 74, 0.07);
        color: var(--muted);
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }

      h1 {
        margin: 0 0 8px;
        font: 700 2rem Georgia, "Times New Roman", serif;
        letter-spacing: 0.02em;
      }

      p {
        margin: 0;
        line-height: 1.5;
        color: var(--muted);
      }

      .card {
        padding: 16px;
        background: var(--panel-strong);
        border: 1px solid rgba(21, 50, 74, 0.08);
        border-radius: 20px;
        box-shadow: 0 14px 34px rgba(36, 42, 49, 0.06);
      }

      .card h2 {
        margin: 0 0 12px;
        font-size: 1rem;
        letter-spacing: 0.01em;
      }

      .stack {
        display: grid;
        gap: 10px;
      }

      .toolbar-row {
        display: flex;
        gap: 10px;
      }

      .toolbar-wrap {
        flex-wrap: wrap;
      }

      input,
      select,
      textarea,
      button {
        font: inherit;
      }

      input,
      select,
      textarea {
        width: 100%;
        padding: 11px 12px;
        border-radius: 14px;
        border: 1px solid rgba(21, 50, 74, 0.14);
        background: rgba(255, 255, 255, 0.86);
        color: var(--ink);
      }

      textarea {
        min-height: 92px;
        resize: vertical;
      }

      .button,
      button {
        border: 0;
        border-radius: 14px;
        padding: 11px 14px;
        cursor: pointer;
        transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
      }

      a.button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        text-decoration: none;
      }

      .button-primary {
        background: var(--ink);
        color: white;
        box-shadow: 0 10px 20px rgba(21, 50, 74, 0.18);
      }

      .button-primary:hover {
        transform: translateY(-1px);
      }

      .button-primary.active {
        background: var(--accent);
      }

      .button-soft {
        background: rgba(21, 50, 74, 0.08);
        color: var(--ink);
      }

      .button-soft.active {
        background: var(--accent-soft);
        color: var(--accent);
      }

      .button-favorite {
        background: rgba(242, 165, 65, 0.16);
        color: #8b5a00;
      }

      .button-danger {
        background: rgba(209, 73, 91, 0.14);
        color: var(--accent);
      }

      .pill-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 14px;
      }

      .pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        width: fit-content;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(21, 50, 74, 0.08);
        color: var(--muted);
        font-size: 0.82rem;
        font-weight: 700;
      }

      .status {
        min-height: 42px;
        padding: 10px 12px;
        border-radius: 14px;
        background: rgba(255, 248, 233, 0.94);
        color: #7f5b1c;
        line-height: 1.4;
      }

      .detail-box {
        min-height: 132px;
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(21, 50, 74, 0.05);
        color: var(--muted);
        line-height: 1.5;
      }

      .detail-box strong {
        color: var(--ink);
      }

      .list {
        display: grid;
        gap: 10px;
      }

      .list-empty {
        color: var(--muted);
        font-style: italic;
      }

      .list-item {
        display: grid;
        gap: 8px;
        padding: 12px;
        border-radius: 16px;
        border: 1px solid rgba(21, 50, 74, 0.08);
        background: rgba(255, 255, 255, 0.78);
      }

      .list-item strong {
        font-size: 0.97rem;
      }

      .list-item p {
        font-size: 0.9rem;
      }

      .list-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .catalog-list {
        max-height: 340px;
        overflow-y: auto;
        padding-right: 4px;
      }

      .catalog-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        width: 100%;
        padding: 10px 12px;
        border-radius: 14px;
        border: 1px solid rgba(21, 50, 74, 0.08);
        background: rgba(255, 255, 255, 0.78);
        color: var(--ink);
        text-align: left;
      }

      .catalog-item:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 20px rgba(36, 42, 49, 0.06);
      }

      .catalog-name {
        font-weight: 600;
      }

      .catalog-note {
        font-size: 0.82rem;
        color: var(--muted);
      }

      .map-shell {
        position: relative;
        min-height: 100vh;
      }

      #map {
        position: absolute;
        inset: 0;
      }

      .map-overlay {
        position: absolute;
        top: 18px;
        right: 18px;
        display: grid;
        gap: 12px;
        width: min(320px, calc(100vw - 28px));
        z-index: 3;
        pointer-events: none;
      }

      .floating-card {
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(255, 251, 244, 0.9);
        border: 1px solid rgba(21, 50, 74, 0.08);
        box-shadow: 0 18px 40px rgba(36, 42, 49, 0.1);
        backdrop-filter: blur(10px);
      }

      .floating-card strong {
        display: block;
        margin-bottom: 6px;
      }

      .floating-card p {
        font-size: 0.92rem;
      }

      .maplibregl-popup-content {
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(21, 50, 74, 0.96);
        color: #fffdf8;
        box-shadow: 0 18px 40px rgba(20, 31, 42, 0.24);
      }

      .maplibregl-popup-content strong {
        display: block;
        margin-bottom: 6px;
      }

      .maplibregl-popup-content .quiet {
        color: #d7e1ea;
      }

      .pin-marker {
        width: 18px;
        height: 18px;
        border-radius: 50% 50% 50% 0;
        background: var(--accent);
        border: 2px solid white;
        transform: rotate(-45deg);
        box-shadow: 0 8px 18px rgba(209, 73, 91, 0.36);
      }

      .pin-marker::after {
        content: "";
        position: absolute;
        left: 4px;
        top: 4px;
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: white;
      }

      .maplibregl-ctrl-group {
        border-radius: 16px !important;
        overflow: hidden;
        box-shadow: 0 12px 24px rgba(36, 42, 49, 0.12) !important;
      }

      @media (max-width: 980px) {
        .app-shell {
          grid-template-columns: 1fr;
        }

        .sidebar {
          order: 2;
          max-height: none;
          border-right: 0;
          border-top: 1px solid rgba(21, 50, 74, 0.08);
        }

        .map-shell {
          min-height: 62vh;
        }
      }
    </style>
  </head>
  <body>
    <div class="app-shell">
      <aside class="sidebar">
        <section class="hero">
          <div class="eyebrow">Connecticut Street Atlas</div>
          <h1>__HERO_TITLE__</h1>
          <p>__HERO_BODY__</p>
          <div class="pill-row">
            <div class="pill" id="dataset-pill"></div>
            <div class="pill" id="filter-pill"></div>
          </div>
        </section>

        __EXPLORE_SECTION__

        <section class="card stack" id="municipality-card"__MUNICIPALITY_CARD_HIDDEN__>
          <h2>Town Filter</h2>
          <select id="municipality-filter"></select>
        </section>

        <section class="card stack">
          <h2>Streets In View</h2>
          <div class="pill" id="street-catalog-count">Pick a town to load its street list.</div>
          <input
            id="street-catalog-filter"
            placeholder="Filter the current town street list"
            autocomplete="off"
          />
          <div class="list catalog-list" id="street-catalog-list"></div>
        </section>

        <section class="card stack">
          <h2>Find A Street</h2>
          <input
            id="street-search"
            list="street-name-options"
            placeholder="__SEARCH_PLACEHOLDER__"
            autocomplete="off"
          />
          <datalist id="street-name-options"></datalist>
          <div class="toolbar-row">
            <button class="button button-primary" id="street-search-button" type="button">
              Fly To Street
            </button>
            <button class="button button-soft" id="clear-selection-button" type="button">
              Clear
            </button>
          </div>
          <div class="status" id="status-message">__STATUS_IDLE__</div>
          <div class="detail-box" id="street-detail">__DETAIL_IDLE__</div>
          <div class="toolbar-row">
            <button class="button button-favorite" id="favorite-toggle-button" type="button" disabled>
              Favorite Selected Street
            </button>
          </div>
        </section>

        <section class="card stack">
          <h2>Pins</h2>
          <div class="toolbar-row">
            <button class="button button-primary" id="pin-mode-button" type="button">
              Add Pin
            </button>
            <button class="button button-soft" id="cancel-pin-button" type="button" disabled>
              Cancel
            </button>
          </div>
          <div class="pill" id="pin-mode-pill">Pin mode off</div>
          <input id="pin-title" placeholder="Pin title" disabled />
          <textarea id="pin-notes" placeholder="Pin notes" disabled></textarea>
          <div class="toolbar-row">
            <button class="button button-primary" id="save-pin-button" type="button" disabled>
              Save Pin
            </button>
            <button class="button button-soft" id="clear-pin-form-button" type="button" disabled>
              Clear Form
            </button>
          </div>
          <div class="list" id="pins-list"></div>
        </section>

        <section class="card stack">
          <h2>Favorite Streets</h2>
          <div class="list" id="favorites-list"></div>
        </section>
      </aside>

      <main class="map-shell">
        <div id="map" aria-label="__MAP_ARIA_LABEL__"></div>
        <div class="map-overlay">
          <div class="floating-card">
            <strong>How To Use It</strong>
            <p>__USAGE_BLURB__</p>
          </div>
        </div>
      </main>
    </div>

    <script src="https://unpkg.com/maplibre-gl@5.16.0/dist/maplibre-gl.js"></script>
    __DATA_LOADING_SCRIPTS__
    <script>
      const MAP_CONFIG = __MAP_CONFIG_JSON__;
      const ROAD_DATA = __ROAD_DATA_EXPR__;
      const INITIAL_BOUNDS = __INITIAL_BOUNDS_JSON__;
      const FAVORITES_KEY = 'connecticut-street-atlas:favorites:v2';
      const LEGACY_FAVORITES_KEY = 'connecticut-street-atlas:favorites:v1';
      const PINS_KEY = 'connecticut-street-atlas:pins:v1';

      const municipalityCard = document.getElementById('municipality-card');
      const municipalityFilter = document.getElementById('municipality-filter');
      const streetCatalogCount = document.getElementById('street-catalog-count');
      const streetCatalogFilterInput = document.getElementById('street-catalog-filter');
      const streetCatalogList = document.getElementById('street-catalog-list');
      const streetSearchInput = document.getElementById('street-search');
      const streetSearchButton = document.getElementById('street-search-button');
      const clearSelectionButton = document.getElementById('clear-selection-button');
      const statusMessage = document.getElementById('status-message');
      const streetDetail = document.getElementById('street-detail');
      const favoriteToggleButton = document.getElementById('favorite-toggle-button');
      const pinModeButton = document.getElementById('pin-mode-button');
      const cancelPinButton = document.getElementById('cancel-pin-button');
      const pinModePill = document.getElementById('pin-mode-pill');
      const pinTitleInput = document.getElementById('pin-title');
      const pinNotesInput = document.getElementById('pin-notes');
      const savePinButton = document.getElementById('save-pin-button');
      const clearPinFormButton = document.getElementById('clear-pin-form-button');
      const favoritesList = document.getElementById('favorites-list');
      const pinsList = document.getElementById('pins-list');
      const streetNameOptions = document.getElementById('street-name-options');
      const datasetPill = document.getElementById('dataset-pill');
      const filterPill = document.getElementById('filter-pill');

      const numberFormatter = new Intl.NumberFormat('en-US');
      const moneyFormatter = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
      });
      const percentFormatter = new Intl.NumberFormat('en-US', {
        maximumFractionDigits: 0,
      });

      function normalizeStreetName(value) {
        return value
          .toUpperCase()
          .replaceAll('.', '')
          .replace(/'S/g, 'S')
          .replace(/\bAVENUE\b/g, 'AV')
          .replace(/\bBOULEVARD\b/g, 'BLVD')
          .replace(/\bCIRCLE\b/g, 'CIR')
          .replace(/\bCOURT\b/g, 'CT')
          .replace(/\bDRIVE\b/g, 'DR')
          .replace(/\bEAST\b/g, 'E')
          .replace(/\bEXTENSION\b/g, 'EXT')
          .replace(/\bHIGHWAY\b/g, 'HWY')
          .replace(/\bHILL\b/g, 'HL')
          .replace(/\bLANE\b/g, 'LA')
          .replace(/\bMOUNT\b/g, 'MT')
          .replace(/\bNORTH\b/g, 'N')
          .replace(/\bPARKWAY\b/g, 'PKWY')
          .replace(/\bPLACE\b/g, 'PL')
          .replace(/\bPOINT\b/g, 'PT')
          .replace(/\bROAD\b/g, 'RD')
          .replace(/\bSAINT\b/g, 'ST')
          .replace(/\bSOUTH\b/g, 'S')
          .replace(/\bSTREET\b/g, 'ST')
          .replace(/\bTERRACE\b/g, 'TER')
          .replace(/\bTURNPIKE\b/g, 'TPKE')
          .replace(/\bWEST\b/g, 'W')
          .replace(/\bBROADWAY\b/g, 'BROADWY')
          .replace(/\s+/g, ' ')
          .trim();
      }

      function normalizeMunicipality(value) {
        return value.toUpperCase().replace(/\s+/g, ' ').trim();
      }

      function makeRoadKey(municipality, normalizedName) {
        return `${normalizeMunicipality(municipality)}|${normalizedName}`;
      }

      function formatNumber(value) {
        return value === null || value === undefined || value === '' ? 'n/a' : numberFormatter.format(value);
      }

      function formatMoney(value) {
        return value === null || value === undefined || value === '' ? 'n/a' : moneyFormatter.format(value);
      }

      function formatAge(value) {
        return value === null || value === undefined || value === '' ? 'n/a' : Number(value).toFixed(1);
      }

      function formatPercent(value) {
        return value === null || value === undefined || value === '' ? 'n/a' : `${percentFormatter.format(value)}%`;
      }

      function getFeatureBounds(features) {
        const bounds = new maplibregl.LngLatBounds();
        for (const feature of features) {
          const geometry = feature.geometry;
          const lines = geometry.type === 'MultiLineString' ? geometry.coordinates : [geometry.coordinates];
          for (const line of lines) {
            for (const point of line) {
              bounds.extend(point);
            }
          }
        }
        return bounds;
      }

      function loadJsonArray(key) {
        try {
          const raw = window.localStorage.getItem(key);
          return raw ? JSON.parse(raw) : [];
        } catch (error) {
          return [];
        }
      }

      function saveJsonArray(key, value) {
        window.localStorage.setItem(key, JSON.stringify(value));
      }

      const roadFeatures = ROAD_DATA.features;
      const roadsById = new Map();
      const roadsByKey = new Map();
      const featuresByMunicipality = new Map();

      for (let index = 0; index < roadFeatures.length; index += 1) {
        const feature = roadFeatures[index];
        feature.id = feature.id ?? index + 1;
        const props = feature.properties ?? {};
        props.display_name = props.display_name || 'Unnamed Road';
        props.municipality = props.municipality || MAP_CONFIG.defaultMunicipality || 'Unknown municipality';
        props.normalized_name = props.normalized_name || normalizeStreetName(props.display_name);
        props.road_key = props.road_key || makeRoadKey(props.municipality, props.normalized_name);
        feature.properties = props;

        roadsById.set(feature.id, feature);

        const groupedFeatures = roadsByKey.get(props.road_key) ?? [];
        groupedFeatures.push(feature);
        roadsByKey.set(props.road_key, groupedFeatures);

        const municipalityFeatures = featuresByMunicipality.get(props.municipality) ?? [];
        municipalityFeatures.push(feature);
        featuresByMunicipality.set(props.municipality, municipalityFeatures);
      }

      const municipalities = Array.from(featuresByMunicipality.keys()).sort((left, right) => left.localeCompare(right));
      const municipalityBounds = new Map();
      for (const municipality of municipalities) {
        municipalityBounds.set(municipality, getFeatureBounds(featuresByMunicipality.get(municipality) ?? []));
      }

      const roadEntries = Array.from(roadsByKey.entries())
        .map(([roadKey, features]) => {
          const props = features[0].properties;
          return {
            roadKey,
            displayName: props.display_name,
            municipality: props.municipality,
            normalizedName: props.normalized_name,
          };
        })
        .sort((left, right) => {
          const nameOrder = left.displayName.localeCompare(right.displayName);
          return nameOrder || left.municipality.localeCompare(right.municipality);
        });

      const displayNameCounts = new Map();
      for (const entry of roadEntries) {
        displayNameCounts.set(entry.displayName, (displayNameCounts.get(entry.displayName) ?? 0) + 1);
      }
      for (const entry of roadEntries) {
        entry.searchLabel =
          (displayNameCounts.get(entry.displayName) ?? 0) > 1
            ? `${entry.displayName} (${entry.municipality})`
            : entry.displayName;
      }

      const roadEntryByKey = new Map(roadEntries.map((entry) => [entry.roadKey, entry]));
      const knownRoadKeys = new Set(roadEntries.map((entry) => entry.roadKey));

      function loadFavoriteKeys() {
        const saved = new Set(loadJsonArray(FAVORITES_KEY).filter((key) => knownRoadKeys.has(key)));
        if (saved.size || !MAP_CONFIG.defaultMunicipality) {
          return saved;
        }

        const legacyFavorites = loadJsonArray(LEGACY_FAVORITES_KEY).filter((value) => typeof value === 'string');
        const migratedKeys = legacyFavorites
          .map((value) => makeRoadKey(MAP_CONFIG.defaultMunicipality, normalizeStreetName(value)))
          .filter((key) => knownRoadKeys.has(key));

        if (migratedKeys.length) {
          const uniqueKeys = Array.from(new Set(migratedKeys)).sort();
          saveJsonArray(FAVORITES_KEY, uniqueKeys);
          return new Set(uniqueKeys);
        }

        return saved;
      }

      const state = {
        selectedRoadKey: null,
        hoveredRoadId: null,
        favoriteKeys: loadFavoriteKeys(),
        pins: loadJsonArray(PINS_KEY),
        pinMode: false,
        pendingPinLngLat: null,
        pinMarkers: new Map(),
        activeMunicipality: municipalities.length === 1 ? municipalities[0] : null,
      };

      const map = new maplibregl.Map({
        container: 'map',
        style: 'https://demotiles.maplibre.org/style.json',
        bounds: INITIAL_BOUNDS,
        fitBoundsOptions: {
          padding: 42,
        },
        hash: true,
      });

      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
      map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'imperial' }), 'bottom-left');

      const hoverPopup = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        offset: 16,
      });

      function visibleRoadEntries() {
        if (!state.activeMunicipality) {
          return roadEntries;
        }
        return roadEntries.filter((entry) => entry.municipality === state.activeMunicipality);
      }

      function shouldShowTownStreetCatalog() {
        return municipalities.length === 1 || Boolean(state.activeMunicipality);
      }

      function favoriteSubsetGeojson() {
        return {
          type: 'FeatureCollection',
          features: Array.from(state.favoriteKeys).flatMap((roadKey) => roadsByKey.get(roadKey) ?? []),
        };
      }

      function selectedSubsetGeojson() {
        if (!state.selectedRoadKey) {
          return { type: 'FeatureCollection', features: [] };
        }
        return {
          type: 'FeatureCollection',
          features: roadsByKey.get(state.selectedRoadKey) ?? [],
        };
      }

      function hoveredSubsetGeojson() {
        if (!state.hoveredRoadId) {
          return { type: 'FeatureCollection', features: [] };
        }
        const feature = roadsById.get(state.hoveredRoadId);
        return {
          type: 'FeatureCollection',
          features: feature ? [feature] : [],
        };
      }

      function writeFavorites() {
        saveJsonArray(FAVORITES_KEY, Array.from(state.favoriteKeys).sort());
      }

      function writePins() {
        saveJsonArray(PINS_KEY, state.pins);
      }

      function popupHtml(feature) {
        const props = feature.properties;
        const geometryNote =
          props.geometry_quality === 'approximate'
            ? 'Approximate fallback line for a street missing from the published centerline data.'
            : `Road source: ${props.road_source}.`;
        return `
          <strong>${props.display_name}</strong>
          <div>${props.municipality}</div>
          <div>${props.acs_block_group_label || 'No block-group match found'}</div>
          <div>Population: ${formatNumber(props.acs_population)}</div>
          <div>Median age: ${formatAge(props.acs_median_age)}</div>
          <div>Median income: ${formatMoney(props.acs_median_income)}</div>
          <div>Owner/renter: ${formatPercent(props.acs_owner_share)} / ${formatPercent(props.acs_renter_share)}</div>
          <div class="quiet">2020-2024 ACS 5-year estimate. ${geometryNote}</div>
        `;
      }

      function detailHtml(feature) {
        const props = feature.properties;
        const favoriteLabel = state.favoriteKeys.has(props.road_key)
          ? 'This street is in your favorites.'
          : 'Click the road or use the button to favorite it.';
        return `
          <strong>${props.display_name}</strong><br />
          ${props.municipality}<br />
          ${props.acs_block_group_label || 'No block-group match found'}<br />
          Population ${formatNumber(props.acs_population)}. Median age ${formatAge(props.acs_median_age)}. Median income ${formatMoney(props.acs_median_income)}.<br />
          Owner/renter ${formatPercent(props.acs_owner_share)} / ${formatPercent(props.acs_renter_share)}.<br />
          ${favoriteLabel}
        `;
      }

      function favoriteButtonLabel() {
        if (!state.selectedRoadKey) {
          return 'Favorite Selected Street';
        }
        return state.favoriteKeys.has(state.selectedRoadKey)
          ? 'Remove Street Favorite'
          : 'Favorite Selected Street';
      }

      function setStatus(message) {
        statusMessage.textContent = message;
      }

      function renderSummaryPills() {
        datasetPill.textContent = `${numberFormatter.format(roadEntries.length)} street groups across ${municipalities.length} towns`;
        filterPill.textContent = state.activeMunicipality
          ? `Showing ${state.activeMunicipality}`
          : `Showing all ${municipalities.length} towns`;
      }

      function refreshSelectionUi() {
        favoriteToggleButton.disabled = !state.selectedRoadKey;
        favoriteToggleButton.textContent = favoriteButtonLabel();

        if (!state.selectedRoadKey) {
          streetDetail.innerHTML = MAP_CONFIG.detailIdle;
          return;
        }

        const features = roadsByKey.get(state.selectedRoadKey) ?? [];
        if (features.length) {
          streetDetail.innerHTML = detailHtml(features[0]);
        }
      }

      function renderSearchOptions() {
        streetNameOptions.innerHTML = '';
        for (const entry of visibleRoadEntries()) {
          const option = document.createElement('option');
          option.value = entry.searchLabel;
          streetNameOptions.appendChild(option);
        }
      }

      function renderMunicipalityOptions() {
        municipalityCard.hidden = municipalities.length <= 1;
        municipalityFilter.innerHTML = '';

        const allOption = document.createElement('option');
        allOption.value = '';
        allOption.textContent = 'All towns in this map';
        municipalityFilter.appendChild(allOption);

        for (const municipality of municipalities) {
          const option = document.createElement('option');
          option.value = municipality;
          option.textContent = municipality;
          municipalityFilter.appendChild(option);
        }

        municipalityFilter.value = state.activeMunicipality ?? '';
      }

      function renderStreetCatalog() {
        streetCatalogList.innerHTML = '';

        if (!shouldShowTownStreetCatalog()) {
          streetCatalogCount.textContent = 'Pick a town to load its street list.';
          streetCatalogFilterInput.value = '';
          streetCatalogFilterInput.disabled = true;
          streetCatalogList.innerHTML =
            '<div class="list-empty">Pick a town from the filter to list every street in that town.</div>';
          return;
        }

        streetCatalogFilterInput.disabled = false;
        const query = streetCatalogFilterInput.value.trim().toUpperCase();
        const townEntries = visibleRoadEntries();
        const filteredEntries = townEntries.filter(
          (entry) =>
            !query ||
            entry.displayName.toUpperCase().includes(query) ||
            entry.searchLabel.toUpperCase().includes(query)
        );

        streetCatalogCount.textContent = query
          ? `${numberFormatter.format(filteredEntries.length)} of ${numberFormatter.format(townEntries.length)} streets`
          : `${numberFormatter.format(townEntries.length)} streets listed`;

        if (!filteredEntries.length) {
          streetCatalogList.innerHTML = '<div class="list-empty">No streets match that filter yet.</div>';
          return;
        }

        for (const entry of filteredEntries) {
          const button = document.createElement('button');
          button.className = 'catalog-item';
          button.type = 'button';
          button.addEventListener('click', () => {
            focusStreet(entry.roadKey);
          });

          const name = document.createElement('span');
          name.className = 'catalog-name';
          name.textContent = entry.displayName;
          button.appendChild(name);

          const note = document.createElement('span');
          note.className = 'catalog-note';
          note.textContent = state.favoriteKeys.has(entry.roadKey) ? 'Saved' : 'Fly to street';
          button.appendChild(note);

          streetCatalogList.appendChild(button);
        }
      }

      function renderFavoritesList() {
        favoritesList.innerHTML = '';

        const roadKeys = Array.from(state.favoriteKeys).sort((left, right) => {
          const leftEntry = roadEntryByKey.get(left);
          const rightEntry = roadEntryByKey.get(right);
          const leftLabel = leftEntry?.searchLabel ?? left;
          const rightLabel = rightEntry?.searchLabel ?? right;
          return leftLabel.localeCompare(rightLabel);
        });

        if (!roadKeys.length) {
          favoritesList.innerHTML = '<div class="list-empty">No favorite streets yet.</div>';
          return;
        }

        for (const roadKey of roadKeys) {
          const entry = roadEntryByKey.get(roadKey);
          const feature = (roadsByKey.get(roadKey) ?? [])[0];
          if (!entry || !feature) {
            continue;
          }

          const item = document.createElement('div');
          item.className = 'list-item';

          const title = document.createElement('strong');
          title.textContent = entry.searchLabel;
          item.appendChild(title);

          const blurb = document.createElement('p');
          blurb.textContent = feature.properties.acs_block_group_label ?? entry.municipality;
          item.appendChild(blurb);

          const actions = document.createElement('div');
          actions.className = 'list-actions';

          const flyButton = document.createElement('button');
          flyButton.className = 'button button-soft';
          flyButton.type = 'button';
          flyButton.textContent = 'Fly To';
          flyButton.addEventListener('click', () => {
            focusStreet(roadKey);
          });
          actions.appendChild(flyButton);

          const removeButton = document.createElement('button');
          removeButton.className = 'button button-danger';
          removeButton.type = 'button';
          removeButton.textContent = 'Remove';
          removeButton.addEventListener('click', () => {
            state.favoriteKeys.delete(roadKey);
            writeFavorites();
            syncFavoriteLayers();
            renderFavoritesList();
            refreshSelectionUi();
            setStatus(`${entry.searchLabel} removed from favorites.`);
          });
          actions.appendChild(removeButton);

          item.appendChild(actions);
          favoritesList.appendChild(item);
        }
      }

      function pinPopupHtml(pin) {
        const notes = pin.notes ? `<div>${pin.notes}</div>` : '';
        return `<strong>${pin.title}</strong>${notes}`;
      }

      function clearPendingPinForm() {
        state.pendingPinLngLat = null;
        pinTitleInput.value = '';
        pinNotesInput.value = '';
        pinTitleInput.disabled = true;
        pinNotesInput.disabled = true;
        savePinButton.disabled = true;
        clearPinFormButton.disabled = true;
      }

      function setPinMode(enabled) {
        state.pinMode = enabled;
        pinModeButton.classList.toggle('active', enabled);
        cancelPinButton.disabled = !enabled;
        pinModePill.textContent = enabled
          ? 'Pin mode on: click the map to choose a location'
          : 'Pin mode off';
        if (!enabled) {
          clearPendingPinForm();
        }
      }

      function renderPins() {
        for (const marker of state.pinMarkers.values()) {
          marker.remove();
        }
        state.pinMarkers.clear();
        pinsList.innerHTML = '';

        if (!state.pins.length) {
          pinsList.innerHTML = '<div class="list-empty">No saved pins yet.</div>';
        }

        for (const pin of state.pins) {
          const markerElement = document.createElement('div');
          markerElement.className = 'pin-marker';
          markerElement.style.position = 'relative';

          const popup = new maplibregl.Popup({ offset: 20 }).setHTML(pinPopupHtml(pin));
          const marker = new maplibregl.Marker({ element: markerElement })
            .setLngLat([pin.lng, pin.lat])
            .setPopup(popup)
            .addTo(map);
          state.pinMarkers.set(pin.id, marker);

          const item = document.createElement('div');
          item.className = 'list-item';

          const title = document.createElement('strong');
          title.textContent = pin.title;
          item.appendChild(title);

          const body = document.createElement('p');
          body.textContent = pin.notes || `${pin.lat.toFixed(5)}, ${pin.lng.toFixed(5)}`;
          item.appendChild(body);

          const actions = document.createElement('div');
          actions.className = 'list-actions';

          const flyButton = document.createElement('button');
          flyButton.className = 'button button-soft';
          flyButton.type = 'button';
          flyButton.textContent = 'Fly To';
          flyButton.addEventListener('click', () => {
            map.flyTo({ center: [pin.lng, pin.lat], zoom: Math.max(map.getZoom(), 16) });
            marker.togglePopup();
          });
          actions.appendChild(flyButton);

          const removeButton = document.createElement('button');
          removeButton.className = 'button button-danger';
          removeButton.type = 'button';
          removeButton.textContent = 'Remove';
          removeButton.addEventListener('click', () => {
            state.pins = state.pins.filter((candidate) => candidate.id !== pin.id);
            writePins();
            renderPins();
            setStatus(`${pin.title} removed.`);
          });
          actions.appendChild(removeButton);

          item.appendChild(actions);
          pinsList.appendChild(item);
        }
      }

      function syncFavoriteLayers() {
        const source = map.getSource('favorite-roads');
        if (source) {
          source.setData(favoriteSubsetGeojson());
        }
      }

      function syncSelectionLayer() {
        const source = map.getSource('selected-road');
        if (source) {
          source.setData(selectedSubsetGeojson());
        }
      }

      function syncHoverLayer() {
        const source = map.getSource('hovered-road');
        if (source) {
          source.setData(hoveredSubsetGeojson());
        }
      }

      function geometryQualityFilter(quality) {
        const filters = [['==', ['get', 'geometry_quality'], quality]];
        if (state.activeMunicipality) {
          filters.push(['==', ['get', 'municipality'], state.activeMunicipality]);
        }
        return filters.length === 1 ? filters[0] : ['all', ...filters];
      }

      function applyRoadFilters() {
        if (map.getLayer('roads-base')) {
          map.setFilter('roads-base', geometryQualityFilter('surveyed'));
        }
        if (map.getLayer('roads-fallback')) {
          map.setFilter('roads-fallback', geometryQualityFilter('approximate'));
        }
      }

      function clearHover() {
        state.hoveredRoadId = null;
        syncHoverLayer();
        hoverPopup.remove();
        map.getCanvas().style.cursor = '';
      }

      function setSelectedStreet(roadKey, announce = false) {
        state.selectedRoadKey = roadKey;
        syncSelectionLayer();
        refreshSelectionUi();
        if (announce && roadKey) {
          const entry = roadEntryByKey.get(roadKey);
          if (entry) {
            setStatus(`${entry.searchLabel} selected.`);
          }
        }
      }

      function setActiveMunicipality(municipality, { announce = false, fit = true } = {}) {
        state.activeMunicipality = municipality || null;
        municipalityFilter.value = state.activeMunicipality ?? '';
        renderSearchOptions();
        renderStreetCatalog();
        renderSummaryPills();
        applyRoadFilters();

        if (state.selectedRoadKey) {
          const selectedEntry = roadEntryByKey.get(state.selectedRoadKey);
          if (selectedEntry && state.activeMunicipality && selectedEntry.municipality !== state.activeMunicipality) {
            setSelectedStreet(null);
          }
        }

        clearHover();

        if (fit) {
          if (state.activeMunicipality) {
            const bounds = municipalityBounds.get(state.activeMunicipality);
            if (bounds) {
              map.fitBounds(bounds, {
                padding: 70,
                duration: 850,
                maxZoom: 14.5,
              });
            }
          } else {
            map.fitBounds(INITIAL_BOUNDS, {
              padding: 42,
              duration: 850,
            });
          }
        }

        if (announce) {
          setStatus(
            state.activeMunicipality
              ? `Showing ${state.activeMunicipality}.`
              : `Showing the full ${MAP_CONFIG.datasetLabel} dataset.`
          );
        }
      }

      function focusStreet(roadKey) {
        const features = roadsByKey.get(roadKey) ?? [];
        const entry = roadEntryByKey.get(roadKey);
        if (!features.length || !entry) {
          setStatus('Street not found in the current map data.');
          return;
        }
        if (state.activeMunicipality && entry.municipality !== state.activeMunicipality) {
          setActiveMunicipality(entry.municipality, { fit: false });
        }
        setSelectedStreet(roadKey, true);
        streetSearchInput.value = entry.searchLabel;
        map.fitBounds(getFeatureBounds(features), {
          padding: 80,
          duration: 900,
          maxZoom: 17,
        });
      }

      function toggleFavorite(roadKey) {
        if (!roadKey) {
          return;
        }
        const entry = roadEntryByKey.get(roadKey);
        const label = entry?.searchLabel ?? roadKey;

        if (state.favoriteKeys.has(roadKey)) {
          state.favoriteKeys.delete(roadKey);
          setStatus(`${label} removed from favorites.`);
        } else {
          state.favoriteKeys.add(roadKey);
          setStatus(`${label} added to favorites.`);
        }

        writeFavorites();
        syncFavoriteLayers();
        renderFavoritesList();
        renderStreetCatalog();
        refreshSelectionUi();
      }

      function resolveSearchQuery(query) {
        const visibleEntries = visibleRoadEntries();
        const upperQuery = query.toUpperCase();

        const exactLabelMatch = visibleEntries.find((entry) => entry.searchLabel.toUpperCase() === upperQuery);
        if (exactLabelMatch) {
          return exactLabelMatch.roadKey;
        }

        const strippedQuery = query.replace(/\s*\([^)]+\)\s*$/, '').trim();
        const normalizedQuery = normalizeStreetName(strippedQuery);
        const exactNameMatches = visibleEntries.filter((entry) => entry.normalizedName === normalizedQuery);
        if (exactNameMatches.length === 1) {
          return exactNameMatches[0].roadKey;
        }
        if (exactNameMatches.length > 1) {
          setStatus('That street name appears in more than one town. Pick a town filter or choose the exact suggestion.');
          return null;
        }

        const partialMatches = visibleEntries.filter(
          (entry) =>
            entry.searchLabel.toUpperCase().includes(upperQuery) ||
            entry.displayName.toUpperCase().includes(upperQuery)
        );
        if (partialMatches.length) {
          if (partialMatches.length > 1) {
            setStatus(`More than one street matched "${query}". Jumping to ${partialMatches[0].searchLabel}.`);
          }
          return partialMatches[0].roadKey;
        }

        return null;
      }

      map.on('load', () => {
        map.addSource('roads', {
          type: 'geojson',
          data: ROAD_DATA,
        });

        map.addSource('favorite-roads', {
          type: 'geojson',
          data: favoriteSubsetGeojson(),
        });

        map.addSource('selected-road', {
          type: 'geojson',
          data: selectedSubsetGeojson(),
        });

        map.addSource('hovered-road', {
          type: 'geojson',
          data: hoveredSubsetGeojson(),
        });

        map.addLayer({
          id: 'roads-base',
          type: 'line',
          source: 'roads',
          filter: geometryQualityFilter('surveyed'),
          paint: {
            'line-color': '#1f4d73',
            'line-opacity': [
              'interpolate',
              ['linear'],
              ['zoom'],
              10,
              0.12,
              13,
              0.24,
              17,
              0.48,
            ],
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              10,
              1.1,
              13,
              2.6,
              17,
              5.8,
            ],
          },
        });

        map.addLayer({
          id: 'roads-fallback',
          type: 'line',
          source: 'roads',
          filter: geometryQualityFilter('approximate'),
          paint: {
            'line-color': '#d77a1f',
            'line-opacity': 0.7,
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              10,
              1.3,
              13,
              3.0,
              17,
              6.2,
            ],
            'line-dasharray': [1.4, 1.1],
          },
        });

        map.addLayer({
          id: 'favorite-roads-layer',
          type: 'line',
          source: 'favorite-roads',
          paint: {
            'line-color': '#f2a541',
            'line-opacity': 0.95,
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              10,
              2.8,
              13,
              4.6,
              17,
              8.2,
            ],
          },
        });

        map.addLayer({
          id: 'selected-road-layer',
          type: 'line',
          source: 'selected-road',
          paint: {
            'line-color': '#3fb4ff',
            'line-opacity': 0.95,
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              10,
              3.0,
              13,
              5.2,
              17,
              9.2,
            ],
          },
        });

        map.addLayer({
          id: 'hovered-road-layer',
          type: 'line',
          source: 'hovered-road',
          paint: {
            'line-color': '#d1495b',
            'line-opacity': 0.95,
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              10,
              3.2,
              13,
              5.6,
              17,
              9.6,
            ],
          },
        });

        renderMunicipalityOptions();
        renderSearchOptions();
        renderStreetCatalog();
        renderSummaryPills();
        renderFavoritesList();
        renderPins();
        refreshSelectionUi();
      });

      map.on('mousemove', 'roads-base', (event) => {
        const feature = event.features?.[0];
        if (!feature) {
          return;
        }
        state.hoveredRoadId = feature.id;
        syncHoverLayer();
        hoverPopup
          .setLngLat(event.lngLat)
          .setHTML(popupHtml(feature))
          .addTo(map);
        map.getCanvas().style.cursor = 'pointer';
      });

      map.on('mousemove', 'roads-fallback', (event) => {
        const feature = event.features?.[0];
        if (!feature) {
          return;
        }
        state.hoveredRoadId = feature.id;
        syncHoverLayer();
        hoverPopup
          .setLngLat(event.lngLat)
          .setHTML(popupHtml(feature))
          .addTo(map);
        map.getCanvas().style.cursor = 'pointer';
      });

      map.on('mouseleave', 'roads-base', clearHover);
      map.on('mouseleave', 'roads-fallback', clearHover);

      function clickStreet(event) {
        if (state.pinMode) {
          return;
        }
        const feature = event.features?.[0];
        if (!feature) {
          return;
        }
        setSelectedStreet(feature.properties.road_key, true);
        toggleFavorite(feature.properties.road_key);
      }

      map.on('click', 'roads-base', clickStreet);
      map.on('click', 'roads-fallback', clickStreet);

      map.on('click', (event) => {
        if (!state.pinMode) {
          return;
        }
        state.pendingPinLngLat = event.lngLat;
        pinTitleInput.disabled = false;
        pinNotesInput.disabled = false;
        savePinButton.disabled = false;
        clearPinFormButton.disabled = false;
        if (!pinTitleInput.value) {
          pinTitleInput.value = `Pin ${state.pins.length + 1}`;
        }
        pinTitleInput.focus();
        setStatus(`Pin location chosen at ${event.lngLat.lat.toFixed(5)}, ${event.lngLat.lng.toFixed(5)}. Add a title and save it.`);
      });

      municipalityFilter.addEventListener('change', () => {
        setActiveMunicipality(municipalityFilter.value || null, { announce: true });
      });

      streetCatalogFilterInput.addEventListener('input', () => {
        renderStreetCatalog();
      });

      streetSearchButton.addEventListener('click', () => {
        const query = streetSearchInput.value.trim();
        if (!query) {
          setStatus('Type a street name first.');
          return;
        }

        const roadKey = resolveSearchQuery(query);
        if (roadKey) {
          focusStreet(roadKey);
          return;
        }

        setStatus(`No matching street found in the current ${MAP_CONFIG.datasetLabel} view.`);
      });

      streetSearchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          streetSearchButton.click();
        }
      });

      clearSelectionButton.addEventListener('click', () => {
        streetSearchInput.value = '';
        setSelectedStreet(null);
        setStatus('Selection cleared.');
        if (state.activeMunicipality) {
          const bounds = municipalityBounds.get(state.activeMunicipality);
          if (bounds) {
            map.fitBounds(bounds, {
              padding: 70,
              duration: 700,
              maxZoom: 14.5,
            });
          }
          return;
        }
        map.fitBounds(INITIAL_BOUNDS, {
          padding: 42,
          duration: 700,
        });
      });

      favoriteToggleButton.addEventListener('click', () => {
        toggleFavorite(state.selectedRoadKey);
      });

      pinModeButton.addEventListener('click', () => {
        setPinMode(true);
        setStatus('Pin mode is on. Click the map to choose a pin location.');
      });

      cancelPinButton.addEventListener('click', () => {
        setPinMode(false);
        setStatus('Pin mode cancelled.');
      });

      clearPinFormButton.addEventListener('click', () => {
        clearPendingPinForm();
        setStatus('Pin form cleared.');
      });

      savePinButton.addEventListener('click', () => {
        if (!state.pendingPinLngLat) {
          setStatus('Choose a point on the map first.');
          return;
        }
        const title = pinTitleInput.value.trim();
        if (!title) {
          setStatus('Give the pin a title first.');
          pinTitleInput.focus();
          return;
        }
        const pin = {
          id: `pin-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          title,
          notes: pinNotesInput.value.trim(),
          lng: Number(state.pendingPinLngLat.lng.toFixed(6)),
          lat: Number(state.pendingPinLngLat.lat.toFixed(6)),
        };
        state.pins = [pin, ...state.pins];
        writePins();
        renderPins();
        setPinMode(false);
        setStatus(`${pin.title} saved.`);
      });
    </script>
  </body>
</html>
"""


def load_geojson(path: Path) -> dict:
    payload = json.loads(path.read_text())
    if payload.get("type") == "feature_collection_parts":
        features: list[dict] = []
        for part_name in payload["part_files"]:
            part_payload = json.loads((path.parent / part_name).read_text())
            features.extend(part_payload["features"])
        return {"type": "FeatureCollection", "features": features}
    return payload


def prepare_geojson(geojson: dict, default_municipality: str | None) -> dict:
    prepared = {"type": "FeatureCollection", "features": []}
    for feature_id, feature in enumerate(geojson["features"], start=1):
        properties = dict(feature.get("properties", {}))
        if default_municipality and not properties.get("municipality"):
            properties["municipality"] = default_municipality
        prepared["features"].append(
            {
                "type": "Feature",
                "id": feature_id,
                "properties": properties,
                "geometry": feature["geometry"],
            }
        )
    return prepared


def bounds_for_geojson(geojson: dict) -> list[list[float]]:
    xs: list[float] = []
    ys: list[float] = []

    for feature in geojson["features"]:
        geometry = feature["geometry"]
        if geometry["type"] == "LineString":
            lines = [geometry["coordinates"]]
        elif geometry["type"] == "MultiLineString":
            lines = geometry["coordinates"]
        else:
            continue
        for line in lines:
            for lon, lat in line:
                xs.append(lon)
                ys.append(lat)

    return [[min(xs), min(ys)], [max(xs), max(ys)]]


def encoded_size(value: str) -> int:
    return len(value.encode("utf-8"))


def write_js_data_parts(stem: Path, features: list[dict]) -> list[str]:
    header = (
        "window.CONNECTICUT_STREET_ATLAS_DATA_PARTS = "
        "window.CONNECTICUT_STREET_ATLAS_DATA_PARTS || [];\n"
        'window.CONNECTICUT_STREET_ATLAS_DATA_PARTS.push({"type":"FeatureCollection","features":['
    )
    footer = "]});\n"
    base_size = encoded_size(header) + encoded_size(footer)
    part_names: list[str] = []
    current_feature_json: list[str] = []
    current_size = base_size
    part_number = 1

    for feature in features:
        feature_json = json.dumps(feature, separators=(",", ":"))
        feature_size = encoded_size(feature_json)
        if base_size + feature_size > MAX_DATA_FILE_BYTES:
            raise RuntimeError("A single data feature exceeded the maximum chunk size.")

        extra_size = feature_size + (1 if current_feature_json else 0)
        if current_feature_json and current_size + extra_size > MAX_DATA_FILE_BYTES:
            filename = f"{stem.name}.part{part_number:02d}.js"
            (stem.parent / filename).write_text(header + ",".join(current_feature_json) + footer)
            part_names.append(filename)
            part_number += 1
            current_feature_json = []
            current_size = base_size
            extra_size = feature_size

        current_feature_json.append(feature_json)
        current_size += extra_size

    if current_feature_json:
        filename = f"{stem.name}.part{part_number:02d}.js"
        (stem.parent / filename).write_text(header + ",".join(current_feature_json) + footer)
        part_names.append(filename)

    return part_names


def build_explore_section(config: DatasetConfig) -> str:
    if not config.sibling_links:
        return ""

    links = [
        '<section class="card stack"><h2>Explore More</h2><div class="toolbar-row toolbar-wrap">'
    ]
    for href, label in config.sibling_links:
        links.append(
            f'<a class="button button-soft" href="{html.escape(href)}">{html.escape(label)}</a>'
        )
    links.append("</div></section>")
    return "".join(links)


def build_data_loading(config: DatasetConfig, geojson: dict) -> tuple[str, str, list[Path]]:
    if not config.externalize_data:
        return "", json.dumps(geojson, separators=(",", ":")), []

    if not config.data_asset_stem:
        raise RuntimeError(f"{config.slug} is configured to externalize data without a data asset stem.")

    part_names = write_js_data_parts(ROOT / config.data_asset_stem, geojson["features"])
    script_tags = ['<script>window.CONNECTICUT_STREET_ATLAS_DATA_PARTS = [];</script>']
    generated_paths = [ROOT / part_name for part_name in part_names]
    for part_name in part_names:
        script_tags.append(f'<script src="{html.escape(part_name)}"></script>')

    road_data_expr = """(() => {
        const features = [];
        for (const part of window.CONNECTICUT_STREET_ATLAS_DATA_PARTS || []) {
          if (part && Array.isArray(part.features)) {
            features.push(...part.features);
          }
        }
        return { type: 'FeatureCollection', features };
      })()"""
    return "\n    ".join(script_tags), road_data_expr, generated_paths


def build_html(config: DatasetConfig, geojson: dict) -> tuple[str, list[Path]]:
    municipalities = {
        feature["properties"].get("municipality", config.default_municipality or "Unknown")
        for feature in geojson["features"]
    }
    show_municipality_filter = len(municipalities) > 1
    bounds = bounds_for_geojson(geojson)
    data_loading_scripts, road_data_expr, generated_paths = build_data_loading(config, geojson)

    map_config_json = json.dumps(
        {
            "slug": config.slug,
            "datasetLabel": config.dataset_label,
            "detailIdle": config.detail_idle,
            "defaultMunicipality": config.default_municipality,
        },
        separators=(",", ":"),
    )

    replacements = {
        "__PAGE_TITLE__": html.escape(config.page_title),
        "__META_DESCRIPTION__": html.escape(config.page_description),
        "__HERO_TITLE__": html.escape(config.hero_title),
        "__HERO_BODY__": html.escape(config.hero_body),
        "__EXPLORE_SECTION__": build_explore_section(config),
        "__MUNICIPALITY_CARD_HIDDEN__": "" if show_municipality_filter else " hidden",
        "__SEARCH_PLACEHOLDER__": html.escape(config.search_placeholder),
        "__STATUS_IDLE__": html.escape(config.status_idle),
        "__DETAIL_IDLE__": html.escape(config.detail_idle),
        "__MAP_ARIA_LABEL__": html.escape(f"{config.dataset_label} street map"),
        "__USAGE_BLURB__": html.escape(config.usage_blurb),
        "__DATA_LOADING_SCRIPTS__": data_loading_scripts,
        "__MAP_CONFIG_JSON__": map_config_json,
        "__ROAD_DATA_EXPR__": road_data_expr,
        "__INITIAL_BOUNDS_JSON__": json.dumps(bounds),
    }

    markup = HTML_TEMPLATE
    for placeholder, replacement in replacements.items():
        markup = markup.replace(placeholder, replacement)

    return markup, generated_paths


def assert_size(path: Path) -> None:
    size = path.stat().st_size
    if size > MAX_ALLOWED_FILE_BYTES:
        raise RuntimeError(f"{path.name} is {size} bytes, which exceeds the 25 MB limit.")


def main() -> None:
    for config in DATASETS:
        geojson = prepare_geojson(load_geojson(config.data_path), config.default_municipality)
        markup, generated_paths = build_html(config, geojson)

        for output_path in config.output_paths:
            output_path.write_text(markup)
            assert_size(output_path)
            print(f"Wrote {output_path.name}")

        for generated_path in generated_paths:
            assert_size(generated_path)
            print(f"Wrote {generated_path.name}")

        print(f"Prepared {len(geojson['features'])} road features for {config.dataset_label}.")


if __name__ == "__main__":
    main()
