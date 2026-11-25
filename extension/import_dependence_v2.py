"""
Import dependence, India's own supplier concentration, and the Strategic
Vulnerability Score, computed from official DGCIS customs data.

This replaces the lease-based proxy for import dependence wherever a measured
figure is possible, and computes the score the original pipeline left gated.

Inputs (all in this folder)
  dgcis_raw/imports_fy2425_fy2526.json   imports by HS code and country, from
                                         tradestat.commerce.gov.in (EIDB), pulled 2026-11-25
  dgcis_raw/exports_totals_fy2425_fy2526.json   export totals for the same codes
  reference_inputs.csv                   domestic production and refining shares, with sources
  ../outputs/05_cr3_hhi_concentration.csv   mining HHI from the core pipeline (run analysis.py first)

Outputs (outputs_v2/)
  dgcis_imports_tidy.csv          one row per HS code x country x year
  import_dependence_measured.csv  apparent consumption and dependence per mineral
  india_supplier_concentration.csv   HHI and top suppliers of India's own imports
  vulnerability_score.csv         the score, its inputs and their quality
  vulnerability_sensitivity.csv   ranking under +/-10 point weight changes and the HHI upper bound

Usage: python import_dependence_v2.py
"""

import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "dgcis_raw")
OUT = os.path.join(HERE, "outputs_v2")
MINING = os.path.join(HERE, "..", "outputs", "05_cr3_hhi_concentration.csv")   # core pipeline output

YEARS = ["FY2024-25", "FY2025-26"]
MAIN_YEAR = "FY2024-25"          # the year domestic manganese production is known for
WEIGHTS = {"import_dependence": 0.40, "mining_hhi_scaled": 0.35, "refining_leader": 0.25}

# Codes counted as the mineral itself. Manganese alloys (81110010) are kept in the tidy
# file but left out of the ore balance, because domestic production is ore tonnes.
ORE_BALANCE_CODES = {"Manganese": ["26020010", "26020020", "26020030", "26020040", "26020050", "26020060"]}
METAL_CODE = {"Nickel": "75021000", "Cobalt": "81052020"}


def num(s):
    s = (s or "").replace(",", "").strip()
    return float(s) if s else 0.0


def tidy_imports():
    raw = json.load(open(os.path.join(RAW, "imports_fy2425_fy2526.json")))
    rows = []
    for hs, block in raw.items():
        for r in block["rows"]:
            country = r[0]
            for i, year in enumerate(YEARS):
                usd_m, kg = num(r[1 + i]), num(r[4 + i])
                if usd_m == 0 and kg == 0:
                    continue
                rows.append({"mineral": block["mineral"], "hs_code": hs, "commodity": block["commodity"],
                             "country": country, "year": year, "usd_million": usd_m, "tonnes": kg / 1000.0})
    return pd.DataFrame(rows)


def exports_totals():
    raw = json.load(open(os.path.join(RAW, "exports_totals_fy2425_fy2526.json")))["data"]
    rows = []
    for hs, v in raw.items():
        for i, year in enumerate(YEARS):
            rows.append({"hs_code": hs, "year": year, "usd_million": num(v[i]), "tonnes": float(v[2 + i]) / 1000.0})
    return pd.DataFrame(rows)


def hhi(shares_pct):
    return float((shares_pct ** 2).sum())


def supplier_concentration(imp):
    """HHI of India's import sources, by value, per mineral and year."""
    out = []
    for (mineral, year), g in imp.groupby(["mineral", "year"]):
        by_c = g.groupby("country")["usd_million"].sum().sort_values(ascending=False)
        share = 100.0 * by_c / by_c.sum()
        out.append({"mineral": mineral, "year": year, "basis": "import value, all HS codes for the mineral",
                    "supplier_countries": int((by_c > 0).sum()), "import_usd_million": round(by_c.sum(), 2),
                    "top1": by_c.index[0], "top1_share_pct": round(share.iloc[0], 2),
                    "top3": ", ".join(by_c.index[:3]), "cr3_pct": round(share.iloc[:3].sum(), 2),
                    "supplier_hhi": round(hhi(share), 0)})
    return pd.DataFrame(out)


def dependence(imp, exp, ref):
    prod = ref[ref["item"] == "domestic_mine_production"].set_index("mineral")["value"]
    rows = []
    for year in YEARS:
        # manganese: ore balance in tonnes
        codes = ORE_BALANCE_CODES["Manganese"]
        m_imp = imp[(imp.hs_code.isin(codes)) & (imp.year == year)]["tonnes"].sum()
        m_exp = exp[(exp.hs_code.isin(codes)) & (exp.year == year)]["tonnes"].sum()
        p = float(prod["Manganese"]) * 1e6 if year == MAIN_YEAR else None
        if p is not None:
            apparent = p + m_imp - m_exp
            rows.append({"mineral": "Manganese", "year": year, "basis": "manganese ore, gross tonnes (HS 2602)",
                         "domestic_production_t": p, "imports_t": round(m_imp), "exports_t": round(m_exp),
                         "apparent_consumption_t": round(apparent),
                         "import_dependence_pct": round(100.0 * m_imp / apparent, 1), "quality": "measured",
                         "note": "grades differ between imported and Indian ore; gross weight, not Mn content"})
        else:
            rows.append({"mineral": "Manganese", "year": year, "basis": "manganese ore, gross tonnes (HS 2602)",
                         "domestic_production_t": None, "imports_t": round(m_imp), "exports_t": round(m_exp),
                         "apparent_consumption_t": None, "import_dependence_pct": None, "quality": "missing",
                         "note": "FY2025-26 domestic production not collected"})
        # nickel and cobalt: zero domestic mine supply, so dependence on primary supply is 100%
        for mineral, code in METAL_CODE.items():
            i_t = imp[(imp.hs_code == code) & (imp.year == year)]["tonnes"].sum()
            e_t = exp[(exp.hs_code == code) & (exp.year == year)]["tonnes"].sum()
            rows.append({"mineral": mineral, "year": year,
                         "basis": f"{'unwrought nickel' if mineral == 'Nickel' else 'unwrought cobalt'}, tonnes (HS {code})",
                         "domestic_production_t": 0, "imports_t": round(i_t), "exports_t": round(e_t),
                         "apparent_consumption_t": round(i_t - e_t), "import_dependence_pct": 100.0,
                         "quality": "measured volumes; zero domestic mine supply",
                         "note": "100% because domestic mine production is zero; volumes now measured, not assumed"})
    return pd.DataFrame(rows)


def score(dep, ref):
    mining = pd.read_csv(MINING).set_index("mineral")
    lead = ref[ref["item"] == "refining_leader_share"].set_index("mineral")
    rows = []
    for mineral in ["Cobalt", "Nickel", "Manganese"]:
        d = dep[(dep.mineral == mineral) & (dep.year == MAIN_YEAR)]["import_dependence_pct"].iloc[0]
        h_low = float(mining.loc[mineral, "hhi_named_lower_bound"])
        other = float(mining.loc[mineral, "other_share_of_world_pct"])
        h_high = h_low + other ** 2           # Other counted as one country: the most HHI can be
        r = float(lead.loc[mineral, "value"])
        s = WEIGHTS["import_dependence"] * d + WEIGHTS["mining_hhi_scaled"] * h_low / 100 + WEIGHTS["refining_leader"] * r
        s_high = WEIGHTS["import_dependence"] * d + WEIGHTS["mining_hhi_scaled"] * h_high / 100 + WEIGHTS["refining_leader"] * r
        rows.append({"mineral": mineral, "import_dependence_pct": d, "mining_hhi_lower": h_low,
                     "mining_hhi_upper": round(h_high, 1), "refining_leader_pct": r,
                     "refining_leader": lead.loc[mineral, "unit"],
                     "score": round(s, 1), "score_with_hhi_upper": round(s_high, 1)})
    out = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    out["rank"] = range(1, len(out) + 1)
    return out


def sensitivity(sc):
    """Move each weight up or down 10 points, rescale the other two so weights sum to 1."""
    out = []
    keys = list(WEIGHTS)
    for k in keys:
        for delta in (-0.10, 0.10):
            w = dict(WEIGHTS)
            w[k] = WEIGHTS[k] + delta
            rest = [x for x in keys if x != k]
            scale = (1 - w[k]) / sum(WEIGHTS[x] for x in rest)
            for x in rest:
                w[x] = WEIGHTS[x] * scale
            s = {r.mineral: w["import_dependence"] * r.import_dependence_pct
                 + w["mining_hhi_scaled"] * r.mining_hhi_lower / 100 + w["refining_leader"] * r.refining_leader_pct
                 for r in sc.itertuples()}
            order = sorted(s, key=s.get, reverse=True)
            out.append({"change": f"{k} {'+' if delta > 0 else '-'}10 pts",
                        "weights": ", ".join(f"{x}={w[x]:.3f}" for x in keys),
                        **{f"score_{m}": round(v, 1) for m, v in s.items()},
                        "ranking": " > ".join(order)})
    return pd.DataFrame(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    ref = pd.read_csv(os.path.join(HERE, "reference_inputs.csv"))
    imp, exp = tidy_imports(), exports_totals()
    imp.to_csv(os.path.join(OUT, "dgcis_imports_tidy.csv"), index=False)
    conc = supplier_concentration(imp)
    conc.to_csv(os.path.join(OUT, "india_supplier_concentration.csv"), index=False)
    dep = dependence(imp, exp, ref)
    dep.to_csv(os.path.join(OUT, "import_dependence_measured.csv"), index=False)
    sc = score(dep, ref)
    sc.to_csv(os.path.join(OUT, "vulnerability_score.csv"), index=False)
    sens = sensitivity(sc)
    sens.to_csv(os.path.join(OUT, "vulnerability_sensitivity.csv"), index=False)
    with pd.option_context("display.width", 220, "display.max_columns", 30, "display.max_colwidth", 60):
        print(dep, conc, sc, sens, sep="\n\n")


if __name__ == "__main__":
    main()
