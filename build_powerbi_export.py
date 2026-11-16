"""
Export the SQLite database into a Power BI ready star schema.

Why this is not just the same tables again. The analysis database is shaped for
SQL, where an aggregate row sitting next to a detail row is handled by a WHERE
clause. Power BI has no WHERE clause between a user and a chart, so anything at
the wrong grain inside a fact table eventually ends up double counted on a
visual. Three modelling decisions follow from that:

  1. Aggregates are split out by grain. Named countries live in
     fact_world_mining while the WORLD TOTAL and the Other bucket live in
     ref_world_totals. The state rows live in fact_mn_resources while the
     national total lives in ref_india_totals. Dragging a country onto a chart
     can no longer pull in the world.
  2. Year columns are unpivoted into rows. The workbook holds production and
     demand as one column per year, which cannot drive a time axis or a year
     slicer. Both come out long here.
  3. Dimensions are separated from facts and keyed. One dim_mineral drives every
     fact, so a single slicer filters the whole report.

Two reference tables carry known correct answers: ref_concentration holds the
CR3 and HHI values this pipeline computes in both SQL and Python, and
ref_vulnerability holds the risk framework inputs. The DAX measures are meant to
reproduce ref_concentration exactly, which turns that table into a built in test
for the Power BI model.

Outputs land in powerbi/data as CSVs and in powerbi/Critical_Minerals_PowerBI.xlsx
as one sheet per table for a single click import.

Usage: python build_powerbi_export.py
"""

import os
import sqlite3

import pandas as pd

import analysis

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "critical_minerals.db")
PBI_DIR = os.path.join(HERE, "powerbi")
DATA_DIR = os.path.join(PBI_DIR, "data")
WORKBOOK = os.path.join(PBI_DIR, "Critical_Minerals_PowerBI.xlsx")

# the validated vibrant palette, carried in dim_mineral so the report can bind
# a colour to a mineral rather than to a chart position
MINERAL_COLOUR = {
    "Nickel": "#378DFF",
    "Cobalt": "#FA04A6",
    "Manganese": "#DB6B04",
}
MINERAL_GROUP = {
    "Nickel": "Battery and stainless steel metal",
    "Cobalt": "Battery metal",
    "Manganese": "Steel alloying metal",
}
MINERAL_ORDER = {"Nickel": 1, "Cobalt": 2, "Manganese": 3}


def build(verbose=True):
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    mining = pd.read_sql_query("SELECT * FROM global_mining_2024", conn)
    mn_res = pd.read_sql_query("SELECT * FROM india_mn_resources_by_state", conn)
    mn_prod = pd.read_sql_query("SELECT * FROM india_mn_production_by_state", conn)
    nico = pd.read_sql_query("SELECT * FROM india_nico_resources", conn)
    imports = pd.read_sql_query("SELECT * FROM india_nico_imports", conn)
    demand = pd.read_sql_query("SELECT * FROM india_demand_projection", conn)
    refining = pd.read_sql_query("SELECT * FROM global_refining_shares", conn)
    conc = analysis.concentration_metrics(conn)
    conc_cmp = analysis.concentration_comparison(conn, conc)
    vuln = analysis.vulnerability_inputs(conn, conc)
    cagr = analysis.demand_cagr(conn)
    quality = pd.read_csv(os.path.join(HERE, "outputs", "eda_quality_findings.csv"))
    conn.close()

    tables = {}

    # ---------------------------------------------------------------- dims
    dim_mineral = pd.DataFrame(
        {"mineral": ["Nickel", "Cobalt", "Manganese"]}
    )
    dim_mineral["mineral_key"] = dim_mineral["mineral"].map(MINERAL_ORDER)
    dim_mineral["mineral_group"] = dim_mineral["mineral"].map(MINERAL_GROUP)
    dim_mineral["theme_colour_hex"] = dim_mineral["mineral"].map(MINERAL_COLOUR)
    dim_mineral["sort_order"] = dim_mineral["mineral_key"]
    dim_mineral = dim_mineral[
        ["mineral_key", "mineral", "mineral_group", "theme_colour_hex", "sort_order"]
    ]
    tables["dim_mineral"] = dim_mineral

    countries = sorted(
        set(mining.loc[mining["row_type"] == "country", "country"])
        | set(refining.loc[refining["is_numeric"] == 1, "country"])
    )
    dim_country = pd.DataFrame({"country": countries})
    dim_country.insert(0, "country_key", range(1, len(dim_country) + 1))
    # the map visual needs a name it recognises, so the source spelling is kept
    # alongside a mapping friendly one rather than being overwritten
    map_fix = {"DR Congo": "Democratic Republic of the Congo",
               "Congo (Kinshasa)": "Democratic Republic of the Congo"}
    dim_country["country_for_map"] = dim_country["country"].replace(map_fix)
    tables["dim_country"] = dim_country

    states = sorted(set(mn_res.loc[mn_res["row_type"] == "state", "state"]))
    dim_state = pd.DataFrame({"state": states})
    dim_state.insert(0, "state_key", range(1, len(dim_state) + 1))
    dim_state["country"] = "India"
    tables["dim_state"] = dim_state

    years = sorted(set([2025, 2026, 2027, 2030]))
    dim_year = pd.DataFrame({"year": years})
    dim_year["year_key"] = dim_year["year"]
    dim_year["year_label"] = dim_year["year"].astype(str)
    dim_year["is_endpoint"] = dim_year["year"].isin([2025, 2030])
    dim_year["in_source"] = True
    # the workbook skips 2028 and 2029, and a reader should see that it skipped
    missing = pd.DataFrame(
        {
            "year": [2028, 2029],
            "year_key": [2028, 2029],
            "year_label": ["2028", "2029"],
            "is_endpoint": [False, False],
            "in_source": [False, False],
        }
    )
    dim_year = pd.concat([dim_year, missing]).sort_values("year").reset_index(drop=True)
    tables["dim_year"] = dim_year[
        ["year_key", "year", "year_label", "is_endpoint", "in_source"]
    ]

    ckey = dict(zip(dim_country["country"], dim_country["country_key"]))
    skey = dict(zip(dim_state["state"], dim_state["state_key"]))
    mkey = MINERAL_ORDER

    # --------------------------------------------------------------- facts
    named = mining[mining["row_type"] == "country"].copy()
    totals = mining[mining["row_type"] == "world_total"].set_index("mineral")["production_t"]
    named["mineral_key"] = named["mineral"].map(mkey)
    named["country_key"] = named["country"].map(ckey)
    named["world_production_t"] = named["mineral"].map(totals)
    named["share_of_world_pct"] = (
        100.0 * named["production_t"] / named["world_production_t"]
    ).round(4)
    named["production_rank"] = named.groupby("mineral")["production_t"].rank(
        ascending=False, method="min"
    ).astype(int)
    named["is_top_3"] = named["production_rank"] <= 3
    tables["fact_world_mining"] = named[
        [
            "mineral_key",
            "country_key",
            "mineral",
            "country",
            "production_t",
            "share_of_world_pct",
            "production_rank",
            "is_top_3",
        ]
    ].sort_values(["mineral_key", "production_rank"]).reset_index(drop=True)

    other = mining[mining["row_type"] == "other_bucket"].set_index("mineral")["production_t"]
    ref_world = pd.DataFrame({"mineral": ["Nickel", "Cobalt", "Manganese"]})
    ref_world["mineral_key"] = ref_world["mineral"].map(mkey)
    ref_world["world_production_t"] = ref_world["mineral"].map(totals)
    ref_world["other_bucket_t"] = ref_world["mineral"].map(other)
    ref_world["named_total_t"] = ref_world["mineral"].map(
        named.groupby("mineral")["production_t"].sum()
    )
    ref_world["other_share_of_world_pct"] = (
        100.0 * ref_world["other_bucket_t"] / ref_world["world_production_t"]
    ).round(2)
    ref_world["grain_note"] = (
        "aggregate rows, held apart from fact_world_mining so a country visual "
        "cannot double count the world"
    )
    tables["ref_world_totals"] = ref_world

    res = mn_res[mn_res["row_type"] == "state"].copy()
    res["state_key"] = res["state"].map(skey)
    res["total_resources_mt"] = (res["total_resources_kt"] / 1000.0).round(3)
    res["share_of_india_pct"] = (
        100.0 * res["total_resources_kt"] / res["total_resources_kt"].sum()
    ).round(4)
    res["resource_rank"] = res["total_resources_kt"].rank(ascending=False, method="min").astype(int)
    tables["fact_mn_resources"] = res[
        [
            "state_key",
            "state",
            "reserves_kt",
            "remaining_resources_kt",
            "total_resources_kt",
            "total_resources_t",
            "total_resources_mt",
            "share_of_india_pct",
            "resource_rank",
        ]
    ].sort_values("resource_rank").reset_index(drop=True)

    prod = mn_prod[mn_prod["row_type"] == "state"].copy()
    long_rows = []
    for fy, qty_col, val_col in [
        ("2019-20", "qty_2019_20_t", "value_2019_20_rs_thousand"),
        ("2020-21", "qty_2020_21_t", "value_2020_21_rs_thousand"),
        ("2021-22", "qty_2021_22_t", "value_2021_22_rs_thousand"),
    ]:
        block = prod[["state", qty_col, val_col]].copy()
        block.columns = ["state", "production_t", "value_rs_thousand"]
        block["fiscal_year"] = fy
        long_rows.append(block)
    prod_long = pd.concat(long_rows, ignore_index=True)
    prod_long["state_key"] = prod_long["state"].map(skey)
    prod_long["is_latest_year"] = prod_long["fiscal_year"] == "2021-22"
    tables["fact_mn_production"] = prod_long[
        ["state_key", "state", "fiscal_year", "production_t", "value_rs_thousand", "is_latest_year"]
    ].sort_values(["fiscal_year", "state"]).reset_index(drop=True)

    india_tot_res = mn_res[mn_res["row_type"] == "national_total"].iloc[0]
    india_tot_prod = mn_prod[mn_prod["row_type"] == "national_total"].iloc[0]
    tables["ref_india_totals"] = pd.DataFrame(
        [
            {
                "metric": "Manganese total resources",
                "value": float(india_tot_res["total_resources_kt"]),
                "unit": "thousand tonnes",
                "value_display": f"{india_tot_res['total_resources_kt']/1000:,.3f} Mt",
                "as_on": "01.04.2020",
            },
            {
                "metric": "Manganese production FY2021-22",
                "value": float(india_tot_prod["qty_2021_22_t"]),
                "unit": "tonnes",
                "value_display": f"{india_tot_prod['qty_2021_22_t']:,.0f} t",
                "as_on": "FY2021-22",
            },
        ]
    )

    nico_f = nico.copy()
    nico_f["mineral_key"] = nico_f["mineral"].map(mkey)
    nico_f["domestic_mine_production_t"] = 0
    nico_f["supply_note"] = "zero active mining leases, so no domestic mine supply"
    tables["fact_nico_resources"] = nico_f[
        [
            "mineral_key",
            "mineral",
            "reserve_mt",
            "remaining_resources_mt",
            "total_resources_mt",
            "active_mining_leases",
            "domestic_mine_production_t",
            "major_states",
            "supply_note",
        ]
    ]

    imp = imports.copy()
    imp["mineral_key"] = imp["mineral"].map(mkey)
    imp["import_value_usd_million"] = (imp["import_value_usd"] / 1e6).round(2)
    imp["import_dependence_pct"] = 100.0
    imp["dependence_basis"] = "PROXY from zero active mining leases, not customs volume"
    imp["value_label"] = imp.apply(
        lambda r: ("US$" + f"{r['import_value_usd']/1e9:,.2f}" + "B")
        if r["import_value_usd"] >= 1e9
        else ("US$" + f"{r['import_value_usd']/1e6:,.0f}" + "M"),
        axis=1,
    )
    imp["period_label"] = "CY" + imp["year"].astype(str)
    # manganese carried as an explicit gap row so an absent bar is never read as zero
    gap = pd.DataFrame(
        [
            {
                "mineral_key": mkey["Manganese"],
                "mineral": "Manganese",
                "year": pd.NA,
                "currency": pd.NA,
                "import_value_usd": pd.NA,
                "import_value_usd_million": pd.NA,
                "import_dependence_pct": pd.NA,
                "import_volume_note": "NOT IN WORKBOOK",
                "dependence_basis": "DATA GAP: no manganese import table in the source",
                "value_label": "no data",
                "period_label": "n/a",
                "source": "n/a",
            }
        ]
    )
    cols = [
        "mineral_key",
        "mineral",
        "year",
        "currency",
        "import_value_usd",
        "import_value_usd_million",
        "import_dependence_pct",
        "import_volume_note",
        "dependence_basis",
        "value_label",
        "period_label",
        "source",
    ]
    tables["fact_imports"] = pd.concat([imp[cols], gap[cols]], ignore_index=True)

    dem_rows = []
    for _, r in demand.iterrows():
        for year, col in [
            (2025, "demand_2025_t"),
            (2026, "demand_2026_t"),
            (2027, "demand_2027_t"),
            (2030, "demand_2030_t"),
        ]:
            dem_rows.append(
                {
                    "mineral_key": mkey[r["mineral"]],
                    "mineral": r["mineral"],
                    "year_key": year,
                    "year": year,
                    "demand_t": float(r[col]),
                }
            )
    dem = pd.DataFrame(dem_rows)
    base = dem[dem["year"] == 2025].set_index("mineral")["demand_t"]
    dem["index_2025_base_100"] = (100.0 * dem["demand_t"] / dem["mineral"].map(base)).round(1)
    tables["fact_demand"] = dem

    cagr_t = cagr.copy()
    cagr_t["mineral_key"] = cagr_t["mineral"].map(mkey)
    tables["ref_demand_cagr"] = cagr_t[
        [
            "mineral_key",
            "mineral",
            "demand_2025_t",
            "demand_2030_t",
            "growth_multiple_2025_to_2030",
            "cagr_2025_2030_pct",
        ]
    ]

    ref = refining.copy()
    ref["mineral_key"] = ref["mineral"].map(mkey)
    ref["country_key"] = ref["country"].map(ckey)
    ref["coverage"] = ref["is_numeric"].map(
        {1: "partial, source lists only countries above 5 percent of world processing",
         0: "missing, no figure in the source map"}
    )
    tables["fact_refining"] = ref[
        [
            "mineral_key",
            "country_key",
            "mineral",
            "country",
            "refining_share_pct",
            "is_numeric",
            "refining_share_raw",
            "coverage",
        ]
    ]

    c = conc.merge(
        conc_cmp[["mineral", "cr3_pct_workbook", "cr3_difference_pp",
                  "hhi_workbook", "hhi_difference"]],
        on="mineral",
    )
    c["mineral_key"] = c["mineral"].map(mkey)
    tables["ref_concentration"] = c[
        [
            "mineral_key",
            "mineral",
            "named_countries",
            "cr3_named_pct",
            "cr3_top3",
            "hhi_named_lower_bound",
            "other_share_of_world_pct",
            "hhi_interpretation",
            "cr3_pct_workbook",
            "cr3_difference_pp",
            "hhi_workbook",
            "hhi_difference",
        ]
    ]

    v = vuln.copy()
    v["mineral_key"] = v["mineral"].map(mkey)
    v["vulnerability_score"] = pd.NA
    tables["ref_vulnerability"] = v[
        [
            "mineral_key",
            "mineral",
            "weight_import_dependence",
            "input_import_dependence_pct",
            "quality_import_dependence",
            "weight_mining_hhi",
            "input_mining_hhi_scaled_0_100",
            "quality_mining_hhi",
            "weight_refining_leader",
            "input_refining_leader_pct",
            "refining_leader_country",
            "quality_refining_leader",
            "vulnerability_score",
            "score_status",
            "score_blocked_reason",
        ]
    ]

    quality = quality.copy()
    quality.insert(0, "finding_key", range(1, len(quality) + 1))
    tables["ref_data_quality"] = quality

    # --------------------------------------------------------------- write
    for name, df in tables.items():
        df.to_csv(os.path.join(DATA_DIR, name + ".csv"), index=False)

    with pd.ExcelWriter(WORKBOOK, engine="openpyxl") as writer:
        for name, df in tables.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)

    if verbose:
        print("=" * 78)
        print("POWER BI STAR SCHEMA EXPORT")
        print("=" * 78)
        for name, df in tables.items():
            kind = "dim " if name.startswith("dim") else ("fact" if name.startswith("fact") else "ref ")
            print(
                "  "
                + kind
                + "  "
                + name.ljust(24)
                + str(len(df)).rjust(4)
                + " rows  "
                + str(len(df.columns)).rjust(3)
                + " cols"
            )
        print("\n  CSVs      -> powerbi/data/")
        print("  Workbook  -> powerbi/Critical_Minerals_PowerBI.xlsx")
    return tables


if __name__ == "__main__":
    build()
