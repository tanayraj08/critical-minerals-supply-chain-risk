# Extension: measured import dependence and the vulnerability score

The original pipeline used a 100% import-dependence **proxy** (zero mining leases) and left the
Strategic Vulnerability Score **not computed**. This folder adds official customs data and computes both.

Run the core pipeline first (`python analysis.py`), then `python extension/import_dependence_v2.py`.
It needs only pandas. Results land in `extension/outputs_v2/`.

## Data added

| File | What it holds | Source |
| --- | --- | --- |
| `dgcis_raw/imports_fy2425_fy2526.json` | India's imports by HS code and country, value (US$ million) and quantity (kg), FY2024-25 and FY2025-26 | DGCIS via [tradestat.commerce.gov.in](https://tradestat.commerce.gov.in/eidb/commodity_wise_all_countries_import), "Commodity-wise all Countries", pulled 25 Nov 2026. Saved totals were checked against the site's own totals for all 17 codes: 0 mismatches |
| `dgcis_raw/exports_totals_fy2425_fy2526.json` | Export totals for the same 17 codes | same site, export side |
| `reference_inputs.csv` | Domestic manganese ore production (3.8 Mt, FY2024-25), nickel/cobalt domestic mining (0), refining leader shares | Ministry of Mines (via [DD News](https://ddnews.gov.in/en/mining-sector-registers-record-production-in-fy-2024-25/)); [USITC, Sept 2025](https://www.usitc.gov/sites/default/files/publications/332/executive_briefings/ebot_guberman_manganese_for_ev_batteries.pdf); USGS 2023 (already in the workbook) |
| `../outputs/05_cr3_hhi_concentration.csv` | Mining HHI | core pipeline |

HS codes used: nickel 75021000, 75022090, 75012000, 28332400; cobalt 81052010, 81052020, 81052030,
81059000, 28220010, 28220020; manganese 26020010 to 26020060 (ore) and 81110010 (metal).

## Results (FY2024-25)

| Metal | Import dependence | How measured | India's supplier HHI (by import value) | Score | Rank |
| --- | --- | --- | --- | --- | --- |
| Cobalt | 100% | 548 t unwrought cobalt imported, 0 domestic mining | 1,687 (China 25.3%) | **80.5** | 1 |
| Nickel | 100% | 35,707 t unwrought nickel imported, 0 domestic mining | 1,215 (China 20.3%) | **67.3** | 2 |
| Manganese | **61.3%** | 6.01 Mt ore imported vs 3.80 Mt mined, 0.01 Mt exported | 2,000 (South Africa 36.8%) | **55.3** | 3 |

Score = 0.40 x import dependence + 0.35 x (mining HHI / 100) + 0.25 x refining leader share.
Refining leaders: Indonesia 56% (nickel), China 80% (cobalt), China 95% of battery-grade manganese sulphate.

**Sensitivity:** moving any weight up or down 10 points (others rescaled) never changes the ranking,
cobalt > nickel > manganese (`vulnerability_sensitivity.csv`). Using the HHI upper bound instead
changes scores by at most 2.6 points (manganese 57.9) and not the ranking.

## What is new 

1. **India imports more manganese ore than it mines**: 6.01 Mt against 3.80 Mt, so 61% import
   dependence even for the metal India produces.
2. **India's own suppliers are far less concentrated than world mining.** Cobalt mining HHI is 5,857, but
   India's import-source HHI is 1,687, because India buys refined products from many refiners and traders
   (China, the USA, the UK, Belgium). The concentration risk sits upstream, in mining and refining, not in
   India's direct supplier list.
3. The score ranking is robust to the weight choice.

