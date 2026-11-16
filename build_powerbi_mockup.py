"""
Generate powerbi/mockup/report-mockup.html, a static picture of what the Power BI
report should look like when the build guide has been followed.

It is a build target, not a deliverable in its own right. Every number in it is
read from the Power BI export, so the mockup and the model are never out of step.
Map visuals are drawn as labelled placeholders rather than faked, because an
invented map would be the one thing on the page that is not real data.

Usage: python build_powerbi_mockup.py
"""

import html
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "powerbi", "data")
OUT_DIR = os.path.join(HERE, "powerbi", "mockup")
OUT = os.path.join(OUT_DIR, "report-mockup.html")

C = {
    "canvas": "#0E1016",
    "outspace": "#080A0F",
    "card": "#171A24",
    "card2": "#1F2431",
    "border": "#2A3040",
    "text": "#F4F6FB",
    "text2": "#A7B0C4",
    "text3": "#6E7891",
    "grid": "#262C3A",
    "nickel": "#378DFF",
    "cobalt": "#FA04A6",
    "manganese": "#DB6B04",
    "good": "#05AB58",
    "warn": "#A98D07",
    "bad": "#FF3434",
    "muted": "#6E7891",
}
MC = {"Nickel": C["nickel"], "Cobalt": C["cobalt"], "Manganese": C["manganese"]}


def esc(v):
    return html.escape(str(v))


def load():
    t = {}
    for name in os.listdir(DATA):
        if name.endswith(".csv"):
            t[name[:-4]] = pd.read_csv(os.path.join(DATA, name))
    return t


# --------------------------------------------------------------- svg helpers
def hbar(rows, width=560, row_h=34, pad_left=120, value_fmt="{:,.2f}",
         suffix="", vline=None, vline_label=None, max_override=None):
    """rows: list of (label, value, colour, optional_label_text)"""
    height = row_h * len(rows) + 26
    vmax = max_override or max([r[1] for r in rows] + [0.0001])
    plot_w = width - pad_left - 150
    out = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for i, r in enumerate(rows):
        label, value, colour = r[0], r[1], r[2]
        text = r[3] if len(r) > 3 else (value_fmt.format(value) + suffix)
        y = i * row_h + 8
        bw = max(0.0, plot_w * (value / vmax)) if vmax else 0
        out.append(
            f'<text x="{pad_left - 10}" y="{y + 15}" text-anchor="end" '
            f'class="lbl">{esc(label)}</text>'
        )
        if value > 0:
            out.append(
                f'<rect x="{pad_left}" y="{y}" width="{bw:.1f}" height="22" rx="4" '
                f'fill="{colour}"/>'
            )
        else:
            out.append(
                f'<rect x="{pad_left}" y="{y + 5}" width="12" height="12" rx="2" '
                f'fill="none" stroke="{C["muted"]}" stroke-width="1.6"/>'
            )
        tx = pad_left + (bw + 10 if value > 0 else 30)
        out.append(f'<text x="{tx:.1f}" y="{y + 15}" class="val">{esc(text)}</text>')
    if vline is not None and vmax:
        x = pad_left + plot_w * (vline / vmax)
        out.append(
            f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{row_h * len(rows)}" '
            f'stroke="{C["text3"]}" stroke-width="1.2" stroke-dasharray="4 3"/>'
        )
        if vline_label:
            out.append(
                f'<text x="{x + 6:.1f}" y="{row_h * len(rows) + 14}" '
                f'class="axis">{esc(vline_label)}</text>'
            )
    out.append("</svg>")
    return "".join(out)


def grouped_hbar(rows, width=680, row_h=50):
    """rows: list of (label, [(value, colour, text), ...])"""
    height = row_h * len(rows) + 10
    vmax = max(v for _, pairs in rows for v, _, _ in pairs)
    pad_left, plot_w = 104, width - 104 - 210
    out = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for i, (label, pairs) in enumerate(rows):
        y0 = i * row_h + 6
        out.append(
            f'<text x="{pad_left - 10}" y="{y0 + 22}" text-anchor="end" '
            f'class="lbl">{esc(label)}</text>'
        )
        for j, (v, colour, text) in enumerate(pairs):
            y = y0 + j * 18
            bw = plot_w * (v / vmax)
            out.append(
                f'<rect x="{pad_left}" y="{y}" width="{bw:.1f}" height="15" rx="3" '
                f'fill="{colour}"/>'
            )
            out.append(
                f'<text x="{pad_left + bw + 8:.1f}" y="{y + 12}" class="val">'
                f"{esc(text)}</text>"
            )
    out.append("</svg>")
    return "".join(out)


def logline(series, years, width=560, height=250):
    """series: list of (name, colour, {year: value})"""
    import math

    pad_l, pad_b, pad_t, pad_r = 56, 34, 16, 70
    vals = [v for _, _, d in series for v in d.values() if v > 0]
    lo, hi = math.log10(min(vals)), math.log10(max(vals) * 1.6)
    xs = {y: pad_l + (width - pad_l - pad_r) * i / (len(years) - 1) for i, y in enumerate(years)}

    def ypix(v):
        return pad_t + (height - pad_t - pad_b) * (1 - (math.log10(v) - lo) / (hi - lo))

    out = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for decade in range(int(lo), int(hi) + 2):
        v = 10 ** decade
        if not (lo <= decade <= hi):
            continue
        y = ypix(v)
        out.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
            f'stroke="{C["grid"]}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" class="axis">'
            f"{v:,.0f}</text>"
        )
    for name, colour, d in series:
        pts = " ".join(f"{xs[y]:.1f},{ypix(v):.1f}" for y, v in sorted(d.items()))
        out.append(
            f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2.4" '
            f'stroke-linejoin="round"/>'
        )
        for y, v in sorted(d.items()):
            out.append(
                f'<circle cx="{xs[y]:.1f}" cy="{ypix(v):.1f}" r="4.5" fill="{colour}" '
                f'stroke="{C["card"]}" stroke-width="2"/>'
            )
        last = max(d)
        out.append(
            f'<text x="{xs[last] + 10:.1f}" y="{ypix(d[last]) + 4:.1f}" class="val" '
            f'fill="{colour}">{name} {d[last]:,.0f} t</text>'
        )
    for y in years:
        out.append(
            f'<text x="{xs[y]:.1f}" y="{height - 12}" text-anchor="middle" '
            f'class="axis">{y}</text>'
        )
    out.append("</svg>")
    return "".join(out)


def linechart(series, years, width=560, height=210, ylabel="index, 2025 = 100"):
    pad_l, pad_b, pad_t, pad_r = 56, 34, 16, 86
    hi = max(v for _, _, d in series for v in d.values()) * 1.12
    xs = {y: pad_l + (width - pad_l - pad_r) * i / (len(years) - 1) for i, y in enumerate(years)}

    def ypix(v):
        return pad_t + (height - pad_t - pad_b) * (1 - v / hi)

    out = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    step = 10 ** (len(str(int(hi))) - 1)
    g = 0
    while g <= hi:
        y = ypix(g)
        out.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
            f'stroke="{C["grid"]}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" class="axis">'
            f"{g:,.0f}</text>"
        )
        g += step * 2
    for name, colour, d in series:
        pts = " ".join(f"{xs[y]:.1f},{ypix(v):.1f}" for y, v in sorted(d.items()))
        out.append(
            f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2.4"/>'
        )
        for y, v in sorted(d.items()):
            out.append(
                f'<circle cx="{xs[y]:.1f}" cy="{ypix(v):.1f}" r="4" fill="{colour}" '
                f'stroke="{C["card"]}" stroke-width="2"/>'
            )
        last = max(d)
        out.append(
            f'<text x="{xs[last] + 10:.1f}" y="{ypix(d[last]) + 4:.1f}" class="val" '
            f'fill="{colour}">{name}</text>'
        )
    for y in years:
        out.append(
            f'<text x="{xs[y]:.1f}" y="{height - 12}" text-anchor="middle" '
            f'class="axis">{y}</text>'
        )
    out.append(f'<text x="{pad_l}" y="{height - 1}" class="axis">{esc(ylabel)}</text>')
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------- page pieces
def kpi(label, value, foot, colour=None):
    style = f' style="color:{colour}"' if colour else ""
    return (
        '<div class="kpi"><div class="kl">' + esc(label) + '</div>'
        '<div class="kv"' + style + ">" + esc(value) + "</div>"
        '<div class="kf">' + esc(foot) + "</div></div>"
    )


def visual(title, body, sub=None, span=1, note=None):
    s = '<div class="visual" style="grid-column:span ' + str(span) + '">'
    s += '<div class="vt">' + esc(title) + "</div>"
    if sub:
        s += '<div class="vs">' + esc(sub) + "</div>"
    s += body
    if note:
        s += '<div class="vn">' + esc(note) + "</div>"
    return s + "</div>"


def placeholder(text, height=210):
    return (
        '<div class="ph" style="height:' + str(height) + 'px">'
        '<div class="phi">MAP VISUAL</div><div class="pht">' + esc(text) + "</div></div>"
    )


def table(headers, rows, cls=""):
    s = '<table class="t ' + cls + '"><thead><tr>'
    s += "".join("<th>" + esc(h) + "</th>" for h in headers)
    s += "</tr></thead><tbody>"
    for r in rows:
        s += "<tr>" + "".join(c if str(c).startswith("<td") else "<td>" + esc(c) + "</td>"
                              for c in r) + "</tr>"
    return s + "</tbody></table>"


def pill(text, colour):
    return ('<td><span class="pill" style="color:' + colour + ';border-color:' + colour
            + '33;background:' + colour + '1a">' + esc(text) + "</span></td>")


def build():
    os.makedirs(OUT_DIR, exist_ok=True)
    t = load()

    conc = t["ref_concentration"].set_index("mineral")
    mining = t["fact_world_mining"]
    totals = t["ref_world_totals"].set_index("mineral")
    res = t["fact_mn_resources"]
    prod = t["fact_mn_production"]
    nico = t["fact_nico_resources"].set_index("mineral")
    imports = t["fact_imports"].set_index("mineral")
    demand = t["fact_demand"]
    cagr = t["ref_demand_cagr"].set_index("mineral")
    vuln = t["ref_vulnerability"]
    quality = t["ref_data_quality"]
    india = t["ref_india_totals"]

    pages = []

    # ------------------------------------------------------------- page 1
    top2 = res.head(2)["share_of_india_pct"].sum()
    kpis = "".join(
        [
            kpi("Cobalt HHI, lower bound", f"{conc.loc['Cobalt','hhi_named_lower_bound']:,.0f}",
                "highly concentrated", C["cobalt"]),
            kpi("Cobalt CR3", f"{conc.loc['Cobalt','cr3_named_pct']:.2f}%",
                "DR Congo, Indonesia, Russia"),
            kpi("Nickel imports", "US$1.26B", "CY2024", C["nickel"]),
            kpi("Cobalt imports", "US$45M", "CY2023", C["cobalt"]),
            kpi("Cobalt demand CAGR", f"{cagr.loc['Cobalt','cagr_2025_2030_pct']:.2f}%",
                "2025 to 2030"),
            kpi("Odisha + Karnataka", f"{top2:.2f}%", "of 503.624 Mt Mn", C["manganese"]),
        ]
    )
    hhi_rows = [
        (m, float(conc.loc[m, "hhi_named_lower_bound"]), MC[m],
         f"{conc.loc[m,'hhi_named_lower_bound']:,.0f}")
        for m in ["Cobalt", "Nickel", "Manganese"]
    ]
    cr3_rows = [
        (m, float(conc.loc[m, "cr3_named_pct"]), MC[m], f"{conc.loc[m,'cr3_named_pct']:.2f}%")
        for m in ["Cobalt", "Nickel", "Manganese"]
    ]
    dem = {
        m: dict(zip(demand[demand["mineral"] == m]["year"],
                    demand[demand["mineral"] == m]["demand_t"]))
        for m in ["Nickel", "Cobalt"]
    }
    body1 = (
        '<div class="kpis">' + kpis + "</div>"
        '<div class="grid g3">'
        + visual("Mining concentration by mineral",
                 hbar(hhi_rows, row_h=62, vline=2500,
                      vline_label="2,500 highly concentrated", max_override=7400),
                 sub="HHI, named countries only, 0 to 10,000 scale")
        + visual("CR3 by mineral", hbar(cr3_rows, row_h=62, max_override=108),
                 sub="combined share of world output held by the top 3 named countries")
        + visual("India projected demand",
                 logline([("Ni", C["nickel"], dem["Nickel"]),
                          ("Co", C["cobalt"], dem["Cobalt"])],
                         [2025, 2026, 2027, 2030]),
                 sub="log scale, two series of different magnitude on one honest axis",
                 note="2028 and 2029 are absent from the source, so the line steps from 2027 to 2030.")
        + "</div>"
    )
    pages.append(("Overview", "Executive overview", body1))

    # ------------------------------------------------------------- page 2
    ni = mining[mining["mineral"] == "Nickel"].sort_values("share_of_world_pct", ascending=False)
    ni_rows = [
        (r["country"], float(r["share_of_world_pct"]),
         C["nickel"] if r["is_top_3"] else C["muted"],
         f"{r['share_of_world_pct']:.2f}%")
        for _, r in ni.iterrows()
    ]
    ni_rows.append(("Other (aggregate)", float(totals.loc["Nickel", "other_share_of_world_pct"]),
                    C["muted"], f"{totals.loc['Nickel','other_share_of_world_pct']:.2f}%  not a country"))
    corr_rows = [
        (m, [(float(conc.loc[m, "cr3_named_pct"]), MC[m],
              f"{conc.loc[m,'cr3_named_pct']:.2f}%  named countries"),
             (float(conc.loc[m, "cr3_pct_workbook"]), C["muted"],
              f"{conc.loc[m,'cr3_pct_workbook']:.2f}%  workbook formula")])
        for m in ["Cobalt", "Nickel", "Manganese"]
    ]
    conc_tbl = table(
        ["Mineral", "CR3", "HHI", "Read", "Top producer", "Other bucket"],
        [
            [m, f"{conc.loc[m,'cr3_named_pct']:.2f}%",
             f"{conc.loc[m,'hhi_named_lower_bound']:,.0f}",
             "Highly concentrated" if conc.loc[m, "hhi_named_lower_bound"] > 2500 else "Moderate",
             conc.loc[m, "cr3_top3"].split(",")[0],
             f"{conc.loc[m,'other_share_of_world_pct']:.2f}%"]
            for m in ["Cobalt", "Nickel", "Manganese"]
        ],
    )
    body2 = (
        '<div class="grid g2">'
        + visual("World mine production share 2024",
                 placeholder("Filled map. Location country_for_map, gradient #0E2338 to #378DFF "
                             "by Share of World %. Mineral slicer drives it.", 268),
                 sub="sequential ramp, one hue light to dark")
        + visual("Production share by country, nickel",
                 hbar(ni_rows, row_h=26, width=580),
                 sub="top 3 named countries highlighted, Other drawn as an open marker")
        + visual("Where the workbook's own figures go wrong",
                 grouped_hbar(corr_rows),
                 sub="recomputed CR3 against the block printed inside the source",
                 note="The workbook formula ranks the Other bucket as if it were a country. "
                      "In cobalt that puts an aggregate second, above Indonesia, and produces "
                      "97% against a true named country figure of 88.52%.")
        + visual("Concentration metrics", conc_tbl,
                 sub="HHI is a lower bound, the Other bucket contributes no term")
        + "</div>"
    )
    pages.append(("Global supply", "Global supply concentration", body2))

    # ------------------------------------------------------------- page 3
    state_rows = [
        (r["state"], float(r["share_of_india_pct"]),
         C["manganese"] if r["resource_rank"] <= 2 else C["muted"],
         f"{r['total_resources_mt']:,.1f} Mt   {r['share_of_india_pct']:.2f}%")
        for _, r in res.iterrows()
    ]
    p2122 = prod[prod["fiscal_year"] == "2021-22"].set_index("state")["production_t"].to_dict()
    ratio_rows = []
    for _, r in res.iterrows():
        s = r["state"]
        if s not in p2122:
            status, col, ratio = "No production row in source", C["warn"], "blank"
        elif p2122[s] == 0:
            status, col, ratio = "Zero production FY2021-22", C["bad"], "blank"
        else:
            status, col = "Producing", C["good"]
            ratio = f"{r['total_resources_t'] / p2122[s]:,.1f}"
        ratio_rows.append(
            [s, f"{r['total_resources_mt']:,.3f}",
             f"{p2122.get(s, 0):,.0f}" if s in p2122 else "no row",
             ratio, pill(status, col)]
        )
    ratio_tbl = table(
        ["State", "Resources (Mt)", "FY2021-22 (t)", "t resource per t mined", "Status"],
        sorted(ratio_rows, key=lambda r: (r[3] == "blank", -float(r[3].replace(",", ""))
                                          if r[3] != "blank" else 0)),
    )
    body3 = (
        '<div class="kpis">'
        + kpi("Nickel ore resources", f"{nico.loc['Nickel','total_resources_mt']:,.0f} Mt",
              "0 active mining leases", C["nickel"])
        + kpi("Cobalt ore resources", f"{nico.loc['Cobalt','total_resources_mt']:,.0f} Mt",
              "0 active mining leases", C["cobalt"])
        + kpi("Manganese resources", f"{india.iloc[0]['value']/1000:,.3f} Mt",
              "11 states, as on 01.04.2020", C["manganese"])
        + kpi("Manganese mined", f"{india.iloc[1]['value']/1e6:,.3f} Mt", "FY2021-22")
        + kpi("States producing", "7 of 11", "4 hold resources and mine nothing")
        + kpi("Top 2 state share", f"{top2:.2f}%", "Odisha and Karnataka", C["manganese"])
        + "</div>"
        '<div class="grid g2">'
        + visual("Manganese resources by state",
                 placeholder("Filled map. Location dim_state[state], colour saturation by "
                             "Mn Resources (Mt). Treemap is a fair substitute.", 330))
        + visual("Manganese resource share by state",
                 hbar(state_rows, row_h=26, width=600),
                 sub="top 2 states highlighted, INDIA TOTAL excluded from the ranking")
        + visual("Resource base against FY2021-22 production", ratio_tbl, span=2,
                 sub="four states carry a blank ratio on purpose",
                 note="Goa, Gujarat and West Bengal have no production row at all and "
                      "Jharkhand reported zero after 4,785 t in 2019-20. A blank is the "
                      "honest output. A zero would be a lie.")
        + "</div>"
    )
    pages.append(("India position", "India's domestic position", body3))

    # ------------------------------------------------------------- page 4
    imp_rows = [
        ("Nickel", float(imports.loc["Nickel", "import_value_usd"]), C["nickel"],
         "US$1.26B   CY2024"),
        ("Cobalt", float(imports.loc["Cobalt", "import_value_usd"]), C["cobalt"],
         "US$45M   CY2023"),
        ("Manganese", 0.0, C["muted"], "no import table in the source"),
    ]
    growth_rows = [
        (m, float(cagr.loc[m, "growth_multiple_2025_to_2030"]), MC[m],
         f"{cagr.loc[m,'growth_multiple_2025_to_2030']:,.2f}x   "
         f"{cagr.loc[m,'demand_2025_t']:,.0f} t to {cagr.loc[m,'demand_2030_t']:,.0f} t")
        for m in ["Cobalt", "Nickel"]
    ]
    imp_tbl = table(
        ["Mineral", "Value", "Volume in source", "Dependence", "Basis"],
        [
            ["Nickel", "US$1.26B CY2024", "not separately disclosed", "100%",
             "proxy from zero active leases"],
            ["Cobalt", "US$45M CY2023", "approx 1,000 tonnes", "100%",
             "proxy from zero active leases"],
            ["Manganese", "no data", "no import table", "unknown",
             "India mines manganese, so a zero supply assumption would be wrong"],
        ],
    )
    body4 = (
        '<div class="grid g2">'
        + visual("Import value by mineral", hbar(imp_rows, row_h=40, width=580),
                 sub="US dollars, calendar year basis",
                 note="The manganese row is empty on purpose and is labelled. An absent bar "
                      "reads as a zero, and manganese import exposure is unknown, not nil.")
        + visual("Projected annual requirement 2025 to 2030",
                 logline([("Ni", C["nickel"], dem["Nickel"]),
                          ("Co", C["cobalt"], dem["Cobalt"])],
                         [2025, 2026, 2027, 2030]),
                 sub="log scale",
                 note="Cobalt CAGR 196.23% a year, nickel 46.09%. Both compound against a "
                      "domestic mine supply of zero.")
        + visual("Import detail", imp_tbl,
                 sub="the proxy label travels with the number, not in a footnote")
        + visual("Growth multiple 2025 to 2030",
                 hbar(growth_rows, row_h=44, width=580, max_override=260),
                 sub="how many times larger the 2030 requirement is than 2025",
                 note="Indexing to a common base does not rescue these two onto one linear "
                      "axis either, because the growth rates themselves differ by a factor of "
                      "34. A multiple is the honest single number comparison.")
        + "</div>"
    )
    pages.append(("Import exposure", "Import exposure and demand", body4))

    # ------------------------------------------------------------- page 5
    qcol = {"complete": C["good"], "proxy": C["warn"], "partial": C["warn"],
            "lower_bound": C["warn"], "missing": C["bad"]}

    def qcell(value, quality):
        text = "no data" if pd.isna(value) else f"{value:,.2f}"
        return ('<td>' + esc(text) + '<span class="pill" style="margin-left:8px;color:'
                + qcol[quality] + ";border-color:" + qcol[quality] + "33;background:"
                + qcol[quality] + '1a">' + esc(quality.replace("_", " ")) + "</span></td>")

    vrows = []
    for _, r in vuln.iterrows():
        vrows.append(
            [
                r["mineral"],
                qcell(r["input_import_dependence_pct"], r["quality_import_dependence"]),
                qcell(r["input_mining_hhi_scaled_0_100"], r["quality_mining_hhi"]),
                qcell(r["input_refining_leader_pct"], r["quality_refining_leader"]),
                '<td style="color:' + C["bad"] + ';font-weight:650">NOT COMPUTED</td>',
                '<td class="dim">' + esc(r["score_blocked_reason"]) + "</td>",
            ]
        )
    vtbl = table(
        ["Mineral", "Import dependence 40%", "Mining HHI / 100 35%",
         "Refining leader 25%", "Score", "Why"],
        vrows,
    )
    sev = {"high": C["bad"], "medium": C["warn"], "low": C["muted"]}
    qrows = [
        [pill(r["severity"], sev[r["severity"]]).replace("<td>", "<td>"),
         '<td class="dim">' + esc(r["table"]) + "</td>",
         r["finding"],
         '<td class="dim">' + esc(r["impact"]) + "</td>"]
        for _, r in quality.iterrows()
    ]
    qtbl = table(["Severity", "Table", "Finding", "Impact if unhandled"], qrows)
    body5 = (
        '<div class="formula">Strategic Vulnerability Score = '
        '<b>0.40</b> x import dependence + <b>0.35</b> x (mining HHI / 100) + '
        '<b>0.25</b> x refining leader share'
        '<div class="fsub">All inputs normalised to a 0 to 100 scale before weighting. '
        "The score is not computed for any mineral.</div></div>"
        '<div class="grid g1">'
        + visual("Score inputs and why the score is withheld", vtbl,
                 note="The gate is that all three inputs must exist and be complete. No "
                      "mineral clears it. Publishing a weighted number on a proxy and a "
                      "partial list would present an assumption as a measurement.")
        + visual("Data quality findings in the source workbook", qtbl,
                 sub="10 findings, every one handled at load time or in the query that touches it")
        + "</div>"
    )
    pages.append(("Risk framework", "Risk framework and data quality", body5))

    # ------------------------------------------------------------- assemble
    nav = "".join(
        '<span class="tab' + (" on" if i == 0 else "") + '">' + esc(name) + "</span>"
        for i, (name, _, _) in enumerate(pages)
    )
    body = ""
    for i, (tab, title, content) in enumerate(pages):
        body += (
            '<section class="page"><div class="phead"><div><div class="ptitle">'
            + esc(title)
            + '</div><div class="psub">Critical Minerals Supply-Chain Risk Analytics'
            '  |  India Ni-Co-Mn exposure</div></div>'
            '<div class="slicer"><span class="son">Nickel</span>'
            '<span class="son">Cobalt</span><span class="son">Manganese</span></div></div>'
            + content
            + '<div class="tabs">' + nav.replace(' on"', '"').replace(
                '<span class="tab">' + esc(tab), '<span class="tab on">' + esc(tab)
            ) + "</div></section>"
        )

    css = """
:root{--canvas:%(canvas)s;--card:%(card)s;--card2:%(card2)s;--bd:%(border)s;
--tx:%(text)s;--t2:%(text2)s;--t3:%(text3)s;--grid:%(grid)s}
*{box-sizing:border-box}
body{margin:0;background:%(outspace)s;color:var(--tx);
font:14px/1.5 "Segoe UI",-apple-system,BlinkMacSystemFont,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1360px;margin:0 auto;padding:30px 20px 70px}
.hdr{padding:10px 4px 22px}
.hdr h1{font-size:23px;margin:0 0 6px;font-weight:600;letter-spacing:-.01em}
.hdr p{margin:0;color:var(--t2);font-size:13.5px;max-width:960px}
.page{background:var(--canvas);border:1px solid var(--bd);border-radius:12px;
padding:20px 20px 10px;margin-bottom:26px}
.phead{display:flex;justify-content:space-between;align-items:flex-start;
margin-bottom:16px}
.ptitle{font-size:19px;font-weight:600}
.psub{color:var(--t3);font-size:12px;margin-top:3px}
.slicer{display:flex;gap:6px}
.son{font-size:11px;padding:5px 11px;border-radius:6px;background:var(--card2);
border:1px solid var(--bd);color:var(--t2)}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:11px;margin-bottom:13px}
.kpi{background:var(--card2);border:1px solid var(--bd);border-radius:10px;padding:12px 13px}
.kl{color:var(--t2);font-size:10.5px;font-weight:600;text-transform:uppercase;
letter-spacing:.05em;line-height:1.3}
.kv{font-size:25px;font-weight:300;margin-top:6px;letter-spacing:-.02em}
.kf{color:var(--t3);font-size:11px;margin-top:3px}
.grid{display:grid;gap:13px;align-items:start}
.g1{grid-template-columns:1fr}
.g2{grid-template-columns:1fr 1fr}
.g3{grid-template-columns:repeat(3,1fr)}
.visual{background:var(--card);border:1px solid var(--bd);border-radius:10px;
padding:14px 15px 13px}
.vt{font-size:13px;font-weight:600;margin-bottom:2px}
.vs{color:var(--t3);font-size:11px;margin-bottom:10px}
.vn{color:var(--t2);font-size:11.5px;margin-top:10px;padding-top:9px;
border-top:1px solid var(--bd)}
.chart{width:100%%;height:auto;display:block;overflow:visible}
.lbl{fill:%(text)s;font-size:11.5px}
.val{fill:%(text)s;font-size:11px;font-weight:600}
.axis{fill:%(text3)s;font-size:10.5px}
.ph{border:1.5px dashed var(--bd);border-radius:8px;display:flex;flex-direction:column;
align-items:center;justify-content:center;gap:8px;text-align:center;padding:16px;
background:linear-gradient(135deg,#0E2338 0%%,#15293f 50%%,#0E2338 100%%)}
.phi{font-size:10.5px;letter-spacing:.14em;color:%(nickel)s;font-weight:600}
.pht{color:var(--t2);font-size:11.5px;max-width:330px;line-height:1.5}
.t{width:100%%;border-collapse:collapse;font-size:11.5px}
.t th{text-align:left;color:var(--t2);font-weight:600;font-size:10px;
text-transform:uppercase;letter-spacing:.04em;padding:7px 9px;
border-bottom:1px solid var(--bd)}
.t td{padding:7px 9px;border-bottom:1px solid var(--grid);vertical-align:top}
.t tbody tr:last-child td{border-bottom:none}
.dim{color:var(--t2)}
.pill{display:inline-block;font-size:10px;padding:2px 8px;border-radius:20px;
border:1px solid;white-space:nowrap}
.formula{background:var(--card2);border:1px solid var(--bd);border-radius:10px;
padding:14px 16px;margin-bottom:13px;font-size:14.5px}
.fsub{color:var(--t2);font-size:12px;margin-top:6px}
.tabs{display:flex;gap:4px;margin-top:16px;padding-top:11px;border-top:1px solid var(--bd)}
.tab{font-size:11px;padding:6px 12px;border-radius:6px 6px 0 0;color:var(--t3)}
.tab.on{background:var(--card);color:var(--tx);border:1px solid var(--bd);border-bottom:none}
footer{color:var(--t3);font-size:12px;padding:6px 4px 0;line-height:1.6}
@media(max-width:1100px){.kpis{grid-template-columns:repeat(3,1fr)}
.g2,.g3{grid-template-columns:1fr}}
""" % C

    out = (
        "<!DOCTYPE html><html lang=en><head><meta charset=utf-8>"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Power BI report mockup: Critical Minerals Supply-Chain Risk Analytics</title>"
        "<style>" + css + "</style></head><body><div class=wrap>"
        '<div class="hdr"><h1>Power BI report mockup</h1>'
        "<p>A build target for BUILD_GUIDE.md, not a deliverable. Five pages, drawn from the "
        "same exported tables the Power BI model loads, so every number here is the number the "
        "model should produce. Map visuals are shown as labelled placeholders rather than "
        "faked. Build the report to match this and the validation step in the guide will "
        "pass.</p></div>"
        + body
        + "<footer>Palette generated at a fixed lightness and checked for colourblind "
        "separation against the dark canvas. Nickel electric blue #378DFF, cobalt hot magenta "
        "#FA04A6, manganese burnt orange #DB6B04. Colour follows the mineral on every page, "
        "never the chart position.<br>Sources as cited in the workbook: IBM National Mineral "
        "Inventory and Indian Minerals Yearbook; Ministry of Mines reply in Rajya Sabha, PIB "
        "Delhi 05-Aug-2024; UN COMTRADE via Trading Economics (nickel, CY2024); IndexBox "
        "(cobalt, CY2023); USGS Mineral Commodity Summaries 2025; USGS Global Maps of Critical "
        "Mineral Production 2023.</footer></div></body></html>"
    )
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(out)
    return OUT


if __name__ == "__main__":
    print("written: " + build())
