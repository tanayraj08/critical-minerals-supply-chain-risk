"""
Load the Critical Minerals Ni-Co-Mn workbook into SQLite.

Every sheet has a title in row 1, a source note in row 2, a blank row 3 and the
real header in row 4, so every read uses header=3. README is skipped.

Cleaning rules applied here:
  1. Global_Mining_2024 carries a CR3/HHI summary block below the country rows.
     Only rows where Mineral and Country are real text and Production is numeric
     are kept as mining rows. The summary block is loaded into its own table so
     the workbook's own figures can be compared against the recomputed ones.
  2. WORLD TOTAL and the Other bucket are kept but tagged in row_type, because
     the world total is the denominator the workbook itself uses for shares.
     Rankings filter on row_type = 'country'.
  3. INDIA TOTAL and India (Total) rows are tagged so state rankings can exclude
     them while the audited national total stays available.
  4. Percentage columns are stored on a 0-100 scale. The workbook stores them as
     fractions formatted as percent, so each is multiplied by 100 on load.
  5. The manganese refining cell holds text, not a number. It is kept verbatim in
     a text column and the numeric column is left NULL. Nothing is invented.

Usage: python load_data.py [path_to_xlsx]
"""

import os
import sqlite3
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_XLSX = os.path.join(HERE, "Critical_Minerals_NiCoMn_Dataset.xlsx")
DB_PATH = os.path.join(HERE, "critical_minerals.db")

HEADER_ROW = 3  # title, source, blank, header
MINERALS = ("Nickel", "Cobalt", "Manganese")


def _sheet(xlsx, name):
    df = pd.read_excel(xlsx, sheet_name=name, header=HEADER_ROW)
    df = df.dropna(how="all")
    return df


def _num(series):
    return pd.to_numeric(series, errors="coerce")


def load_mn_resources(xlsx):
    df = _sheet(xlsx, "India_Mn_Resources_by_State")
    df.columns = [
        "state",
        "reserves_kt",
        "remaining_resources_kt",
        "total_resources_kt",
        "share_of_india_total_pct",
    ]
    df = df[df["state"].notna()].copy()
    df["state"] = df["state"].astype(str).str.strip()
    for c in ["reserves_kt", "remaining_resources_kt", "total_resources_kt"]:
        df[c] = _num(df[c])
    # workbook stores the share as a fraction, so rescale to 0-100
    df["share_of_india_total_pct"] = _num(df["share_of_india_total_pct"]) * 100
    df["row_type"] = df["state"].apply(
        lambda s: "national_total" if s.upper() == "INDIA TOTAL" else "state"
    )
    df["total_resources_t"] = df["total_resources_kt"] * 1000
    return df[df["total_resources_kt"].notna()].reset_index(drop=True)


def load_mn_production(xlsx):
    df = _sheet(xlsx, "India_Mn_Production_by_State")
    df.columns = [
        "state",
        "qty_2019_20_t",
        "value_2019_20_rs_thousand",
        "qty_2020_21_t",
        "value_2020_21_rs_thousand",
        "qty_2021_22_t",
        "value_2021_22_rs_thousand",
    ]
    df = df[df["state"].notna()].copy()
    df["state"] = df["state"].astype(str).str.strip()
    for c in df.columns:
        if c != "state":
            df[c] = _num(df[c])
    df["row_type"] = df["state"].apply(
        lambda s: "national_total" if s.lower().startswith("india") else "state"
    )
    return df[df["qty_2021_22_t"].notna()].reset_index(drop=True)


def load_nico_resources(xlsx):
    df = _sheet(xlsx, "India_NiCo_Resources")
    df.columns = [
        "mineral_raw",
        "reserve_mt",
        "remaining_resources_mt",
        "total_resources_mt",
        "active_mining_leases",
        "major_states",
    ]
    df["reserve_mt"] = _num(df["reserve_mt"])
    # the trailing GSI note row has no numeric reserve, so it drops out here
    df = df[df["mineral_raw"].notna() & df["reserve_mt"].notna()].copy()
    for c in ["remaining_resources_mt", "total_resources_mt", "active_mining_leases"]:
        df[c] = _num(df[c])
    # "Cobalt (Ore)" becomes "Cobalt" so the table joins to the other sheets
    df["mineral"] = (
        df["mineral_raw"].astype(str).str.replace(r"\s*\(Ore\)", "", regex=True).str.strip()
    )
    cols = [
        "mineral",
        "mineral_raw",
        "reserve_mt",
        "remaining_resources_mt",
        "total_resources_mt",
        "active_mining_leases",
        "major_states",
    ]
    return df[cols].reset_index(drop=True)


def load_nico_imports(xlsx):
    df = _sheet(xlsx, "India_NiCo_Imports")
    df.columns = ["mineral", "year", "import_value_usd", "import_volume_note", "source"]
    df = df[df["mineral"].notna()].copy()
    df["mineral"] = df["mineral"].astype(str).str.strip()
    df["year"] = _num(df["year"]).astype("Int64")
    df["import_value_usd"] = _num(df["import_value_usd"])
    df["currency"] = "USD"
    df["period_basis"] = "calendar_year"
    return df.reset_index(drop=True)


def load_demand(xlsx):
    df = _sheet(xlsx, "India_Demand_Projection")
    df.columns = [
        "mineral",
        "demand_2025_t",
        "demand_2026_t",
        "demand_2027_t",
        "demand_2030_t",
        "cagr_2025_2030_workbook",
    ]
    df = df[df["mineral"].notna()].copy()
    df["mineral"] = df["mineral"].astype(str).str.strip()
    for c in df.columns:
        if c != "mineral":
            df[c] = _num(df[c])
    df["cagr_2025_2030_workbook_pct"] = df["cagr_2025_2030_workbook"] * 100
    return df.reset_index(drop=True)


def load_global_mining(xlsx):
    """Country rows only. The CR3/HHI block below them is handled separately."""
    df = _sheet(xlsx, "Global_Mining_2024")
    df.columns = ["mineral", "country", "production_t", "share_of_world_pct"]
    df["production_t"] = _num(df["production_t"])

    keep = (
        df["mineral"].isin(MINERALS)
        & df["country"].notna()
        # a real country name is text; the summary block puts a number here
        & df["country"].apply(lambda v: isinstance(v, str))
        & df["production_t"].notna()
    )
    df = df[keep].copy()
    df["country"] = df["country"].str.strip()
    df["share_of_world_pct"] = _num(df["share_of_world_pct"]) * 100

    def row_type(country):
        upper = country.upper()
        if upper == "WORLD TOTAL":
            return "world_total"
        if upper == "OTHER":
            return "other_bucket"
        return "country"

    df["row_type"] = df["country"].apply(row_type)
    return df.reset_index(drop=True)


def load_global_mining_workbook_metrics(xlsx):
    """The CR3/HHI block printed at the bottom of Global_Mining_2024."""
    raw = pd.read_excel(xlsx, sheet_name="Global_Mining_2024", header=None)
    marker = raw[raw[0].astype(str).str.startswith("Concentration Metrics")].index
    if len(marker) == 0:
        return pd.DataFrame(
            columns=["mineral", "cr3_pct_workbook", "hhi_workbook", "concentration_read"]
        )
    block = raw.loc[marker[0] + 2 :, [0, 1, 2, 3]].copy()
    block.columns = ["mineral", "cr3_pct_workbook", "hhi_workbook", "concentration_read"]
    block = block[block["mineral"].isin(MINERALS)].copy()
    block["cr3_pct_workbook"] = _num(block["cr3_pct_workbook"]) * 100
    block["hhi_workbook"] = _num(block["hhi_workbook"])
    block["basis"] = "workbook formula, Other bucket counted as if it were one country"
    return block.reset_index(drop=True)


def load_refining(xlsx):
    df = _sheet(xlsx, "Global_Refining_Shares")
    df.columns = ["mineral", "country", "refining_share_raw"]
    df = df[df["mineral"].notna()].copy()
    df["mineral"] = df["mineral"].astype(str).str.strip()
    df["country"] = df["country"].astype(str).str.strip()
    # manganese holds a sentence, not a number, so the numeric column stays NULL
    df["refining_share_pct"] = _num(df["refining_share_raw"])
    df["refining_share_raw"] = df["refining_share_raw"].astype(str).str.strip()
    df["is_numeric"] = df["refining_share_pct"].notna()
    return df.reset_index(drop=True)


TABLES = {
    "india_mn_resources_by_state": load_mn_resources,
    "india_mn_production_by_state": load_mn_production,
    "india_nico_resources": load_nico_resources,
    "india_nico_imports": load_nico_imports,
    "india_demand_projection": load_demand,
    "global_mining_2024": load_global_mining,
    "global_mining_concentration_workbook": load_global_mining_workbook_metrics,
    "global_refining_shares": load_refining,
}


def build_database(xlsx_path=DEFAULT_XLSX, db_path=DB_PATH, verbose=True):
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    frames = {}
    for table, loader in TABLES.items():
        frame = loader(xlsx_path)
        frame.to_sql(table, conn, index=False, if_exists="replace")
        frames[table] = frame
    if verbose:
        print_schema(conn)
    conn.commit()
    return conn, frames


def print_schema(conn):
    cur = conn.cursor()
    tables = [
        r[0]
        for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]
    print("=" * 78)
    print("SQLITE SCHEMA: critical_minerals.db")
    print("=" * 78)
    for t in tables:
        n = cur.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
        print("\n" + t + "  (" + str(n) + " rows)")
        for col in cur.execute("PRAGMA table_info(" + t + ")").fetchall():
            print("    " + col[1].ljust(34) + col[2])
    print("\n" + "=" * 78)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XLSX
    conn, _ = build_database(path)
    conn.close()
    print("Database written to " + DB_PATH)
