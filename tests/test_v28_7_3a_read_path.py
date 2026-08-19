from __future__ import annotations

import pytest

import project_domain_reader as rdr


class Resp:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = {}
        self._limit = None
        self.insert_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def limit(self, value):
        self._limit = value
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def execute(self):
        if self.insert_payload is not None:
            self.client.inserts.append((self.table, self.insert_payload))
            return Resp([self.insert_payload])
        rows = [dict(row) for row in self.client.tables.get(self.table, [])]
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        if self._limit is not None:
            rows = rows[: self._limit]
        return Resp(rows)


class Client:
    def __init__(self, tables):
        self.tables = tables
        self.inserts = []

    def table(self, name):
        return Query(self, name)


def state(mode, readiness="ready", findings=None):
    return {
        "project_id": "p1",
        "domain_key": "journey",
        "read_mode": mode,
        "readiness_state": readiness,
        "hard_blockers": [],
        "governed_findings": findings or [],
    }


def test_domain_primary_empty_is_truth_and_never_calls_legacy():
    called = {"legacy": 0}

    def legacy():
        called["legacy"] += 1
        return [{"legacy": True}]

    client = Client({
        "project_domain_cutover_readiness": [state("domain_primary")],
        "project_journey_moments": [],
    })
    result = rdr.read_domain(client, "p1", "journey", legacy_loader=legacy)
    assert result.served_source == "domain"
    assert result.data == []
    assert result.fallback_used is False
    assert called["legacy"] == 0


def test_domain_primary_requires_ready_state():
    client = Client({
        "project_domain_cutover_readiness": [state("domain_primary", "blocked")],
        "project_journey_moments": [],
    })
    with pytest.raises(rdr.DomainReadBlocked):
        rdr.read_domain(client, "p1", "journey", legacy_loader=lambda: [])


def test_shadow_compare_serves_legacy_without_mixing():
    client = Client({
        "project_domain_cutover_readiness": [state("shadow_compare")],
        "project_journey_moments": [{"id": "d1", "project_id": "p1", "lifecycle_status": "active"}],
    })
    result = rdr.read_domain(client, "p1", "journey", legacy_loader=lambda: [{"id": "l1"}])
    assert result.served_source == "legacy"
    assert result.data == [{"id": "l1"}]
    assert result.domain_candidate[0]["id"] == "d1"
    assert all(row.get("id") != "d1" for row in result.data)
    assert result.fallback_used is False


def test_legacy_primary_does_not_touch_domain_table():
    client = Client({"project_domain_cutover_readiness": [state("legacy_primary", "not_ready")]})
    result = rdr.read_domain(client, "p1", "journey", legacy_loader=lambda: [{"id": "l1"}])
    assert result.data == [{"id": "l1"}]
    assert result.domain_candidate == []


def test_legacy_serving_modes_require_explicit_adapter():
    client = Client({"project_domain_cutover_readiness": [state("shadow_compare")]})
    with pytest.raises(rdr.LegacyLoaderRequired):
        rdr.read_domain(client, "p1", "journey")


def test_supported_domain_contract():
    assert rdr.SUPPORTED_DOMAIN_KEYS == (
        "context", "requirements", "solutions", "outcomes",
        "strategy", "creative", "experience", "journey",
    )
