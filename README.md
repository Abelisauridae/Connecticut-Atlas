# Connecticut Street Map

Interactive street-map project for Connecticut, starting with a detailed North Haven build.

The current North Haven demo includes:

- a MapLibre street basemap
- hover tooltips with street names and demographic context
- clickable favorite streets saved in the browser
- custom pins with titles and notes saved in the browser
- block-group demographic estimates from the 2020-2024 ACS 5-year release
- fallback private/missing roads reconstructed from the Census geocoder
- trackpad pinch, Ctrl/Cmd + wheel zoom, drag pan, and street search

## Current Demo

- `index.html`: GitHub Pages friendly entry point
- `north_haven_ct_street_map.html`: the same interactive map file
- `north_haven_ct_street_map.svg`: static poster-style export

## Regenerating The Map

From the project root:

```bash
python3 prepare_north_haven_map_data.py
python3 build_connecticut_street_map.py
```

## Key Files

- `prepare_north_haven_map_data.py`: merges CT DOT roads, Census block-group demographics, and fallback road geometry
- `build_connecticut_street_map.py`: builds the MapLibre app HTML with embedded North Haven road data
- `north_haven_map_features.geojson`: enriched road features used by the map
- `north_haven_ct_geocoder_fallback_roads.geojson`: approximate fallback roads for streets missing from the core centerline data

## Data Sources

- Connecticut DOT road centerlines
- U.S. Census TIGER block groups
- U.S. Census ACS 2020-2024 5-year estimates
- U.S. Census geocoder
- North Haven 2020 street list PDF

## Connecticut Expansion

The cleanest way to scale this to the whole state is:

1. Keep a town-by-town pipeline for detailed maps with private-road fallback handling.
2. Add a statewide landing page with town search and links into per-town maps.
3. Only build a single all-Connecticut street map if a simplified statewide layer is acceptable, because a full-detail self-contained HTML for every road in Connecticut would get very large.

North Haven is the first complete town in this repo. The MapLibre app structure is ready for more towns, shared favorites/pins UX, and a future statewide landing page.
