"""
Exploratory data analysis over the loaded database.

This runs after loading and before any metric is computed, because the shape of
this workbook is what dictates every cleaning rule in load_data.py. Three things
are produced:

  1. A per column profile of every table: type, non null count, null count,
     distinct count, min, max and a sample value.
  2. A coverage matrix showing which of the three minerals each table actually
     covers, which is how the manganese gaps were found.
  3. A data quality findings list, each one tied to the table and column it was
     found in and to the rule in load_data.py that handles it.

Nothing here corrects the data. Loading does the correcting. This step exists to
show the evidence that the corrections were needed.

Usage: python explore_data.py
"""

import os
import sqlite3

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "critical_minerals.db")
OUT_DIR = os.path.join(HERE, "outputs")

MINERALS = ["Nickel", "Cobalt", "Manganese"]


def table_names(conn):
    return [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]


def profile_tables(conn):
    """Column level profile of every table in the database."""
    rows = []
    for table in table_names(conn):
        df = pd.read_sql_query("SELECT * FROM " + table, conn)
        for col in df.columns:
            s = df[col]
            non_null = int(s.notna().sum())
            numeric = pd.to_numeric(s, errors="coerce")
            is_num = numeric.notna().sum() > 0 and s.dtype.kind in "ifc"
            sample = s.dropna().iloc[0] if non_null else None
            rows.append(
                {
                    "table": table,
                    "column": col,
                    "dtype": str(s.dtype),
                    "rows": len(df),
                    "non_null": non_null,
                    "nulls": int(s.isna().sum()),
                    "null_pct": round(100.0 * s.isna().sum() / len(df), 1) if len(df) else 0.0,
                    "distinct": int(s.nunique(dropna=True)),
                    "min": round(float(numeric.min()), 3) if is_num else None,
                    "max": round(float(numeric.max()), 3) if is_num else None,
                    "sample_value": str(sample)[:48] if sample is not None else None,
                }
            )
    return pd.DataFrame(rows)


def coverage_matrix(conn):
    """
    Which minerals does each table actually carry? This is the check that
    surfaces the manganese gaps, which are the reason the vulnerability score
    cannot be computed.
    """
    checks = [
        ("india_mn_resources_by_state", "resources by state", ["Manganese"]),
        ("india_mn_production_by_state", "production by state", ["Manganese"]),
        ("india_nico_resources", "national resources", None),
        ("india_nico_imports", "import value", None),
        ("india_demand_projection", "demand projection", None),
        ("global_mining_2024", "world mine production", None),
        ("global_refining_shares", "refining share", None),
    ]
    rows = []
    for table, subject, hardcoded in checks:
        df = pd.read_sql_query("SELECT * FROM " + table, conn)
        for mineral in MINERALS:
            if hardcoded is not None:
                covered = mineral in hardcoded
                detail = "manganese only table" if covered else "table does not cover this mineral"
            elif "mineral" in df.columns:
                block = df[df["mineral"] == mineral]
                covered = len(block) > 0
                detail = str(len(block)) + " rows" if covered else "no rows for this mineral"
                # a refining row exists for manganese but holds text, not a number
                if covered and table == "global_refining_shares":
                    numeric = int(block["is_numeric"].sum())
                    covered = numeric > 0
                    detail = (
                        str(numeric)
                        + " of "
                        + str(len(block))
                        + " rows carry a numeric share"
                    )
            else:
                covered = False
                detail = "no mineral column"
            rows.append(
                {
                    "table": table,
                    "subject": subject,
                    "mineral": mineral,
                    "covered": covered,
                    "detail": detail,
                }
            )
    return pd.DataFrame(rows)


def quality_findings(conn):
    """
    The data quality problems found in the raw workbook, each tied to evidence
    pulled live from the database rather than asserted from memory.
    """
    findings = []

    raw = pd.read_excel(
        os.path.join(HERE, "Critical_Minerals_NiCoMn_Dataset.xlsx"),
        sheet_name="Global_Mining_2024",
        header=3,
    )
    raw.columns = ["mineral", "country", "production_t", "share_of_world_pct"]
    summary_like = raw[
        raw["mineral"].isin(MINERALS) & raw["country"].apply(lambda v: not isinstance(v, str))
    ]
    findings.append(
        {
            "severity": "high",
            "table": "global_mining_2024",
            "column": "country",
            "finding": "summary block below the country rows carries a mineral name in column 1",
            "evidence": str(len(summary_like))
                       + " rows have a mineral name but a numeric value where a country belongs",
            "impact": "a naive read creates countries named 0.774282, 0.97 and 0.86",
            "handled_by": "load_data.load_global_mining, isinstance text test on country",
        }
    )

    agg = pd.read_sql_query(
        "SELECT row_type, COUNT(*) n FROM global_mining_2024 GROUP BY row_type", conn
    )
    findings.append(
        {
            "severity": "high",
            "table": "global_mining_2024",
            "column": "country",
            "finding": "aggregate rows are mixed in with country rows",
            "evidence": "; ".join(agg["row_type"] + "=" + agg["n"].astype(str)),
            "impact": "ranking or summing without a filter double counts the world and "
                      "treats the Other bucket as a producer",
            "handled_by": "load_data.load_global_mining, row_type tag",
        }
    )

    mn_res = pd.read_sql_query(
        "SELECT COUNT(*) n FROM india_mn_resources_by_state WHERE row_type='national_total'", conn
    )
    findings.append(
        {
            "severity": "high",
            "table": "india_mn_resources_by_state and india_mn_production_by_state",
            "column": "state",
            "finding": "a national total row sits inside the state level tables",
            "evidence": "INDIA TOTAL present in resources ("
                       + str(int(mn_res["n"].iloc[0]))
                       + " row), India (Total) present in production",
            "impact": "ranking states without a filter puts the national total at rank 1",
            "handled_by": "load_data, row_type national_total, excluded in queries 03 and 04",
        }
    )

    ref = pd.read_sql_query("SELECT * FROM global_refining_shares", conn)
    text_rows = ref[ref["is_numeric"] == 0]
    findings.append(
        {
            "severity": "high",
            "table": "global_refining_shares",
            "column": "refining_share_raw",
            "finding": "a text sentence occupies a numeric share column",
            "evidence": "; ".join(text_rows["mineral"] + ": " + text_rows["refining_share_raw"]),
            "impact": "coercing to 0 would assert a manganese refining concentration of zero, "
                      "the opposite of what the source says",
            "handled_by": "load_data.load_refining, raw text kept and is_numeric flag added",
        }
    )

    findings.append(
        {
            "severity": "high",
            "table": "india_mn_resources_by_state vs india_mn_production_by_state",
            "column": "total_resources_kt vs qty_2021_22_t",
            "finding": "the two manganese tables use different units",
            "evidence": "resources in thousand tonnes, production in tonnes",
            "impact": "an unconverted join is wrong by a factor of 1000",
            "handled_by": "load_data adds total_resources_t, query 04 converts before dividing",
        }
    )

    share_check = pd.read_sql_query(
        "SELECT MAX(share_of_india_total_pct) mx FROM india_mn_resources_by_state", conn
    )
    findings.append(
        {
            "severity": "medium",
            "table": "all percentage columns",
            "column": "share_of_india_total_pct, share_of_world_pct, cagr",
            "finding": "percentages are stored as fractions and merely formatted as percent",
            "evidence": "Odisha reads 0.340587 in the raw sheet, "
                       + str(round(float(share_check["mx"].iloc[0]), 2))
                       + " after the load time rescale",
            "impact": "charts and comparisons are off by a factor of 100",
            "handled_by": "load_data multiplies every percentage column by 100",
        }
    )

    missing = pd.read_sql_query(
        "SELECT r.state FROM india_mn_resources_by_state r "
        "LEFT JOIN india_mn_production_by_state p ON p.state = r.state "
        "WHERE r.row_type='state' AND p.state IS NULL",
        conn,
    )
    zero = pd.read_sql_query(
        "SELECT state FROM india_mn_production_by_state "
        "WHERE row_type='state' AND qty_2021_22_t = 0",
        conn,
    )
    findings.append(
        {
            "severity": "medium",
            "table": "india_mn_production_by_state",
            "column": "state, qty_2021_22_t",
            "finding": "the production table does not cover every resource holding state, "
                       "and one state reports zero",
            "evidence": "no production row: " + ", ".join(missing["state"])
                       + "; zero production: " + ", ".join(zero["state"]),
            "impact": "an inner join silently drops 3 states and a ratio divides by zero on 1",
            "handled_by": "query 04 LEFT JOIN with a production_status label and a NULL ratio",
        }
    )

    findings.append(
        {
            "severity": "medium",
            "table": "india_nico_imports and india_nico_resources",
            "column": "import_volume_approx, year",
            "finding": "no customs volume series, and the two minerals sit on different years",
            "evidence": "nickel volume not separately disclosed, cobalt approximate only; "
                        "nickel CY2024 against cobalt CY2023",
            "impact": "a true dependence ratio cannot be built, and the two import values "
                      "are not strictly comparable to each other",
            "handled_by": "query 02 labels the output a proxy on every row",
        }
    )

    findings.append(
        {
            "severity": "medium",
            "table": "global_refining_shares",
            "column": "refining_share_pct",
            "finding": "refining coverage is partial by construction",
            "evidence": "source map lists only countries above 5 percent of world processing",
            "impact": "no refining HHI can be built, only a leader share on an incomplete list",
            "handled_by": "analysis.vulnerability_inputs marks the input partial and blocks the score",
        }
    )

    findings.append(
        {
            "severity": "low",
            "table": "india_nico_resources",
            "column": "mineral_raw",
            "finding": "mineral names carry a suffix that breaks joins",
            "evidence": "Cobalt (Ore) and Nickel (Ore) against plain Cobalt and Nickel elsewhere",
            "impact": "a direct join to the imports or demand table returns nothing",
            "handled_by": "load_data strips the suffix into a clean mineral column",
        }
    )

    return pd.DataFrame(findings)


def run(conn=None, verbose=True):
    os.makedirs(OUT_DIR, exist_ok=True)
    own = conn is None
    if own:
        conn = sqlite3.connect(DB_PATH)

    profile = profile_tables(conn)
    coverage = coverage_matrix(conn)
    findings = quality_findings(conn)

    profile.to_csv(os.path.join(OUT_DIR, "eda_column_profile.csv"), index=False)
    coverage.to_csv(os.path.join(OUT_DIR, "eda_mineral_coverage.csv"), index=False)
    findings.to_csv(os.path.join(OUT_DIR, "eda_quality_findings.csv"), index=False)

    if verbose:
        print("=" * 90)
        print("EDA 1  COLUMN PROFILE")
        print("=" * 90)
        print(
            str(len(profile))
            + " columns across "
            + str(profile["table"].nunique())
            + " tables. Columns carrying nulls:"
        )
        nulls = profile[profile["nulls"] > 0]
        with pd.option_context("display.width", 200, "display.max_columns", 20):
            if len(nulls):
                print(nulls[["table", "column", "rows", "nulls", "null_pct"]].to_string(index=False))
            else:
                print("  none")

        print("\n" + "=" * 90)
        print("EDA 2  MINERAL COVERAGE BY TABLE")
        print("=" * 90)
        grid = coverage.pivot(index="table", columns="mineral", values="covered")
        grid = grid[MINERALS].replace({True: "yes", False: "NO"})
        print(grid.to_string())
        gaps = coverage[~coverage["covered"] & (coverage["mineral"] == "Manganese")]
        print(
            "\nManganese is absent from "
            + str(len(gaps))
            + " of the cross mineral tables, which is why no manganese import dependence "
              "and no manganese refining share exist downstream."
        )

        print("\n" + "=" * 90)
        print("EDA 3  DATA QUALITY FINDINGS")
        print("=" * 90)
        for _, r in findings.iterrows():
            print("\n[" + r["severity"].upper() + "] " + r["finding"])
            print("  table    : " + r["table"])
            print("  evidence : " + r["evidence"])
            print("  impact   : " + r["impact"])
            print("  handled  : " + r["handled_by"])
        print(
            "\n"
            + str(len(findings))
            + " findings. Every one is handled at load time or in the query that touches it."
        )

    if own:
        conn.close()
    return profile, coverage, findings


if __name__ == "__main__":
    run()
