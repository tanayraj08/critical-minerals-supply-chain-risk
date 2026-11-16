"""
Critical Minerals Supply-Chain Risk Analytics: India's Ni-Co-Mn Exposure
Python layer. SQL does the ranking and joining, Python does the concentration
metrics, the growth arithmetic and the risk framework.

What is computed here
  1. CR3 and HHI per mineral for the mining stage, NAMED COUNTRIES ONLY.
  2. Demand CAGR 2025 to 2030 for nickel and cobalt.
  3. Strategic Vulnerability Score inputs, weights and gate.

Two rules hold throughout.
  No number is invented. Every figure traces to a cell in the workbook or to an
  arithmetic operation on workbook cells, and every gap is printed as a gap.
  The Other bucket is never treated as a country. It is an aggregate of many
  unnamed producers, so counting it as one producer would overstate
  concentration. It is excluded from the numerator of CR3 and from every HHI
  term, while remaining inside the world total that forms the denominator.
  The consequence is stated wherever the metric appears: HHI here is a LOWER
  BOUND on true mining concentration.

Usage: python analysis.py
"""

import os
import sqlite3

import pandas as pd

import explore_data
import load_data
import run_sql

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "critical_minerals.db")
OUT_DIR = os.path.join(HERE, "outputs")
XLSX = os.path.join(HERE, "Critical_Minerals_NiCoMn_Dataset.xlsx")

MINERAL_ORDER = ["Nickel", "Cobalt", "Manganese"]

# Strategic Vulnerability Score weights
WEIGHTS = {
    "import_dependence_pct": 0.40,
    "mining_hhi_scaled": 0.35,   # HHI divided by 100, so 0 to 100
    "refining_leader_pct": 0.25,
}


def banner(text):
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


# ---------------------------------------------------------------------------
# 1. CR3 and HHI, named countries only
# ---------------------------------------------------------------------------
def concentration_metrics(conn):
    """
    CR3  = combined share of world mine production held by the top 3 NAMED
           countries.
    HHI  = sum of squared percentage shares of the named countries, 0 to 10,000.

    Both use the workbook world total as the denominator, which is the same
    basis the workbook uses for its own Share of World column. The Other bucket
    sits in that denominator but contributes no term of its own, so the HHI
    returned is a lower bound: splitting Other into its real constituent
    countries could only add positive squared terms.
    """
    mining = pd.read_sql_query("SELECT * FROM global_mining_2024", conn)
    rows = []
    for mineral in MINERAL_ORDER:
        block = mining[mining["mineral"] == mineral]
        named = block[block["row_type"] == "country"].copy()
        world_total = float(block.loc[block["row_type"] == "world_total", "production_t"].iloc[0])
        other = block[block["row_type"] == "other_bucket"]["production_t"]
        other_t = float(other.iloc[0]) if len(other) else 0.0

        named["share_pct"] = 100.0 * named["production_t"] / world_total
        named = named.sort_values("production_t", ascending=False)

        cr3 = named["share_pct"].head(3).sum()
        hhi = (named["share_pct"] ** 2).sum()

        rows.append(
            {
                "mineral": mineral,
                "named_countries": len(named),
                "named_production_t": named["production_t"].sum(),
                "other_bucket_t": other_t,
                "world_total_t": world_total,
                "other_share_of_world_pct": round(100.0 * other_t / world_total, 2),
                "cr3_named_pct": round(cr3, 2),
                "cr3_top3": ", ".join(named["country"].head(3)),
                "hhi_named_lower_bound": round(hhi, 0),
                "hhi_basis": "sum of squared percent shares of named countries, 0-10000 scale",
                "hhi_interpretation": (
                    "highly concentrated (US DOJ/FTC threshold 2500)"
                    if hhi > 2500
                    else "moderately concentrated"
                ),
                "coverage_note": (
                    "LOWER BOUND: the Other bucket holds "
                    + str(round(100.0 * other_t / world_total, 2))
                    + " percent of world output and contributes no HHI term"
                ),
            }
        )
    return pd.DataFrame(rows)


def concentration_comparison(conn, computed):
    """
    Compare the recomputed metrics against the CR3/HHI block printed inside the
    workbook. The workbook block sorts the Other bucket in with the countries
    and therefore counts it as if it were a single producer. The named-country
    figures are the defensible ones and the difference is reported, not hidden.
    """
    wb = pd.read_sql_query("SELECT * FROM global_mining_concentration_workbook", conn)
    merged = computed.merge(wb, on="mineral", how="left")
    merged["cr3_difference_pp"] = (
        merged["cr3_named_pct"] - merged["cr3_pct_workbook"]
    ).round(2)
    merged["hhi_difference"] = (
        merged["hhi_named_lower_bound"] - merged["hhi_workbook"]
    ).round(0)
    merged["reason_for_difference"] = (
        "workbook counts the Other bucket as one country in both metrics, "
        "this analysis excludes it from the numerator and from every HHI term"
    )
    cols = [
        "mineral",
        "cr3_named_pct",
        "cr3_pct_workbook",
        "cr3_difference_pp",
        "hhi_named_lower_bound",
        "hhi_workbook",
        "hhi_difference",
        "reason_for_difference",
    ]
    return merged[cols]


# ---------------------------------------------------------------------------
# 2. Demand CAGR
# ---------------------------------------------------------------------------
def demand_cagr(conn):
    """
    CAGR 2025 to 2030 = (value_2030 / value_2025) ** (1/5) - 1.
    Five compounding periods between the 2025 and 2030 endpoints.
    """
    demand = pd.read_sql_query("SELECT * FROM india_demand_projection", conn)
    demand["years"] = 5
    demand["cagr_2025_2030"] = (
        demand["demand_2030_t"] / demand["demand_2025_t"]
    ) ** (1.0 / demand["years"]) - 1.0
    demand["cagr_2025_2030_pct"] = (demand["cagr_2025_2030"] * 100).round(2)
    demand["growth_multiple_2025_to_2030"] = (
        demand["demand_2030_t"] / demand["demand_2025_t"]
    ).round(2)
    demand["matches_workbook_cagr"] = (
        (demand["cagr_2025_2030"] - demand["cagr_2025_2030_workbook"]).abs() < 1e-6
    )
    demand["units"] = "tonnes per year, domestic requirement"
    cols = [
        "mineral",
        "demand_2025_t",
        "demand_2026_t",
        "demand_2027_t",
        "demand_2030_t",
        "growth_multiple_2025_to_2030",
        "cagr_2025_2030_pct",
        "cagr_2025_2030_workbook_pct",
        "matches_workbook_cagr",
        "units",
    ]
    return demand[cols].sort_values("mineral").reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. Strategic Vulnerability Score
# ---------------------------------------------------------------------------
def vulnerability_inputs(conn, concentration):
    """
    Design only. The score is deliberately NOT computed.

    Intended form:
        score = 0.40 * import_dependence_pct
              + 0.35 * (mining_hhi / 100)
              + 0.25 * refining_leader_share_pct
    All three inputs are on a 0 to 100 scale before weighting, which is why the
    HHI is divided by 100.

    The gate is that all three inputs must exist AND be complete for a mineral.
    No mineral clears it:
      Nickel     import dependence is a proxy from zero active leases, and the
                 refining share comes from a partial USGS map that lists only
                 countries above 5 percent of world processing.
      Cobalt     same two limitations.
      Manganese  no import table in the workbook at all and no refining figure,
                 so two of the three inputs are simply absent.
    Publishing a weighted score on those inputs would read as a measurement when
    it is an assumption, so the score column stays empty and the reason is
    carried in the output.
    """
    refining = pd.read_sql_query("SELECT * FROM global_refining_shares", conn)
    imports = pd.read_sql_query("SELECT * FROM india_nico_imports", conn)
    rows = []

    for mineral in MINERAL_ORDER:
        conc = concentration[concentration["mineral"] == mineral].iloc[0]

        # input A: import dependence
        imp = imports[imports["mineral"] == mineral]
        if len(imp):
            import_dep = 100.0
            import_quality = "proxy"
            import_note = (
                "100 percent proxy from zero active mining leases, "
                "import value US$ "
                + f"{imp['import_value_usd'].iloc[0]:,.0f}"
                + " in CY"
                + str(imp["year"].iloc[0])
            )
        else:
            import_dep = None
            import_quality = "missing"
            import_note = "no manganese import table in the workbook"

        # input B: mining concentration
        hhi_scaled = round(float(conc["hhi_named_lower_bound"]) / 100.0, 2)
        hhi_quality = "lower_bound"
        hhi_note = (
            "named countries only, Other bucket holds "
            + str(conc["other_share_of_world_pct"])
            + " percent of world output and adds no term"
        )

        # input C: refining leader share
        ref = refining[(refining["mineral"] == mineral) & (refining["is_numeric"] == 1)]
        if len(ref):
            lead = ref.sort_values("refining_share_pct", ascending=False).iloc[0]
            refining_leader = float(lead["refining_share_pct"])
            refining_country = lead["country"]
            refining_quality = "partial"
            refining_note = (
                "USGS 2023 map lists only countries above 5 percent of world "
                "processing, so this is a leader share on partial coverage"
            )
        else:
            refining_leader = None
            refining_country = None
            refining_quality = "missing"
            raw = refining[refining["mineral"] == mineral]["refining_share_raw"]
            refining_note = raw.iloc[0] if len(raw) else "no refining row in the workbook"

        qualities = [import_quality, hhi_quality, refining_quality]
        complete = all(q == "complete" for q in qualities)
        missing = [
            name
            for name, q in zip(
                ["import_dependence", "mining_hhi", "refining_leader_share"], qualities
            )
            if q == "missing"
        ]
        degraded = [
            name
            for name, q in zip(
                ["import_dependence", "mining_hhi", "refining_leader_share"], qualities
            )
            if q in ("proxy", "partial", "lower_bound")
        ]

        if missing:
            reason = "INPUTS ABSENT: " + ", ".join(missing)
        else:
            reason = "INPUTS PRESENT BUT NOT COMPLETE: " + ", ".join(degraded)

        rows.append(
            {
                "mineral": mineral,
                "weight_import_dependence": WEIGHTS["import_dependence_pct"],
                "input_import_dependence_pct": import_dep,
                "quality_import_dependence": import_quality,
                "note_import_dependence": import_note,
                "weight_mining_hhi": WEIGHTS["mining_hhi_scaled"],
                "input_mining_hhi_raw": float(conc["hhi_named_lower_bound"]),
                "input_mining_hhi_scaled_0_100": hhi_scaled,
                "quality_mining_hhi": hhi_quality,
                "note_mining_hhi": hhi_note,
                "weight_refining_leader": WEIGHTS["refining_leader_pct"],
                "input_refining_leader_pct": refining_leader,
                "refining_leader_country": refining_country,
                "quality_refining_leader": refining_quality,
                "note_refining_leader": refining_note,
                "all_inputs_complete": complete,
                "vulnerability_score": None,
                "score_status": "NOT COMPUTED",
                "score_blocked_reason": reason,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Headline block
# ---------------------------------------------------------------------------
def headline_block(conn, concentration, cagr, vuln, sql_results):
    mn = sql_results["03_state_mn_resource_rank"]
    imports = pd.read_sql_query("SELECT * FROM india_nico_imports", conn)
    nico = pd.read_sql_query("SELECT * FROM india_nico_resources", conn)
    ratio = sql_results["04_resource_vs_production"]

    india_total_kt = float(mn["workbook_india_total_kt"].iloc[0])
    top2 = mn.head(2)
    top2_share = 100.0 * top2["total_resources_kt"].sum() / india_total_kt

    lines = []
    add = lines.append
    add("=" * 78)
    add("HEADLINE NUMBERS  (every figure traced to the workbook)")
    add("=" * 78)

    add("\n[1] INDIA MANGANESE RESOURCE BASE  (IBM NMI as on 01.04.2020)")
    add("    States covered                 : " + str(len(mn)))
    add("    India total resources          : " + f"{india_total_kt/1000:,.3f}" + " Mt")
    for _, r in mn.head(5).iterrows():
        add(
            "    "
            + str(int(r["resource_rank"])).rjust(2)
            + ". "
            + r["state"].ljust(16)
            + f"{r['total_resources_mt']:>9,.3f} Mt   "
            + f"{r['share_of_india_pct']:>6.2f} %"
        )
    add("    Odisha + Karnataka combined    : " + f"{top2_share:.2f}" + " %")

    add("\n[2] INDIA NICKEL AND COBALT RESOURCES  (NMI as on 01.04.2020)")
    for _, r in nico.sort_values("mineral").iterrows():
        add(
            "    "
            + r["mineral"].ljust(10)
            + f"{r['total_resources_mt']:>8,.0f} Mt ore   "
            + "active mining leases: "
            + str(int(r["active_mining_leases"]))
        )

    add("\n[3] IMPORT EXPOSURE  (value in US dollars, calendar year basis)")
    for _, r in imports.sort_values("mineral").iterrows():
        add(
            "    "
            + r["mineral"].ljust(10)
            + "US$ "
            + f"{r['import_value_usd']:,.0f}"
            + "  (CY"
            + str(int(r["year"]))
            + ")   volume: "
            + str(r["import_volume_note"])
        )
    add("    Manganese imports              : NOT IN WORKBOOK (gap)")

    add("\n[4] GLOBAL MINING CONCENTRATION 2024  (named countries only)")
    for _, r in concentration.iterrows():
        add(
            "    "
            + r["mineral"].ljust(10)
            + "CR3 "
            + f"{r['cr3_named_pct']:>6.2f} %   "
            + "HHI (lower bound) "
            + f"{r['hhi_named_lower_bound']:>8,.0f}   "
            + "top 3: "
            + r["cr3_top3"]
        )

    add("\n[5] PROJECTED INDIAN DEMAND, CAGR 2025 to 2030")
    for _, r in cagr.iterrows():
        add(
            "    "
            + r["mineral"].ljust(10)
            + f"{r['demand_2025_t']:>7,.0f} t (2025)  to  "
            + f"{r['demand_2030_t']:>7,.0f} t (2030)   CAGR "
            + f"{r['cagr_2025_2030_pct']:>7.2f} %"
        )

    add("\n[6] REFINING STAGE  (USGS 2023, partial coverage)")
    refining = pd.read_sql_query("SELECT * FROM global_refining_shares", conn)
    for _, r in refining.iterrows():
        value = (
            f"{r['refining_share_pct']:.0f} %"
            if r["is_numeric"] == 1
            else "NO FIGURE: " + str(r["refining_share_raw"])
        )
        add("    " + r["mineral"].ljust(10) + str(r["country"]).ljust(18) + value)

    add("\n[7] STRATEGIC VULNERABILITY SCORE")
    add("    Status: NOT COMPUTED for any mineral.")
    for _, r in vuln.iterrows():
        add("    " + r["mineral"].ljust(10) + r["score_blocked_reason"])

    add("\n[8] RESOURCE BASE AGAINST FY2021-22 PRODUCTION")
    producing = ratio[ratio["production_status"] == "producing"]
    add(
        "    States producing in FY2021-22  : "
        + str(len(producing))
        + " of "
        + str(len(ratio))
    )
    for _, r in ratio[ratio["production_status"] != "producing"].iterrows():
        add("    " + r["state"].ljust(16) + r["production_status"])
    add("=" * 78)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    banner("STEP 1  LOAD WORKBOOK INTO SQLITE")
    conn, _ = load_data.build_database(XLSX, DB_PATH)
    conn.close()

    banner("STEP 2  EXPLORATORY DATA ANALYSIS")
    conn = sqlite3.connect(DB_PATH)
    explore_data.run(conn)
    conn.close()

    banner("STEP 3  RUN THE SQL FILES")
    sql_results = run_sql.run_all(DB_PATH, verbose=False)
    for name, df in sql_results.items():
        print("  " + name.ljust(34) + str(len(df)).rjust(3) + " rows  ->  outputs/" + name + ".csv")

    conn = sqlite3.connect(DB_PATH)

    banner("STEP 4  CR3 AND HHI, NAMED COUNTRIES ONLY")
    conc = concentration_metrics(conn)
    conc.to_csv(os.path.join(OUT_DIR, "metric_cr3_hhi.csv"), index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(
            conc[
                [
                    "mineral",
                    "named_countries",
                    "cr3_named_pct",
                    "hhi_named_lower_bound",
                    "other_share_of_world_pct",
                    "cr3_top3",
                ]
            ].to_string(index=False)
        )
    print(
        "\nHHI is a LOWER BOUND. The Other bucket is excluded from every term "
        "because it aggregates many unnamed producers."
    )

    banner("STEP 4b  SQL AND PYTHON CROSS CHECK")
    sql_conc = sql_results["05_cr3_hhi_concentration"]
    cross = conc[["mineral", "cr3_named_pct", "hhi_named_lower_bound"]].merge(
        sql_conc[["mineral", "cr3_named_pct", "hhi_named_lower_bound"]],
        on="mineral",
        suffixes=("_python", "_sql"),
    )
    cross["cr3_agrees"] = (
        cross["cr3_named_pct_python"] - cross["cr3_named_pct_sql"]
    ).abs() < 0.005
    cross["hhi_agrees"] = (
        cross["hhi_named_lower_bound_python"] - cross["hhi_named_lower_bound_sql"]
    ).abs() < 0.5
    cross.to_csv(os.path.join(OUT_DIR, "metric_sql_python_cross_check.csv"), index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(cross.to_string(index=False))
    if bool(cross["cr3_agrees"].all() and cross["hhi_agrees"].all()):
        print("\nSQL query 05 and analysis.py agree on every mineral.")
    else:
        print("\nWARNING: the SQL and Python concentration metrics disagree.")

    cmp_df = concentration_comparison(conn, conc)
    cmp_df.to_csv(os.path.join(OUT_DIR, "metric_concentration_vs_workbook.csv"), index=False)
    banner("STEP 4c  RECOMPUTED METRICS AGAINST THE WORKBOOK CR3/HHI BLOCK")
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(cmp_df.drop(columns=["reason_for_difference"]).to_string(index=False))
    print(
        "\nDifference reason: the workbook block sorts the Other bucket in with "
        "the countries, so it counts an aggregate as a single producer."
    )

    banner("STEP 5  DEMAND CAGR 2025 TO 2030")
    cagr = demand_cagr(conn)
    cagr.to_csv(os.path.join(OUT_DIR, "metric_demand_cagr.csv"), index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(cagr.to_string(index=False))
    print("\nNo manganese demand projection exists in the workbook, so none is shown.")

    banner("STEP 6  STRATEGIC VULNERABILITY SCORE INPUTS")
    vuln = vulnerability_inputs(conn, conc)
    vuln.to_csv(os.path.join(OUT_DIR, "metric_vulnerability_inputs.csv"), index=False)
    print("Weights: import dependence 40 percent, mining HHI / 100 35 percent, "
          "refining leader share 25 percent.\n")
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(
            vuln[
                [
                    "mineral",
                    "input_import_dependence_pct",
                    "quality_import_dependence",
                    "input_mining_hhi_scaled_0_100",
                    "quality_mining_hhi",
                    "input_refining_leader_pct",
                    "quality_refining_leader",
                    "score_status",
                ]
            ].to_string(index=False)
        )
    print("\nSCORE NOT COMPUTED for any mineral:")
    for _, r in vuln.iterrows():
        print("  " + r["mineral"].ljust(11) + r["score_blocked_reason"])

    banner("STEP 7  HEADLINE BLOCK")
    text = headline_block(conn, conc, cagr, vuln, sql_results)
    print(text)
    with open(os.path.join(OUT_DIR, "headline_numbers.txt"), "w", encoding="ascii") as fh:
        fh.write(text + "\n")

    conn.close()

    banner("STEP 8  DASHBOARD")
    import build_dashboard

    build_dashboard.build()
    print("dashboard.html written")

    banner("STEP 9  POWER BI STAR SCHEMA EXPORT")
    import build_powerbi_export

    build_powerbi_export.build()

    banner("STEP 10  POWER BI REPORT MOCKUP")
    import build_powerbi_mockup

    print("written: " + build_powerbi_mockup.build())

    banner("STEP 11  POWER BI TEMPLATE FILES")
    import build_pbit

    build_pbit.build()

    banner("STEP 12  PDF EXPORTS")
    import build_pdf

    build_pdf.build()


if __name__ == "__main__":
    main()
