"""Regression test for the fact_aliases NOT-NULL bug: a PRIMARY KEY on
(concept, element_name, cik) silently forces cik NOT NULL in Postgres,
which breaks the "NULL cik = applies to any company" seed rows. No local
Postgres is available to run the DDL against, so this is a text-level
guard against the specific regression, not a full schema test.
"""
import re

from stance.db import _SCHEMA_SQL


def _extract_table_block(ddl: str, table_name: str) -> str:
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS {table_name}\s*\((.*?)\n\);", ddl, re.DOTALL
    )
    assert match, f"could not find CREATE TABLE block for '{table_name}'"
    return match.group(1)


def _strip_sql_comments(block: str) -> str:
    """Drops '-- ...' line comments so a comment that merely *mentions* a
    forbidden phrase (to explain why it's forbidden) doesn't trip the check
    that scans for actual SQL syntax."""
    return "\n".join(line.split("--", 1)[0] for line in block.splitlines())


def test_fact_aliases_cik_is_not_forced_not_null_by_a_composite_primary_key():
    block = _strip_sql_comments(_extract_table_block(_SCHEMA_SQL, "fact_aliases"))
    assert "PRIMARY KEY" not in block.upper(), (
        "fact_aliases must not use a composite PRIMARY KEY including cik — "
        "Postgres forces PK columns NOT NULL, which breaks NULL-cik "
        "(applies-to-any-company) seed rows. Use UNIQUE NULLS NOT DISTINCT instead."
    )
    assert "NULLS NOT DISTINCT" in block.upper(), (
        "fact_aliases needs a NULLS NOT DISTINCT unique constraint so repeated "
        "NULL-cik rows still dedupe on re-seed."
    )
    cik_line = next(line for line in block.splitlines() if line.strip().startswith("cik "))
    assert "NOT NULL" not in cik_line.upper(), "cik column itself must stay nullable"
