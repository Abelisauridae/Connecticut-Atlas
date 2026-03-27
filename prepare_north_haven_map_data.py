from __future__ import annotations

import json
import math
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OFFICIAL_STREETS_PATH = ROOT / "north_haven_ct_streets_2020.txt"
STREET_LIST_PDF_PATH = ROOT / "north_haven_street_list_2020.pdf"
DOT_ROADS_PATH = ROOT / "north_haven_ct_roads.geojson"
BLOCK_GROUPS_PATH = ROOT / "south_central_ct_block_groups_2024.geojson"
ACS_PATH = ROOT / "south_central_ct_acs5_2024_block_groups.json"
ENRICHED_ROADS_PATH = ROOT / "north_haven_map_features.geojson"
FALLBACK_ROADS_PATH = ROOT / "north_haven_ct_geocoder_fallback_roads.geojson"
GEOCODER_CACHE_PATH = ROOT / "north_haven_geocoder_cache.json"

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

SKIP_LINE_PARTS = (
    "NORTH HAVEN, CT",
    "Streets and Voting District List",
    "Congressional District",
    "Assembly District",
    "Voting Districts:",
    "Printed 04-28-2020",
    "*Indicates Dist 3",
)

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def normalize_name(name: str) -> str:
    name = name.upper().replace(".", "").replace("'S", "S").strip()
    tokens = re.split(r"\s+", name)
    normalized = []
    for token in tokens:
        token = SPECIAL_TOKENS.get(token, token)
        normalized.append(TOKEN_TO_ABBR.get(token, token))
    return " ".join(normalized)


def load_json(path: Path) -> object:
    return json.loads(path.read_text())


def load_official_names() -> list[str]:
    return [
        line.strip()
        for line in OFFICIAL_STREETS_PATH.read_text().splitlines()
        if line.strip()
    ]


def load_pdf_text() -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(STREET_LIST_PDF_PATH), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def extract_pdf_specs(pdf_text: str) -> list[str]:
    pattern = re.compile(r"(.+?)\s{2,}([1-5]\*?)(?=(?:\s{2,}\S)|\s*$)")
    specs: list[str] = []
    for raw_line in pdf_text.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if any(marker in line for marker in SKIP_LINE_PARTS):
            continue
        for match in pattern.finditer(line):
            spec = match.group(1).strip()
            if spec:
                specs.append(spec)
    return specs


def map_specs_to_streets(
    official_names: list[str],
    specs: list[str],
) -> dict[str, list[str]]:
    official_map = {normalize_name(name): name for name in official_names}
    official_tokens = sorted(
        ((norm_name.split(), official_map[norm_name]) for norm_name in official_map),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    spec_map: dict[str, list[str]] = {name: [] for name in official_names}

    for spec in specs:
        spec_tokens = normalize_name(spec).split()
        for official_name_tokens, official_name in official_tokens:
            token_count = len(official_name_tokens)
            if spec_tokens[:token_count] == official_name_tokens:
                remainder = " ".join(spec_tokens[token_count:])
                spec_map[official_name].append(remainder)
                break

    return spec_map


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


def load_block_groups() -> list[dict[str, object]]:
    geojson = load_json(BLOCK_GROUPS_PATH)
    block_groups: list[dict[str, object]] = []
    for feature in geojson["features"]:
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


def load_acs_stats() -> dict[str, dict[str, object]]:
    rows = load_json(ACS_PATH)
    header = rows[0]
    stats_by_geoid: dict[str, dict[str, object]] = {}
    for row in rows[1:]:
        entry = dict(zip(header, row))
        geoid = (
            entry["state"]
            + entry["county"]
            + entry["tract"]
            + entry["block group"]
        )

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


def load_geocoder_cache() -> dict[str, object]:
    if GEOCODER_CACHE_PATH.exists():
        return json.loads(GEOCODER_CACHE_PATH.read_text())
    return {}


def save_geocoder_cache(cache: dict[str, object]) -> None:
    GEOCODER_CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def geocode_address(
    address: str,
    cache: dict[str, object],
) -> dict[str, object] | None:
    if address in cache:
        cached = cache[address]
        return cached if cached else None

    params = urllib.parse.urlencode(
        {
            "address": address,
            "benchmark": "Public_AR_Current",
            "format": "json",
        }
    )
    request = urllib.request.Request(
        f"{GEOCODER_URL}?{params}",
        headers={"User-Agent": "Codex/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    matches = payload["result"]["addressMatches"]
    if not matches:
        cache[address] = None
        return None

    match = matches[0]
    cache[address] = match
    time.sleep(0.05)
    return match


def sample_numbers_from_remainder(remainder: str) -> list[int]:
    upper = remainder.upper()
    odd = "ODD" in upper
    even = "EVEN" in upper
    has_end = "END" in upper
    explicit_only = "ONLY" in upper or "#" in upper or "&" in upper
    numbers = sorted({int(value) for value in re.findall(r"\d+", upper)})

    def adjust(value: int) -> int:
        value = max(1, value)
        if odd and value % 2 == 0:
            value += 1
        if even and value % 2 == 1:
            value += 1
        return value

    candidates: list[int] = []
    if numbers:
        low = min(numbers)
        high = max(numbers)
        if len(numbers) == 1:
            candidates.append(adjust(low))
            if explicit_only:
                candidates.append(adjust(low))
            elif has_end:
                for delta in (24, 48, 98, 198):
                    candidates.append(adjust(low + delta))
            else:
                for delta in (12, 24, 48):
                    candidates.append(adjust(low + delta))
        else:
            mid = (low + high) // 2
            quarter = low + (high - low) // 4
            three_quarter = low + (3 * (high - low)) // 4
            candidates.extend(
                adjust(value)
                for value in (low, quarter, mid, three_quarter, high)
            )
    elif odd:
        candidates.extend([1, 25, 49, 73, 97])
    elif even:
        candidates.extend([2, 24, 48, 72, 96])
    else:
        candidates.extend([1, 25, 49, 73, 97, 2, 24, 48, 72, 96])

    deduped: list[int] = []
    seen = set()
    for candidate in candidates:
        if candidate > 0 and candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped


def build_candidate_numbers(remainders: list[str]) -> list[int]:
    candidates: list[int] = []
    for remainder in remainders:
        candidates.extend(sample_numbers_from_remainder(remainder))
    if not candidates:
        candidates.extend([1, 25, 49, 73, 97, 2, 24, 48, 72, 96])
    deduped: list[int] = []
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped


def build_follow_up_numbers(
    from_address: str,
    to_address: str,
    preferred_parity: int,
) -> list[int]:
    start = parse_number(from_address) or preferred_parity or 1
    end = parse_number(to_address) or max(start + 40, start)
    if end < start:
        start, end = end, start

    if preferred_parity % 2 == 0:
        parity = 0
    else:
        parity = 1

    span = max(0, end - start)
    steps = [0, span // 4, span // 2, (3 * span) // 4, span]
    samples: list[int] = []
    for step in steps:
        value = start + step
        if value % 2 != parity:
            value += 1
        if value > end:
            value -= 2
        if value >= start and value not in samples:
            samples.append(value)
    return samples


def coords_key(lon: float, lat: float) -> tuple[int, int]:
    return round(lon * 10_000_000), round(lat * 10_000_000)


def build_fallback_roads(
    official_names: list[str],
    spec_map: dict[str, list[str]],
    dot_features: list[dict],
) -> tuple[list[dict], list[str]]:
    dot_names = {
        normalize_name(feature["properties"].get("STREET_NAME", ""))
        for feature in dot_features
        if feature["properties"].get("STREET_NAME")
    }
    missing_names = [
        name
        for name in official_names
        if normalize_name(name) not in dot_names
    ]

    geocoder_cache = load_geocoder_cache()
    fallback_features: list[dict] = []
    unresolved: list[str] = []

    for street_name in missing_names:
        seed_numbers = build_candidate_numbers(spec_map.get(street_name, []))
        groups: dict[str, dict[str, object]] = {}

        for number in seed_numbers[:10]:
            address = f"{number} {street_name}, North Haven, CT 06473"
            match = geocode_address(address, geocoder_cache)
            if not match:
                continue
            tiger_line = match.get("tigerLine", {}).get("tigerLineId")
            if not tiger_line:
                continue
            entry = groups.setdefault(
                tiger_line,
                {
                    "from_address": match["addressComponents"].get("fromAddress", ""),
                    "to_address": match["addressComponents"].get("toAddress", ""),
                    "points": [],
                    "seen_coords": set(),
                    "preferred_parity": number,
                },
            )
            lon = match["coordinates"]["x"]
            lat = match["coordinates"]["y"]
            key = coords_key(lon, lat)
            if key not in entry["seen_coords"]:
                entry["points"].append((number, lon, lat))
                entry["seen_coords"].add(key)

        for tiger_line, entry in groups.items():
            follow_up_numbers = build_follow_up_numbers(
                str(entry["from_address"]),
                str(entry["to_address"]),
                int(entry["preferred_parity"]),
            )
            for number in follow_up_numbers:
                address = f"{number} {street_name}, North Haven, CT 06473"
                match = geocode_address(address, geocoder_cache)
                if not match:
                    continue
                if match.get("tigerLine", {}).get("tigerLineId") != tiger_line:
                    continue
                lon = match["coordinates"]["x"]
                lat = match["coordinates"]["y"]
                key = coords_key(lon, lat)
                if key not in entry["seen_coords"]:
                    entry["points"].append((number, lon, lat))
                    entry["seen_coords"].add(key)

        created_any = False
        for tiger_line, entry in groups.items():
            ordered_points = sorted(entry["points"], key=lambda item: item[0])
            unique_coords = [(lon, lat) for _, lon, lat in ordered_points]
            if len(unique_coords) < 2:
                continue
            fallback_features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "display_name": street_name,
                        "normalized_name": normalize_name(street_name),
                        "road_source": "Census geocoder fallback",
                        "geometry_quality": "approximate",
                        "tiger_line_id": tiger_line,
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": unique_coords,
                    },
                }
            )
            created_any = True

        if not created_any:
            unresolved.append(street_name)

    save_geocoder_cache(geocoder_cache)
    return fallback_features, unresolved


def owner_renter_shares(stats: dict[str, object]) -> tuple[float | None, float | None]:
    occupied_units = stats.get("occupied_units")
    owner_units = stats.get("owner_units")
    renter_units = stats.get("renter_units")
    if not occupied_units or occupied_units <= 0:
        return None, None
    owner_share = (owner_units / occupied_units) * 100 if owner_units is not None else None
    renter_share = (renter_units / occupied_units) * 100 if renter_units is not None else None
    return owner_share, renter_share


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


def format_tract(tract: str) -> str:
    tract = str(tract)
    if len(tract) == 6:
        return f"{int(tract[:4])}.{tract[4:]}" if tract[4:] != "00" else str(int(tract[:4]))
    return tract


def build_dot_features(official_name_map: dict[str, str]) -> list[dict]:
    geojson = load_json(DOT_ROADS_PATH)
    features: list[dict] = []
    for feature in geojson["features"]:
        raw_name = feature["properties"].get("STREET_NAME", "").strip()
        if not raw_name:
            continue
        normalized_name = normalize_name(raw_name)
        display_name = official_name_map.get(normalized_name, raw_name.title())
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "display_name": display_name,
                    "normalized_name": normalize_name(display_name),
                    "road_source": "CT DOT centerline",
                    "geometry_quality": "surveyed",
                },
                "geometry": feature["geometry"],
            }
        )
    return features


def main() -> None:
    official_names = load_official_names()
    official_name_map = {normalize_name(name): name for name in official_names}
    dot_features = build_dot_features(official_name_map)
    pdf_specs = extract_pdf_specs(load_pdf_text())
    spec_map = map_specs_to_streets(official_names, pdf_specs)
    fallback_features, unresolved = build_fallback_roads(
        official_names,
        spec_map,
        load_json(DOT_ROADS_PATH)["features"],
    )
    block_groups = load_block_groups()
    acs_stats = load_acs_stats()

    combined_features = enrich_features(
        dot_features + fallback_features,
        block_groups,
        acs_stats,
    )

    FALLBACK_ROADS_PATH.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": fallback_features,
                "unresolved_official_streets": unresolved,
            },
            indent=2,
        )
    )
    ENRICHED_ROADS_PATH.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": combined_features},
            indent=2,
        )
    )

    print(f"Wrote {ENRICHED_ROADS_PATH.name} with {len(combined_features)} features")
    print(f"Wrote {FALLBACK_ROADS_PATH.name} with {len(fallback_features)} fallback features")
    print(f"Unresolved official streets: {len(unresolved)}")


if __name__ == "__main__":
    main()
