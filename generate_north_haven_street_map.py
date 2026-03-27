from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ROADS_PATH = ROOT / "north_haven_ct_roads.geojson"
ENRICHED_ROADS_PATH = ROOT / "north_haven_map_features.geojson"
STREET_LIST_PATH = ROOT / "north_haven_ct_streets_2020.txt"
SVG_PATH = ROOT / "north_haven_ct_street_map.svg"
HTML_PATH = ROOT / "north_haven_ct_street_map.html"

TOKEN_TO_ABBR = {
    "AVENUE": "AV",
    "BOULEVARD": "BLVD",
    "CIRCLE": "CIR",
    "COURT": "CT",
    "CROSSING": "CROSSING",
    "DRIVE": "DR",
    "EAST": "E",
    "EXTENSION": "EXT",
    "HIGHWAY": "HWY",
    "HILL": "HL",
    "LANE": "LA",
    "MOUNT": "MT",
    "NORTH": "N",
    "PARKWAY": "PKWY",
    "PLACE": "PL",
    "POINT": "PT",
    "ROAD": "RD",
    "SAINT": "ST",
    "SOUTH": "S",
    "STREET": "ST",
    "TERRACE": "TER",
    "TURNPIKE": "TPKE",
    "WAY": "WAY",
    "WEST": "W",
}

ABBR_TO_TITLE = {
    "AV": "Avenue",
    "BLVD": "Boulevard",
    "CIR": "Circle",
    "CT": "Court",
    "DR": "Drive",
    "E": "East",
    "EXT": "Extension",
    "HWY": "Highway",
    "HL": "Hill",
    "LA": "Lane",
    "MT": "Mount",
    "N": "North",
    "PKWY": "Parkway",
    "PL": "Place",
    "PT": "Point",
    "RD": "Road",
    "S": "South",
    "ST": "Street",
    "TER": "Terrace",
    "TPKE": "Turnpike",
    "W": "West",
    "WAY": "Way",
}

SPECIAL_TOKENS = {
    "BROADWAY": "BROADWY",
}


def normalize_name(name: str) -> str:
    name = name.upper().replace(".", "").replace("'S", "S").strip()
    tokens = re.split(r"\s+", name)
    normalized = []
    for token in tokens:
        token = SPECIAL_TOKENS.get(token, token)
        normalized.append(TOKEN_TO_ABBR.get(token, token))
    return " ".join(normalized)


def title_case_token(token: str) -> str:
    if token in ABBR_TO_TITLE:
        return ABBR_TO_TITLE[token]
    if token in {"I", "II", "III", "IV"}:
        return token
    if token.isdigit():
        return token
    return token.capitalize()


def display_name_from_geo(raw_name: str, official_name_map: dict[str, str]) -> str:
    normalized = normalize_name(raw_name)
    if normalized in official_name_map:
        return official_name_map[normalized]
    return " ".join(title_case_token(token) for token in normalized.split())


def iter_lines(geometry: dict) -> list[list[list[float]]]:
    if geometry["type"] == "LineString":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiLineString":
        return geometry["coordinates"]
    raise ValueError(f"Unsupported geometry type: {geometry['type']}")


def project(lon: float, lat: float, cos_lat: float) -> tuple[float, float]:
    return lon * cos_lat, lat


def make_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    start_x, start_y = points[0]
    commands = [f"M {start_x:.2f} {start_y:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in points[1:])
    return " ".join(commands)


def load_data() -> tuple[list[dict], list[str]]:
    source_path = ENRICHED_ROADS_PATH if ENRICHED_ROADS_PATH.exists() else ROADS_PATH
    geojson = json.loads(source_path.read_text())
    official_names = [
        line.strip()
        for line in STREET_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]
    return geojson["features"], official_names


def attr(value: object | None) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def build_map_assets() -> tuple[str, str]:
    features, official_names = load_data()
    official_name_map = {normalize_name(name): name for name in official_names}

    all_points: list[tuple[float, float]] = []
    raw_segments: list[dict[str, object]] = []
    latitudes = []

    for feature in features:
        latitudes.extend(
            lat
            for line in iter_lines(feature["geometry"])
            for _, lat in line
        )

    mid_lat = sum(latitudes) / len(latitudes)
    cos_lat = math.cos(math.radians(mid_lat))

    for feature in features:
        feature_properties = feature["properties"]
        raw_name = feature_properties.get("STREET_NAME", "").strip()
        display_name = feature_properties.get("display_name")
        if display_name:
            display_name = str(display_name).strip()
        elif raw_name:
            display_name = display_name_from_geo(raw_name, official_name_map)
        else:
            continue
        normalized_name = str(
            feature_properties.get("normalized_name", normalize_name(display_name))
        )
        road_source = str(feature_properties.get("road_source", "CT DOT centerline"))
        geometry_quality = str(feature_properties.get("geometry_quality", "surveyed"))

        for line in iter_lines(feature["geometry"]):
            projected_line = [project(lon, lat, cos_lat) for lon, lat in line]
            all_points.extend(projected_line)
            raw_segments.append(
                {
                    "display_name": display_name,
                    "normalized_name": normalized_name,
                    "road_source": road_source,
                    "geometry_quality": geometry_quality,
                    "block_group_label": feature_properties.get(
                        "acs_block_group_label", ""
                    ),
                    "population": feature_properties.get("acs_population"),
                    "median_age": feature_properties.get("acs_median_age"),
                    "median_income": feature_properties.get("acs_median_income"),
                    "owner_share": feature_properties.get("acs_owner_share"),
                    "renter_share": feature_properties.get("acs_renter_share"),
                    "points": projected_line,
                }
            )

    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_y = min(point[1] for point in all_points)
    max_y = max(point[1] for point in all_points)

    map_width = 1100.0
    x_span = max_x - min_x
    y_span = max_y - min_y
    map_height = map_width * (y_span / x_span)

    left_pad = 48.0
    right_pad = 48.0
    top_pad = 120.0
    bottom_pad = 110.0
    svg_width = left_pad + map_width + right_pad
    svg_height = top_pad + map_height + bottom_pad

    def scale_point(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        scaled_x = left_pad + ((x - min_x) / x_span) * map_width
        scaled_y = top_pad + map_height - ((y - min_y) / y_span) * map_height
        return scaled_x, scaled_y

    road_paths: list[dict[str, object]] = []
    mapped_names = set()
    fallback_names = set()

    for segment in raw_segments:
        points = [scale_point(point) for point in segment["points"]]
        path_d = make_path(points)
        display_name = str(segment["display_name"])
        normalized_name = str(segment["normalized_name"])
        mapped_names.add(display_name)
        road_source = str(segment.get("road_source", "CT DOT centerline"))
        geometry_quality = str(segment.get("geometry_quality", "surveyed"))
        if road_source != "CT DOT centerline":
            fallback_names.add(display_name)
        road_paths.append(
            {
                "display_name": display_name,
                "normalized_name": normalized_name,
                "path_d": path_d,
                "road_source": road_source,
                "geometry_quality": geometry_quality,
                "block_group_label": str(segment.get("block_group_label", "")),
                "population": segment.get("population"),
                "median_age": segment.get("median_age"),
                "median_income": segment.get("median_income"),
                "owner_share": segment.get("owner_share"),
                "renter_share": segment.get("renter_share"),
            }
        )

    mapped_name_list = sorted(mapped_names)
    mapped_normalized = {normalize_name(name) for name in mapped_name_list}
    unmatched_names = sorted(
        name for name in official_names if normalize_name(name) not in mapped_normalized
    )

    svg_paths_markup = "\n".join(
        (
            f'    <path class="road{" fallback-road" if road["geometry_quality"] == "approximate" else ""}" '
            f'data-display-name="{attr(road["display_name"])}" '
            f'data-name="{attr(road["normalized_name"])}" '
            f'data-road-source="{attr(road["road_source"])}" '
            f'data-geometry-quality="{attr(road["geometry_quality"])}" '
            f'data-block-group-label="{attr(road["block_group_label"])}" '
            f'data-population="{attr(road["population"])}" '
            f'data-median-age="{attr(road["median_age"])}" '
            f'data-median-income="{attr(road["median_income"])}" '
            f'data-owner-share="{attr(road["owner_share"])}" '
            f'data-renter-share="{attr(road["renter_share"])}" '
            f'd="{road["path_d"]}">'
            f"<title>{html.escape(str(road['display_name']))}</title></path>"
        )
        for road in road_paths
    )

    matched_official_count = len(official_names) - len(unmatched_names)
    fallback_note = (
        f" plus {len(fallback_names)} Census-geocoder fallback roads"
        if fallback_names
        else ""
    )
    subtitle = (
        f"{len(mapped_name_list)} named roads drawn from CT DOT centerlines{fallback_note}. "
        f"{matched_official_count} match the {len(official_names)}-name April 28, 2020 "
        "North Haven street list."
    )
    footer = (
        "Road geometry: CT DOT centerlines, with Census-geocoder fallbacks for some missing "
        "official streets. Area demographics: 2020-2024 ACS 5-year block-group estimates. "
        "Street-name list source: North Haven voting district street list printed April 28, 2020."
    )

    svg_markup = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width:.0f} {svg_height:.0f}" role="img" aria-labelledby="title desc">
  <title id="title">North Haven, Connecticut Street Map</title>
  <desc id="desc">{html.escape(subtitle)}</desc>
  <defs>
    <linearGradient id="paper" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#f8f4e8" />
      <stop offset="100%" stop-color="#efe5d3" />
    </linearGradient>
  </defs>
  <style>
    .title {{ font: 700 34px Georgia, 'Times New Roman', serif; fill: #17324d; letter-spacing: 0.02em; }}
    .subtitle {{ font: 500 15px 'Avenir Next', 'Gill Sans', sans-serif; fill: #4b6176; }}
    .footer {{ font: 500 12px 'Avenir Next', 'Gill Sans', sans-serif; fill: #5f6e7a; }}
    .road {{ fill: none; stroke: #0d3b66; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; opacity: 0.82; }}
    .road:hover {{ stroke: #d1495b; stroke-width: 2.7; opacity: 1; }}
  </style>
  <rect x="0" y="0" width="{svg_width:.0f}" height="{svg_height:.0f}" fill="url(#paper)" rx="28" ry="28" />
  <rect x="24" y="24" width="{svg_width - 48:.0f}" height="{svg_height - 48:.0f}" fill="none" stroke="#d7cab6" stroke-width="2" rx="24" ry="24" />
  <text class="title" x="{svg_width / 2:.1f}" y="62" text-anchor="middle">North Haven Street Map</text>
  <text class="subtitle" x="{svg_width / 2:.1f}" y="89" text-anchor="middle">{html.escape(subtitle)}</text>
  <g aria-label="Road centerlines">
{svg_paths_markup}
  </g>
  <text class="footer" x="{svg_width / 2:.1f}" y="{svg_height - 52:.1f}" text-anchor="middle">{html.escape(footer)}</text>
  <text class="footer" x="{svg_width / 2:.1f}" y="{svg_height - 34:.1f}" text-anchor="middle">Hover in a browser for street names. A few street-list entries are not present in the geometry source.</text>
</svg>
"""

    datalist_options = "\n".join(
        f'          <option value="{html.escape(name)}"></option>' for name in mapped_name_list
    )
    unmatched_markup = "\n".join(
        f'            <li>{html.escape(name)}</li>' for name in unmatched_names
    )
    unmatched_summary = (
        f"{len(unmatched_names)} names from the 2020 street list were not present in the "
        "Connecticut DOT geometry source used for the map."
    )

    html_markup = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>North Haven Street Map</title>
    <style>
      :root {{
        --paper: #f8f4e8;
        --paper-shadow: #efe5d3;
        --ink: #17324d;
        --muted: #53697c;
        --road: #0d3b66;
        --road-dim: #b7c2cb;
        --road-highlight: #d1495b;
        --card: rgba(255, 251, 244, 0.9);
        --border: #d6c9b4;
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        font-family: 'Avenir Next', 'Gill Sans', 'Segoe UI', sans-serif;
        background:
          radial-gradient(circle at top, rgba(255, 255, 255, 0.55), transparent 30%),
          linear-gradient(180deg, var(--paper) 0%, var(--paper-shadow) 100%);
        color: var(--ink);
      }}

      main {{
        width: min(1400px, calc(100vw - 32px));
        margin: 24px auto 40px;
        display: grid;
        grid-template-columns: minmax(260px, 330px) minmax(0, 1fr);
        gap: 18px;
      }}

      .panel {{
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 20px;
        box-shadow: 0 18px 40px rgba(52, 66, 82, 0.08);
        backdrop-filter: blur(8px);
      }}

      .sidebar {{
        padding: 22px;
        align-self: start;
        position: sticky;
        top: 24px;
      }}

      h1 {{
        margin: 0 0 10px;
        font: 700 2rem Georgia, 'Times New Roman', serif;
        letter-spacing: 0.02em;
      }}

      p {{
        margin: 0 0 14px;
        color: var(--muted);
        line-height: 1.45;
      }}

      label {{
        display: block;
        margin: 18px 0 8px;
        font-weight: 700;
        color: var(--ink);
      }}

      input {{
        width: 100%;
        padding: 12px 14px;
        border-radius: 12px;
        border: 1px solid #c8baa4;
        background: rgba(255, 255, 255, 0.9);
        font: inherit;
        color: var(--ink);
      }}

      .meta {{
        margin-top: 12px;
        padding: 12px 14px;
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.72);
        border: 1px solid rgba(214, 201, 180, 0.8);
      }}

      .meta strong {{
        display: block;
        color: var(--ink);
        margin-bottom: 4px;
      }}

      .hover-detail {{
        margin-top: 8px;
        color: var(--muted);
        line-height: 1.45;
        font-size: 0.96rem;
      }}

      .hover-detail strong {{
        color: var(--ink);
      }}

      .map-shell {{
        display: flex;
        flex-direction: column;
        overflow: hidden;
        position: relative;
      }}

      .map-toolbar {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 16px 18px 0;
      }}

      .zoom-controls {{
        display: flex;
        align-items: center;
        gap: 10px;
      }}

      .zoom-button {{
        min-width: 44px;
        min-height: 44px;
        border: 1px solid #c8baa4;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.9);
        color: var(--ink);
        font: 700 1.2rem Georgia, 'Times New Roman', serif;
        cursor: pointer;
      }}

      .zoom-button:hover {{
        background: rgba(255, 248, 238, 1);
      }}

      .zoom-readout {{
        min-width: 72px;
        text-align: center;
        font-weight: 700;
        color: var(--ink);
      }}

      .map-hint {{
        margin: 0;
        font-size: 0.95rem;
      }}

      .map-viewport {{
        margin: 16px;
        overflow: auto;
        height: min(78vh, 980px);
        border-radius: 18px;
        border: 1px solid rgba(214, 201, 180, 0.9);
        background: rgba(255, 255, 255, 0.22);
        cursor: grab;
        touch-action: pan-x pan-y pinch-zoom;
      }}

      .map-viewport.dragging {{
        cursor: grabbing;
      }}

      .map-viewport svg {{
        display: block;
        width: auto;
        max-width: none;
        height: auto;
        user-select: none;
      }}

      .street-tooltip {{
        position: fixed;
        left: 0;
        top: 0;
        transform: translate(14px, 14px);
        padding: 10px 12px;
        border-radius: 10px;
        background: rgba(23, 50, 77, 0.94);
        color: #fffdf7;
        font-size: 0.92rem;
        line-height: 1.4;
        box-shadow: 0 10px 24px rgba(24, 34, 43, 0.22);
        pointer-events: none;
        opacity: 0;
        transition: opacity 100ms ease;
        z-index: 20;
        white-space: normal;
        max-width: 280px;
      }}

      .street-tooltip.visible {{
        opacity: 1;
      }}

      .street-tooltip strong {{
        display: block;
        font-size: 0.98rem;
        margin-bottom: 4px;
      }}

      .street-tooltip span {{
        display: block;
      }}

      .street-tooltip .quiet {{
        color: #d7e1ea;
      }}

      .road {{
        fill: none;
        stroke: var(--road);
        stroke-width: 1.7;
        stroke-linecap: round;
        stroke-linejoin: round;
        opacity: 0.82;
        transition: stroke 120ms ease, stroke-width 120ms ease, opacity 120ms ease;
      }}

      .road.dimmed {{
        stroke: var(--road-dim);
        opacity: 0.18;
      }}

      .road.highlight {{
        stroke: var(--road-highlight);
        stroke-width: 3.1;
        opacity: 1;
      }}

      .fallback-road {{
        stroke-dasharray: 6 4;
      }}

      details {{
        margin-top: 18px;
        border-top: 1px solid rgba(214, 201, 180, 0.9);
        padding-top: 16px;
      }}

      summary {{
        cursor: pointer;
        font-weight: 700;
        color: var(--ink);
      }}

      .unmatched-list {{
        columns: 2;
        column-gap: 18px;
        padding-left: 20px;
        color: var(--muted);
      }}

      .unmatched-list li {{
        break-inside: avoid;
        margin-bottom: 6px;
      }}

      @media (max-width: 980px) {{
        main {{
          grid-template-columns: 1fr;
        }}

        .sidebar {{
          position: static;
        }}

        .unmatched-list {{
          columns: 1;
        }}

        .map-toolbar {{
          padding-top: 14px;
        }}

        .map-viewport {{
          height: 68vh;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="panel sidebar">
        <h1>North Haven Street Map</h1>
        <p>{html.escape(subtitle)}</p>
        <p>Type part of a street name to highlight matching roads on the map. Hover over a road to see its name.</p>

        <label for="street-search">Find a street</label>
        <input id="street-search" name="street-search" list="street-names" placeholder="Try Ridge, Maple, or Whitney" autocomplete="off" />
        <datalist id="street-names">
{datalist_options}
        </datalist>

        <div class="meta">
          <strong id="status-line">{len(mapped_name_list)} mapped street names</strong>
          <span id="hover-line">Hover over a road to see its name here.</span>
          <div class="hover-detail" id="hover-detail">Hover a road to see block-group demographic estimates here.</div>
        </div>

        <details>
          <summary>Street-list names not shown in this geometry source</summary>
          <p>{html.escape(unmatched_summary)}</p>
          <ul class="unmatched-list">
{unmatched_markup}
          </ul>
        </details>
      </section>

      <section class="panel map-shell">
        <div class="map-toolbar">
          <div class="zoom-controls" aria-label="Map zoom controls">
            <button class="zoom-button" id="zoom-out" type="button" aria-label="Zoom out">-</button>
            <div class="zoom-readout" id="zoom-readout">100%</div>
            <button class="zoom-button" id="zoom-in" type="button" aria-label="Zoom in">+</button>
            <button class="zoom-button" id="zoom-reset" type="button">Reset</button>
          </div>
          <p class="map-hint">Use the buttons, trackpad pinch, or Ctrl/Cmd + wheel to zoom. Scroll or drag to pan.</p>
        </div>
        <div class="map-viewport" id="map-viewport">
{svg_markup}
        </div>
        <div class="street-tooltip" id="street-tooltip" aria-hidden="true"></div>
      </section>
    </main>

    <script>
      const searchInput = document.getElementById('street-search');
      const statusLine = document.getElementById('status-line');
      const hoverLine = document.getElementById('hover-line');
      const hoverDetail = document.getElementById('hover-detail');
      const mapViewport = document.getElementById('map-viewport');
      const mapSvg = mapViewport.querySelector('svg');
      const streetTooltip = document.getElementById('street-tooltip');
      const zoomOutButton = document.getElementById('zoom-out');
      const zoomInButton = document.getElementById('zoom-in');
      const zoomResetButton = document.getElementById('zoom-reset');
      const zoomReadout = document.getElementById('zoom-readout');
      const roads = Array.from(document.querySelectorAll('.road'));
      const totalNames = {len(mapped_name_list)};
      const svgAspectRatio = {svg_height / svg_width:.6f};
      const minFitWidth = 680;
      const minZoom = 0.65;
      const maxZoom = 6;
      const zoomStep = 1.12;
      const wheelZoomSensitivity = 0.0012;
      const gestureZoomExponent = 0.55;
      let zoomLevel = 1;
      let baseMapWidth = 0;
      let isDragging = false;
      let dragStartX = 0;
      let dragStartY = 0;
      let dragScrollLeft = 0;
      let dragScrollTop = 0;
      let gestureStartZoom = 1;
      const numberFormatter = new Intl.NumberFormat('en-US');
      const moneyFormatter = new Intl.NumberFormat('en-US', {{
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
      }});
      const percentFormatter = new Intl.NumberFormat('en-US', {{
        maximumFractionDigits: 0,
      }});

      function normalizeName(value) {{
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

      function clamp(value, min, max) {{
        return Math.min(max, Math.max(min, value));
      }}

      function parseDataNumber(value) {{
        if (value === undefined || value === null || value === '') {{
          return null;
        }}
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
      }}

      function formatPopulation(value) {{
        return value === null ? 'n/a' : numberFormatter.format(value);
      }}

      function formatMoney(value) {{
        return value === null ? 'n/a' : moneyFormatter.format(value);
      }}

      function formatAge(value) {{
        return value === null ? 'n/a' : value.toFixed(1);
      }}

      function formatPercent(value) {{
        return value === null ? 'n/a' : `${{percentFormatter.format(value)}}%`;
      }}

      function buildTooltipHtml(road) {{
        const population = parseDataNumber(road.dataset.population);
        const medianAge = parseDataNumber(road.dataset.medianAge);
        const medianIncome = parseDataNumber(road.dataset.medianIncome);
        const ownerShare = parseDataNumber(road.dataset.ownerShare);
        const renterShare = parseDataNumber(road.dataset.renterShare);
        const areaLabel = road.dataset.blockGroupLabel || 'No census block-group match found';
        const geometryNote = road.dataset.geometryQuality === 'approximate'
          ? 'Road shape is an approximate fallback for a missing street.'
          : 'Road shape comes from the map centerline source.';
        return `
          <strong>${{road.dataset.displayName}}</strong>
          <span>${{areaLabel}}</span>
          <span>Population: ${{formatPopulation(population)}}</span>
          <span>Median age: ${{formatAge(medianAge)}}</span>
          <span>Median income: ${{formatMoney(medianIncome)}}</span>
          <span>Owner/renter: ${{formatPercent(ownerShare)}} / ${{formatPercent(renterShare)}}</span>
          <span class="quiet">2020-2024 ACS 5-year estimate. ${{geometryNote}}</span>
        `;
      }}

      function buildHoverDetailHtml(road) {{
        const population = parseDataNumber(road.dataset.population);
        const medianAge = parseDataNumber(road.dataset.medianAge);
        const medianIncome = parseDataNumber(road.dataset.medianIncome);
        const ownerShare = parseDataNumber(road.dataset.ownerShare);
        const renterShare = parseDataNumber(road.dataset.renterShare);
        const areaLabel = road.dataset.blockGroupLabel || 'No census block-group match found';
        const sourceLine = road.dataset.geometryQuality === 'approximate'
          ? 'Road shape: approximate Census geocoder fallback.'
          : `Road shape: ${{road.dataset.roadSource}}.`;
        return `
          <strong>${{areaLabel}}</strong><br />
          Population ${{formatPopulation(population)}}. Median age ${{formatAge(medianAge)}}. Median income ${{formatMoney(medianIncome)}}.<br />
          Owner/renter ${{formatPercent(ownerShare)}} / ${{formatPercent(renterShare)}}. 2020-2024 ACS 5-year estimate.<br />
          ${{sourceLine}}
        `;
      }}

      function getBaseMapWidth() {{
        const viewportWidth = Math.max(mapViewport.clientWidth, 0);
        return Math.max(minFitWidth, viewportWidth - 2);
      }}

      function renderZoom(anchorX, anchorY) {{
        const oldWidth = mapSvg.getBoundingClientRect().width || baseMapWidth || getBaseMapWidth();
        const oldHeight = mapSvg.getBoundingClientRect().height || oldWidth * svgAspectRatio;
        const focusX = anchorX ?? mapViewport.clientWidth / 2;
        const focusY = anchorY ?? mapViewport.clientHeight / 2;
        const relativeX = oldWidth ? (mapViewport.scrollLeft + focusX) / oldWidth : 0;
        const relativeY = oldHeight ? (mapViewport.scrollTop + focusY) / oldHeight : 0;

        baseMapWidth = getBaseMapWidth();
        const newWidth = baseMapWidth * zoomLevel;
        const newHeight = newWidth * svgAspectRatio;

        mapSvg.style.width = `${{newWidth}}px`;
        zoomReadout.textContent = `${{Math.round(zoomLevel * 100)}}%`;

        requestAnimationFrame(() => {{
          mapViewport.scrollLeft = Math.max(0, relativeX * newWidth - focusX);
          mapViewport.scrollTop = Math.max(0, relativeY * newHeight - focusY);
        }});
      }}

      function setZoom(nextZoom, anchorX, anchorY) {{
        const clampedZoom = clamp(nextZoom, minZoom, maxZoom);
        if (Math.abs(clampedZoom - zoomLevel) < 0.001) {{
          return;
        }}
        zoomLevel = clampedZoom;
        renderZoom(anchorX, anchorY);
      }}

      function updateHighlights() {{
        const query = normalizeName(searchInput.value);
        const matches = new Set();

        roads.forEach((road) => {{
          const roadName = road.dataset.name;
          const isMatch = !query || roadName.includes(query);
          road.classList.toggle('highlight', Boolean(query) && isMatch);
          road.classList.toggle('dimmed', Boolean(query) && !isMatch);
          if (Boolean(query) && isMatch) {{
            matches.add(road.dataset.displayName);
          }}
        }});

        if (!query) {{
          statusLine.textContent = `${{totalNames}} mapped street names`;
          return;
        }}

        statusLine.textContent = `${{matches.size}} matching street names`;
      }}

      function showTooltip(road, clientX, clientY) {{
        streetTooltip.innerHTML = buildTooltipHtml(road);
        streetTooltip.classList.add('visible');
        streetTooltip.setAttribute('aria-hidden', 'false');
        moveTooltip(clientX, clientY);
      }}

      function moveTooltip(clientX, clientY) {{
        streetTooltip.style.left = `${{clientX}}px`;
        streetTooltip.style.top = `${{clientY}}px`;
      }}

      function hideTooltip() {{
        streetTooltip.classList.remove('visible');
        streetTooltip.setAttribute('aria-hidden', 'true');
      }}

      function resetHoverPanel() {{
        hoverLine.textContent = 'Hover over a road to see its name here.';
        hoverDetail.textContent = 'Hover a road to see block-group demographic estimates here.';
      }}

      roads.forEach((road) => {{
        road.addEventListener('mouseenter', (event) => {{
          hoverLine.textContent = road.dataset.displayName;
          hoverDetail.innerHTML = buildHoverDetailHtml(road);
          showTooltip(road, event.clientX, event.clientY);
        }});

        road.addEventListener('mousemove', (event) => {{
          moveTooltip(event.clientX, event.clientY);
        }});

        road.addEventListener('mouseleave', () => {{
          resetHoverPanel();
          hideTooltip();
        }});
      }});

      zoomInButton.addEventListener('click', () => {{
        setZoom(zoomLevel * zoomStep);
      }});

      zoomOutButton.addEventListener('click', () => {{
        setZoom(zoomLevel / zoomStep);
      }});

      zoomResetButton.addEventListener('click', () => {{
        zoomLevel = 1;
        renderZoom();
      }});

      mapViewport.addEventListener('wheel', (event) => {{
        if (!(event.ctrlKey || event.metaKey)) {{
          return;
        }}
        event.preventDefault();
        const rect = mapViewport.getBoundingClientRect();
        const anchorX = event.clientX - rect.left;
        const anchorY = event.clientY - rect.top;
        const nextZoom = zoomLevel * Math.exp(-event.deltaY * wheelZoomSensitivity);
        setZoom(nextZoom, anchorX, anchorY);
      }}, {{ passive: false }});

      mapViewport.addEventListener('pointerdown', (event) => {{
        if (event.pointerType === 'touch') {{
          return;
        }}
        if (event.button !== 0) {{
          return;
        }}
        hideTooltip();
        isDragging = true;
        dragStartX = event.clientX;
        dragStartY = event.clientY;
        dragScrollLeft = mapViewport.scrollLeft;
        dragScrollTop = mapViewport.scrollTop;
        mapViewport.classList.add('dragging');
        mapViewport.setPointerCapture(event.pointerId);
      }});

      mapViewport.addEventListener('pointermove', (event) => {{
        if (!isDragging) {{
          return;
        }}
        mapViewport.scrollLeft = dragScrollLeft - (event.clientX - dragStartX);
        mapViewport.scrollTop = dragScrollTop - (event.clientY - dragStartY);
      }});

      function stopDragging(event) {{
        if (!isDragging) {{
          return;
        }}
        isDragging = false;
        mapViewport.classList.remove('dragging');
        if (event && mapViewport.hasPointerCapture(event.pointerId)) {{
          mapViewport.releasePointerCapture(event.pointerId);
        }}
      }}

      mapViewport.addEventListener('pointerup', stopDragging);
      mapViewport.addEventListener('pointercancel', stopDragging);
      mapViewport.addEventListener('pointerleave', stopDragging);

      mapViewport.addEventListener('gesturestart', (event) => {{
        gestureStartZoom = zoomLevel;
        hideTooltip();
        event.preventDefault();
      }});

      mapViewport.addEventListener('gesturechange', (event) => {{
        event.preventDefault();
        const rect = mapViewport.getBoundingClientRect();
        const anchorX = event.clientX - rect.left;
        const anchorY = event.clientY - rect.top;
        setZoom(
          gestureStartZoom * Math.pow(event.scale, gestureZoomExponent),
          anchorX,
          anchorY,
        );
      }});

      mapViewport.addEventListener('gestureend', (event) => {{
        event.preventDefault();
      }});

      window.addEventListener('resize', () => {{
        renderZoom();
      }});

      searchInput.addEventListener('input', updateHighlights);
      renderZoom();
      updateHighlights();
      resetHoverPanel();
    </script>
  </body>
</html>
"""

    return svg_markup, html_markup


def main() -> None:
    svg_markup, html_markup = build_map_assets()
    SVG_PATH.write_text(svg_markup)
    HTML_PATH.write_text(html_markup)
    print(f"Wrote {SVG_PATH.name}")
    print(f"Wrote {HTML_PATH.name}")


if __name__ == "__main__":
    main()
