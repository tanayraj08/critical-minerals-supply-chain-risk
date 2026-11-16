"""
Execute the SQL analysis file against critical_minerals.db and write one CSV per
query into outputs/.

All five queries live in one file, sql/critical_minerals_analysis.sql, separated
by `-- @query: <name>` marker comments. This splits on those markers so a single
file still produces a named CSV per query. The markers are ordinary SQL comments,
so the same file opens and runs section by section in any SQLite client.

Usage: python run_sql.py
"""

import os
import re
import sqlite3

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "critical_minerals.db")
SQL_FILE = os.path.join(HERE, "sql", "critical_minerals_analysis.sql")
OUT_DIR = os.path.join(HERE, "outputs")

MARKER = re.compile(r"^--\s*@query:\s*(\S+)\s*$", re.MULTILINE)


def split_queries(path=SQL_FILE):
    """Return [(name, sql), ...] in file order."""
    text = open(path, "r", encoding="utf-8").read()
    marks = list(MARKER.finditer(text))
    if not marks:
        raise ValueError("no -- @query: markers found in " + path)
    blocks = []
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end].strip()
        if body:
            blocks.append((m.group(1), body))
    return blocks


def run_all(db_path=DB_PATH, verbose=True):
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = sqlite3.connect(db_path)
    results = {}
    for name, query in split_queries():
        df = pd.read_sql_query(query, conn)
        out = os.path.join(OUT_DIR, name + ".csv")
        df.to_csv(out, index=False)
        results[name] = df
        if verbose:
            print("\n" + "=" * 78)
            print("QUERY: " + name + "   rows: " + str(len(df)))
            print("=" * 78)
            with pd.option_context("display.width", 200, "display.max_columns", 40):
                print(df.to_string(index=False))
            print("written to outputs/" + name + ".csv")
    conn.close()
    return results


if __name__ == "__main__":
    run_all()
