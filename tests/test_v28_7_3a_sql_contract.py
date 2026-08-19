from pathlib import Path

SQL = Path(__file__).resolve().parents[1] / "NAVE_V28_7_3A_DOMAIN_READ_PATH_CUTOVER_REGISTRY.sql"
TEXT = SQL.read_text(encoding="utf-8")


def test_v2873a_never_promotes_domain_primary():
    assert "default 'shadow_compare'" in TEXT
    assert "'domain_primary_promoted',false" in TEXT
    assert "update public.project_domain_read_state\n    set read_mode = 'domain_primary'" not in TEXT


def test_future_projects_are_seeded():
    assert "after insert on public.projects" in TEXT
    assert "seed_project_domain_read_state_v2873a" in TEXT


def test_empty_domain_is_explicitly_valid():
    assert "'empty_domain_is_valid',true" in TEXT
    assert "Zero rows" in TEXT or "Zero rows" in TEXT


def test_aggregate_migration_state_is_not_rewritten():
    assert "update public.project_domain_migration_state" not in TEXT.lower()
