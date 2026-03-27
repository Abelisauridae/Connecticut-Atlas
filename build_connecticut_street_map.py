from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ROADS_PATH = ROOT / "north_haven_map_features.geojson"
INDEX_PATH = ROOT / "index.html"
MAP_PATH = ROOT / "north_haven_ct_street_map.html"


def load_geojson() -> dict:
    geojson = json.loads(ROADS_PATH.read_text())
    features = geojson["features"]
    for feature_id, feature in enumerate(features, start=1):
        feature["id"] = feature_id
    return geojson


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


def build_html(geojson: dict) -> str:
    unique_street_names = sorted(
        {
            feature["properties"]["display_name"]
            for feature in geojson["features"]
            if feature["properties"].get("display_name")
        }
    )
    favorite_ready_names = sorted(
        {
            feature["properties"]["normalized_name"]
            for feature in geojson["features"]
            if feature["properties"].get("normalized_name")
        }
    )
    bounds = bounds_for_geojson(geojson)

    geojson_js = json.dumps(geojson, separators=(",", ":"))
    street_names_js = json.dumps(unique_street_names, separators=(",", ":"))
    favorite_names_js = json.dumps(favorite_ready_names, separators=(",", ":"))
    bounds_js = json.dumps(bounds)

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Connecticut Street Atlas</title>
    <meta
      name="description"
      content="Interactive Connecticut street atlas with favorites, custom pins, and North Haven demographic road overlays."
    />
    <link
      href="https://unpkg.com/maplibre-gl@5.16.0/dist/maplibre-gl.css"
      rel="stylesheet"
    />
    <style>
      :root {{
        --paper: #f5efe2;
        --paper-deep: #eadfca;
        --ink: #15324a;
        --muted: #5e7281;
        --line: rgba(21, 50, 74, 0.14);
        --accent: #d1495b;
        --accent-soft: rgba(209, 73, 91, 0.12);
        --favorite: #f2a541;
        --water: #b8d5e3;
        --panel: rgba(255, 251, 244, 0.93);
        --panel-strong: rgba(255, 250, 241, 0.98);
        --shadow: rgba(36, 42, 49, 0.12);
      }}

      * {{
        box-sizing: border-box;
      }}

      html,
      body {{
        margin: 0;
        min-height: 100%;
        font-family: "Avenir Next", "Segoe UI", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top, rgba(255, 255, 255, 0.55), transparent 34%),
          linear-gradient(180deg, var(--paper) 0%, var(--paper-deep) 100%);
      }}

      body {{
        min-height: 100vh;
      }}

      .app-shell {{
        display: grid;
        grid-template-columns: 360px minmax(0, 1fr);
        min-height: 100vh;
      }}

      .sidebar {{
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
      }}

      .hero {{
        padding: 18px 18px 16px;
        background: linear-gradient(145deg, rgba(255, 255, 255, 0.72), rgba(255, 247, 237, 0.9));
        border: 1px solid rgba(21, 50, 74, 0.08);
        border-radius: 22px;
        box-shadow: 0 18px 40px rgba(36, 42, 49, 0.08);
      }}

      .eyebrow {{
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
      }}

      h1 {{
        margin: 0 0 8px;
        font: 700 2rem Georgia, "Times New Roman", serif;
        letter-spacing: 0.02em;
      }}

      p {{
        margin: 0;
        line-height: 1.5;
        color: var(--muted);
      }}

      .card {{
        padding: 16px;
        background: var(--panel-strong);
        border: 1px solid rgba(21, 50, 74, 0.08);
        border-radius: 20px;
        box-shadow: 0 14px 34px rgba(36, 42, 49, 0.06);
      }}

      .card h2 {{
        margin: 0 0 12px;
        font-size: 1rem;
        letter-spacing: 0.01em;
      }}

      .stack {{
        display: grid;
        gap: 10px;
      }}

      .toolbar-row {{
        display: flex;
        gap: 10px;
      }}

      input,
      textarea,
      button {{
        font: inherit;
      }}

      input,
      textarea {{
        width: 100%;
        padding: 11px 12px;
        border-radius: 14px;
        border: 1px solid rgba(21, 50, 74, 0.14);
        background: rgba(255, 255, 255, 0.86);
        color: var(--ink);
      }}

      textarea {{
        min-height: 92px;
        resize: vertical;
      }}

      .button,
      button {{
        border: 0;
        border-radius: 14px;
        padding: 11px 14px;
        cursor: pointer;
        transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
      }}

      .button-primary {{
        background: var(--ink);
        color: white;
        box-shadow: 0 10px 20px rgba(21, 50, 74, 0.18);
      }}

      .button-primary:hover {{
        transform: translateY(-1px);
      }}

      .button-primary.active {{
        background: var(--accent);
      }}

      .button-soft {{
        background: rgba(21, 50, 74, 0.08);
        color: var(--ink);
      }}

      .button-soft.active {{
        background: var(--accent-soft);
        color: var(--accent);
      }}

      .button-favorite {{
        background: rgba(242, 165, 65, 0.16);
        color: #8b5a00;
      }}

      .button-danger {{
        background: rgba(209, 73, 91, 0.14);
        color: var(--accent);
      }}

      .pill {{
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
      }}

      .status {{
        min-height: 42px;
        padding: 10px 12px;
        border-radius: 14px;
        background: rgba(255, 248, 233, 0.94);
        color: #7f5b1c;
        line-height: 1.4;
      }}

      .detail-box {{
        min-height: 132px;
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(21, 50, 74, 0.05);
        color: var(--muted);
        line-height: 1.5;
      }}

      .detail-box strong {{
        color: var(--ink);
      }}

      .list {{
        display: grid;
        gap: 10px;
      }}

      .list-empty {{
        color: var(--muted);
        font-style: italic;
      }}

      .list-item {{
        display: grid;
        gap: 8px;
        padding: 12px;
        border-radius: 16px;
        border: 1px solid rgba(21, 50, 74, 0.08);
        background: rgba(255, 255, 255, 0.78);
      }}

      .list-item strong {{
        font-size: 0.97rem;
      }}

      .list-item p {{
        font-size: 0.9rem;
      }}

      .list-actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}

      .map-shell {{
        position: relative;
        min-height: 100vh;
      }}

      #map {{
        position: absolute;
        inset: 0;
      }}

      .map-overlay {{
        position: absolute;
        top: 18px;
        right: 18px;
        display: grid;
        gap: 12px;
        width: min(320px, calc(100vw - 28px));
        z-index: 3;
        pointer-events: none;
      }}

      .floating-card {{
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(255, 251, 244, 0.9);
        border: 1px solid rgba(21, 50, 74, 0.08);
        box-shadow: 0 18px 40px rgba(36, 42, 49, 0.1);
        backdrop-filter: blur(10px);
      }}

      .floating-card strong {{
        display: block;
        margin-bottom: 6px;
      }}

      .floating-card p {{
        font-size: 0.92rem;
      }}

      .maplibregl-popup-content {{
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(21, 50, 74, 0.96);
        color: #fffdf8;
        box-shadow: 0 18px 40px rgba(20, 31, 42, 0.24);
      }}

      .maplibregl-popup-content strong {{
        display: block;
        margin-bottom: 6px;
      }}

      .maplibregl-popup-content .quiet {{
        color: #d7e1ea;
      }}

      .pin-marker {{
        width: 18px;
        height: 18px;
        border-radius: 50% 50% 50% 0;
        background: var(--accent);
        border: 2px solid white;
        transform: rotate(-45deg);
        box-shadow: 0 8px 18px rgba(209, 73, 91, 0.36);
      }}

      .pin-marker::after {{
        content: "";
        position: absolute;
        left: 4px;
        top: 4px;
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: white;
      }}

      .maplibregl-ctrl-group {{
        border-radius: 16px !important;
        overflow: hidden;
        box-shadow: 0 12px 24px rgba(36, 42, 49, 0.12) !important;
      }}

      @media (max-width: 980px) {{
        .app-shell {{
          grid-template-columns: 1fr;
        }}

        .sidebar {{
          order: 2;
          max-height: none;
          border-right: 0;
          border-top: 1px solid rgba(21, 50, 74, 0.08);
        }}

        .map-shell {{
          min-height: 62vh;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="app-shell">
      <aside class="sidebar">
        <section class="hero">
          <div class="eyebrow">Connecticut Street Atlas</div>
          <h1>North Haven Explorer</h1>
          <p>
            A MapLibre-powered street map with hover demographics, favorite streets,
            and custom pins you can save locally in your browser.
          </p>
        </section>

        <section class="card stack">
          <h2>Find A Street</h2>
          <input
            id="street-search"
            list="street-name-options"
            placeholder="Search for Whitney Avenue, Adeline Drive, or Ridge Road"
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
          <div class="status" id="status-message">
            Hover a street for details. Click a street to favorite it.
          </div>
          <div class="detail-box" id="street-detail">
            Hover or search for a road to see its block-group demographic estimates here.
          </div>
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
        <div id="map" aria-label="North Haven map"></div>
        <div class="map-overlay">
          <div class="floating-card">
            <strong>How To Use It</strong>
            <p>
              Trackpad pinch or mousewheel with Ctrl/Cmd zooms the map. Click a street to favorite it.
              Turn on pin mode, click the map, and save a custom pin.
            </p>
          </div>
        </div>
      </main>
    </div>

    <script src="https://unpkg.com/maplibre-gl@5.16.0/dist/maplibre-gl.js"></script>
    <script>
      const ROAD_DATA = {geojson_js};
      const STREET_NAME_OPTIONS = {street_names_js};
      const KNOWN_NORMALIZED_STREETS = new Set({favorite_names_js});
      const INITIAL_BOUNDS = {bounds_js};
      const FAVORITES_KEY = 'connecticut-street-atlas:favorites:v1';
      const PINS_KEY = 'connecticut-street-atlas:pins:v1';

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

      const numberFormatter = new Intl.NumberFormat('en-US');
      const moneyFormatter = new Intl.NumberFormat('en-US', {{
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
      }});
      const percentFormatter = new Intl.NumberFormat('en-US', {{
        maximumFractionDigits: 0,
      }});

      const roadFeatures = ROAD_DATA.features;
      const roadsById = new Map();
      const roadsByName = new Map();
      const roadsByNormalizedName = new Map();

      for (const feature of roadFeatures) {{
        const id = feature.id;
        const props = feature.properties;
        roadsById.set(id, feature);

        const byDisplay = roadsByName.get(props.display_name) ?? [];
        byDisplay.push(feature);
        roadsByName.set(props.display_name, byDisplay);

        const byNormalized = roadsByNormalizedName.get(props.normalized_name) ?? [];
        byNormalized.push(feature);
        roadsByNormalizedName.set(props.normalized_name, byNormalized);
      }}

      for (const streetName of STREET_NAME_OPTIONS) {{
        const option = document.createElement('option');
        option.value = streetName;
        streetNameOptions.appendChild(option);
      }}

      function loadJsonArray(key) {{
        try {{
          const raw = window.localStorage.getItem(key);
          return raw ? JSON.parse(raw) : [];
        }} catch (error) {{
          return [];
        }}
      }}

      function saveJsonArray(key, value) {{
        window.localStorage.setItem(key, JSON.stringify(value));
      }}

      const state = {{
        selectedNormalizedName: null,
        hoveredRoadId: null,
        favoriteNames: new Set(loadJsonArray(FAVORITES_KEY).filter((name) => KNOWN_NORMALIZED_STREETS.has(name))),
        pins: loadJsonArray(PINS_KEY),
        pinMode: false,
        pendingPinLngLat: null,
        pinMarkers: new Map(),
      }};

      function normalizeStreetName(value) {{
        return value
          .toUpperCase()
          .replaceAll('.', '')
          .replace(/'S/g, 'S')
          .replace(/\\bAVENUE\\b/g, 'AV')
          .replace(/\\bBOULEVARD\\b/g, 'BLVD')
          .replace(/\\bCIRCLE\\b/g, 'CIR')
          .replace(/\\bCOURT\\b/g, 'CT')
          .replace(/\\bDRIVE\\b/g, 'DR')
          .replace(/\\bEAST\\b/g, 'E')
          .replace(/\\bEXTENSION\\b/g, 'EXT')
          .replace(/\\bHIGHWAY\\b/g, 'HWY')
          .replace(/\\bHILL\\b/g, 'HL')
          .replace(/\\bLANE\\b/g, 'LA')
          .replace(/\\bMOUNT\\b/g, 'MT')
          .replace(/\\bNORTH\\b/g, 'N')
          .replace(/\\bPARKWAY\\b/g, 'PKWY')
          .replace(/\\bPLACE\\b/g, 'PL')
          .replace(/\\bPOINT\\b/g, 'PT')
          .replace(/\\bROAD\\b/g, 'RD')
          .replace(/\\bSAINT\\b/g, 'ST')
          .replace(/\\bSOUTH\\b/g, 'S')
          .replace(/\\bSTREET\\b/g, 'ST')
          .replace(/\\bTERRACE\\b/g, 'TER')
          .replace(/\\bTURNPIKE\\b/g, 'TPKE')
          .replace(/\\bWEST\\b/g, 'W')
          .replace(/\\bBROADWAY\\b/g, 'BROADWY')
          .replace(/\\s+/g, ' ')
          .trim();
      }}

      function formatNumber(value) {{
        return value === null || value === undefined || value === '' ? 'n/a' : numberFormatter.format(value);
      }}

      function formatMoney(value) {{
        return value === null || value === undefined || value === '' ? 'n/a' : moneyFormatter.format(value);
      }}

      function formatAge(value) {{
        return value === null || value === undefined || value === '' ? 'n/a' : Number(value).toFixed(1);
      }}

      function formatPercent(value) {{
        return value === null || value === undefined || value === '' ? 'n/a' : `${{percentFormatter.format(value)}}%`;
      }}

      function getFeatureBounds(features) {{
        const bounds = new maplibregl.LngLatBounds();
        for (const feature of features) {{
          const geometry = feature.geometry;
          const lines = geometry.type === 'MultiLineString' ? geometry.coordinates : [geometry.coordinates];
          for (const line of lines) {{
            for (const point of line) {{
              bounds.extend(point);
            }}
          }}
        }}
        return bounds;
      }}

      function favoriteSubsetGeojson() {{
        return {{
          type: 'FeatureCollection',
          features: roadFeatures.filter((feature) => state.favoriteNames.has(feature.properties.normalized_name)),
        }};
      }}

      function selectedSubsetGeojson() {{
        if (!state.selectedNormalizedName) {{
          return {{ type: 'FeatureCollection', features: [] }};
        }}
        return {{
          type: 'FeatureCollection',
          features: roadsByNormalizedName.get(state.selectedNormalizedName) ?? [],
        }};
      }}

      function hoveredSubsetGeojson() {{
        if (!state.hoveredRoadId) {{
          return {{ type: 'FeatureCollection', features: [] }};
        }}
        const feature = roadsById.get(state.hoveredRoadId);
        return {{
          type: 'FeatureCollection',
          features: feature ? [feature] : [],
        }};
      }}

      function writeFavorites() {{
        saveJsonArray(FAVORITES_KEY, Array.from(state.favoriteNames).sort());
      }}

      function writePins() {{
        saveJsonArray(PINS_KEY, state.pins);
      }}

      function popupHtml(feature) {{
        const props = feature.properties;
        const geometryNote = props.geometry_quality === 'approximate'
          ? 'Approximate fallback line for a street missing from the published centerline data.'
          : `Road source: ${{props.road_source}}.`;
        return `
          <strong>${{props.display_name}}</strong>
          <div>${{props.acs_block_group_label || 'No block-group match found'}}</div>
          <div>Population: ${{formatNumber(props.acs_population)}}</div>
          <div>Median age: ${{formatAge(props.acs_median_age)}}</div>
          <div>Median income: ${{formatMoney(props.acs_median_income)}}</div>
          <div>Owner/renter: ${{formatPercent(props.acs_owner_share)}} / ${{formatPercent(props.acs_renter_share)}}</div>
          <div class="quiet">2020-2024 ACS 5-year estimate. ${{geometryNote}}</div>
        `;
      }}

      function detailHtml(feature) {{
        const props = feature.properties;
        const favoriteLabel = state.favoriteNames.has(props.normalized_name)
          ? 'This street is in your favorites.'
          : 'Click the road or use the button to favorite it.';
        return `
          <strong>${{props.display_name}}</strong><br />
          ${{props.acs_block_group_label || 'No block-group match found'}}<br />
          Population ${{formatNumber(props.acs_population)}}. Median age ${{formatAge(props.acs_median_age)}}. Median income ${{formatMoney(props.acs_median_income)}}.<br />
          Owner/renter ${{formatPercent(props.acs_owner_share)}} / ${{formatPercent(props.acs_renter_share)}}.<br />
          ${{favoriteLabel}}
        `;
      }}

      function favoriteButtonLabel() {{
        if (!state.selectedNormalizedName) {{
          return 'Favorite Selected Street';
        }}
        return state.favoriteNames.has(state.selectedNormalizedName)
          ? 'Remove Street Favorite'
          : 'Favorite Selected Street';
      }}

      const map = new maplibregl.Map({{
        container: 'map',
        style: 'https://demotiles.maplibre.org/style.json',
        bounds: INITIAL_BOUNDS,
        fitBoundsOptions: {{
          padding: 42,
        }},
        hash: true,
      }});

      map.addControl(new maplibregl.NavigationControl({{ showCompass: false }}), 'top-left');
      map.addControl(new maplibregl.ScaleControl({{ maxWidth: 120, unit: 'imperial' }}), 'bottom-left');

      const hoverPopup = new maplibregl.Popup({{
        closeButton: false,
        closeOnClick: false,
        offset: 16,
      }});

      function setStatus(message) {{
        statusMessage.textContent = message;
      }}

      function refreshSelectionUi() {{
        favoriteToggleButton.disabled = !state.selectedNormalizedName;
        favoriteToggleButton.textContent = favoriteButtonLabel();

        if (!state.selectedNormalizedName) {{
          streetDetail.innerHTML = 'Hover or search for a road to see its block-group demographic estimates here.';
          return;
        }}

        const features = roadsByNormalizedName.get(state.selectedNormalizedName) ?? [];
        if (!features.length) {{
          return;
        }}

        streetDetail.innerHTML = detailHtml(features[0]);
      }}

      function renderFavoritesList() {{
        favoritesList.innerHTML = '';

        const names = Array.from(state.favoriteNames).sort((left, right) => {{
          const leftName = (roadsByNormalizedName.get(left) ?? [])[0]?.properties.display_name ?? left;
          const rightName = (roadsByNormalizedName.get(right) ?? [])[0]?.properties.display_name ?? right;
          return leftName.localeCompare(rightName);
        }});

        if (!names.length) {{
          favoritesList.innerHTML = '<div class="list-empty">No favorite streets yet.</div>';
          return;
        }}

        for (const normalizedName of names) {{
          const features = roadsByNormalizedName.get(normalizedName) ?? [];
          const feature = features[0];
          const item = document.createElement('div');
          item.className = 'list-item';

          const title = document.createElement('strong');
          title.textContent = feature?.properties.display_name ?? normalizedName;
          item.appendChild(title);

          const blurb = document.createElement('p');
          blurb.textContent = feature?.properties.acs_block_group_label ?? 'Saved favorite street';
          item.appendChild(blurb);

          const actions = document.createElement('div');
          actions.className = 'list-actions';

          const flyButton = document.createElement('button');
          flyButton.className = 'button button-soft';
          flyButton.type = 'button';
          flyButton.textContent = 'Fly To';
          flyButton.addEventListener('click', () => {{
            focusStreet(normalizedName);
          }});
          actions.appendChild(flyButton);

          const removeButton = document.createElement('button');
          removeButton.className = 'button button-danger';
          removeButton.type = 'button';
          removeButton.textContent = 'Remove';
          removeButton.addEventListener('click', () => {{
            state.favoriteNames.delete(normalizedName);
            writeFavorites();
            syncFavoriteLayers();
            renderFavoritesList();
            refreshSelectionUi();
            setStatus(`${{feature?.properties.display_name ?? normalizedName}} removed from favorites.`);
          }});
          actions.appendChild(removeButton);

          item.appendChild(actions);
          favoritesList.appendChild(item);
        }}
      }}

      function pinPopupHtml(pin) {{
        const notes = pin.notes ? `<div>${{pin.notes}}</div>` : '';
        return `<strong>${{pin.title}}</strong>${{notes}}`;
      }}

      function clearPendingPinForm() {{
        state.pendingPinLngLat = null;
        pinTitleInput.value = '';
        pinNotesInput.value = '';
        pinTitleInput.disabled = true;
        pinNotesInput.disabled = true;
        savePinButton.disabled = true;
        clearPinFormButton.disabled = true;
      }}

      function setPinMode(enabled) {{
        state.pinMode = enabled;
        pinModeButton.classList.toggle('active', enabled);
        cancelPinButton.disabled = !enabled;
        pinModePill.textContent = enabled
          ? 'Pin mode on: click the map to choose a location'
          : 'Pin mode off';
        if (!enabled) {{
          clearPendingPinForm();
        }}
      }}

      function renderPins() {{
        for (const marker of state.pinMarkers.values()) {{
          marker.remove();
        }}
        state.pinMarkers.clear();
        pinsList.innerHTML = '';

        if (!state.pins.length) {{
          pinsList.innerHTML = '<div class="list-empty">No saved pins yet.</div>';
        }}

        for (const pin of state.pins) {{
          const markerElement = document.createElement('div');
          markerElement.className = 'pin-marker';
          markerElement.style.position = 'relative';

          const popup = new maplibregl.Popup({{ offset: 20 }}).setHTML(pinPopupHtml(pin));
          const marker = new maplibregl.Marker({{ element: markerElement }})
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
          body.textContent = pin.notes || `${{pin.lat.toFixed(5)}}, ${{pin.lng.toFixed(5)}}`;
          item.appendChild(body);

          const actions = document.createElement('div');
          actions.className = 'list-actions';

          const flyButton = document.createElement('button');
          flyButton.className = 'button button-soft';
          flyButton.type = 'button';
          flyButton.textContent = 'Fly To';
          flyButton.addEventListener('click', () => {{
            map.flyTo({{ center: [pin.lng, pin.lat], zoom: Math.max(map.getZoom(), 16) }});
            marker.togglePopup();
          }});
          actions.appendChild(flyButton);

          const removeButton = document.createElement('button');
          removeButton.className = 'button button-danger';
          removeButton.type = 'button';
          removeButton.textContent = 'Remove';
          removeButton.addEventListener('click', () => {{
            state.pins = state.pins.filter((candidate) => candidate.id !== pin.id);
            writePins();
            renderPins();
            setStatus(`${{pin.title}} removed.`);
          }});
          actions.appendChild(removeButton);

          item.appendChild(actions);
          pinsList.appendChild(item);
        }}
      }}

      function syncFavoriteLayers() {{
        const source = map.getSource('favorite-roads');
        if (source) {{
          source.setData(favoriteSubsetGeojson());
        }}
      }}

      function syncSelectionLayer() {{
        const source = map.getSource('selected-road');
        if (source) {{
          source.setData(selectedSubsetGeojson());
        }}
      }}

      function syncHoverLayer() {{
        const source = map.getSource('hovered-road');
        if (source) {{
          source.setData(hoveredSubsetGeojson());
        }}
      }}

      function setSelectedStreet(normalizedName, announce = false) {{
        state.selectedNormalizedName = normalizedName;
        syncSelectionLayer();
        refreshSelectionUi();
        if (announce && normalizedName) {{
          const feature = (roadsByNormalizedName.get(normalizedName) ?? [])[0];
          if (feature) {{
            setStatus(`${{feature.properties.display_name}} selected.`);
          }}
        }}
      }}

      function focusStreet(normalizedName) {{
        const features = roadsByNormalizedName.get(normalizedName) ?? [];
        if (!features.length) {{
          setStatus('Street not found in the current town data.');
          return;
        }}
        setSelectedStreet(normalizedName, true);
        streetSearchInput.value = features[0].properties.display_name;
        map.fitBounds(getFeatureBounds(features), {{
          padding: 80,
          duration: 900,
          maxZoom: 17,
        }});
      }}

      function toggleFavorite(normalizedName) {{
        if (!normalizedName) {{
          return;
        }}
        const features = roadsByNormalizedName.get(normalizedName) ?? [];
        const displayName = features[0]?.properties.display_name ?? normalizedName;

        if (state.favoriteNames.has(normalizedName)) {{
          state.favoriteNames.delete(normalizedName);
          setStatus(`${{displayName}} removed from favorites.`);
        }} else {{
          state.favoriteNames.add(normalizedName);
          setStatus(`${{displayName}} added to favorites.`);
        }}

        writeFavorites();
        syncFavoriteLayers();
        renderFavoritesList();
        refreshSelectionUi();
      }}

      map.on('load', () => {{
        map.addSource('roads', {{
          type: 'geojson',
          data: ROAD_DATA,
        }});

        map.addSource('favorite-roads', {{
          type: 'geojson',
          data: favoriteSubsetGeojson(),
        }});

        map.addSource('selected-road', {{
          type: 'geojson',
          data: selectedSubsetGeojson(),
        }});

        map.addSource('hovered-road', {{
          type: 'geojson',
          data: hoveredSubsetGeojson(),
        }});

        map.addLayer({{
          id: 'roads-base',
          type: 'line',
          source: 'roads',
          filter: ['==', ['get', 'geometry_quality'], 'surveyed'],
          paint: {{
            'line-color': '#1f4d73',
            'line-opacity': [
              'interpolate',
              ['linear'],
              ['zoom'],
              11,
              0.18,
              14,
              0.34,
              17,
              0.52,
            ],
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              11,
              1.4,
              14,
              3.2,
              17,
              6.2,
            ],
          }},
        }});

        map.addLayer({{
          id: 'roads-fallback',
          type: 'line',
          source: 'roads',
          filter: ['==', ['get', 'geometry_quality'], 'approximate'],
          paint: {{
            'line-color': '#d77a1f',
            'line-opacity': 0.7,
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              11,
              1.6,
              14,
              3.6,
              17,
              6.6,
            ],
            'line-dasharray': [1.4, 1.1],
          }},
        }});

        map.addLayer({{
          id: 'favorite-roads-layer',
          type: 'line',
          source: 'favorite-roads',
          paint: {{
            'line-color': '#f2a541',
            'line-opacity': 0.95,
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              11,
              3.2,
              14,
              5.6,
              17,
              9.2,
            ],
          }},
        }});

        map.addLayer({{
          id: 'selected-road-layer',
          type: 'line',
          source: 'selected-road',
          paint: {{
            'line-color': '#3fb4ff',
            'line-opacity': 0.95,
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              11,
              3.4,
              14,
              6.2,
              17,
              10.2,
            ],
          }},
        }});

        map.addLayer({{
          id: 'hovered-road-layer',
          type: 'line',
          source: 'hovered-road',
          paint: {{
            'line-color': '#d1495b',
            'line-opacity': 0.95,
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              11,
              3.8,
              14,
              6.8,
              17,
              10.6,
            ],
          }},
        }});

        renderFavoritesList();
        renderPins();
        refreshSelectionUi();
      }});

      map.on('mousemove', 'roads-base', (event) => {{
        const feature = event.features?.[0];
        if (!feature) {{
          return;
        }}
        state.hoveredRoadId = feature.id;
        syncHoverLayer();
        hoverPopup
          .setLngLat(event.lngLat)
          .setHTML(popupHtml(feature))
          .addTo(map);
        map.getCanvas().style.cursor = 'pointer';
      }});

      map.on('mousemove', 'roads-fallback', (event) => {{
        const feature = event.features?.[0];
        if (!feature) {{
          return;
        }}
        state.hoveredRoadId = feature.id;
        syncHoverLayer();
        hoverPopup
          .setLngLat(event.lngLat)
          .setHTML(popupHtml(feature))
          .addTo(map);
        map.getCanvas().style.cursor = 'pointer';
      }});

      function clearHover() {{
        state.hoveredRoadId = null;
        syncHoverLayer();
        hoverPopup.remove();
        map.getCanvas().style.cursor = '';
      }}

      map.on('mouseleave', 'roads-base', clearHover);
      map.on('mouseleave', 'roads-fallback', clearHover);

      function clickStreet(event) {{
        if (state.pinMode) {{
          return;
        }}
        const feature = event.features?.[0];
        if (!feature) {{
          return;
        }}
        setSelectedStreet(feature.properties.normalized_name, true);
        toggleFavorite(feature.properties.normalized_name);
      }}

      map.on('click', 'roads-base', clickStreet);
      map.on('click', 'roads-fallback', clickStreet);

      map.on('click', (event) => {{
        if (!state.pinMode) {{
          return;
        }}
        state.pendingPinLngLat = event.lngLat;
        pinTitleInput.disabled = false;
        pinNotesInput.disabled = false;
        savePinButton.disabled = false;
        clearPinFormButton.disabled = false;
        if (!pinTitleInput.value) {{
          pinTitleInput.value = `Pin ${{state.pins.length + 1}}`;
        }}
        pinTitleInput.focus();
        setStatus(`Pin location chosen at ${{event.lngLat.lat.toFixed(5)}}, ${{event.lngLat.lng.toFixed(5)}}. Add a title and save it.`);
      }});

      streetSearchButton.addEventListener('click', () => {{
        const query = streetSearchInput.value.trim();
        if (!query) {{
          setStatus('Type a street name first.');
          return;
        }}
        const normalized = normalizeStreetName(query);
        const exactMatch = roadsByNormalizedName.has(normalized) ? normalized : null;
        if (exactMatch) {{
          focusStreet(exactMatch);
          return;
        }}
        const partialMatch = Array.from(roadsByNormalizedName.keys()).find((name) => {{
          const feature = (roadsByNormalizedName.get(name) ?? [])[0];
          return feature?.properties.display_name.toUpperCase().includes(query.toUpperCase());
        }});
        if (partialMatch) {{
          focusStreet(partialMatch);
          return;
        }}
        setStatus('No matching street found in the current North Haven dataset.');
      }});

      streetSearchInput.addEventListener('keydown', (event) => {{
        if (event.key === 'Enter') {{
          event.preventDefault();
          streetSearchButton.click();
        }}
      }});

      clearSelectionButton.addEventListener('click', () => {{
        streetSearchInput.value = '';
        setSelectedStreet(null);
        setStatus('Selection cleared.');
        map.fitBounds(INITIAL_BOUNDS, {{
          padding: 42,
          duration: 700,
        }});
      }});

      favoriteToggleButton.addEventListener('click', () => {{
        toggleFavorite(state.selectedNormalizedName);
      }});

      pinModeButton.addEventListener('click', () => {{
        setPinMode(true);
        setStatus('Pin mode is on. Click the map to choose a pin location.');
      }});

      cancelPinButton.addEventListener('click', () => {{
        setPinMode(false);
        setStatus('Pin mode cancelled.');
      }});

      clearPinFormButton.addEventListener('click', () => {{
        clearPendingPinForm();
        setStatus('Pin form cleared.');
      }});

      savePinButton.addEventListener('click', () => {{
        if (!state.pendingPinLngLat) {{
          setStatus('Choose a point on the map first.');
          return;
        }}
        const title = pinTitleInput.value.trim();
        if (!title) {{
          setStatus('Give the pin a title first.');
          pinTitleInput.focus();
          return;
        }}
        const pin = {{
          id: `pin-${{Date.now()}}-${{Math.random().toString(36).slice(2, 8)}}`,
          title,
          notes: pinNotesInput.value.trim(),
          lng: Number(state.pendingPinLngLat.lng.toFixed(6)),
          lat: Number(state.pendingPinLngLat.lat.toFixed(6)),
        }};
        state.pins = [pin, ...state.pins];
        writePins();
        renderPins();
        setPinMode(false);
        setStatus(`${{pin.title}} saved.`);
      }});
    </script>
  </body>
</html>
"""


def main() -> None:
    geojson = load_geojson()
    html_markup = build_html(geojson)
    INDEX_PATH.write_text(html_markup)
    MAP_PATH.write_text(html_markup)
    print(f"Wrote {INDEX_PATH.name}")
    print(f"Wrote {MAP_PATH.name}")
    print(f"Embedded {len(geojson['features'])} road features")


if __name__ == "__main__":
    main()
