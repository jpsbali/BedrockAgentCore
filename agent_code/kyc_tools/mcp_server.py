import json
import os
import re
import sqlite3

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kyc-tools", host="0.0.0.0", port=8000)
_SRC_DB = os.path.join(os.path.dirname(__file__), "kyc_data.db")
DB_PATH = "/tmp/kyc_data.db"

if not os.path.exists(DB_PATH):
    import shutil

    shutil.copy2(_SRC_DB, DB_PATH)


def normalize_query(query: str) -> str:
    """Expand initials (W. → W), then build an OR query from each token."""
    query = re.sub(r"\b(\w)\.\s*", r"\1 ", query)
    tokens = [t for t in query.split() if len(t) >= 2]
    return " OR ".join(tokens) if tokens else query


def query_fts(table: str, fts_table: str, query: str, limit: int = 5) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"SELECT t.* FROM {table} t JOIN {fts_table} fts ON t.rowid = fts.rowid "
        f"WHERE {fts_table} MATCH ? ORDER BY bm25({fts_table}) LIMIT ?",
        (normalize_query(query), limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@mcp.tool()
def search_credit_reports(query: str, limit: int = 5) -> str:
    """Search credit reports by name or address using fuzzy text matching."""
    return json.dumps(
        query_fts("credit_reports", "credit_reports_fts", query, limit), default=str
    )


@mcp.tool()
def search_income_verification(query: str, limit: int = 5) -> str:
    """Search income verification records by employee name."""
    return json.dumps(
        query_fts("income_verification", "income_verification_fts", query, limit),
        default=str,
    )


@mcp.tool()
def search_property_records(query: str, limit: int = 5) -> str:
    """Search property records by owner name or address."""
    return json.dumps(
        query_fts("property_records", "property_records_fts", query, limit), default=str
    )


@mcp.tool()
def search_lien_records(query: str, limit: int = 5) -> str:
    """Search lien records by debtor name or address."""
    return json.dumps(
        query_fts("lien_records", "lien_records_fts", query, limit), default=str
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
