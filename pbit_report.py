"""
The report half of the Power BI template: five pages of visuals as Report/Layout
JSON.

Formatting is written explicitly onto every visual rather than left to a theme
reference, so the pages come up in the right colours even if the theme does not
load. The importable theme JSON is still shipped for manual use.
"""

import json

W, H = 1280, 720

CANVAS = "#0E1016"
OUTSPACE = "#080A0F"
CARD = "#171A24"
CARD2 = "#1F2431"
BORDER = "#2A3040"
TEXT = "#F4F6FB"
TEXT2 = "#A7B0C4"
TEXT3 = "#6E7891"
GRID = "#262C3A"
NI = "#378DFF"
CO = "#FA04A6"
MN = "#DB6B04"
BAD = "#FF3434"
MUTED = "#6E7891"
MINERAL_COLOUR = {"Nickel": NI, "Cobalt": CO, "Manganese": MN}

_counter = [0]


def vid(prefix="v"):
    _counter[0] += 1
    return prefix + str(_counter[0]).zfill(3)


def lit(value):
    if isinstance(value, bool):
        v = "true" if value else "false"
    elif isinstance(value, str):
        v = "'" + value.replace("'", "''") + "'"
    elif isinstance(value, int):
        v = str(value) + "L"
    else:
        v = str(float(value)) + "D"
    return {"expr": {"Literal": {"Value": v}}}


def solid(colour):
    return {"solid": {"color": lit(colour)}}


class Query:
    """Builds the prototypeQuery that binds a visual to the model."""

    def __init__(self):
        self.entities = {}
        self.selects = []
        self.order = []

    def _alias(self, entity):
        if entity not in self.entities:
            self.entities[entity] = chr(ord("a") + len(self.entities))
        return self.entities[entity]

    def column(self, entity, prop):
        a = self._alias(entity)
        name = entity + "." + prop
        self.selects.append(
            {
                "Column": {"Expression": {"SourceRef": {"Source": a}}, "Property": prop},
                "Name": name,
                "NativeReferenceName": prop,
            }
        )
        return name

    def measure(self, prop, entity="_Measures"):
        a = self._alias(entity)
        name = entity + "." + prop
        self.selects.append(
            {
                "Measure": {"Expression": {"SourceRef": {"Source": a}}, "Property": prop},
                "Name": name,
                "NativeReferenceName": prop,
            }
        )
        return name

    def order_by_measure(self, prop, descending=True, entity="_Measures"):
        a = self._alias(entity)
        self.order.append(
            {
                "Direction": 2 if descending else 1,
                "Expression": {
                    "Measure": {"Expression": {"SourceRef": {"Source": a}}, "Property": prop}
                },
            }
        )

    def order_by_column(self, entity, prop, descending=True):
        a = self._alias(entity)
        self.order.append(
            {
                "Direction": 2 if descending else 1,
                "Expression": {
                    "Column": {"Expression": {"SourceRef": {"Source": a}}, "Property": prop}
                },
            }
        )

    def build(self):
        q = {
            "Version": 2,
            "From": [
                {"Name": a, "Entity": e, "Type": 0} for e, a in self.entities.items()
            ],
            "Select": self.selects,
        }
        if self.order:
            q["OrderBy"] = self.order
        return q


def mineral_filter(mineral):
    """A visual level filter pinning one mineral."""
    return [
        {
            "name": vid("flt"),
            "expression": {
                "Column": {
                    "Expression": {"SourceRef": {"Entity": "dim_mineral"}},
                    "Property": "mineral",
                }
            },
            "filter": {
                "Version": 2,
                "From": [{"Name": "d", "Entity": "dim_mineral", "Type": 0}],
                "Where": [
                    {
                        "Condition": {
                            "In": {
                                "Expressions": [
                                    {
                                        "Column": {
                                            "Expression": {"SourceRef": {"Source": "d"}},
                                            "Property": "mineral",
                                        }
                                    }
                                ],
                                "Values": [[{"Literal": {"Value": "'" + mineral + "'"}}]],
                            }
                        }
                    }
                ],
            },
            "type": "Categorical",
            "howCreated": 0,
        }
    ]


def vc_objects(title=None, subtitle=None, background=CARD, border=True):
    vc = {
        "background": [
            {"properties": {"show": lit(True), "color": solid(background), "transparency": lit(0.0)}}
        ],
        "dropShadow": [{"properties": {"show": lit(False)}}],
    }
    if border:
        vc["border"] = [
            {"properties": {"show": lit(True), "color": solid(BORDER), "radius": lit(10.0)}}
        ]
    if title:
        vc["title"] = [
            {
                "properties": {
                    "show": lit(True),
                    "text": lit(title),
                    "fontColor": solid(TEXT),
                    "background": solid("#00000000"),
                    "alignment": lit("left"),
                    "fontSize": lit(12.0),
                    "titleWrap": lit(True),
                }
            }
        ]
    else:
        vc["title"] = [{"properties": {"show": lit(False)}}]
    if subtitle:
        vc["subTitle"] = [
            {
                "properties": {
                    "show": lit(True),
                    "text": lit(subtitle),
                    "fontColor": solid(TEXT2),
                    "alignment": lit("left"),
                    "fontSize": lit(9.0),
                }
            }
        ]
    return vc


def container(x, y, w, h, visual_type, query, projections, title=None, subtitle=None,
              objects=None, filters=None, z=None, background=CARD, border=True):
    name = vid()
    z = z if z is not None else _counter[0]
    single = {
        "visualType": visual_type,
        "drillFilterOtherVisuals": True,
        "objects": objects or {},
        "vcObjects": vc_objects(title, subtitle, background, border),
    }
    if query is not None:
        single["prototypeQuery"] = query
    if projections is not None:
        single["projections"] = projections
    config = {
        "name": name,
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z * 1000
                },
            }
        ],
        "singleVisual": single,
    }
    return {
        "x": x, "y": y, "z": z, "width": w, "height": h,
        "config": json.dumps(config, separators=(",", ":")),
        "filters": json.dumps(filters or [], separators=(",", ":")),
    }


# ------------------------------------------------------------------ visuals
def textbox(x, y, w, h, runs, background=None, border=False):
    """runs: list of (text, size_pt, colour, bold)"""
    paragraphs = []
    for group in runs:
        text_runs = []
        for text, size, colour, bold in group:
            style = {"fontSize": str(size) + "pt", "color": colour}
            if bold:
                style["fontWeight"] = "bold"
            text_runs.append({"value": text, "textStyle": style})
        paragraphs.append({"textRuns": text_runs, "horizontalTextAlignment": "left"})
    objects = {"general": [{"properties": {"paragraphs": paragraphs}}]}
    return container(
        x, y, w, h, "textbox", None, None, objects=objects,
        background=background or CANVAS, border=border,
    )


def card(x, y, w, h, measure, title, colour=TEXT, mineral=None, font=28.0):
    q = Query()
    ref = q.measure(measure)
    objects = {
        "labels": [
            {
                "properties": {
                    "color": solid(colour),
                    "fontSize": lit(font),
                    "labelDisplayUnits": lit(0.0),
                }
            }
        ],
        "categoryLabels": [{"properties": {"show": lit(False)}}],
        "wordWrap": [{"properties": {"show": lit(True)}}],
    }
    return container(
        x, y, w, h, "card", q.build(), {"Values": [{"queryRef": ref}]},
        title=title, objects=objects, filters=mineral_filter(mineral) if mineral else None,
        background=CARD2,
    )


def _axis_objects(label_colour=TEXT2, show_value_axis=True, log=False):
    value_axis = {
        "show": lit(show_value_axis),
        "labelColor": solid(label_colour),
        "fontSize": lit(9.0),
        "showAxisTitle": lit(False),
        "gridlineShow": lit(True),
        "gridlineColor": solid(GRID),
        "gridlineThickness": lit(1.0),
    }
    if log:
        value_axis["axisScale"] = lit("Log")
    return {
        "categoryAxis": [
            {
                "properties": {
                    "show": lit(True),
                    "labelColor": solid(TEXT),
                    "fontSize": lit(10.0),
                    "showAxisTitle": lit(False),
                    "gridlineShow": lit(False),
                }
            }
        ],
        "valueAxis": [{"properties": value_axis}],
        "labels": [
            {
                "properties": {
                    "show": lit(True),
                    "color": solid(TEXT),
                    "fontSize": lit(9.0),
                    "labelDisplayUnits": lit(0.0),
                }
            }
        ],
        "legend": [{"properties": {"show": lit(False)}}],
    }


def mineral_datapoints():
    """Per mineral bar colours, so colour follows the entity and not the slot."""
    points = []
    for mineral, colour in MINERAL_COLOUR.items():
        points.append(
            {
                "properties": {"fill": solid(colour)},
                "selector": {
                    "data": [
                        {
                            "scopeId": {
                                "Comparison": {
                                    "ComparisonKind": 0,
                                    "Left": {
                                        "Column": {
                                            "Expression": {
                                                "SourceRef": {"Entity": "dim_mineral"}
                                            },
                                            "Property": "mineral",
                                        }
                                    },
                                    "Right": {"Literal": {"Value": "'" + mineral + "'"}},
                                }
                            }
                        }
                    ]
                },
            }
        )
    return points


def bar_by_mineral(x, y, w, h, measure, title, subtitle=None, constant_line=None):
    q = Query()
    cat = q.column("dim_mineral", "mineral")
    val = q.measure(measure)
    q.order_by_measure(measure)
    objects = _axis_objects()
    objects["dataPoint"] = mineral_datapoints()
    if constant_line is not None:
        objects["y1AxisReferenceLine"] = [
            {
                "properties": {
                    "show": lit(True),
                    "value": lit(float(constant_line)),
                    "lineColor": solid(TEXT2),
                    "style": lit("dashed"),
                    "transparency": lit(20.0),
                },
                "selector": {"id": "ref1"},
            }
        ]
    return container(
        x, y, w, h, "clusteredBarChart", q.build(),
        {"Category": [{"queryRef": cat}], "Y": [{"queryRef": val}]},
        title=title, subtitle=subtitle, objects=objects,
    )


def bar_by_column(x, y, w, h, entity, column, measure, title, subtitle=None,
                  colour=NI, mineral=None, sort_desc=True):
    q = Query()
    cat = q.column(entity, column)
    val = q.measure(measure)
    q.order_by_measure(measure, descending=sort_desc)
    objects = _axis_objects()
    objects["dataPoint"] = [{"properties": {"fill": solid(colour)}}]
    return container(
        x, y, w, h, "clusteredBarChart", q.build(),
        {"Category": [{"queryRef": cat}], "Y": [{"queryRef": val}]},
        title=title, subtitle=subtitle, objects=objects,
        filters=mineral_filter(mineral) if mineral else None,
    )


def bar_two_measures(x, y, w, h, measure_a, measure_b, title, subtitle=None):
    q = Query()
    cat = q.column("dim_mineral", "mineral")
    a = q.measure(measure_a)
    b = q.measure(measure_b)
    objects = _axis_objects()
    objects["legend"] = [
        {
            "properties": {
                "show": lit(True),
                "position": lit("Top"),
                "labelColor": solid(TEXT2),
                "fontSize": lit(9.0),
                "showTitle": lit(False),
            }
        }
    ]
    objects["dataPoint"] = [
        {"properties": {"fill": solid(NI)}, "selector": {"metadata": a}},
        {"properties": {"fill": solid(MUTED)}, "selector": {"metadata": b}},
    ]
    return container(
        x, y, w, h, "clusteredBarChart", q.build(),
        {"Category": [{"queryRef": cat}], "Y": [{"queryRef": a}, {"queryRef": b}]},
        title=title, subtitle=subtitle, objects=objects,
    )


def line_demand(x, y, w, h, title, subtitle=None, log=True):
    q = Query()
    cat = q.column("dim_year", "year")
    series = q.column("dim_mineral", "mineral")
    val = q.measure("Demand (t)")
    q.order_by_column("dim_year", "year", descending=False)
    objects = _axis_objects(log=log)
    objects["legend"] = [
        {
            "properties": {
                "show": lit(True),
                "position": lit("Top"),
                "labelColor": solid(TEXT2),
                "fontSize": lit(9.0),
                "showTitle": lit(False),
            }
        }
    ]
    objects["dataPoint"] = mineral_datapoints()
    objects["lineStyles"] = [
        {"properties": {"strokeWidth": lit(3.0), "showMarker": lit(True), "markerSize": lit(5.0)}}
    ]
    return container(
        x, y, w, h, "lineChart", q.build(),
        {
            "Category": [{"queryRef": cat}],
            "Y": [{"queryRef": val}],
            "Series": [{"queryRef": series}],
        },
        title=title, subtitle=subtitle, objects=objects,
    )


def table_visual(x, y, w, h, fields, title, subtitle=None, filters=None):
    """fields: list of ('column', entity, prop) or ('measure', name)"""
    q = Query()
    refs = []
    for f in fields:
        if f[0] == "column":
            refs.append(q.column(f[1], f[2]))
        else:
            refs.append(q.measure(f[1]))
    objects = {
        "grid": [
            {
                "properties": {
                    "gridVertical": lit(False),
                    "gridHorizontal": lit(True),
                    "gridHorizontalColor": solid(GRID),
                    "outlineColor": solid(BORDER),
                    "outlineWeight": lit(1.0),
                    "rowPadding": lit(4.0),
                    "textSize": lit(9.0),
                }
            }
        ],
        "columnHeaders": [
            {
                "properties": {
                    "fontColor": solid(TEXT2),
                    "backColor": solid(CARD2),
                    "fontSize": lit(9.0),
                    "bold": lit(True),
                    "wordWrap": lit(True),
                }
            }
        ],
        "values": [
            {
                "properties": {
                    "fontColor": solid(TEXT),
                    "backColor": solid(CARD),
                    "fontSize": lit(9.0),
                    "wordWrap": lit(True),
                }
            }
        ],
    }
    return container(
        x, y, w, h, "tableEx", q.build(), {"Values": [{"queryRef": r} for r in refs]},
        title=title, subtitle=subtitle, objects=objects, filters=filters,
    )


def mineral_slicer(x, y, w, h):
    q = Query()
    ref = q.column("dim_mineral", "mineral")
    q.order_by_column("dim_mineral", "sort_order", descending=False)
    objects = {
        "general": [{"properties": {"orientation": lit(2), "outlineWeight": lit(0.0)}}],
        "items": [
            {
                "properties": {
                    "fontColor": solid(TEXT2),
                    "background": solid(CARD2),
                    "fontSize": lit(9.0),
                    "outline": lit("None"),
                }
            }
        ],
        "selection": [
            {"properties": {"selectAllCheckboxEnabled": lit(False), "singleSelect": lit(False)}}
        ],
        "header": [{"properties": {"show": lit(False)}}],
    }
    return container(
        x, y, w, h, "slicer", q.build(), {"Values": [{"queryRef": ref}]},
        objects=objects, background=CARD2,
    )


# -------------------------------------------------------------------- pages
def page_config():
    return json.dumps(
        {
            "objects": {
                "background": [
                    {"properties": {"color": solid(CANVAS), "transparency": lit(0.0)}}
                ],
                "outspace": [
                    {"properties": {"color": solid(OUTSPACE), "transparency": lit(0.0)}}
                ],
                "outspacePane": [
                    {
                        "properties": {
                            "backgroundColor": solid(CARD),
                            "foregroundColor": solid(TEXT),
                            "borderColor": solid(BORDER),
                            "transparency": lit(0.0),
                        }
                    }
                ],
            }
        },
        separators=(",", ":"),
    )


def heading(title, sub):
    return textbox(
        16, 12, 820, 56,
        [
            [(title, 20, TEXT, True)],
            [(sub, 10, TEXT2, False)],
        ],
    )


def note(x, y, w, h, lines, colour=TEXT2):
    return textbox(x, y, w, h, [[(line, 10, colour, False)] for line in lines],
                   background=CARD, border=True)


def build_sections():
    sections = []

    # ------------------------------------------------------------ page 1
    v = [
        heading(
            "Critical Minerals Supply-Chain Risk Analytics",
            "India's nickel, cobalt and manganese exposure. Mining concentration, "
            "domestic resources, import dependence and projected demand.",
        ),
        mineral_slicer(1000, 16, 264, 46),
        card(16, 78, 200, 92, "HHI (lower bound)", "Cobalt HHI, lower bound", CO, "Cobalt"),
        card(224, 78, 200, 92, "CR3 %", "Cobalt CR3", TEXT, "Cobalt"),
        card(432, 78, 200, 92, "Import Value (US$)", "Nickel imports CY2024", NI, "Nickel"),
        card(640, 78, 200, 92, "Import Value (US$)", "Cobalt imports CY2023", CO, "Cobalt"),
        card(848, 78, 200, 92, "Demand CAGR 2025-2030", "Cobalt demand CAGR", TEXT, "Cobalt"),
        card(1056, 78, 208, 92, "Top 2 States Share %", "Odisha + Karnataka, Mn", MN),
        bar_by_mineral(
            16, 182, 410, 250, "HHI (lower bound)",
            "Mining concentration by mineral",
            "HHI, named countries only, 0 to 10,000 scale",
            constant_line=2500,
        ),
        bar_by_mineral(
            436, 182, 410, 250, "CR3 %", "CR3 by mineral",
            "share of world output held by the top 3 named countries",
        ),
        line_demand(
            856, 182, 408, 250, "India projected demand",
            "log scale, tonnes a year",
        ),
        table_visual(
            16, 442, 830, 262,
            [
                ("column", "dim_mineral", "mineral"),
                ("measure", "CR3 %"),
                ("measure", "HHI (lower bound)"),
                ("measure", "HHI Read"),
                ("measure", "Top Producer"),
                ("measure", "Other Bucket Share %"),
            ],
            "Concentration metrics",
            "HHI is a lower bound, the Other bucket contributes no term",
        ),
        note(
            856, 442, 408, 262,
            [
                "HHI is a LOWER BOUND.",
                "",
                "The Other bucket aggregates many unnamed producers and is not a "
                "country, so it is excluded from CR3 and from every HHI term. "
                "Splitting it into its real constituents could only add positive "
                "squared terms.",
                "",
                "Other holds 8.21% of world nickel output, 11.48% of cobalt and "
                "27.00% of manganese.",
                "",
                "2028 and 2029 are absent from the demand source, so the line steps "
                "from 2027 to 2030.",
            ],
        ),
    ]
    sections.append(("Overview", v))

    # ------------------------------------------------------------ page 2
    v = [
        heading(
            "Global supply concentration",
            "World mine production 2024, USGS. Use the slicer to change mineral.",
        ),
        mineral_slicer(1000, 16, 264, 46),
        bar_by_column(
            16, 78, 620, 400, "dim_country", "country", "Share of World %",
            "Production share by country",
            "named countries only, Other and WORLD TOTAL are held in a separate table",
            colour=NI, mineral="Nickel",
        ),
        bar_two_measures(
            656, 78, 608, 210, "CR3 %", "CR3 Workbook %",
            "Where the workbook's own figures go wrong",
            "recomputed CR3 against the block printed inside the source",
        ),
        note(
            656, 296, 608, 182,
            [
                "The source workbook appends its own CR3 and HHI block.",
                "",
                "That formula ranks the Other bucket as if it were a country. In "
                "cobalt it puts an aggregate second, above Indonesia, and produces "
                "a CR3 of 97% against a true named country figure of 88.52%.",
                "",
                "The block is loaded into its own table so its figures can be "
                "audited rather than inherited.",
            ],
        ),
        table_visual(
            16, 488, 1248, 216,
            [
                ("column", "dim_mineral", "mineral"),
                ("measure", "CR3 %"),
                ("measure", "CR3 Workbook %"),
                ("measure", "CR3 Gap (pp)"),
                ("measure", "HHI (lower bound)"),
                ("measure", "Other Bucket Share %"),
                ("measure", "Top Producer"),
            ],
            "Recomputed against the workbook",
        ),
    ]
    sections.append(("Global supply", v))

    # ------------------------------------------------------------ page 3
    v = [
        heading(
            "India's domestic position",
            "Manganese is mined domestically and concentrated in two states. "
            "Nickel and cobalt are not mined at all.",
        ),
        card(16, 78, 304, 92, "Domestic Resources (Mt)", "Nickel ore resources, 0 leases", NI, "Nickel"),
        card(328, 78, 304, 92, "Domestic Resources (Mt)", "Cobalt ore resources, 0 leases", CO, "Cobalt"),
        card(640, 78, 304, 92, "Mn Resources (Mt)", "Manganese resources, 11 states", MN),
        card(952, 78, 312, 92, "Top 2 States Share %", "Odisha + Karnataka share", MN),
        bar_by_column(
            16, 182, 620, 400, "dim_state", "state", "Mn Resources Share %",
            "Manganese resource share by state",
            "INDIA TOTAL is held in a separate table and cannot enter this ranking",
            colour=MN,
        ),
        table_visual(
            656, 182, 608, 400,
            [
                ("column", "dim_state", "state"),
                ("measure", "Mn Resources (Mt)"),
                ("measure", "Mn Production FY2021-22 (t)"),
                ("measure", "Resource t per t Production"),
                ("measure", "Production Status"),
            ],
            "Resource base against FY2021-22 production",
            "four states carry a blank ratio on purpose",
        ),
        note(
            16, 592, 1248, 112,
            [
                "Goa, Gujarat and West Bengal hold manganese resources and have no "
                "production row in the source for any year. Jharkhand is in the "
                "production table and reported 0 t in FY2021-22 after 4,785 t in "
                "2019-20.",
                "",
                "All four return a blank ratio rather than a zero or a divide by "
                "zero error. A blank is the honest output. A zero would be a lie.",
            ],
        ),
    ]
    sections.append(("India position", v))

    # ------------------------------------------------------------ page 4
    v = [
        heading(
            "Import exposure and demand",
            "Import values are US dollars on a calendar year basis. Dependence is a "
            "structural proxy, not a customs volume calculation.",
        ),
        mineral_slicer(1000, 16, 264, 46),
        bar_by_mineral(
            16, 78, 620, 222, "Import Value (US$)", "Import value by mineral",
            "manganese carries no value because the source has no import table",
        ),
        table_visual(
            16, 310, 620, 248,
            [
                ("column", "dim_mineral", "mineral"),
                ("measure", "Import Value Label"),
                ("column", "fact_imports", "import_volume_note"),
                ("column", "fact_imports", "dependence_basis"),
            ],
            "Import detail",
            "the proxy label travels with the number, not in a footnote",
        ),
        line_demand(
            656, 78, 608, 250, "Projected annual requirement 2025 to 2030",
            "log scale, tonnes a year",
        ),
        bar_by_mineral(
            656, 340, 608, 218, "Growth Multiple", "Growth multiple 2025 to 2030",
            "how many times larger the 2030 requirement is than 2025",
        ),
        note(
            16, 568, 1248, 136,
            [
                "India holds 189 Mt of nickel and 45 Mt of cobalt ore resources and "
                "mines neither, so the 100 percent import dependence is structural. "
                "It is derived from zero active mining leases, not from imported "
                "volume over apparent consumption.",
                "",
                "Manganese import value is absent from the source and is shown as a "
                "gap, not a zero. India does mine manganese domestically, so reusing "
                "the zero supply assumption there would be wrong rather than merely "
                "unsupported.",
            ],
        ),
    ]
    sections.append(("Import exposure", v))

    # ------------------------------------------------------------ page 5
    v = [
        textbox(
            16, 12, 1248, 76,
            [
                [
                    ("Strategic Vulnerability Score = ", 14, TEXT, False),
                    ("0.40", 14, NI, True),
                    (" x import dependence + ", 14, TEXT, False),
                    ("0.35", 14, MN, True),
                    (" x (mining HHI / 100) + ", 14, TEXT, False),
                    ("0.25", 14, CO, True),
                    (" x refining leader share", 14, TEXT, False),
                ],
                [
                    (
                        "All inputs normalised to a 0 to 100 scale before weighting. "
                        "The score is NOT COMPUTED for any mineral.",
                        10,
                        TEXT2,
                        False,
                    )
                ],
            ],
            background=CARD2,
            border=True,
        ),
        table_visual(
            16, 98, 1248, 226,
            [
                ("column", "dim_mineral", "mineral"),
                ("column", "ref_vulnerability", "input_import_dependence_pct"),
                ("column", "ref_vulnerability", "quality_import_dependence"),
                ("column", "ref_vulnerability", "input_mining_hhi_scaled_0_100"),
                ("column", "ref_vulnerability", "quality_mining_hhi"),
                ("column", "ref_vulnerability", "input_refining_leader_pct"),
                ("column", "ref_vulnerability", "quality_refining_leader"),
                ("measure", "Score Status"),
            ],
            "Score inputs and why the score is withheld",
            "the gate is that all three inputs must exist and be complete",
        ),
        table_visual(
            16, 334, 1248, 292,
            [
                ("column", "ref_data_quality", "severity"),
                ("column", "ref_data_quality", "table"),
                ("column", "ref_data_quality", "finding"),
                ("column", "ref_data_quality", "impact"),
                ("column", "ref_data_quality", "handled_by"),
            ],
            "Data quality findings in the source workbook",
            "10 findings, every one handled at load time or in the query that touches it",
        ),
        note(
            16, 636, 1248, 68,
            [
                "No mineral clears the gate. Nickel and cobalt carry a proxy import "
                "dependence and a refining share drawn from a partial country list. "
                "Manganese is missing both an import table and a refining figure.",
                "Publishing a weighted number on those inputs would present an "
                "assumption as a measurement, so the score column stays empty and the "
                "reason is carried in the output.",
            ],
        ),
    ]
    sections.append(("Risk framework", v))

    out = []
    for i, (display, visuals) in enumerate(sections):
        out.append(
            {
                "id": i,
                "name": "ReportSection" + str(i).zfill(2),
                "displayName": display,
                "filters": "[]",
                "ordinal": i,
                "visualContainers": visuals,
                "config": page_config(),
                "displayOption": 1,
                "width": W,
                "height": H,
            }
        )
    return out


def build_layout():
    return {
        "id": 0,
        "resourcePackages": [],
        "sections": build_sections(),
        "config": json.dumps(
            {
                "version": "5.43",
                "activeSectionIndex": 0,
                "defaultDrillFilterOtherVisuals": True,
                "settings": {
                    "useStylableVisualContainerHeader": True,
                    "allowChangeFilterTypes": True,
                    "useNewFilterPaneExperience": True,
                    "useCrossReportDrillthrough": False,
                },
            },
            separators=(",", ":"),
        ),
        "layoutOptimization": 0,
        "publicCustomVisuals": [],
    }
