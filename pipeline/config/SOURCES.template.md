# SOURCES — data provenance log

Copy this file to `data/<ISO3>/SOURCES.md` and fill one row per layer **at the
time you download it**. Provenance is part of the audit trail: a number is only
as defensible as the layer behind it. Record the *exact* download (URL, the year
the data represents, the file version/DOI, and the licence), not just "WorldPop".

**Country:** <country name> (`<ISO3>`)
**Assembled by:** <name> — **on:** <YYYY-MM-DD>
**Target publication for validation (Phase 2):** <citation + DOI>

| Layer | Source / dataset | Exact download URL | Layer year | Version / DOI | Licence | Downloaded on | Notes |
|-------|------------------|--------------------|-----------|----------------|---------|---------------|-------|
| Population | | | | | | | resample=sum; also Base layer |
| Administrative boundaries | | | | | | | mask layer |
| Urban/rural split | | | | | | | resample=nearest |
| Baseline cooking fuel use | | | | | | | feeds current_share_* |
| MV lines | | | | | | | |
| Night-time lights | | | | | | | resample=average |
| Travel time / friction | | | | | | | LPG + collection time |
| Forest cover | | | | | | | resample=average |
| Livestock (GLW) | | | | | | | 6 species |
| Temperature | | | | | | | biogas potential |
| Relative wealth index | | | | | | | affordability |
| Water scarcity | | | | | | | biogas constraint |

## Non-layer assumptions

Recorded in `config.yaml` (and `soc_specs.csv` / `tech_specs.csv`). List the
source for each headline assumption here so the config and its provenance travel
together:

| Assumption | Value | Source | Notes |
|------------|-------|--------|-------|
| fNRB (floor) | | CDM TOOL33 v3.0 | national default; conservative floor |
| fNRB (project-grade) | | MoFuSS sub-national | label fnrb_source accordingly |
| Discount rate | | | |
| VSL | | | |
| Carbon price | | | USD/tCO2e |
| Crediting period | | | years (Article 6 / VCM) |
| Mortality/morbidity rates | | IHME GBD | per 100k/yr |

## Reproducibility stamp (fill at freeze, Phase 2)

- OnStove code version / commit: `<git sha or release>`
- conda lockfile: `pipeline/environment.lock.yml`
- pip lockfile: `pipeline/requirements.lock`
- config hash: `<sha256 of config.yaml>`
- validation status: `provisional` | `validated`
