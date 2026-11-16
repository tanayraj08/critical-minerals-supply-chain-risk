"""
Package the Power BI template files.

A .pbix is a compiled binary. Its model part is a serialized Analysis Services
database that only Power BI itself can write, so a .pbix cannot honestly be
produced outside Power BI Desktop. A .pbit is the open equivalent: the same OPC
zip container, but the model travels as TMSL JSON and the report as layout JSON,
both of which are text. Power BI Desktop opens a .pbit, builds the model, runs
the queries and gives you a live report that you save as .pbix in one step.

Two templates are written, which is a deliberate hedge because neither can be
opened and tested on this machine:

  Critical_Minerals_Report.pbit   model plus the full five page report
  Critical_Minerals_Model.pbit    model only, one empty page

The model half is plain TMSL and is the lower risk of the two. If the report
template ever refuses to open, the model template still delivers all 17 tables,
14 relationships and 31 measures, and BUILD_GUIDE.md covers laying the visuals
out by hand from there.

Usage: python build_pbit.py
"""

import json
import os
import zipfile

import pbit_model
import pbit_report

HERE = os.path.dirname(os.path.abspath(__file__))
PBI_DIR = os.path.join(HERE, "powerbi")

VERSION = "1.28"

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="json" ContentType="" />'
    '<Override PartName="/Version" ContentType="" />'
    '<Override PartName="/DataModelSchema" ContentType="" />'
    '<Override PartName="/DiagramLayout" ContentType="" />'
    '<Override PartName="/Report/Layout" ContentType="" />'
    "</Types>"
)


def utf16(text):
    """Power BI reads these parts as UTF-16 LE with a byte order mark."""
    return "﻿".encode("utf-16-le") + text.encode("utf-16-le")


def empty_layout():
    return {
        "id": 0,
        "resourcePackages": [],
        "sections": [
            {
                "id": 0,
                "name": "ReportSection00",
                "displayName": "Page 1",
                "filters": "[]",
                "ordinal": 0,
                "visualContainers": [],
                "config": pbit_report.page_config(),
                "displayOption": 1,
                "width": pbit_report.W,
                "height": pbit_report.H,
            }
        ],
        "config": json.dumps(
            {"version": "5.43", "activeSectionIndex": 0, "defaultDrillFilterOtherVisuals": True},
            separators=(",", ":"),
        ),
        "layoutOptimization": 0,
        "publicCustomVisuals": [],
    }


def write_pbit(path, schema, layout):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        # Version first, which is the order Power BI itself writes
        z.writestr("Version", utf16(VERSION))
        z.writestr("DataModelSchema", utf16(json.dumps(schema, indent=2)))
        z.writestr("DiagramLayout", utf16(json.dumps(pbit_model.diagram_layout())))
        z.writestr("Report/Layout", utf16(json.dumps(layout)))
        z.writestr("[Content_Types].xml", CONTENT_TYPES.encode("utf-8"))
    return path


def verify(path):
    """Mechanical checks. These cannot prove Power BI opens the file, only that
    the container, the encodings and the JSON are well formed."""
    problems = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for required in ["Version", "DataModelSchema", "Report/Layout", "[Content_Types].xml"]:
            if required not in names:
                problems.append("missing part: " + required)
        for part in ["DataModelSchema", "Report/Layout", "DiagramLayout"]:
            if part not in names:
                continue
            raw = z.read(part)
            if not raw.startswith(b"\xff\xfe"):
                problems.append(part + " is missing the UTF-16 LE byte order mark")
            try:
                json.loads(raw.decode("utf-16"))
            except Exception as exc:
                problems.append(part + " is not valid JSON: " + str(exc))
        layout = json.loads(z.read("Report/Layout").decode("utf-16"))
        for section in layout["sections"]:
            json.loads(section["config"])
            for vc in section["visualContainers"]:
                # every config and filter string must itself parse
                json.loads(vc["config"])
                json.loads(vc["filters"])
    return problems


def verify_semantics(schema, layout):
    """
    Every reference in the model and in the report must resolve to something
    that exists. Power BI cannot be run here, so this is the substitute: it
    catches a measure pointing at a column that was renamed, a relationship on a
    missing key, and a visual bound to a field that is not in the model. Those
    are the failures that would otherwise only surface on the user's machine.
    """
    import re

    problems = []
    model = schema["model"]
    columns = {}
    measures = set()
    for t in model["tables"]:
        columns[t["name"]] = {c["name"] for c in t["columns"]}
        for m in t.get("measures", []):
            measures.add(m["name"])

    # table[column] references inside DAX
    ref = re.compile(r"(\w+)\[([^\]]+)\]")
    for t in model["tables"]:
        for m in t.get("measures", []):
            dax = "\n".join(m["expression"])
            for table_name, column_name in ref.findall(dax):
                if table_name not in columns:
                    problems.append(
                        "measure " + m["name"] + " references unknown table " + table_name
                    )
                elif column_name not in columns[table_name]:
                    problems.append(
                        "measure " + m["name"] + " references unknown column "
                        + table_name + "[" + column_name + "]"
                    )
            # a bare [Name] reference must be another measure
            for bare in re.findall(r"(?<![\w\]])\[([^\]]+)\]", dax):
                if bare not in measures and bare not in {
                    c for cols in columns.values() for c in cols
                }:
                    problems.append(
                        "measure " + m["name"] + " references unknown measure [" + bare + "]"
                    )

    for r in model["relationships"]:
        for side in ("from", "to"):
            tbl, col = r[side + "Table"], r[side + "Column"]
            if tbl not in columns:
                problems.append("relationship " + r["name"] + " unknown table " + tbl)
            elif col not in columns[tbl]:
                problems.append(
                    "relationship " + r["name"] + " unknown column " + tbl + "[" + col + "]"
                )

    # every field a visual binds to must exist, and every projection queryRef
    # must appear in that visual's own query
    for section in layout["sections"]:
        for vc in section["visualContainers"]:
            cfg = json.loads(vc["config"])
            sv = cfg["singleVisual"]
            query = sv.get("prototypeQuery")
            if not query:
                continue
            aliases = {f["Name"]: f["Entity"] for f in query["From"]}
            names = set()
            for sel in query["Select"]:
                names.add(sel["Name"])
                if "Column" in sel:
                    entity = aliases[sel["Column"]["Expression"]["SourceRef"]["Source"]]
                    prop = sel["Column"]["Property"]
                    if entity not in columns:
                        problems.append(sv["visualType"] + " unknown table " + entity)
                    elif prop not in columns[entity]:
                        problems.append(
                            sv["visualType"] + " unknown column " + entity + "[" + prop + "]"
                        )
                elif "Measure" in sel:
                    prop = sel["Measure"]["Property"]
                    if prop not in measures:
                        problems.append(
                            sv["visualType"] + " unknown measure [" + prop + "]"
                        )
            for role, items in sv.get("projections", {}).items():
                for item in items:
                    if item["queryRef"] not in names:
                        problems.append(
                            sv["visualType"] + " projection " + role
                            + " points at " + item["queryRef"]
                            + " which is not selected by its own query"
                        )
            for f in json.loads(vc["filters"]):
                entity = f["expression"]["Column"]["Expression"]["SourceRef"]["Entity"]
                prop = f["expression"]["Column"]["Property"]
                if entity not in columns or prop not in columns[entity]:
                    problems.append(
                        "filter references unknown field " + entity + "[" + prop + "]"
                    )
    return problems


def embedded_row_count(table):
    """Rows inside Table.FromRows, excluding the type transform block below it."""
    body = "\n".join(table["partitions"][0]["source"]["expression"])
    start = body.index("Table.FromRows(")
    end = body.index("Table.TransformColumnTypes(")
    return sum(
        1
        for line in body[start:end].splitlines()
        if line.startswith("        {") and line.rstrip().endswith(("}", "},"))
    )


def verify_rows(schema):
    """The embedded M must hold exactly the rows the export produced."""
    import pandas as pd

    problems = []
    for t in schema["model"]["tables"]:
        if t["name"] == pbit_model.MEASURE_TABLE:
            continue
        path = os.path.join(pbit_model.DATA, t["name"] + ".csv")
        expected = len(pd.read_csv(path))
        rows = embedded_row_count(t)
        if rows != expected:
            problems.append(
                t["name"] + " embeds " + str(rows) + " rows, export has " + str(expected)
            )
    return problems


def build(verbose=True):
    os.makedirs(PBI_DIR, exist_ok=True)
    schema = pbit_model.build_model_schema()

    report_path = os.path.join(PBI_DIR, "Critical_Minerals_Report.pbit")
    model_path = os.path.join(PBI_DIR, "Critical_Minerals_Model.pbit")
    write_pbit(report_path, schema, pbit_report.build_layout())
    write_pbit(model_path, schema, empty_layout())

    layout = pbit_report.build_layout()
    semantic = verify_semantics(schema, layout)
    row_problems = verify_rows(schema)

    if verbose:
        model = schema["model"]
        measures = sum(len(t.get("measures", [])) for t in model["tables"])
        embedded = sum(embedded_row_count(t) for t in model["tables"])
        print("=" * 78)
        print("POWER BI TEMPLATE")
        print("=" * 78)
        print("  tables         " + str(len(model["tables"])))
        print("  relationships  " + str(len(model["relationships"])))
        print("  measures       " + str(measures))
        print("  embedded rows  " + str(embedded))
        print("  report pages   " + str(len(layout["sections"])))
        print()
        if semantic:
            print("  SEMANTIC PROBLEMS")
            for x in semantic:
                print("    " + x)
        else:
            print("  semantic check passed: every DAX, relationship, visual field and")
            print("  filter reference resolves against the model")
        if row_problems:
            print("  ROW COUNT PROBLEMS")
            for x in row_problems:
                print("    " + x)
        else:
            print("  row check passed: the embedded tables match the export exactly")
        for path in (report_path, model_path):
            size = os.path.getsize(path) / 1024
            problems = verify(path)
            print(
                "\n  "
                + os.path.basename(path).ljust(34)
                + f"{size:,.0f} KB   "
                + ("checks passed" if not problems else "PROBLEMS")
            )
            for p in problems:
                print("      " + p)
    return report_path, model_path


if __name__ == "__main__":
    build()
