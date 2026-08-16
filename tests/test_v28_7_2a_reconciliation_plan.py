from project_domain_reconciliation import build_reconciliation_plan


def _obs(idx, name, kind="solution_candidate", role="execution", phase="execution", observed_status=None):
    return {
        "id": f"00000000-0000-0000-0000-{idx:012d}",
        "source_asset_id": f"10000000-0000-0000-0000-{idx:012d}",
        "evidence_unit_id": f"20000000-0000-0000-0000-{idx:012d}",
        "observation_kind": kind,
        "observed_name": name,
        "observed_type": "material" if kind == "material_mention" else "activation",
        "occurrence_phase": phase,
        "occurrence_role": role,
        "observed_status": ("executed" if kind == "solution_candidate" and phase == "execution" and observed_status is None else observed_status),
        "model_confidence": 0.98,
        "source_authority_score": 0.94,
    }


def test_golden_execution_set_creates_four_and_attaches_four_without_logistics_pollution():
    existing = [
        {"id": "00000000-0000-0000-1000-000000000001", "entity_id": "00000000-0000-0000-2000-000000000001", "name": "Jogo da memória"},
        {"id": "00000000-0000-0000-1000-000000000002", "entity_id": "00000000-0000-0000-2000-000000000002", "name": "Mascote em Tamanho Real"},
        {"id": "00000000-0000-0000-1000-000000000003", "entity_id": "00000000-0000-0000-2000-000000000003", "name": "Oficina Origami de Coração"},
        {"id": "00000000-0000-0000-1000-000000000004", "entity_id": "00000000-0000-0000-2000-000000000004", "name": "Tatuagens Temporárias"},
    ]
    names = [
        "Amarelinha", "Jogo da Memória", "Pescaria", "Distribuição de Produtos",
        "Mascote Chambinho (Chambão)", "Tatuagem", "Folhas para colorir", "Oficina de Origami",
    ]
    observations = [_obs(i + 1, name) for i, name in enumerate(names)]
    observations += [
        _obs(101, "Polpas", kind="material_mention", role="result", phase="post_event"),
        _obs(102, "Pouchs", kind="material_mention", role="result", phase="post_event"),
        _obs(103, "Garrafinhas", kind="material_mention", role="result", phase="post_event"),
    ]

    plan = build_reconciliation_plan("00000000-0000-0000-3000-000000000001", observations, existing)
    assert {row["name"] for row in plan["solutions"]} == {
        "Amarelinha", "Pescaria", "Distribuição de Produtos", "Folhas para colorir"
    }
    assert len(plan["outcomes"]) == 8
    assert len([row for row in plan["occurrences"] if row["occurrence_role"] == "execution"]) == 8
    no_domain = [row for row in plan["observation_resolutions"] if row["status"] == "no_domain_object"]
    assert len(no_domain) == 3
    assert not any(row.get("name") in {"Polpas", "Pouchs", "Garrafinhas"} for row in plan["solutions"])


def test_reconciliation_plan_never_emits_merge_for_existing_identities():
    existing = [
        {"id": "00000000-0000-0000-1000-000000000001", "entity_id": "00000000-0000-0000-2000-000000000001", "name": "Pelúcia"},
        {"id": "00000000-0000-0000-1000-000000000002", "entity_id": "00000000-0000-0000-2000-000000000002", "name": "Chaveiro"},
    ]
    plan = build_reconciliation_plan(
        "00000000-0000-0000-3000-000000000001",
        [_obs(1, "Chaveiro de Pelúcia")],
        existing,
    )
    serialized = str(plan).lower()
    assert "auto_merge" not in serialized
    assert '"merge"' not in serialized


def test_non_executed_observation_never_becomes_executed_truth():
    observations = [_obs(1, "Ativação Teste", observed_status="not_executed", role="result")]
    plan = build_reconciliation_plan(
        "00000000-0000-0000-3000-000000000001", observations, []
    )
    execution = [row for row in plan["outcomes"] if row.get("outcome_type") == "execution_status"]
    assert len(execution) == 1
    assert execution[0]["outcome_status"] == "not_executed"
    assert execution[0]["outcome_status"] != "executed"


def test_reference_or_feedback_mention_cannot_create_new_solution_by_itself():
    observation = _obs(1, "Possível referência", kind="solution_candidate", role="feedback_context", phase="feedback", observed_status=None)
    plan = build_reconciliation_plan(
        "00000000-0000-0000-3000-000000000001", [observation], []
    )
    assert plan["solutions"] == []
    assert plan["occurrences"] == []
    resolution = plan["observation_resolutions"][0]
    assert resolution["status"] == "open"
    assert resolution["resolution_action"] == "insufficient_evidence"


def test_proposal_mention_can_create_new_solution_without_legacy_inventory():
    observation = _obs(1, "Nova Mecânica", kind="solution_mention", role="proposal", phase="proposal", observed_status=None)
    plan = build_reconciliation_plan(
        "00000000-0000-0000-3000-000000000001", [observation], []
    )
    assert [row["name"] for row in plan["solutions"]] == ["Nova Mecânica"]
    assert len(plan["occurrences"]) == 1
    proposal = [row for row in plan["outcomes"] if row["outcome_type"] == "proposal_status"]
    assert len(proposal) == 1 and proposal[0]["outcome_status"] == "proposed"


def test_historical_proposal_occurrence_does_not_overwrite_existing_current_decision():
    existing = [{
        "id": "00000000-0000-0000-1000-000000000001",
        "entity_id": "00000000-0000-0000-2000-000000000001",
        "name": "Ativação A",
    }]
    current = [{
        "entity_id": "00000000-0000-0000-2000-000000000001",
        "outcome_type": "proposal_status",
        "outcome_status": "rejected",
    }]
    observation = _obs(1, "Ativação A", kind="solution_mention", role="proposal", phase="proposal", observed_status=None)
    plan = build_reconciliation_plan(
        "00000000-0000-0000-3000-000000000001", [observation], existing, current
    )
    assert len(plan["occurrences"]) == 1
    assert not any(row["outcome_type"] == "proposal_status" for row in plan["outcomes"])


def test_low_confidence_proposal_signal_stays_open_instead_of_creating_truth():
    observation = _obs(1, "Solução Fraca", kind="solution_mention", role="proposal", phase="proposal", observed_status=None)
    observation["model_confidence"] = 0.75
    plan = build_reconciliation_plan(
        "00000000-0000-0000-3000-000000000001", [observation], []
    )
    assert plan["solutions"] == []
    assert plan["outcomes"] == []
    assert plan["observation_resolutions"][0]["resolution_action"] == "insufficient_evidence"
