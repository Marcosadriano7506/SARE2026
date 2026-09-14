import os

import pytest

from app import config as config_module


def test_engine_options_apply_postgres_search_path(monkeypatch):
    monkeypatch.setenv("DB_SCHEMA", "sare_production")

    options = config_module._engine_options(
        "postgresql+psycopg://user:pass@example.com:5432/postgres"
    )

    assert options["connect_args"]["options"] == "-csearch_path=sare_production"


def test_engine_options_leave_schema_unset_by_default(monkeypatch):
    monkeypatch.delenv("DB_SCHEMA", raising=False)

    options = config_module._engine_options(
        "postgresql+psycopg://user:pass@example.com:5432/postgres"
    )

    assert "connect_args" not in options


@pytest.mark.parametrize(
    "schema",
    [
        "sare-production",
        "sare production",
        "public;drop schema public",
        "123schema",
    ],
)
def test_database_schema_rejects_invalid_identifiers(monkeypatch, schema):
    monkeypatch.setenv("DB_SCHEMA", schema)

    with pytest.raises(RuntimeError):
        config_module._database_schema()
