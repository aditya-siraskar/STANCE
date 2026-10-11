"""Regression test for a genuine failure: SQLAlchemy's text() bind-param
parser does not recognize Postgres's ":name::type" cast shorthand —
`text(":cik::text ...")._bindparams` silently comes back WITHOUT 'cik' at
all, dropping the parameter from the query rather than raising. No live
Postgres needed: this is purely about whether SQLAlchemy extracts the
bind parameters correctly from the SQL text.
"""
from sqlalchemy import text

from stance.retrieval.hybrid import _HYBRID_SQL

_EXPECTED_PARAMS = {
    "query_text", "query_embedding", "cik", "fiscal_year",
    "item_code", "candidate_pool", "top_k", "rrf_k",
}


def test_sqlalchemy_detects_every_expected_bind_param():
    stmt = text(_HYBRID_SQL)
    assert set(stmt._bindparams.keys()) == _EXPECTED_PARAMS


def test_no_ambiguous_colon_colon_cast_shorthand_used():
    """The ':name::type' shorthand must never be reintroduced — it's
    silently mis-parsed by SQLAlchemy (see module docstring). Casts must
    use CAST(:name AS type) instead."""
    assert "::" not in _HYBRID_SQL
