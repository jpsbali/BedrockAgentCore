#!/usr/bin/env python3
"""Build kyc_data.db from synthetic JSONL files.

Creates a SQLite database with regular tables and FTS5 virtual tables
using the trigram tokenizer for fuzzy text matching.

Usage:
    python build_db.py [--data-dir DIR] [--output FILE]
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

DB_NAME = "kyc_data.db"

SCHEMA = [
    """\
CREATE TABLE credit_reports (
    government_id TEXT PRIMARY KEY,
    full_legal_name TEXT,
    date_of_birth INTEGER,
    primary_address TEXT,
    credit_score INTEGER,
    account_tradelines TEXT
)""",
    """\
CREATE TABLE income_verification (
    government_id TEXT PRIMARY KEY,
    employee_name TEXT,
    employer_name TEXT,
    verified_annual_salary REAL
)""",
    """\
CREATE TABLE property_records (
    property_id TEXT PRIMARY KEY,
    owner_name_on_deed TEXT,
    property_address TEXT,
    assessed_value REAL
)""",
    """\
CREATE TABLE lien_records (
    lien_id TEXT PRIMARY KEY,
    property_id TEXT,
    debtor_name TEXT,
    debtor_address TEXT,
    lien_holder TEXT,
    lien_amount REAL,
    lien_status TEXT
)""",
    """\
CREATE VIRTUAL TABLE credit_reports_fts USING fts5(
    full_legal_name, primary_address,
    content=credit_reports, content_rowid=rowid,
    tokenize='trigram'
)""",
    """\
CREATE VIRTUAL TABLE income_verification_fts USING fts5(
    employee_name,
    content=income_verification, content_rowid=rowid,
    tokenize='trigram'
)""",
    """\
CREATE VIRTUAL TABLE property_records_fts USING fts5(
    owner_name_on_deed, property_address,
    content=property_records, content_rowid=rowid,
    tokenize='trigram'
)""",
    """\
CREATE VIRTUAL TABLE lien_records_fts USING fts5(
    debtor_name, debtor_address,
    content=lien_records, content_rowid=rowid,
    tokenize='trigram'
)""",
]

LOADERS = {
    "credit_reports": {
        "file": "synthetic_credit_reports.json",
        "insert": "INSERT INTO credit_reports VALUES (?,?,?,?,?,?)",
        "transform": lambda r: (
            r["government_id"],
            r["full_legal_name"],
            r["date_of_birth"],
            r["primary_address"],
            r["credit_score"],
            json.dumps(r["account_tradelines"]),
        ),
    },
    "income_verification": {
        "file": "synthetic_income_verification.json",
        "insert": "INSERT INTO income_verification VALUES (?,?,?,?)",
        "transform": lambda r: (
            r["government_id"],
            r["employee_name"],
            r["employer_name"],
            r["verified_annual_salary"],
        ),
    },
    "property_records": {
        "file": "synthetic_property_records.json",
        "insert": "INSERT INTO property_records VALUES (?,?,?,?)",
        "transform": lambda r: (
            r["property_id"],
            r["owner_name_on_deed"],
            r["property_address"],
            r["assessed_value"],
        ),
    },
    "lien_records": {
        "file": "synthetic_lien_records.json",
        "insert": "INSERT INTO lien_records VALUES (?,?,?,?,?,?,?)",
        "transform": lambda r: (
            r["lien_id"],
            r["property_id"],
            r["debtor_name"],
            r["debtor_address"],
            r["lien_holder"],
            r["lien_amount"],
            r["lien_status"],
        ),
    },
}

FTS_TABLES = {
    "credit_reports": "credit_reports_fts",
    "income_verification": "income_verification_fts",
    "property_records": "property_records_fts",
    "lien_records": "lien_records_fts",
}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_db(data_dir: Path, db_path: Path):
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    for stmt in SCHEMA:
        conn.execute(stmt)

    counts = {}
    for table_name, cfg in LOADERS.items():
        jsonl_path = data_dir / cfg["file"]
        if not jsonl_path.exists():
            print(f"[WARN] {cfg['file']} not found, skipping {table_name}")
            continue

        rows = read_jsonl(jsonl_path)
        conn.executemany(cfg["insert"], (cfg["transform"](r) for r in rows))
        counts[table_name] = len(rows)

    conn.commit()

    for base_table, fts_table in FTS_TABLES.items():
        if base_table in counts:
            conn.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES ('rebuild')")
    conn.commit()

    print(f"Built {db_path}")
    for table_name, count in counts.items():
        fts = FTS_TABLES.get(table_name, "")
        actual = conn.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
        print(f"  {table_name}: {actual} rows ({fts})")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Build kyc_data.db from JSONL files")
    parser.add_argument("--data-dir", default=None, help="Directory containing JSONL files (default: script directory)")
    parser.add_argument("--output", default=None, help="Output DB path (default: <data-dir>/kyc_data.db)")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    data_dir = Path(args.data_dir) if args.data_dir else script_dir
    db_path = Path(args.output) if args.output else data_dir / DB_NAME

    build_db(data_dir, db_path)


if __name__ == "__main__":
    main()
