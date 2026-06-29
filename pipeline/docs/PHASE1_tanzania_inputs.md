# Phase 1 — Tanzania input-acquisition checklist

**Goal:** assemble every OnStove input layer for **Tanzania** (ISO3 `TZA`),
each documented with source, URL, year, and licence, plus a single
`config.yaml` capturing every assumption that is *not* a downloaded layer.

> **Canonical source for this project.** The input layers are available
> pre-assembled in the published dataset **"OnStove inputs and outputs"**,
> Mendeley Data [doi:10.17632/7y943f6wf8.2](https://data.mendeley.com/datasets/7y943f6wf8/2)
> (OnStove v0.1.1). Use `pipeline/scripts/fetch_inputs.py` to stage it. The table
> below documents the upstream provenance of each layer (what the dataset was
> built from) so the bundle stays auditable and reproducible from primary sources.

> **Validate one country first.** Do not start with all 44 SSA countries.
> Tanzania is recommended: high national fNRB (~0.51 per CDM TOOL33 v3.0),
> published OnStove/IEA coverage, and the country the prototype drill-down was
> designed around.

## How to use this checklist

1. Create the per-country data folder (see structure below).
2. For each layer, download from the listed source, then **record the exact
   URL, layer year, file version/DOI, and licence** in `config/SOURCES.md`
   (copy `config/SOURCES.template.md`). Match every layer's year to the target
   publication you validate against (Phase 2).
3. Reproject and align all rasters to OnStove's working CRS/resolution
   (`EPSG:3395`, 1 km cells) using `DataProcessor` — see
   `example/OnStove_notebook.ipynb` for the exact calls.
4. Record every non-layer assumption (discount rate, VSL, carbon price, fNRB,
   crediting period, …) in `config/tanzania.yaml`.

Confirm the exact required-layer list against the OnStove version you install —
this table mirrors `example/OnStove_notebook.ipynb` for the current package.

## Required input layers

| # | Layer (OnStove category/name) | Recommended source | URL | Year to use | Licence | Notes |
|---|-------------------------------|--------------------|-----|-------------|---------|-------|
| 1 | **Population** (`Demographics/Population`, raster) | WorldPop unconstrained 1 km, or GHSL | https://www.worldpop.org/datacatalog/ (TZA) · https://ghsl.jrc.ec.europa.eu/ | match publication (e.g. 2020) | WorldPop CC-BY-4.0; GHSL free w/ attribution | Resample `sum`. This is also the OnStove `Base` layer. |
| 2 | **Administrative boundaries** (`Administrative/Country_boundaries`, vector) | GADM, or Tanzania NBS official | https://gadm.org/download_country.html (TZA) | current | GADM free for academic/non-commercial — **check terms for commercial use** | Used as the mask layer. |
| 3 | **Urban/rural split** (`Demographics/Urban_rural_divide`, raster) | GHS-SMOD settlement model | https://ghsl.jrc.ec.europa.eu/ghs_smod2023.php | match population year | GHSL free w/ attribution | Resample `nearest`; used to calibrate urban/rural. |
| 4 | **Current cooking fuel / baseline stove use** | DHS Program (TZA DHS), WHO Household Energy DB, or publication source | https://dhsprogram.com/ · https://www.who.int/data/gho/data/themes/air-pollution/who-household-energy-db | survey year nearest publication | DHS requires free registration; WHO open | Feeds `current_share_urban/rural` in `tech_specs.csv`. |
| 5 | **Electricity — MV lines** (`Electricity/MV_lines`, vector) | gridfinder, or national utility (TANESCO) | https://gridfinder.org/ (Zenodo: doi:10.5281/zenodo.3628142) | 2020 (gridfinder) | gridfinder CC-BY-4.0 | For the electric-cooking option / electrification. |
| 6 | **Electricity — night-time lights** (`Electricity/Night_time_lights`, raster) | VIIRS DNB annual composite (EOG) | https://eogdata.mines.edu/products/vnl/ | match population year | EOG free w/ attribution | Resample `average`. |
| 7 | **Travel time / friction surface** (`LPG/Traveltime`, `Biomass/Friction`, raster) | Malaria Atlas Project 2020 motorised friction | https://malariaatlas.org/ (data: doi:10.6084/m9.figshare.7638134) | 2019/2020 | MAP CC-BY-4.0 | Fuel-collection + LPG supply time. |
| 8 | **Forest cover** (`Biomass/Forest`, raster) | Hansen Global Forest Change, or ESA CCI / Copernicus land cover | https://glad.earthengine.app/view/global-forest-change · https://www.esa-landcover-cci.org/ | match publication | Hansen free w/ attribution; ESA CCI free | Resample `average`. Drives sustainable-harvest / fNRB calcs. |
| 9 | **Biomass productivity / biogas inputs** (`Biogas/Livestock/*`, `Biogas/Temperature`, raster) | FAO GLW livestock; WorldClim/ERA5 temperature | https://www.fao.org/livestock-systems/global-distributions/ · https://www.worldclim.org/ | latest GLW; climatology | GLW CC-BY-4.0; WorldClim free academic | Cattle/buffalo/poultry/goats/pigs/sheep + temperature for biogas potential. |
| 10 | **Relative wealth index** (`Demographics/Relative wealth index`, csv) | Meta/Data for Good RWI | https://dataforgood.facebook.com/dfg/tools/relative-wealth-index | 2021 | Meta DFG terms — **check commercial use** | Used by `extract_wealth_index` / affordability. |
| 11 | **Water scarcity** (`Biogas/Water scarcity`, vector) | WRI Aqueduct | https://www.wri.org/aqueduct | latest | CC-BY-4.0 | Constrains biogas where water-scarce. |

### Parameters / specs that are not downloadable layers

| Item | Source | Value for Tanzania | Where it lives |
|------|--------|--------------------|----------------|
| **fNRB** (floor) | CDM TOOL33 v3.0 national defaults | ~0.51 (national) | `config/tanzania.yaml → fnrb`, `tech_specs` `epsilon` |
| **fNRB** (project-grade) | MoFuSS sub-national | per-region MoFuSS raster/value | `config/tanzania.yaml`, label `fnrb_source: MoFuSS_subnational` |
| **Mortality / morbidity rates** | IHME GBD for TZA | `Mort_*` / `Morb_*` in `soc_specs.csv` | scenario CSV |
| **Cost of illness (COI)** | publication / WHO-CHOICE | `COI_*` in `soc_specs.csv` | scenario CSV |
| **VSL, discount rate, carbon price, minimum wage, HH size** | publication assumptions | see `config/tanzania.yaml` | config + scenario CSV |
| **Techno-economic stove specs** | publication / GACC / manufacturer | capex, efficiency, PM2.5, fuel cost, lifetime, O&M | `tech_specs.csv` |

## Per-country folder structure

Mirror the structure OnStove's `DataProcessor` expects (see the notebook). The
raw downloads live under `gis_data/`; aligned outputs are written under the
country code by `save_datasets`.

```
data/TZA/
├── config.yaml                 # copy of pipeline/config/tanzania.yaml, frozen per run
├── SOURCES.md                  # provenance log (copy of SOURCES.template.md)
├── soc_specs.csv               # social/scenario specs (see example/data_templates/)
├── tech_specs.csv              # stove techno-economic specs
├── gis_data/                   # raw downloads (NOT reprojected)
│   ├── Administrative/Country_boundaries/Country_boundaries.geojson
│   ├── Population/Population.tif
│   ├── Urban/Urban.tif
│   ├── Forest/Forest.tif
│   ├── Friction/Friction.tif
│   ├── MV lines/MV_lines.geojson
│   ├── Night time lights/Night_time_lights.tif
│   ├── Traveltime/Traveltime.tif
│   ├── Livestock/{buffaloes,cattles,poultry,goats,pigs,sheeps}/*.tif
│   ├── Temperature/Temperature.tif
│   ├── Water scarcity/Water scarcity.gpkg
│   └── Relative wealth index/TZA_relative_wealth_index.csv
└── TZA/                        # aligned outputs from DataProcessor.save_datasets('all')
```

## Deliverable checklist

- [ ] `data/TZA/gis_data/` populated with every layer above.
- [ ] `config/SOURCES.md` records URL + year + version/DOI + licence per layer.
- [ ] All rasters reprojected/aligned to `EPSG:3395`, 1 km (via `DataProcessor`).
- [ ] `config/tanzania.yaml` captures every non-layer assumption.
- [ ] `soc_specs.csv` / `tech_specs.csv` populated for Tanzania.
- [ ] Bundle is reproducible purely from documented downloads.
