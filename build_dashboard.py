"""
Build dashboard.html: one self-contained file, no CDN and no external assets.

Every figure is rendered twice, once for the light surface and once for the dark
surface, and CSS shows the right one. Charts carry direct value labels so a
reader never has to decode a colour, and no panel uses two y scales.

Panels
  1  world mine production share by country, per mineral, top 3 highlighted
  2  CR3 against HHI, drawn as two separate charts because they are two scales
  3  Indian state manganese resource distribution
  4  import exposure against the domestic resource base that is not being mined
  5  projected Indian demand 2025 to 2030, one panel per mineral
  6  Strategic Vulnerability Score inputs, marked SCORE NOT COMPUTED

Usage: python build_dashboard.py   (expects critical_minerals.db and outputs/)
"""

import base64
import io
import os
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import analysis

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "critical_minerals.db")
OUT_DIR = os.path.join(HERE, "outputs")
DASHBOARD = os.path.join(HERE, "dashboard.html")

THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "text": "#0b0b0b",
        "muted_text": "#52514e",
        "grid": "#e3e2dd",
        "accent": "#2a78d6",
        "accent2": "#eb6834",
        "rest": "#c2c1ba",
        "other": "#8f8e87",
    },
    "dark": {
        "surface": "#1a1a19",
        "text": "#f0efec",
        "muted_text": "#c3c2b7",
        "grid": "#333331",
        "accent": "#3987e5",
        "accent2": "#d95926",
        "rest": "#55544f",
        "other": "#7a7974",
    },
}

MINERALS = ["Nickel", "Cobalt", "Manganese"]


def style(ax, t, xlabel=None, title=None):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.spines["bottom"].set_linewidth(1.0)
    ax.tick_params(colors=t["muted_text"], labelsize=9, length=0)
    ax.grid(axis="x", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel, color=t["muted_text"], fontsize=9)
    if title:
        ax.set_title(title, color=t["text"], fontsize=11, fontweight="bold", loc="left", pad=8)


def to_b64(fig, t):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, facecolor=t["surface"], bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# --------------------------------------------------------------------- panel 1
def panel_production_share(mining, mode):
    t = THEMES[mode]
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.4), facecolor=t["surface"])
    for ax, mineral in zip(axes, MINERALS):
        block = mining[mining["mineral"] == mineral]
        world = float(block.loc[block["row_type"] == "world_total", "production_t"].iloc[0])
        named = block[block["row_type"] == "country"].copy()
        named["share"] = 100.0 * named["production_t"] / world
        named = named.sort_values("share", ascending=True)
        other = block[block["row_type"] == "other_bucket"].copy()
        other["share"] = 100.0 * other["production_t"] / world

        labels = list(named["country"]) + ["Other (aggregate)"]
        shares = list(named["share"]) + [float(other["share"].iloc[0])]
        top3 = set(named.sort_values("share", ascending=False)["country"].head(3))
        colors = [t["accent"] if c in top3 else t["rest"] for c in named["country"]]
        colors.append(t["other"])

        ypos = range(len(labels))
        bars = ax.barh(list(ypos), shares, height=0.68, color=colors,
                       edgecolor=t["surface"], linewidth=2)
        bars[-1].set_hatch("//")
        ax.set_yticks(list(ypos))
        ax.set_yticklabels(labels, color=t["text"], fontsize=9)
        span = max(shares)
        for y, v in zip(ypos, shares):
            ax.text(v + span * 0.02, y, f"{v:.2f}%", va="center",
                    color=t["text"], fontsize=8.5)
        ax.set_xlim(0, span * 1.22)
        style(ax, t, xlabel="share of world mine production, percent", title=mineral)
    fig.suptitle(
        "World mine production 2024, share by country. Top 3 named countries highlighted.",
        color=t["text"], fontsize=12.5, fontweight="bold", x=0.005, ha="left", y=1.045,
    )
    fig.text(0.005, -0.045,
             "Other is a bucket of many unnamed producers, not a country. It is drawn "
             "hatched and is excluded from CR3 and HHI.",
             color=t["muted_text"], fontsize=9, ha="left")
    fig.tight_layout()
    return to_b64(fig, t)


# --------------------------------------------------------------------- panel 2
def panel_cr3_hhi(conc, mode):
    t = THEMES[mode]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.0), facecolor=t["surface"])
    order = conc.sort_values("hhi_named_lower_bound", ascending=True)

    ax = axes[0]
    ax.barh(order["mineral"], order["cr3_named_pct"], height=0.6,
            color=t["accent"], edgecolor=t["surface"], linewidth=2)
    for y, v in enumerate(order["cr3_named_pct"]):
        ax.text(v + 1.6, y, f"{v:.2f}%", va="center", color=t["text"], fontsize=9)
    ax.set_xlim(0, 108)
    style(ax, t, xlabel="CR3, combined share of world output held by top 3 named countries, percent",
          title="CR3 by mineral")

    ax = axes[1]
    ax.barh(order["mineral"], order["hhi_named_lower_bound"], height=0.6,
            color=t["accent2"], edgecolor=t["surface"], linewidth=2)
    for y, v in enumerate(order["hhi_named_lower_bound"]):
        ax.text(v + 90, y, f"{v:,.0f}", va="center", color=t["text"], fontsize=9)
    ax.axvline(2500, color=t["muted_text"], linewidth=1.2, linestyle=(0, (4, 3)))
    ax.text(2560, 2.46, "2,500 highly concentrated threshold",
            color=t["muted_text"], fontsize=8.5, va="center")
    ax.set_xlim(0, max(order["hhi_named_lower_bound"]) * 1.26)
    style(ax, t, xlabel="HHI, sum of squared percent shares, 0 to 10,000 scale",
          title="HHI lower bound by mineral")

    fig.suptitle("Mining stage concentration, named countries only",
                 color=t["text"], fontsize=12.5, fontweight="bold", x=0.005, ha="left", y=1.05)
    fig.text(0.005, -0.06,
             "Two measures on two scales are drawn as two charts, never on one pair of axes. "
             "HHI is a lower bound because the Other bucket contributes no term.",
             color=t["muted_text"], fontsize=9, ha="left")
    fig.tight_layout()
    return to_b64(fig, t)


# --------------------------------------------------------------------- panel 3
def panel_states(states, mode):
    t = THEMES[mode]
    fig, ax = plt.subplots(figsize=(11.5, 5.0), facecolor=t["surface"])
    d = states.sort_values("total_resources_mt", ascending=True)
    top2 = set(states.sort_values("total_resources_mt", ascending=False)["state"].head(2))
    colors = [t["accent"] if s in top2 else t["rest"] for s in d["state"]]
    ax.barh(d["state"], d["total_resources_mt"], height=0.66,
            color=colors, edgecolor=t["surface"], linewidth=2)
    for y, (v, share) in enumerate(zip(d["total_resources_mt"], d["share_of_india_pct"])):
        ax.text(v + 3.2, y, f"{v:,.1f} Mt   {share:.2f}%", va="center",
                color=t["text"], fontsize=9)
    ax.set_xlim(0, d["total_resources_mt"].max() * 1.38)
    ax.tick_params(axis="y", labelcolor=t["text"], labelsize=9.5)
    style(ax, t, xlabel="total manganese ore resources, million tonnes",
          title="India manganese resources by state, 11 states, 503.624 Mt national total")
    fig.text(0.005, -0.04,
             "IBM National Mineral Inventory as on 01.04.2020. The INDIA TOTAL row is "
             "excluded from the ranking. Odisha and Karnataka together hold 58.67 percent.",
             color=t["muted_text"], fontsize=9, ha="left")
    fig.tight_layout()
    return to_b64(fig, t)


# ------------------------------------------------------------------- panel 3b
def panel_import_exposure(imports, nico, mn_total_mt, mn_production_mt, mode):
    """
    Import exposure against the domestic supply gap.

    Left: import value in US dollars, with manganese drawn as an explicit gap
    rather than left out, because an absent bar reads as a zero.
    Right: the domestic resource base, with each bar annotated by what that base
    actually supplies. Nickel and cobalt supply nothing at all.
    """
    t = THEMES[mode]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.0), facecolor=t["surface"])

    ax = axes[0]
    ni = imports[imports["mineral"] == "Nickel"].iloc[0]
    co = imports[imports["mineral"] == "Cobalt"].iloc[0]
    labels = ["Manganese", "Cobalt", "Nickel"]
    values = [0.0, float(co["import_value_usd"]), float(ni["import_value_usd"])]
    colors = [t["other"], t["accent2"], t["accent"]]
    bars = ax.barh(labels, values, height=0.6, color=colors,
                   edgecolor=t["surface"], linewidth=2)
    bars[0].set_hatch("//")
    # an absent bar is indistinguishable from a zero, so the gap row gets an
    # open marker at the baseline to say no value was recorded
    ax.plot([1.2e7], [0], marker="s", markersize=9, markerfacecolor="none",
            markeredgecolor=t["other"], markeredgewidth=1.6, linestyle="none")
    notes = [
        "no import table in the workbook",
        "US$45M  CY" + str(int(co["year"])),
        "US$1.26B  CY" + str(int(ni["year"])),
    ]
    for y, (v, note) in enumerate(zip(values, notes)):
        ax.text(max(v, 0) + 3.4e7, y, note, va="center", color=t["text"], fontsize=9)
    ax.set_xlim(0, 1.72e9)
    ax.set_xticks([0, 4e8, 8e8, 1.2e9])
    ax.set_xticklabels(["0", "400M", "800M", "1.2B"])
    style(ax, t, xlabel="import value, US dollars",
          title="Import value by mineral")

    ax = axes[1]
    ni_r = nico[nico["mineral"] == "Nickel"].iloc[0]
    co_r = nico[nico["mineral"] == "Cobalt"].iloc[0]
    rlabels = ["Cobalt", "Nickel", "Manganese"]
    rvalues = [
        float(co_r["total_resources_mt"]),
        float(ni_r["total_resources_mt"]),
        float(mn_total_mt),
    ]
    rcolors = [t["accent2"], t["accent"], t["rest"]]
    ax.barh(rlabels, rvalues, height=0.6, color=rcolors,
            edgecolor=t["surface"], linewidth=2)
    rnotes = [
        f"{rvalues[0]:,.0f} Mt   0 leases, 0 t mined",
        f"{rvalues[1]:,.0f} Mt   0 leases, 0 t mined",
        f"{rvalues[2]:,.1f} Mt   " + f"{mn_production_mt:,.3f}" + " Mt mined FY2021-22",
    ]
    for y, (v, note) in enumerate(zip(rvalues, rnotes)):
        ax.text(v + 12, y, note, va="center", color=t["text"], fontsize=9)
    ax.set_xlim(0, 940)
    style(ax, t, xlabel="total resources, million tonnes of ore",
          title="Resource base against what it actually supplies")

    fig.suptitle("Import exposure and the domestic supply gap",
                 color=t["text"], fontsize=12.5, fontweight="bold", x=0.005, ha="left", y=1.05)
    fig.text(0.005, -0.06,
             "India holds 189 Mt of nickel and 45 Mt of cobalt ore resources and mines "
             "neither, so the 100 percent import dependence is structural. It is a proxy "
             "from zero active leases, not a customs volume calculation. Manganese import "
             "value is absent from the source and is shown as a gap, not a zero.",
             color=t["muted_text"], fontsize=9, ha="left")
    fig.tight_layout()
    return to_b64(fig, t)


# --------------------------------------------------------------------- panel 4
def panel_demand(demand, mode):
    t = THEMES[mode]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.0), facecolor=t["surface"])
    years = [2025, 2026, 2027, 2030]
    cols = ["demand_2025_t", "demand_2026_t", "demand_2027_t", "demand_2030_t"]
    for ax, (mineral, colour) in zip(axes, [("Nickel", t["accent"]), ("Cobalt", t["accent2"])]):
        row = demand[demand["mineral"] == mineral].iloc[0]
        values = [float(row[c]) for c in cols]
        ax.plot(years, values, color=colour, linewidth=2, marker="o",
                markersize=8, markerfacecolor=colour, markeredgecolor=t["surface"],
                markeredgewidth=2)
        for x, v in zip(years, values):
            ax.annotate(f"{v:,.0f} t", (x, v), textcoords="offset points",
                        xytext=(0, 11), ha="center", color=t["text"], fontsize=9)
        ax.set_ylim(0, max(values) * 1.3)
        ax.set_xticks(years)
        ax.set_xticklabels([str(y) for y in years], color=t["muted_text"])
        style(ax, t, xlabel="projection year",
              title=mineral + "   CAGR " + f"{row['cagr_2025_2030_pct']:.2f}" + "% a year")
        ax.grid(axis="y", color=t["grid"], linewidth=0.8)
        ax.grid(axis="x", visible=False)
    fig.suptitle("India projected annual requirement, tonnes a year",
                 color=t["text"], fontsize=12.5, fontweight="bold", x=0.005, ha="left", y=1.05)
    fig.text(0.005, -0.06,
             "Each mineral has its own panel because the two volumes differ by orders of "
             "magnitude. 2028 and 2029 are not in the workbook, so the line steps from 2027 "
             "to 2030. No manganese projection exists in the source.",
             color=t["muted_text"], fontsize=9, ha="left")
    fig.tight_layout()
    return to_b64(fig, t)


# --------------------------------------------------------------------- panel 5
def vulnerability_table_html(vuln):
    def cell(value, quality):
        if value is None or pd.isna(value):
            return '<span class="gap">no data</span>'
        badge = '<span class="q q-' + quality + '">' + quality.replace("_", " ") + "</span>"
        return f"{value:,.2f}" + badge

    rows = []
    for _, r in vuln.iterrows():
        rows.append(
            "<tr>"
            + "<th scope=row>" + r["mineral"] + "</th>"
            + "<td>" + cell(r["input_import_dependence_pct"], r["quality_import_dependence"]) + "</td>"
            + "<td>" + cell(r["input_mining_hhi_scaled_0_100"], r["quality_mining_hhi"]) + "</td>"
            + "<td>" + cell(r["input_refining_leader_pct"], r["quality_refining_leader"]) + "</td>"
            + '<td class="nc">not computed</td>'
            + '<td class="reason">' + r["score_blocked_reason"] + "</td>"
            + "</tr>"
        )
    return (
        "<table>"
        "<caption>Strategic Vulnerability Score inputs. "
        "Score = 0.40 x import dependence + 0.35 x (mining HHI / 100) + 0.25 x refining leader share. "
        "All inputs sit on a 0 to 100 scale before weighting.</caption>"
        "<thead><tr>"
        "<th scope=col>Mineral</th>"
        "<th scope=col>Import dependence, 40%</th>"
        "<th scope=col>Mining HHI / 100, 35%</th>"
        "<th scope=col>Refining leader share, 25%</th>"
        "<th scope=col>Score</th>"
        "<th scope=col>Why</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


# --------------------------------------------------------------------------
def build():
    conn = sqlite3.connect(DB_PATH)
    mining = pd.read_sql_query("SELECT * FROM global_mining_2024", conn)
    conc = analysis.concentration_metrics(conn)
    demand = analysis.demand_cagr(conn)
    vuln = analysis.vulnerability_inputs(conn, conc)
    imports = pd.read_sql_query("SELECT * FROM india_nico_imports", conn)
    nico = pd.read_sql_query("SELECT * FROM india_nico_resources", conn)
    mn_total_mt = float(
        pd.read_sql_query(
            "SELECT total_resources_kt / 1000.0 AS mt FROM india_mn_resources_by_state "
            "WHERE row_type = 'national_total'",
            conn,
        )["mt"].iloc[0]
    )
    mn_production_mt = float(
        pd.read_sql_query(
            "SELECT qty_2021_22_t / 1000000.0 AS mt FROM india_mn_production_by_state "
            "WHERE row_type = 'national_total'",
            conn,
        )["mt"].iloc[0]
    )
    states = pd.read_csv(os.path.join(OUT_DIR, "03_state_mn_resource_rank.csv"))
    conn.close()

    figs = {}
    for mode in ("light", "dark"):
        figs[mode] = {
            "production": panel_production_share(mining, mode),
            "cr3hhi": panel_cr3_hhi(conc, mode),
            "states": panel_states(states, mode),
            "imports": panel_import_exposure(
                imports, nico, mn_total_mt, mn_production_mt, mode
            ),
            "demand": panel_demand(demand, mode),
        }

    def img(key, alt):
        return (
            '<img class="light-only" alt="' + alt + '" src="data:image/png;base64,'
            + figs["light"][key] + '">'
            '<img class="dark-only" alt="' + alt + '" src="data:image/png;base64,'
            + figs["dark"][key] + '">'
        )

    html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Critical Minerals Supply-Chain Risk Analytics: India's Ni-Co-Mn Exposure</title>
<style>
  :root { color-scheme: light dark;
    --surface:#fcfcfb; --panel:#ffffff; --text:#0b0b0b; --muted:#52514e;
    --line:#e3e2dd; --accent:#2a78d6; --warn:#eb6834; }
  @media (prefers-color-scheme: dark) { :root {
    --surface:#1a1a19; --panel:#201f1e; --text:#f0efec; --muted:#c3c2b7;
    --line:#333331; --accent:#3987e5; --warn:#d95926; } }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--surface); color:var(--text);
    font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  .wrap { max-width:1180px; margin:0 auto; padding:34px 22px 70px; }
  header { border-bottom:1px solid var(--line); padding-bottom:20px; margin-bottom:26px; }
  h1 { font-size:26px; margin:0 0 8px; letter-spacing:-0.01em; }
  .sub { color:var(--muted); font-size:14px; max-width:860px; }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(192px,1fr));
    gap:12px; margin:26px 0 8px; }
  .kpi { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:15px 16px; }
  .kpi .label { color:var(--muted); font-size:12px; text-transform:uppercase;
    letter-spacing:0.05em; }
  .kpi .value { font-size:25px; font-weight:650; margin-top:5px; letter-spacing:-0.02em; }
  .kpi .foot { color:var(--muted); font-size:12px; margin-top:4px; }
  section { background:var(--panel); border:1px solid var(--line); border-radius:12px;
    padding:22px 22px 26px; margin-top:22px; }
  section h2 { font-size:17px; margin:0 0 4px; }
  section .note { color:var(--muted); font-size:13px; margin:0 0 16px; }
  img { width:100%; height:auto; display:block; }
  .dark-only { display:none; }
  @media (prefers-color-scheme: dark) {
    .light-only { display:none; } .dark-only { display:block; } }
  table { width:100%; border-collapse:collapse; font-size:13.5px; }
  caption { text-align:left; color:var(--muted); font-size:13px; padding-bottom:12px; }
  th,td { text-align:left; padding:10px 12px; border-bottom:1px solid var(--line);
    vertical-align:top; }
  thead th { color:var(--muted); font-weight:600; font-size:12px;
    text-transform:uppercase; letter-spacing:0.04em; }
  tbody th { font-weight:600; }
  .q { display:inline-block; margin-left:8px; font-size:10.5px; padding:2px 7px;
    border-radius:20px; border:1px solid var(--line); color:var(--muted);
    text-transform:uppercase; letter-spacing:0.04em; }
  .gap { color:var(--warn); font-weight:600; }
  .nc { color:var(--warn); font-weight:650; }
  .reason { color:var(--muted); font-size:12.5px; max-width:300px; }
  .flag { border-left:3px solid var(--warn); background:var(--surface);
    padding:13px 16px; border-radius:0 8px 8px 0; margin-top:16px;
    color:var(--muted); font-size:13px; }
  footer { color:var(--muted); font-size:12.5px; margin-top:30px;
    border-top:1px solid var(--line); padding-top:16px; }
</style></head><body><div class="wrap">
<header>
  <h1>Critical Minerals Supply-Chain Risk Analytics</h1>
  <div class="sub">India's nickel, cobalt and manganese exposure. Mining concentration,
  state level resource distribution, import dependence and projected demand, built from
  one sourced workbook. Every figure on this page traces to a workbook cell or to
  arithmetic on workbook cells. Gaps are shown as gaps.</div>
</header>
<div class="kpis">
  __KPIS__
</div>
<section>
  <h2>Production share by country, per mineral</h2>
  <p class="note">Top three named countries highlighted. The Other bucket is drawn
  hatched because it aggregates many unnamed producers and is not a country.</p>
  __PRODUCTION__
</section>
<section>
  <h2>CR3 against HHI</h2>
  <p class="note">Two measures, two scales, two charts. Cobalt is the most
  concentrated mineral at both the top-3 level and across the whole distribution.</p>
  __CR3HHI__
</section>
<section>
  <h2>Indian state manganese resource distribution</h2>
  <p class="note">Eleven states. The national total row is excluded from the ranking
  and used only as a reconciliation check.</p>
  __STATES__
</section>
<section>
  <h2>Import exposure</h2>
  <p class="note">Import value against the domestic resource base that is not being
  mined. Manganese is drawn as a gap rather than omitted, because a missing bar
  reads as a zero.</p>
  __IMPORTS__
</section>
<section>
  <h2>Projected Indian demand 2025 to 2030</h2>
  <p class="note">Nickel and cobalt only. The workbook carries no manganese demand
  projection, so none is shown.</p>
  __DEMAND__
</section>
<section>
  <h2>Strategic Vulnerability Score inputs</h2>
  <p class="note">The framework is designed and its inputs are published. The score
  itself is deliberately left uncomputed.</p>
  __VULN__
  <div class="flag"><strong>Score not computed.</strong> The gate is that all three
  inputs must exist and be complete for a mineral. No mineral clears it. Nickel and
  cobalt carry a proxy import dependence and a partial refining share, and manganese
  is missing both an import table and a refining figure. A weighted number built on
  those inputs would read as a measurement when it is an assumption.</div>
</section>
<footer>
  Sources, as cited inside the workbook: IBM National Mineral Inventory and Indian
  Minerals Yearbook (manganese resources and production); Ministry of Mines reply in
  Rajya Sabha, PIB Delhi 05-Aug-2024 (nickel and cobalt resources, demand projection);
  UN COMTRADE via Trading Economics (nickel imports, CY2024); IndexBox (cobalt imports,
  CY2023); USGS Mineral Commodity Summaries 2025 (mine production); USGS Global Maps of
  Critical Mineral Production 2023 (refining shares, partial coverage).
  Import values are US dollars. Resource position is as on 01.04.2020.
</footer>
</div></body></html>"""

    ni = conc[conc["mineral"] == "Nickel"].iloc[0]
    co = conc[conc["mineral"] == "Cobalt"].iloc[0]
    mn = conc[conc["mineral"] == "Manganese"].iloc[0]
    co_cagr = demand[demand["mineral"] == "Cobalt"].iloc[0]["cagr_2025_2030_pct"]
    ni_cagr = demand[demand["mineral"] == "Nickel"].iloc[0]["cagr_2025_2030_pct"]
    states_top2 = states.head(2)["share_of_india_pct"].sum()

    kpis = "".join(
        [
            kpi("Cobalt HHI", f"{co['hhi_named_lower_bound']:,.0f}",
                "lower bound, most concentrated"),
            kpi("Nickel HHI", f"{ni['hhi_named_lower_bound']:,.0f}", "lower bound"),
            kpi("Manganese HHI", f"{mn['hhi_named_lower_bound']:,.0f}", "lower bound"),
            kpi("Ni import dependence", "100%", "proxy, zero active mining leases"),
            kpi("Nickel imports", "US$1.26B", "CY2024"),
            kpi("Cobalt imports", "US$45M", "CY2023"),
            kpi("Cobalt demand CAGR", f"{co_cagr:,.2f}%", "2025 to 2030, 17 t to 3,878 t"),
            kpi("Nickel demand CAGR", f"{ni_cagr:,.2f}%", "2025 to 2030, 2,629 t to 17,492 t"),
            kpi("Odisha + Karnataka", f"{states_top2:,.2f}%", "of 503.624 Mt Mn resources"),
            kpi("Vulnerability score", "not computed", "inputs incomplete for all three"),
        ]
    )

    html = (
        html.replace("__KPIS__", kpis)
        .replace("__PRODUCTION__", img("production", "Production share by country per mineral"))
        .replace("__CR3HHI__", img("cr3hhi", "CR3 and HHI by mineral"))
        .replace("__STATES__", img("states", "Indian state manganese resource distribution"))
        .replace("__IMPORTS__", img("imports", "Import exposure and the domestic supply gap"))
        .replace("__DEMAND__", img("demand", "Projected nickel and cobalt demand 2025 to 2030"))
        .replace("__VULN__", vulnerability_table_html(vuln))
    )
    with open(DASHBOARD, "w", encoding="utf-8") as fh:
        fh.write(html)
    return DASHBOARD


def kpi(label, value, foot):
    return ('<div class="kpi"><div class="label">' + label + '</div><div class="value">'
            + value + '</div><div class="foot">' + foot + "</div></div>")


if __name__ == "__main__":
    print("written: " + build())
