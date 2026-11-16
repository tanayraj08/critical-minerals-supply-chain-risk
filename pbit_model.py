"""
The data model half of the Power BI template: TMSL schema, M partitions with the
data embedded as literal rows, relationships and DAX measures.

Why the data is embedded rather than linked. A template that points at a file
path only opens on the machine that has that path. Embedding the rows as literal
M tables makes the template open anywhere with no prompts, no gateway and no
broken refresh, and the whole model is about 100 rows. The build guide shows the
two line change that repoints any table at the Excel workbook instead.
"""

import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "powerbi", "data")

MEASURE_TABLE = "_Measures"

# tables loaded into the model, in field list order
TABLE_ORDER = [
    "dim_mineral",
    "dim_country",
    "dim_state",
    "dim_year",
    "fact_world_mining",
    "fact_mn_resources",
    "fact_mn_production",
    "fact_nico_resources",
    "fact_imports",
    "fact_demand",
    "fact_refining",
    "ref_world_totals",
    "ref_india_totals",
    "ref_concentration",
    "ref_demand_cagr",
    "ref_vulnerability",
    "ref_data_quality",
]

RELATIONSHIPS = [
    ("fact_world_mining", "mineral_key", "dim_mineral", "mineral_key"),
    ("fact_nico_resources", "mineral_key", "dim_mineral", "mineral_key"),
    ("fact_imports", "mineral_key", "dim_mineral", "mineral_key"),
    ("fact_demand", "mineral_key", "dim_mineral", "mineral_key"),
    ("fact_refining", "mineral_key", "dim_mineral", "mineral_key"),
    ("ref_world_totals", "mineral_key", "dim_mineral", "mineral_key"),
    ("ref_concentration", "mineral_key", "dim_mineral", "mineral_key"),
    ("ref_vulnerability", "mineral_key", "dim_mineral", "mineral_key"),
    ("ref_demand_cagr", "mineral_key", "dim_mineral", "mineral_key"),
    ("fact_world_mining", "country_key", "dim_country", "country_key"),
    ("fact_refining", "country_key", "dim_country", "country_key"),
    ("fact_mn_resources", "state_key", "dim_state", "state_key"),
    ("fact_mn_production", "state_key", "dim_state", "state_key"),
    ("fact_demand", "year_key", "dim_year", "year_key"),
]

# (name, dax, format string, display folder)
MEASURES = [
    ("Production (t)", "SUM ( fact_world_mining[production_t] )", "#,0", "1 Production"),
    ("World Production (t)", "SUM ( ref_world_totals[world_production_t] )", "#,0", "1 Production"),
    ("Share of World %", "DIVIDE ( [Production (t)], [World Production (t)] )", "0.00%", "1 Production"),
    (
        "Other Bucket Share %",
        "DIVIDE ( SUM ( ref_world_totals[other_bucket_t] ), [World Production (t)] )",
        "0.00%",
        "1 Production",
    ),
    (
        "CR3 %",
        "\n".join(
            [
                "VAR Countries = SUMMARIZE ( fact_world_mining, dim_country[country] )",
                "VAR Top3 = TOPN ( 3, Countries, CALCULATE ( [Production (t)] ), DESC )",
                "VAR Top3Production = SUMX ( Top3, CALCULATE ( [Production (t)] ) )",
                "RETURN DIVIDE ( Top3Production, [World Production (t)] )",
            ]
        ),
        "0.00%",
        "2 Concentration",
    ),
    (
        "HHI (lower bound)",
        "\n".join(
            [
                "VAR World = [World Production (t)]",
                "RETURN",
                "SUMX (",
                "    SUMMARIZE ( fact_world_mining, dim_country[country] ),",
                "    VAR SharePct = DIVIDE ( CALCULATE ( [Production (t)] ), World ) * 100",
                "    RETURN SharePct * SharePct",
                ")",
            ]
        ),
        "#,0",
        "2 Concentration",
    ),
    (
        "HHI Read",
        "\n".join(
            [
                "VAR H = [HHI (lower bound)]",
                "RETURN",
                "SWITCH ( TRUE (),",
                '    H > 2500, "Highly concentrated",',
                '    H > 1500, "Moderately concentrated",',
                '    "Unconcentrated" )',
            ]
        ),
        None,
        "2 Concentration",
    ),
    (
        "Top Producer",
        "\n".join(
            [
                "VAR Countries = SUMMARIZE ( fact_world_mining, dim_country[country] )",
                "RETURN MAXX ( TOPN ( 1, Countries, CALCULATE ( [Production (t)] ), DESC ), dim_country[country] )",
            ]
        ),
        None,
        "2 Concentration",
    ),
    (
        "CR3 Workbook %",
        "DIVIDE ( SUM ( ref_concentration[cr3_pct_workbook] ), 100 )",
        "0.00%",
        "2 Concentration",
    ),
    (
        "CR3 Gap (pp)",
        "[CR3 %] * 100 - SUM ( ref_concentration[cr3_pct_workbook] )",
        "0.00",
        "2 Concentration",
    ),
    (
        "CR3 Check",
        "ROUND ( [CR3 %] * 100, 2 ) - ROUND ( SUM ( ref_concentration[cr3_named_pct] ), 2 )",
        "0.00",
        "9 Validation",
    ),
    (
        "HHI Check",
        "ROUND ( [HHI (lower bound)], 0 ) - ROUND ( SUM ( ref_concentration[hhi_named_lower_bound] ), 0 )",
        "0.00",
        "9 Validation",
    ),
    ("Mn Resources (Mt)", "SUM ( fact_mn_resources[total_resources_mt] )", "#,0.0", "3 India"),
    (
        "Mn Resources Share %",
        "\n".join(
            [
                "DIVIDE (",
                "    SUM ( fact_mn_resources[total_resources_kt] ),",
                "    CALCULATE ( SUM ( fact_mn_resources[total_resources_kt] ), REMOVEFILTERS ( dim_state ) )",
                ")",
            ]
        ),
        "0.00%",
        "3 India",
    ),
    (
        "Top 2 States Share %",
        "\n".join(
            [
                "VAR States = SUMMARIZE ( fact_mn_resources, dim_state[state] )",
                "VAR Top2 = TOPN ( 2, States, CALCULATE ( SUM ( fact_mn_resources[total_resources_kt] ) ), DESC )",
                "VAR Top2Total = SUMX ( Top2, CALCULATE ( SUM ( fact_mn_resources[total_resources_kt] ) ) )",
                "VAR National = CALCULATE ( SUM ( fact_mn_resources[total_resources_kt] ), REMOVEFILTERS ( dim_state ) )",
                "RETURN DIVIDE ( Top2Total, National )",
            ]
        ),
        "0.00%",
        "3 India",
    ),
    ("Mn Production (t)", "SUM ( fact_mn_production[production_t] )", "#,0", "3 India"),
    (
        "Mn Production FY2021-22 (t)",
        'CALCULATE ( SUM ( fact_mn_production[production_t] ), fact_mn_production[fiscal_year] = "2021-22" )',
        "#,0",
        "3 India",
    ),
    (
        "Resource t per t Production",
        "\n".join(
            [
                "VAR Resource = SUM ( fact_mn_resources[total_resources_t] )",
                "VAR Produced = [Mn Production FY2021-22 (t)]",
                "RETURN IF ( Produced > 0, DIVIDE ( Resource, Produced ) )",
            ]
        ),
        "#,0.0",
        "3 India",
    ),
    (
        "Production Status",
        "\n".join(
            [
                "VAR HasRow =",
                "    NOT ISEMPTY ( CALCULATETABLE ( fact_mn_production, fact_mn_production[fiscal_year] = \"2021-22\" ) )",
                "VAR Produced = [Mn Production FY2021-22 (t)]",
                "RETURN",
                "SWITCH ( TRUE (),",
                '    NOT HasRow, "No production row in source",',
                '    Produced = 0, "Zero production FY2021-22",',
                '    "Producing" )',
            ]
        ),
        None,
        "3 India",
    ),
    ("Import Value (US$)", "SUM ( fact_imports[import_value_usd] )", '\\$#,0', "4 Imports"),
    (
        "Import Value Label",
        "\n".join(
            [
                "VAR V = [Import Value (US$)]",
                "VAR Period = SELECTEDVALUE ( fact_imports[period_label] )",
                "RETURN",
                "IF ( ISBLANK ( V ),",
                '    "no data in source",',
                "    IF ( V >= 1000000000,",
                '        "US$" & FORMAT ( V / 1000000000, "0.00" ) & "B  " & Period,',
                '        "US$" & FORMAT ( V / 1000000, "0" ) & "M  " & Period ) )',
            ]
        ),
        None,
        "4 Imports",
    ),
    (
        "Import Dependence %",
        "DIVIDE ( AVERAGE ( fact_imports[import_dependence_pct] ), 100 )",
        "0%",
        "4 Imports",
    ),
    (
        "Domestic Resources (Mt)",
        "SUM ( fact_nico_resources[total_resources_mt] )",
        "#,0",
        "4 Imports",
    ),
    (
        "Active Mining Leases",
        "SUM ( fact_nico_resources[active_mining_leases] )",
        "#,0",
        "4 Imports",
    ),
    ("Demand (t)", "SUM ( fact_demand[demand_t] )", "#,0", "5 Demand"),
    ("Demand 2025 (t)", "CALCULATE ( [Demand (t)], dim_year[year] = 2025 )", "#,0", "5 Demand"),
    ("Demand 2030 (t)", "CALCULATE ( [Demand (t)], dim_year[year] = 2030 )", "#,0", "5 Demand"),
    (
        "Demand CAGR 2025-2030",
        "\n".join(
            [
                "VAR Start = [Demand 2025 (t)]",
                "VAR Finish = [Demand 2030 (t)]",
                "RETURN IF ( Start > 0 && Finish > 0, ( Finish / Start ) ^ ( 1 / 5 ) - 1 )",
            ]
        ),
        "0.00%",
        "5 Demand",
    ),
    (
        "Growth Multiple",
        "DIVIDE ( [Demand 2030 (t)], [Demand 2025 (t)] )",
        "#,0.00",
        "5 Demand",
    ),
    (
        "Weighted Score (blocked)",
        "\n".join(
            [
                "VAR AllComplete =",
                "    CALCULATE (",
                "        COUNTROWS ( ref_vulnerability ),",
                '        ref_vulnerability[quality_import_dependence] = "complete",',
                '        ref_vulnerability[quality_mining_hhi] = "complete",',
                '        ref_vulnerability[quality_refining_leader] = "complete"',
                "    )",
                "RETURN",
                "IF ( AllComplete > 0,",
                "    0.40 * AVERAGE ( ref_vulnerability[input_import_dependence_pct] )",
                "        + 0.35 * AVERAGE ( ref_vulnerability[input_mining_hhi_scaled_0_100] )",
                "        + 0.25 * AVERAGE ( ref_vulnerability[input_refining_leader_pct] ) )",
            ]
        ),
        "0.0",
        "6 Risk framework",
    ),
    (
        "Score Status",
        '\n'.join(
            [
                "IF ( ISBLANK ( [Weighted Score (blocked)] ),",
                '    "NOT COMPUTED",',
                '    FORMAT ( [Weighted Score (blocked)], "0.0" ) )',
            ]
        ),
        None,
        "6 Risk framework",
    ),
    (
        "Inputs Missing",
        "\n".join(
            [
                "COALESCE (",
                "    COUNTROWS (",
                "        FILTER ( ref_vulnerability,",
                '            ref_vulnerability[quality_import_dependence] = "missing"',
                '                || ref_vulnerability[quality_refining_leader] = "missing" )',
                "    ), 0 )",
            ]
        ),
        "#,0",
        "6 Risk framework",
    ),
]

# columns that must not get an implicit SUM on a visual
NO_SUMMARIZE = (
    "_key",
    "_rank",
    "year",
    "sort_order",
    "active_mining_leases",
    "named_countries",
    "finding_key",
)


def m_literal(value):
    """Render one Python value as a Power Query literal."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NA:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float):
        if float(value).is_integer():
            return str(int(value))
        return repr(round(float(value), 10))
    text = str(value).replace('"', '""').replace("\n", " ").replace("\r", " ")
    return '"' + text + '"'


def column_type(series):
    """Map a pandas column onto a TMSL data type and a Power Query type name."""
    s = series.dropna()
    if series.dtype == bool or (len(s) and all(isinstance(v, bool) for v in s)):
        return "boolean", "type logical"
    if pd.api.types.is_integer_dtype(series):
        return "int64", "Int64.Type"
    if pd.api.types.is_float_dtype(series):
        # a float column that holds only whole numbers and blanks is an integer
        # that pandas widened because of the blanks
        if len(s) and all(float(v).is_integer() for v in s):
            return "int64", "Int64.Type"
        return "double", "type number"
    return "string", "type text"


def load_tables():
    tables = {}
    for name in TABLE_ORDER:
        # only a genuinely empty cell is a blank. pandas treats n/a, NA, null
        # and several other strings as missing by default, which would turn the
        # literal text in the gap rows into nulls the source never contained.
        df = pd.read_csv(
            os.path.join(DATA, name + ".csv"), keep_default_na=False, na_values=[""]
        )
        # pandas reads a bool column of True/False strings as object, normalise it
        for col in df.columns:
            vals = set(df[col].dropna().unique())
            if vals and vals <= {True, False, "True", "False"}:
                df[col] = df[col].map({True: True, False: False, "True": True, "False": False})
        tables[name] = df
    return tables


def m_expression(name, df):
    """A readable Power Query expression holding the table's rows as literals."""
    cols = list(df.columns)
    types = {c: column_type(df[c]) for c in cols}
    rows = []
    for _, r in df.iterrows():
        rows.append("        {" + ", ".join(m_literal(r[c]) for c in cols) + "}")
    lines = [
        "let",
        "    // rows embedded so the template opens anywhere with no file path,",
        "    // no gateway and no broken refresh. See BUILD_GUIDE.md to repoint",
        "    // this at Critical_Minerals_PowerBI.xlsx instead.",
        "    Source = Table.FromRows(",
        "    {",
        ",\n".join(rows),
        "    },",
        "    {" + ", ".join('"' + c + '"' for c in cols) + "}",
        "    ),",
        "    Typed = Table.TransformColumnTypes(Source, {",
        ",\n".join(
            '        {"' + c + '", ' + types[c][1] + "}" for c in cols
        ),
        "    })",
        "in",
        "    Typed",
    ]
    return lines


def build_model_schema():
    tables = load_tables()
    tmsl_tables = []

    for name in TABLE_ORDER:
        df = tables[name]
        columns = []
        for col in df.columns:
            dtype, _ = column_type(df[col])
            summarize = "none"
            if dtype in ("int64", "double") and not any(
                k in col.lower() for k in NO_SUMMARIZE
            ):
                summarize = "sum"
            entry = {
                "name": col,
                "dataType": dtype,
                "sourceColumn": col,
                "summarizeBy": summarize,
                "annotations": [
                    {"name": "SummarizationSetBy", "value": "Automatic"}
                ],
            }
            if col == "year" and name == "dim_year":
                entry["isKey"] = False
            columns.append(entry)
        tmsl_tables.append(
            {
                "name": name,
                "columns": columns,
                "partitions": [
                    {
                        "name": name,
                        "mode": "import",
                        "source": {"type": "m", "expression": m_expression(name, df)},
                    }
                ],
                "annotations": [{"name": "PBI_ResultType", "value": "Table"}],
            }
        )

    # a one column hidden table that exists only to hold the measures
    measures = []
    for mname, dax, fmt, folder in MEASURES:
        m = {
            "name": mname,
            "expression": dax.split("\n"),
            "displayFolder": folder,
            "lineageTag": "m-" + mname.lower().replace(" ", "-").replace("%", "pct"),
        }
        if fmt:
            m["formatString"] = fmt
        measures.append(m)

    tmsl_tables.append(
        {
            "name": MEASURE_TABLE,
            "isHidden": False,
            "columns": [
                {
                    "name": "_",
                    "dataType": "int64",
                    "sourceColumn": "_",
                    "summarizeBy": "none",
                    "isHidden": True,
                }
            ],
            "partitions": [
                {
                    "name": MEASURE_TABLE,
                    "mode": "import",
                    "source": {
                        "type": "m",
                        "expression": [
                            "let",
                            "    // a one row placeholder so the measures have a home",
                            '    Source = Table.FromRows({{1}}, {"_"}),',
                            '    Typed = Table.TransformColumnTypes(Source, {{"_", Int64.Type}})',
                            "in",
                            "    Typed",
                        ],
                    },
                }
            ],
            "measures": measures,
        }
    )

    relationships = []
    for i, (ft, fc, tt, tc) in enumerate(RELATIONSHIPS, start=1):
        relationships.append(
            {
                "name": "rel_" + str(i).zfill(2) + "_" + ft + "_" + tt,
                "fromTable": ft,
                "fromColumn": fc,
                "toTable": tt,
                "toColumn": tc,
                "crossFilteringBehavior": "oneDirection",
            }
        )

    return {
        "name": "Critical Minerals Supply-Chain Risk Analytics",
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True,
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": tmsl_tables,
            "relationships": relationships,
            "annotations": [
                {"name": "PBI_QueryOrder", "value": "[]"},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            ],
        },
    }


def diagram_layout():
    """A tidy star layout so Model view is readable on open."""
    nodes = []
    centre = {"dim_mineral": (520, 300)}
    ring = [
        ("fact_world_mining", 120, 60),
        ("fact_nico_resources", 120, 300),
        ("fact_imports", 120, 540),
        ("fact_demand", 920, 60),
        ("fact_refining", 920, 300),
        ("ref_world_totals", 920, 540),
        ("ref_concentration", 520, 60),
        ("ref_vulnerability", 520, 540),
        ("ref_demand_cagr", 320, 680),
        ("dim_country", 120, 780),
        ("dim_state", 520, 780),
        ("dim_year", 920, 780),
        ("fact_mn_resources", 320, 920),
        ("fact_mn_production", 720, 920),
        ("ref_india_totals", 1120, 780),
        ("ref_data_quality", 1120, 60),
        (MEASURE_TABLE, 520, 180),
    ]
    for name, (x, y) in centre.items():
        nodes.append({"location": {"x": x, "y": y}, "nodeIndex": name, "size": {"height": 160, "width": 200}, "zIndex": 0})
    for i, (name, x, y) in enumerate(ring, start=1):
        nodes.append(
            {
                "location": {"x": x, "y": y},
                "nodeIndex": name,
                "size": {"height": 150, "width": 220},
                "zIndex": i,
            }
        )
    return {
        "version": "1.1.0",
        "diagrams": [
            {
                "ordinal": 0,
                "scrollPosition": {"x": 0, "y": 0},
                "nodes": nodes,
                "name": "All tables",
                "zoomValue": 70,
                "pinKeyFieldsToTop": False,
                "showExtraHeaderInfo": False,
                "hideKeyFieldsWhenCollapsed": False,
                "tablesLocked": False,
            }
        ],
        "selectedDiagram": "All tables",
        "defaultDiagram": "All tables",
    }
