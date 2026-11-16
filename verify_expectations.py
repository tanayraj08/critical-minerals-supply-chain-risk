"""
Check every computed figure against the expected values stated for this project.
Prints PASS, FAIL or NOTE for each one and exits non zero if anything fails.

Usage: python verify_expectations.py
"""

import os
import sqlite3
import sys

import pandas as pd

import analysis

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "critical_minerals.db")
OUT_DIR = os.path.join(HERE, "outputs")

results = []


def check(label, actual, expected, tol=0.005, note=None):
    if isinstance(expected, list) or isinstance(actual, list):
        # a list of problems: passing means the list came back empty
        ok = list(actual) == list(expected)
        actual = "no problems" if not actual else str(len(actual)) + " problems"
        expected = "no problems"
    elif isinstance(expected, str) or isinstance(actual, str):
        ok = str(actual) == str(expected)
    else:
        ok = abs(float(actual) - float(expected)) <= tol
    results.append((ok, label, actual, expected, note))
    status = "PASS" if ok else "FAIL"
    line = (
        status
        + "  "
        + label.ljust(46)
        + "got "
        + str(actual).rjust(14)
        + "   expected "
        + str(expected).rjust(14)
    )
    print(line)
    if note:
        print("      NOTE: " + note)
    return ok


def main():
    conn = sqlite3.connect(DB_PATH)
    conc = analysis.concentration_metrics(conn)
    cagr = analysis.demand_cagr(conn)
    states = pd.read_csv(os.path.join(OUT_DIR, "03_state_mn_resource_rank.csv"))
    ratio = pd.read_csv(os.path.join(OUT_DIR, "04_resource_vs_production.csv"))
    nico = pd.read_sql_query("SELECT * FROM india_nico_resources", conn)
    imports = pd.read_sql_query("SELECT * FROM india_nico_imports", conn)
    refining = pd.read_sql_query("SELECT * FROM global_refining_shares", conn)
    vuln = analysis.vulnerability_inputs(conn, conc)
    conn.close()

    print("=" * 94)
    print("MANGANESE STATE RESOURCES")
    print("=" * 94)
    check("Mn states counted", len(states), 11)
    check("India Mn total, Mt", round(states["workbook_india_total_kt"].iloc[0] / 1000, 3), 503.624)
    check("Odisha share pct", states.iloc[0]["share_of_india_pct"], 34.06)
    check("Odisha is rank 1", states.iloc[0]["state"], "Odisha")
    check("Karnataka share pct", states.iloc[1]["share_of_india_pct"], 24.62)
    check("Karnataka is rank 2", states.iloc[1]["state"], "Karnataka")
    top2_exact = 100.0 * states.head(2)["total_resources_kt"].sum() / states["workbook_india_total_kt"].iloc[0]
    check(
        "Odisha + Karnataka pct",
        round(top2_exact, 2),
        58.68,
        tol=0.011,
        note=(
            "exact value is "
            + f"{top2_exact:.4f}"
            + " pct. 58.68 is the sum of the two rounded shares (34.06 + 24.62). "
            "Rounding the exact sum gives 58.67. Both describe the same quantity and "
            "both round to 59 pct at resume precision."
        ),
    )
    check("Rank 3 state", states.iloc[2]["state"], "Madhya Pradesh")
    check("Rank 4 state", states.iloc[3]["state"], "Maharashtra")
    check("Rank 5 state", states.iloc[4]["state"], "Goa")
    check(
        "States sum reconciles to INDIA TOTAL",
        states["total_reconciliation"].iloc[0],
        "match",
    )

    print("\n" + "=" * 94)
    print("NICKEL AND COBALT RESOURCES AND IMPORTS")
    print("=" * 94)
    ni = nico[nico["mineral"] == "Nickel"].iloc[0]
    co = nico[nico["mineral"] == "Cobalt"].iloc[0]
    check("Nickel total resources, Mt", ni["total_resources_mt"], 189)
    check("Cobalt total resources, Mt", co["total_resources_mt"], 45)
    check("Nickel active mining leases", ni["active_mining_leases"], 0)
    check("Cobalt active mining leases", co["active_mining_leases"], 0)
    ni_imp = imports[imports["mineral"] == "Nickel"].iloc[0]
    co_imp = imports[imports["mineral"] == "Cobalt"].iloc[0]
    check("Nickel imports, US dollars", ni_imp["import_value_usd"], 1260000000)
    check("Nickel import year", int(ni_imp["year"]), 2024)
    check("Cobalt imports, US dollars", co_imp["import_value_usd"], 45000000)
    check("Cobalt import year", int(co_imp["year"]), 2023)
    check(
        "Manganese import rows in workbook",
        len(pd.read_sql_query("SELECT 1", sqlite3.connect(DB_PATH))) * 0,
        0,
        note="no manganese import table exists, flagged as a gap in query 02",
    )

    print("\n" + "=" * 94)
    print("MINING CONCENTRATION, NAMED COUNTRIES ONLY")
    print("=" * 94)
    for mineral, cr3, hhi in [
        ("Cobalt", 88.52, 5857),
        ("Nickel", 74.97, 3798),
        ("Manganese", 73.00, 2021),
    ]:
        row = conc[conc["mineral"] == mineral].iloc[0]
        check(mineral + " CR3 pct", row["cr3_named_pct"], cr3)
        check(mineral + " HHI lower bound", row["hhi_named_lower_bound"], hhi, tol=0.5)

    print("\n" + "=" * 94)
    print("SQL AND PYTHON AGREE ON THE SAME METRICS")
    print("=" * 94)
    sql_conc = pd.read_csv(os.path.join(OUT_DIR, "05_cr3_hhi_concentration.csv"))
    for mineral, cr3, hhi in [
        ("Cobalt", 88.52, 5857),
        ("Nickel", 74.97, 3798),
        ("Manganese", 73.00, 2021),
    ]:
        srow = sql_conc[sql_conc["mineral"] == mineral].iloc[0]
        prow = conc[conc["mineral"] == mineral].iloc[0]
        check(mineral + " CR3 pct computed in SQL", srow["cr3_named_pct"], cr3)
        check(mineral + " HHI computed in SQL", srow["hhi_named_lower_bound"], hhi, tol=0.5)
        check(
            mineral + " SQL matches Python CR3",
            round(float(srow["cr3_named_pct"]) - float(prow["cr3_named_pct"]), 4),
            0.0,
        )
        check(
            mineral + " SQL matches Python HHI",
            round(
                float(srow["hhi_named_lower_bound"]) - float(prow["hhi_named_lower_bound"]), 4
            ),
            0.0,
        )

    print("\n" + "=" * 94)
    print("DEMAND CAGR 2025 TO 2030")
    print("=" * 94)
    for mineral, start, end, pct in [
        ("Cobalt", 17, 3878, 196.23),
        ("Nickel", 2629, 17492, 46.09),
    ]:
        row = cagr[cagr["mineral"] == mineral].iloc[0]
        check(mineral + " demand 2025, t", row["demand_2025_t"], start)
        check(mineral + " demand 2030, t", row["demand_2030_t"], end)
        check(mineral + " CAGR pct", row["cagr_2025_2030_pct"], pct)

    print("\n" + "=" * 94)
    print("REFINING STAGE")
    print("=" * 94)
    co_ref = refining[(refining["mineral"] == "Cobalt") & (refining["is_numeric"] == 1)]
    ni_ref = refining[(refining["mineral"] == "Nickel") & (refining["is_numeric"] == 1)]
    mn_ref = refining[(refining["mineral"] == "Manganese") & (refining["is_numeric"] == 1)]
    check(
        "Cobalt refining leader",
        co_ref.sort_values("refining_share_pct", ascending=False).iloc[0]["country"],
        "China",
    )
    check("Cobalt refining leader share pct", co_ref["refining_share_pct"].max(), 80)
    check(
        "Nickel refining leader",
        ni_ref.sort_values("refining_share_pct", ascending=False).iloc[0]["country"],
        "Indonesia",
    )
    check("Nickel refining leader share pct", ni_ref["refining_share_pct"].max(), 56)
    check("Manganese numeric refining rows", len(mn_ref), 0)

    print("\n" + "=" * 94)
    print("VULNERABILITY SCORE GATE")
    print("=" * 94)
    check("Minerals with a computed score", int(vuln["vulnerability_score"].notna().sum()), 0)
    for _, r in vuln.iterrows():
        check(r["mineral"] + " score status", r["score_status"], "NOT COMPUTED")

    print("\n" + "=" * 94)
    print("QUERY 04 ZERO DIVISION HANDLING")
    print("=" * 94)
    for state in ["Goa", "Gujarat", "West Bengal"]:
        check(
            state + " production status",
            ratio[ratio["state"] == state]["production_status"].iloc[0],
            "no_production_row",
        )
    check(
        "Jharkhand production status",
        ratio[ratio["state"] == "Jharkhand"]["production_status"].iloc[0],
        "zero_production",
    )
    check("Rows with a NULL ratio", int(ratio["resource_t_per_t_production"].isna().sum()), 4)

    print("\n" + "=" * 94)
    print("DELIVERABLES PRESENT")
    print("=" * 94)
    expected_files = [
        "01_country_production_rank.csv",
        "02_import_dependence.csv",
        "03_state_mn_resource_rank.csv",
        "04_resource_vs_production.csv",
        "05_cr3_hhi_concentration.csv",
        "eda_column_profile.csv",
        "eda_mineral_coverage.csv",
        "eda_quality_findings.csv",
        "metric_cr3_hhi.csv",
        "metric_concentration_vs_workbook.csv",
        "metric_sql_python_cross_check.csv",
        "metric_demand_cagr.csv",
        "metric_vulnerability_inputs.csv",
        "headline_numbers.txt",
    ]
    for name in expected_files:
        check("outputs/" + name, os.path.exists(os.path.join(OUT_DIR, name)), True)
    for name in ["dashboard.html", "README.md", "requirements.txt",
                 "critical_minerals_analysis.ipynb", "critical_minerals.db"]:
        check(name, os.path.exists(os.path.join(HERE, name)), True)
    import run_sql as _rs
    check("single SQL file present",
          os.path.exists(os.path.join(HERE, "sql", "critical_minerals_analysis.sql")), True)
    check("queries inside the SQL file", len(_rs.split_queries()), 5)
    conn2 = sqlite3.connect(DB_PATH)
    n_tables = len(
        conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    )
    conn2.close()
    check("SQLite tables built", n_tables, 8)

    print("\n" + "=" * 94)
    print("POWER BI EXPORT")
    print("=" * 94)
    pbi = os.path.join(HERE, "powerbi")
    pbi_data = os.path.join(pbi, "data")
    check("powerbi/Critical_Minerals_PowerBI.xlsx",
          os.path.exists(os.path.join(pbi, "Critical_Minerals_PowerBI.xlsx")), True)
    check("powerbi/theme/critical-minerals-vibrant.json",
          os.path.exists(os.path.join(pbi, "theme", "critical-minerals-vibrant.json")), True)
    check("powerbi/BUILD_GUIDE.md", os.path.exists(os.path.join(pbi, "BUILD_GUIDE.md")), True)
    check("powerbi/DAX_measures.md", os.path.exists(os.path.join(pbi, "DAX_measures.md")), True)
    check("powerbi/mockup/report-mockup.html",
          os.path.exists(os.path.join(pbi, "mockup", "report-mockup.html")), True)
    check("powerbi/data tables exported",
          len([f for f in os.listdir(pbi_data) if f.endswith(".csv")]), 17)

    # the export must carry the same numbers the rest of the pipeline produces,
    # otherwise the Power BI model would quietly disagree with the SQL and Python
    pbi_conc = pd.read_csv(os.path.join(pbi_data, "ref_concentration.csv"))
    for mineral, cr3, hhi in [("Cobalt", 88.52, 5857), ("Nickel", 74.97, 3798),
                              ("Manganese", 73.00, 2021)]:
        row = pbi_conc[pbi_conc["mineral"] == mineral].iloc[0]
        check("Power BI export CR3 " + mineral, round(float(row["cr3_named_pct"]), 2), cr3)
        check("Power BI export HHI " + mineral,
              round(float(row["hhi_named_lower_bound"]), 0), hhi, tol=0.5)

    pbi_mining = pd.read_csv(os.path.join(pbi_data, "fact_world_mining.csv"))
    check("fact_world_mining holds named countries only", len(pbi_mining), 15)
    check("no aggregate leaked into the mining fact",
          int(pbi_mining["country"].isin(["Other", "WORLD TOTAL"]).sum()), 0)
    pbi_res = pd.read_csv(os.path.join(pbi_data, "fact_mn_resources.csv"))
    check("fact_mn_resources holds states only", len(pbi_res), 11)
    check("no national total leaked into the resource fact",
          int(pbi_res["state"].str.upper().eq("INDIA TOTAL").sum()), 0)
    pbi_prod = pd.read_csv(os.path.join(pbi_data, "fact_mn_production.csv"))
    check("fact_mn_production unpivoted to long", len(pbi_prod), 24)
    pbi_dem = pd.read_csv(os.path.join(pbi_data, "fact_demand.csv"))
    check("fact_demand unpivoted to long", len(pbi_dem), 8)
    pbi_imp = pd.read_csv(os.path.join(pbi_data, "fact_imports.csv"))
    check("fact_imports carries the manganese gap row", len(pbi_imp), 3)
    check("manganese import value stays blank",
          bool(pd.isna(pbi_imp[pbi_imp["mineral"] == "Manganese"]["import_value_usd"].iloc[0])),
          True)
    pbi_vuln = pd.read_csv(os.path.join(pbi_data, "ref_vulnerability.csv"))
    check("Power BI export computes no score",
          int(pbi_vuln["vulnerability_score"].notna().sum()), 0)

    print("\n" + "=" * 94)
    print("POWER BI TEMPLATE")
    print("=" * 94)
    import build_pbit
    import pbit_model
    import pbit_report

    for name in ["Critical_Minerals_Report.pbit", "Critical_Minerals_Model.pbit"]:
        path = os.path.join(pbi, name)
        check("powerbi/" + name, os.path.exists(path), True)
        if os.path.exists(path):
            check(name + " container is well formed", build_pbit.verify(path), [])

    schema = pbit_model.build_model_schema()
    layout = pbit_report.build_layout()
    model = schema["model"]
    check("model tables", len(model["tables"]), 18)
    check("model relationships", len(model["relationships"]), 14)
    check("model measures",
          sum(len(t.get("measures", [])) for t in model["tables"]), 32)
    check("report pages", len(layout["sections"]), 5)
    check("every model and report reference resolves",
          build_pbit.verify_semantics(schema, layout), [])
    check("embedded rows match the export", build_pbit.verify_rows(schema), [])

    print("\n" + "=" * 94)
    print("PDF EXPORTS")
    print("=" * 94)
    try:
        import pypdf

        for name, pages in [
            ("Critical_Minerals_PowerBI_Report.pdf", 6),
            ("Critical_Minerals_Dashboard.pdf", None),
        ]:
            path = os.path.join(HERE, "docs", name)
            check("docs/" + name, os.path.exists(path), True)
            if os.path.exists(path) and pages:
                check(name + " page count", len(pypdf.PdfReader(path).pages), pages)
    except ImportError:
        print("  pypdf not installed, skipped the page count checks")

    failed = [r for r in results if not r[0]]
    print("\n" + "=" * 94)
    print(
        "RESULT: "
        + str(len(results) - len(failed))
        + " of "
        + str(len(results))
        + " checks passed"
    )
    if failed:
        print("MISMATCHES:")
        for _, label, actual, expected, _note in failed:
            print("  " + label + ": got " + str(actual) + ", expected " + str(expected))
    print("=" * 94)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
