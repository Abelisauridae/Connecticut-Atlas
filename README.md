# Connecticut Street Map

Interactive street-map project for Connecticut with two live demos today:

- `index.html`: New Haven County explorer
- `new_haven_county_street_map.html`: the same county-wide map file
- `north_haven_ct_street_map.html`: detailed North Haven explorer with the private-road fallback work
- `north_haven_ct_street_map.svg`: static North Haven poster export

## What The Maps Include

- MapLibre street basemap
- hover tooltips with street names and demographic context
- favorite streets saved in the browser
- custom pins with titles and notes saved in the browser
- block-group demographic estimates from the 2020-2024 ACS 5-year release
- municipality-aware favorites so duplicate street names do not collide across towns
- North Haven fallback/private roads reconstructed from the Census geocoder
- trackpad pinch, Ctrl/Cmd + wheel zoom, drag pan, street search, and county town filtering

## Regenerating The Maps

From the project root:

```bash
python3 prepare_north_haven_map_data.py
python3 prepare_new_haven_county_map_data.py
python3 build_connecticut_street_map.py
```

## File Size Guardrail

No generated file should exceed `25 MB`.

The county pipeline honors that by:

- splitting the enriched county GeoJSON into part files
- loading county map data from split JavaScript assets instead of embedding one giant HTML blob

## Key Files

- `prepare_north_haven_map_data.py`: builds the detailed North Haven dataset with geocoder fallback roads
- `prepare_new_haven_county_map_data.py`: fetches New Haven County CT DOT roads, merges in the North Haven fallback dataset, and enriches county roads with ACS block-group demographics
- `build_connecticut_street_map.py`: builds the MapLibre HTML apps and sharded county data-loader assets
- `new_haven_county_map_features_manifest.json`: manifest for the county GeoJSON part files
- `new_haven_county_map_features.part01.geojson`: county road features kept under the file-size cap
- `new_haven_county_street_map_data.part01.js`: browser-ready county road data chunk
- `north_haven_map_features.geojson`: enriched North Haven road features used by the town map

## Data Sources

- Connecticut DOT local road centerlines
- U.S. Census TIGER block groups
- U.S. Census ACS 2020-2024 5-year estimates
- U.S. Census geocoder
- North Haven 2020 street list PDF

## Next Expansion

The current structure is now ready for more county builds or a broader Connecticut atlas:

1. Add another county prep script that writes split GeoJSON parts under the same size limit.
2. Point `build_connecticut_street_map.py` at the new dataset and generate another explorer page.
3. Add a statewide landing page once there are enough county-level maps to browse.
