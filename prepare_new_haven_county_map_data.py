from __future__ import annotations

import json
import math
import subprocess
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parent
NORTH_HAVEN_FEATURES_PATH = ROOT / "north_haven_map_features.geojson"
COUNTY_FEATURES_STEM = ROOT / "new_haven_county_map_features"
COUNTY_FEATURES_MANIFEST_PATH = ROOT / "new_haven_county_map_features_manifest.json"
MAX_PART_BYTES = 24_000_000

DOT_LAYER_URL = (
    "https://gisportal.dot.ct.gov/server/rest/services/Datamart/"
    "State_Routes_and_Local_Roads/FeatureServer/1/query"
)
BLOCK_GROUPS_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/tigerWMS_ACS2024/MapServer/10/query"
)
ACS_BASE_URL = "https://api.census.gov/data/2024/acs/acs5"

NEW_HAVEN_COUNTY_TOWNS = [
    "Ansonia",
    "Beacon Falls",
    "Bethany",
    "Branford",
    "Cheshire",
    "Derby",
    "East Haven",
    "Guilford",
    "Hamden",
    "Madison",
    "Meriden",
    "Middlebury",
    "Milford",
    "Naugatuck",
    "New Haven",
    "North Branford",
    "North Haven",
    "Orange",
    "Oxford",
    "Prospect",
    "Seymour",
    "Southbury",
    "Wallingford",
    "Waterbury",
    "West Haven",
    "Wolcott",
    "Woodbridge",
]

CONNECTICUT_COUNTY_EQUIVALENT_CODES = [
    "110",
    "120",
    "130",
    "140",
    "150",
    "160",
    "170",
    "180",
    "190",
]

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

SPECIAL_TOKENS = {
    "BROADWAY": "BROADWY",
}


def normalize_name(name: str) -> str:
    name = name.upper().replace(".", "").replace("'S", "S").strip()
    tokens = name.split()
    normalized: list[str] = []
    for token in tokens:
        token = SPECIAL_TOKENS.get(token, token)
        normalized.append(TOKEN_TO_ABBR.get(token, token))
    return " ".join(normalized)


def load_json(path: Path) -> object:
    return json.loads(path.read_text())


def encoded_size(value: str) -> int:
    return len(value.encode("utf-8"))


def fetch_json(url: str) -> object:
    result = subprocess.run(
        ["curl", "-Lsf", url],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def fetch_arcgis_geojson(
    base_url: str,
    where: str,
    out_fields: list[str],
) -> list[dict]:
    count_params = urllib.parse.urlencode(
        {
            "where": where,
            "returnCountOnly": "true",
            "f": "json",
        }
    )
    count_payload = fetch_json(f"{base_url}?{count_params}")
    total_count = int(count_payload.get("count", 0))

    features: list[dict] = []
    offset = 0
    while offset < total_count:
        params = urllib.parse.urlencode(
            {
                "where": where,
                "outFields": ",".join(out_fields),
                "orderByFields": "OBJECTID",
                "resultOffset": offset,
                "resultRecordCount": 2000,
                "outSR": 4326,
                "f": "geojson",
            }
        )
        payload = fetch_json(f"{base_url}?{params}")
        batch = payload.get("features", [])
        if not batch:
            break
        features.extend(batch)
        offset += len(batch)

    return features


def fetch_block_groups() -> list[dict]:
    return fetch_arcgis_geojson(
        BLOCK_GROUPS_URL,
        "STATE='09'",
        ["GEOID", "TRACT", "BLKGRP", "COUNTY"],
    )


def fetch_acs_rows() -> list[list[str]]:
    header: list[str] | None = None
    rows: list[list[str]] = []

    for county_code in CONNECTICUT_COUNTY_EQUIVALENT_CODES:
        params = urllib.parse.urlencode(
            {
                "get": ",".join(
                    [
                        "NAME",
                        "B01003_001E",
                        "B01002_001E",
                        "B19013_001E",
                        "B25003_001E",
                        "B25003_002E",
                        "B25003_003E",
                    ]
                ),
                "for": "block group:*",
                "in": f"state:09 county:{county_code}",
            }
        )
        payload = fetch_json(f"{ACS_BASE_URL}?{params}")
        if not payload:
            continue
        if header is None:
            header = payload[0]
        rows.extend(payload[1:])

    if header is None:
        raise RuntimeError("Unable to load ACS data for Connecticut block groups.")

    return [header, *rows]


def fetch_county_roads() -> list[dict]:
    town_list = ", ".join(f"'{town}'" for town in NEW_HAVEN_COUNTY_TOWNS)
    where = f"TOWN_NAME IN ({town_list})"
    return fetch_arcgis_geojson(
        DOT_LAYER_URL,
        where,
        ["TOWN_NAME", "STREET_NAME"],
    )


def iter_lines(geometry: dict) -> list[list[list[float]]]:
    if geometry["type"] == "LineString":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiLineString":
        return geometry["coordinates"]
    raise ValueError(f"Unsupported geometry type: {geometry['type']}")


def point_in_ring(point: tuple[float, float], ring: list[list[float]]) -> bool:
    x, y = point
    inside = False
    count = len(ring)
    if count < 3:
        return False
    for index in range(count):
        x1, y1 = ring[index]
        x2, y2 = ring[(index + 1) % count]
        intersects = (y1 > y) != (y2 > y)
        if not intersects:
            continue
        slope = (x2 - x1) / (y2 - y1)
        intersection_x = x1 + (y - y1) * slope
        if intersection_x > x:
            inside = not inside
    return inside


def point_in_polygon(point: tuple[float, float], geometry: dict) -> bool:
    if geometry["type"] == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        return False

    for polygon in polygons:
        if not polygon:
            continue
        outer_ring = polygon[0]
        if not point_in_ring(point, outer_ring):
            continue
        if any(point_in_ring(point, hole) for hole in polygon[1:]):
            continue
        return True

    return False


def geometry_bbox(geometry: dict) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    if geometry["type"] == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        raise ValueError(f"Unsupported polygon geometry: {geometry['type']}")
    for polygon in polygons:
        for ring in polygon:
            for lon, lat in ring:
                xs.append(lon)
                ys.append(lat)
    return min(xs), min(ys), max(xs), max(ys)


def line_midpoint(geometry: dict) -> tuple[float, float]:
    lines = iter_lines(geometry)
    points = [point for line in lines for point in line]
    if not points:
        raise ValueError("Empty line geometry")
    if len(points) == 1:
        return tuple(points[0])

    lat0 = sum(lat for _, lat in points) / len(points)
    cos_lat = math.cos(math.radians(lat0))

    lengths: list[float] = []
    total_length = 0.0
    for line in lines:
        for (lon1, lat1), (lon2, lat2) in zip(line, line[1:]):
            dx = (lon2 - lon1) * cos_lat
            dy = lat2 - lat1
            segment_length = math.hypot(dx, dy)
            lengths.append(segment_length)
            total_length += segment_length

    if total_length == 0:
        return tuple(points[0])

    target = total_length / 2
    traversed = 0.0
    segment_index = 0
    for line in lines:
        for (lon1, lat1), (lon2, lat2) in zip(line, line[1:]):
            segment_length = lengths[segment_index]
            segment_index += 1
            if traversed + segment_length >= target and segment_length > 0:
                ratio = (target - traversed) / segment_length
                return (
                    lon1 + (lon2 - lon1) * ratio,
                    lat1 + (lat2 - lat1) * ratio,
                )
            traversed += segment_length

    return tuple(points[-1])


def parse_number(value: str) -> int | None:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def parse_float(value: str) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def load_block_groups_from_features(features: list[dict]) -> list[dict[str, object]]:
    block_groups: list[dict[str, object]] = []
    for feature in features:
        geometry = feature["geometry"]
        properties = feature["properties"]
        block_groups.append(
            {
                "geometry": geometry,
                "bbox": geometry_bbox(geometry),
                "properties": properties,
            }
        )
    return block_groups


def load_acs_stats(rows: list[list[str]]) -> dict[str, dict[str, object]]:
    header = rows[0]
    stats_by_geoid: dict[str, dict[str, object]] = {}
    for row in rows[1:]:
        entry = dict(zip(header, row))
        geoid = entry["state"] + entry["county"] + entry["tract"] + entry["block group"]

        occupied_total = parse_number(entry["B25003_001E"])
        owner_units = parse_number(entry["B25003_002E"])
        renter_units = parse_number(entry["B25003_003E"])

        stats_by_geoid[geoid] = {
            "population": parse_number(entry["B01003_001E"]),
            "median_age": parse_float(entry["B01002_001E"]),
            "median_income": parse_number(entry["B19013_001E"]),
            "owner_units": owner_units,
            "renter_units": renter_units,
            "occupied_units": occupied_total,
        }
    return stats_by_geoid


def choose_block_group(
    point: tuple[float, float],
    block_groups: list[dict[str, object]],
) -> dict[str, object] | None:
    lon, lat = point
    for block_group in block_groups:
        min_lon, min_lat, max_lon, max_lat = block_group["bbox"]
        if lon < min_lon or lon > max_lon or lat < min_lat or lat > max_lat:
            continue
        if point_in_polygon(point, block_group["geometry"]):
            return block_group
    return None


def owner_renter_shares(stats: dict[str, object]) -> tuple[float | None, float | None]:
    occupied_units = stats.get("occupied_units")
    owner_units = stats.get("owner_units")
    renter_units = stats.get("renter_units")
    if not occupied_units or occupied_units <= 0:
        return None, None
    owner_share = (owner_units / occupied_units) * 100 if owner_units is not None else None
    renter_share = (renter_units / occupied_units) * 100 if renter_units is not None else None
    return owner_share, renter_share


def format_tract(tract: str) -> str:
    tract = str(tract)
    if len(tract) == 6:
        suffix = tract[4:]
        return f"{int(tract[:4])}.{suffix}" if suffix != "00" else str(int(tract[:4]))
    return tract


def build_ctdot_features(dot_features: list[dict]) -> list[dict]:
    features: list[dict] = []
    for feature in dot_features:
        properties = feature["properties"]
        municipality = (properties.get("TOWN_NAME") or "").strip()
        if not municipality or municipality == "North Haven":
            continue
        raw_name = (properties.get("STREET_NAME") or "").strip()
        if not raw_name:
            continue
        display_name = raw_name.title()
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "display_name": display_name,
                    "normalized_name": normalize_name(display_name),
                    "municipality": municipality,
                    "road_source": "CT DOT centerline",
                    "geometry_quality": "surveyed",
                },
                "geometry": feature["geometry"],
            }
        )
    return features


def load_north_haven_features() -> list[dict]:
    geojson = load_json(NORTH_HAVEN_FEATURES_PATH)
    features: list[dict] = []
    for feature in geojson["features"]:
        properties = dict(feature["properties"])
        properties["municipality"] = "North Haven"
        if not properties.get("normalized_name") and properties.get("display_name"):
            properties["normalized_name"] = normalize_name(properties["display_name"])
        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": feature["geometry"],
            }
        )
    return features


def enrich_features(
    features: list[dict],
    block_groups: list[dict[str, object]],
    acs_stats: dict[str, dict[str, object]],
) -> list[dict]:
    enriched: list[dict] = []
    for feature in features:
        midpoint = line_midpoint(feature["geometry"])
        block_group = choose_block_group(midpoint, block_groups)
        properties = dict(feature["properties"])
        if block_group is not None:
            bg_properties = block_group["properties"]
            geoid = bg_properties["GEOID"]
            stats = acs_stats.get(geoid, {})
            owner_share, renter_share = owner_renter_shares(stats)
            properties.update(
                {
                    "acs_block_group_geoid": geoid,
                    "acs_tract": bg_properties["TRACT"],
                    "acs_block_group": bg_properties["BLKGRP"],
                    "acs_block_group_label": (
                        f"Block Group {bg_properties['BLKGRP']}, "
                        f"Census Tract {format_tract(bg_properties['TRACT'])}"
                    ),
                    "acs_population": stats.get("population"),
                    "acs_median_age": stats.get("median_age"),
                    "acs_median_income": stats.get("median_income"),
                    "acs_owner_share": owner_share,
                    "acs_renter_share": renter_share,
                }
            )
        enriched.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": feature["geometry"],
            }
        )
    return enriched


def write_feature_collection_parts(stem: Path, features: list[dict]) -> list[str]:
    header = '{"type":"FeatureCollection","features":['
    footer = "]}"
    max_empty_bytes = encoded_size(header) + encoded_size(footer)
    part_names: list[str] = []
    current_feature_json: list[str] = []
    current_size = max_empty_bytes
    part_number = 1

    for feature in features:
        feature_json = json.dumps(feature, separators=(",", ":"))
        feature_size = encoded_size(feature_json)
        minimum_size = max_empty_bytes + feature_size
        if minimum_size > MAX_PART_BYTES:
            raise RuntimeError("A single road feature exceeded the maximum part size.")

        additional_bytes = feature_size + (1 if current_feature_json else 0)
        if current_feature_json and current_size + additional_bytes > MAX_PART_BYTES:
            filename = f"{stem.name}.part{part_number:02d}.geojson"
            (stem.parent / filename).write_text(header + ",".join(current_feature_json) + footer)
            part_names.append(filename)
            part_number += 1
            current_feature_json = []
            current_size = max_empty_bytes
            additional_bytes = feature_size

        current_feature_json.append(feature_json)
        current_size += additional_bytes

    if current_feature_json:
        filename = f"{stem.name}.part{part_number:02d}.geojson"
        (stem.parent / filename).write_text(header + ",".join(current_feature_json) + footer)
        part_names.append(filename)

    return part_names


def main() -> None:
    print("Fetching New Haven County CT DOT roads...")
    dot_features = fetch_county_roads()
    print(f"Fetched {len(dot_features)} county road segments from CT DOT.")

    print("Fetching Connecticut block-group geometry...")
    block_group_features = fetch_block_groups()
    block_groups = load_block_groups_from_features(block_group_features)
    print(f"Fetched {len(block_groups)} Connecticut block groups.")

    print("Fetching Connecticut ACS block-group estimates...")
    acs_rows = fetch_acs_rows()
    acs_stats = load_acs_stats(acs_rows)
    print(f"Loaded ACS estimates for {len(acs_stats)} block groups.")

    county_features = load_north_haven_features() + build_ctdot_features(dot_features)
    print(f"Preparing {len(county_features)} county road features for enrichment...")
    enriched_features = enrich_features(county_features, block_groups, acs_stats)

    part_names = write_feature_collection_parts(COUNTY_FEATURES_STEM, enriched_features)
    manifest = {
        "type": "feature_collection_parts",
        "name": COUNTY_FEATURES_STEM.name,
        "part_files": part_names,
        "feature_count": len(enriched_features),
        "municipalities": sorted(
            {
                feature["properties"].get("municipality", "Unknown")
                for feature in enriched_features
            }
        ),
    }
    COUNTY_FEATURES_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    print(
        f"Wrote {COUNTY_FEATURES_MANIFEST_PATH.name} and "
        f"{len(part_names)} GeoJSON part files for {len(enriched_features)} road features."
    )


if __name__ == "__main__":
    main()
