from __future__ import annotations

"""NAVE IQ Bench Runner v1.

Runner determinístico e versionável para medir a inteligência da NAVE sem transformar
casos reais em regras de produção. O módulo não depende de Streamlit, Supabase ou LLM.

Ele recebe saídas estruturadas de qualquer pipeline candidato e compara essas saídas
contra os contratos YAML em ``evals/``. Avaliações semânticas por LLM poderão ser
acopladas depois; a v1 prioriza métricas auditáveis e determinísticas.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
import argparse
import importlib
import json
import math
import re
import sys
import unicodedata

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - erro explicado em runtime
    yaml = None


RUNNER_VERSION = "1.1.0"


# ---------------------------------------------------------------------------
# Modelos simples
# ---------------------------------------------------------------------------

@dataclass
class MetricResult:
    name: str
    value: float | None
    status: str = "scored"  # scored | not_evaluated | error
    details: str | None = None


@dataclass
class GateResult:
    name: str
    status: str  # pass | fail | not_evaluated
    actual: Any = None
    expected: Any = None
    details: str | None = None


@dataclass
class CaseResult:
    case_id: str
    case_type: str
    status: str  # passed | failed | not_run | error
    score: float | None
    metrics: list[MetricResult] = field(default_factory=list)
    gate_signals: dict[str, Any] = field(default_factory=dict)
    fixture_status: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class SuiteResult:
    suite_id: str
    suite_version: str
    runner_version: str
    started_at: str
    finished_at: str
    status: str  # pass | blocked | provisional | validate_only
    overall_score: float | None
    dimension_scores: dict[str, float | None]
    case_results: list[CaseResult]
    gates: list[GateResult]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _require_yaml() -> None:
    if yaml is None:
        raise RuntimeError(
            "PyYAML não está instalado. Instale requirements-evals.txt antes de executar o IQ Bench."
        )


def load_yaml(path: str | Path) -> dict[str, Any]:
    _require_yaml()
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"YAML inválido ou não-objeto: {path}")
    return data


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def token_set(value: Any) -> set[str]:
    stop = {
        "de", "da", "do", "das", "dos", "e", "em", "para", "por", "com", "um", "uma",
        "the", "a", "an", "of", "to", "and", "for", "on", "in", "is", "are", "was", "were",
        "projeto", "project", "evento", "event",
    }
    return {t for t in normalize_text(value).split() if len(t) >= 3 and t not in stop}


def token_f1(a: Any, b: Any) -> float:
    aa, bb = token_set(a), token_set(b)
    if not aa or not bb:
        return 0.0
    inter = len(aa & bb)
    if not inter:
        return 0.0
    precision = inter / len(aa)
    recall = inter / len(bb)
    return 2 * precision * recall / (precision + recall)


def approx_equal(actual: Any, expected: Any, tolerance: float = 0.01) -> bool:
    try:
        a, e = float(actual), float(expected)
    except (TypeError, ValueError):
        return False
    return math.isfinite(a) and math.isfinite(e) and abs(a - e) <= tolerance


def _first(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _dict_list(candidate: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [x for x in _list(candidate.get(key)) if isinstance(x, dict)]


def file_sha256(path: str | Path) -> str:
    h = sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_fixtures(case: Mapping[str, Any], fixture_dirs: Sequence[str | Path]) -> dict[str, Any]:
    """Resolve fixtures reais por basename + SHA-256.

    Não copia arquivos proprietários e não exige fixtures para casos inline/sintéticos.
    """
    result: dict[str, Any] = {"required": 0, "resolved": 0, "files": []}
    roots = [Path(p) for p in fixture_dirs]
    for source in _list(case.get("sources")):
        if not isinstance(source, dict) or not source.get("basename"):
            continue
        result["required"] += 1
        basename = str(source["basename"])
        expected_hash = str(source.get("sha256") or "").lower()
        found: Path | None = None
        hash_ok = False
        for root in roots:
            candidate = root / basename
            if candidate.exists() and candidate.is_file():
                found = candidate
                if expected_hash:
                    hash_ok = file_sha256(candidate).lower() == expected_hash
                else:
                    hash_ok = True
                if hash_ok:
                    break
        entry = {
            "role": source.get("role"),
            "basename": basename,
            "path": str(found) if found else None,
            "hash_ok": hash_ok,
        }
        result["files"].append(entry)
        if found and hash_ok:
            result["resolved"] += 1
    result["complete"] = result["required"] == result["resolved"]
    return result


# ---------------------------------------------------------------------------
# Contrato de resposta / adapters
# ---------------------------------------------------------------------------

class ResponseDirectoryAdapter:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def __call__(self, case: Mapping[str, Any], fixture_status: Mapping[str, Any]) -> dict[str, Any] | None:
        path = self.directory / f"{case['case_id']}.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"Resposta deve ser objeto JSON: {path}")
        return data


def load_callable(spec: str) -> Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any] | None]:
    if ":" not in spec:
        raise ValueError("Adapter deve usar formato modulo:function")
    module_name, function_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    fn = getattr(module, function_name)
    if not callable(fn):
        raise TypeError(f"Adapter não é callable: {spec}")
    return fn


# ---------------------------------------------------------------------------
# Matchers genéricos
# ---------------------------------------------------------------------------

def _match_text_rule(actual: Any, expected: Mapping[str, Any], key: str = "value_text") -> bool:
    raw = str(actual or "")
    norm = normalize_text(raw)
    if key in expected:
        return norm == normalize_text(expected[key])
    if f"{key}_contains" in expected:
        return normalize_text(expected[f"{key}_contains"]) in norm
    if f"{key}_one_of" in expected:
        return any(norm == normalize_text(v) for v in _list(expected[f"{key}_one_of"]))
    return True


def _claim_matches(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    for field in ("subject", "predicate"):
        if field in expected and normalize_text(actual.get(field)) != normalize_text(expected[field]):
            return False
    if "value_numeric" in expected:
        tol = float(expected.get("tolerance", 0.01))
        if not approx_equal(_first(actual, "value_numeric", "numeric_value", "value"), expected["value_numeric"], tol):
            return False
    if "value_date" in expected:
        if str(_first(actual, "value_date", "date_value", "value"))[:10] != str(expected["value_date"])[:10]:
            return False
    if any(k in expected for k in ("value_text", "value_text_contains", "value_text_one_of")):
        if not _match_text_rule(_first(actual, "value_text", "text_value", "value"), expected):
            return False
    for field in ("currency", "unit", "status"):
        if field in expected and normalize_text(actual.get(field)) != normalize_text(expected[field]):
            return False
    if "status_one_of" in expected:
        if normalize_text(actual.get("status")) not in {normalize_text(v) for v in _list(expected["status_one_of"])}:
            return False
    return True


def _entity_matches(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    if "type" in expected and normalize_text(_first(actual, "type", "entity_type")) != normalize_text(expected["type"]):
        return False
    name = str(_first(actual, "canonical_name", "name", "title") or "")
    if "name" in expected and normalize_text(name) != normalize_text(expected["name"]):
        return False
    if "canonical_name" in expected and normalize_text(name) != normalize_text(expected["canonical_name"]):
        return False
    if "name_contains" in expected and normalize_text(expected["name_contains"]) not in normalize_text(name):
        return False
    return True


def _relation_matches(actual: Mapping[str, Any], expected: Mapping[str, Any], entities: Sequence[Mapping[str, Any]]) -> bool:
    for field, aliases in {
        "source": ("source", "source_id", "source_key"),
        "relation": ("relation", "predicate", "relation_type"),
        "target": ("target", "target_id", "target_key"),
    }.items():
        if field in expected:
            if normalize_text(_first(actual, *aliases)) != normalize_text(expected[field]):
                return False
    if "target_type_one_of" in expected:
        target_type = _first(actual, "target_type", "target_entity_type")
        if not target_type:
            target_id = _first(actual, "target", "target_id", "target_key")
            for ent in entities:
                if str(_first(ent, "id", "key", "slug")) == str(target_id):
                    target_type = _first(ent, "type", "entity_type")
                    break
        allowed = {normalize_text(v) for v in _list(expected["target_type_one_of"])}
        if normalize_text(target_type) not in allowed:
            return False
    return True


def _feedback_claim_matches(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    for field in ("target", "polarity", "topic"):
        if field in expected and normalize_text(actual.get(field)) != normalize_text(expected[field]):
            return False
    return True


def _finding_grounded(finding: Mapping[str, Any]) -> bool:
    refs = _list(_first(finding, "evidence_refs", "evidence", "evidence_units"))
    roles = _list(_first(finding, "evidence_roles", "source_roles"))
    return bool(refs or roles)


def _finding_matches(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    if "kind" in expected and normalize_text(_first(actual, "kind", "finding_type")) != normalize_text(expected["kind"]):
        return False
    text = str(_first(actual, "text", "analysis", "summary", "message", "title") or "")
    if "must_express" in expected and token_f1(text, expected["must_express"]) < 0.28:
        return False
    required_roles = {normalize_text(x) for x in _list(expected.get("requires_evidence_from"))}
    if required_roles:
        actual_roles = {normalize_text(x) for x in _list(_first(actual, "evidence_roles", "source_roles"))}
        # aceita refs com prefixo de role: briefing:p20, budget:row94 etc.
        for ref in _list(_first(actual, "evidence_refs", "evidence")):
            n = normalize_text(ref)
            for role in required_roles:
                if role and role in n:
                    actual_roles.add(role)
        if not required_roles.issubset(actual_roles):
            return False
    return True


# ---------------------------------------------------------------------------
# Avaliações por família
# ---------------------------------------------------------------------------

def _ratio(found: int, total: int) -> float | None:
    return (found / total) if total else None


def evaluate_source_roles(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> MetricResult | None:
    expected = case.get("expected", {}).get("source_roles")
    if not isinstance(expected, dict):
        return None
    actual = candidate.get("source_roles") or {}
    if not isinstance(actual, dict):
        actual = {}
    ok = sum(
        1 for key, value in expected.items()
        if normalize_text(actual.get(key)) == normalize_text(value)
    )
    return MetricResult("source_role_accuracy", _ratio(ok, len(expected)), details=f"{ok}/{len(expected)}")


def evaluate_claims(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    expected_root = case.get("expected", {})
    expected_claims = _list(expected_root.get("claims_required") or expected_root.get("claims"))
    if not expected_claims:
        return []
    actual_claims = _dict_list(candidate, "claims")
    matched_expected = 0
    matched_actual_indexes: set[int] = set()
    for exp in expected_claims:
        if not isinstance(exp, dict):
            continue
        for idx, act in enumerate(actual_claims):
            if idx in matched_actual_indexes:
                continue
            if _claim_matches(act, exp):
                matched_expected += 1
                matched_actual_indexes.add(idx)
                break
    recall = _ratio(matched_expected, len(expected_claims))
    precision = _ratio(len(matched_actual_indexes), len(actual_claims)) if actual_claims else (1.0 if not expected_claims else 0.0)
    return [
        MetricResult("claim_recall", recall, details=f"{matched_expected}/{len(expected_claims)}"),
        MetricResult("claim_precision", precision, details=f"{len(matched_actual_indexes)}/{len(actual_claims)}"),
        MetricResult("claim_accuracy", recall),
    ]


def evaluate_entities(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    expected = _list(case.get("expected", {}).get("entities_required"))
    if not expected:
        return []
    actual = _dict_list(candidate, "entities")
    found = 0
    for exp in expected:
        if isinstance(exp, dict) and any(_entity_matches(act, exp) for act in actual):
            found += 1
    return [MetricResult("entity_resolution_precision", _ratio(found, len(expected)), details=f"{found}/{len(expected)}")]


def evaluate_ambiguous_entity_case(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    if case.get("case_id") != "adversarial_ambiguous_entity_resolution":
        return []
    entities = _dict_list(candidate, "entities")
    vivo_brands = [e for e in entities if normalize_text(_first(e, "type", "entity_type")) == "brand" and normalize_text(_first(e, "canonical_name", "name")) == "vivo"]
    false_merges = max(0, len(vivo_brands) - 1)
    precision = 1.0 if len(vivo_brands) == 1 else 0.0
    return [
        MetricResult("entity_resolution_precision", precision),
        MetricResult("false_merge_count", float(false_merges)),
    ]


def evaluate_relations(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    expected = _list(case.get("expected", {}).get("relations_required"))
    if not expected:
        return []
    actual = _dict_list(candidate, "relations")
    entities = _dict_list(candidate, "entities")
    matched_actual: set[int] = set()
    found = 0
    for exp in expected:
        if not isinstance(exp, dict):
            continue
        for idx, act in enumerate(actual):
            if idx in matched_actual:
                continue
            if _relation_matches(act, exp, entities):
                found += 1
                matched_actual.add(idx)
                break
    recall = _ratio(found, len(expected))
    # precisão crítica considera relações candidatas que usam predicates esperados.
    expected_predicates = {normalize_text(x.get("relation")) for x in expected if isinstance(x, dict)}
    critical_actual = [a for a in actual if normalize_text(_first(a, "relation", "predicate", "relation_type")) in expected_predicates]
    precision = _ratio(len(matched_actual), len(critical_actual)) if critical_actual else (1.0 if not expected else 0.0)
    return [
        MetricResult("critical_relation_recall", recall, details=f"{found}/{len(expected)}"),
        MetricResult("critical_relation_precision", precision, details=f"{len(matched_actual)}/{len(critical_actual)}"),
    ]


def evaluate_feedback_claims(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    expected = _list(case.get("expected", {}).get("feedback_claims_required"))
    if not expected:
        return []
    actual = _dict_list(candidate, "feedback_claims")
    found = 0
    for exp in expected:
        if isinstance(exp, dict) and any(_feedback_claim_matches(act, exp) for act in actual):
            found += 1
    return [MetricResult("feedback_target_accuracy", _ratio(found, len(expected)), details=f"{found}/{len(expected)}")]


def evaluate_financial(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    expected_root = case.get("expected", {})
    expected_fin = expected_root.get("financial")
    expected_facts = expected_root.get("facts")
    actual_fin = candidate.get("financial") if isinstance(candidate.get("financial"), dict) else {}
    actual_facts = candidate.get("facts") if isinstance(candidate.get("facts"), dict) else {}
    metrics: list[MetricResult] = []

    if isinstance(expected_facts, dict):
        ok = 0
        for key, exp in expected_facts.items():
            actual = actual_facts.get(key)
            if actual is None:
                actual = actual_fin.get(key)
            if approx_equal(actual, exp, 0.01):
                ok += 1
        metrics.extend([
            MetricResult("financial_state_accuracy", _ratio(ok, len(expected_facts)), details=f"{ok}/{len(expected_facts)}"),
            MetricResult("exact_numeric_accuracy", _ratio(ok, len(expected_facts)), details=f"{ok}/{len(expected_facts)}"),
        ])

    if isinstance(expected_fin, dict):
        numeric_keys = [
            k for k, v in expected_fin.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        ]
        ok = 0
        for key in numeric_keys:
            tol = 0.02 if "pct" not in key else 0.02
            if approx_equal(actual_fin.get(key), expected_fin[key], tol):
                ok += 1
        if numeric_keys:
            metrics.append(MetricResult("exact_numeric_accuracy", _ratio(ok, len(numeric_keys)), details=f"{ok}/{len(numeric_keys)}"))

        # Ranking e valores de categorias / linhas principais.
        for list_key, metric_name in (
            ("top_categories_after_tax", "financial_top_category_accuracy"),
            ("largest_line_items_after_tax", "financial_top_line_accuracy"),
        ):
            exp_list = _list(expected_fin.get(list_key))
            if not exp_list:
                continue
            act_list = _list(actual_fin.get(list_key))
            matches = 0
            for idx, exp in enumerate(exp_list):
                if idx >= len(act_list):
                    continue
                act = act_list[idx]
                if isinstance(exp, list) and len(exp) >= 2 and isinstance(act, (list, tuple)) and len(act) >= 2:
                    if normalize_text(act[0]) == normalize_text(exp[0]) and approx_equal(act[1], exp[1], 0.05):
                        matches += 1
                elif isinstance(exp, dict) and isinstance(act, dict):
                    ename = _first(exp, "name", "category", "item")
                    aname = _first(act, "name", "category", "item")
                    evalue = _first(exp, "value", "total", "amount")
                    avalue = _first(act, "value", "total", "amount")
                    if normalize_text(aname) == normalize_text(ename) and approx_equal(avalue, evalue, 0.05):
                        matches += 1
            metrics.append(MetricResult(metric_name, _ratio(matches, len(exp_list)), details=f"{matches}/{len(exp_list)}"))
    return metrics


def evaluate_conflict(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    expected = case.get("expected", {})
    if not expected.get("conflict_set_required"):
        return []
    claims = _dict_list(candidate, "claims")
    exp_claims = _list(expected.get("claims_required"))
    preserved = all(any(_claim_matches(act, exp) for act in claims) for exp in exp_claims if isinstance(exp, dict))
    conflict_sets = _list(candidate.get("conflict_sets"))
    has_conflict = bool(conflict_sets)
    current_values = candidate.get("current_values") if isinstance(candidate.get("current_values"), dict) else {}
    actual_current = current_values.get("event_date") or candidate.get("current_value")
    current_ok = str(actual_current)[:10] == str(expected.get("current_value"))[:10]
    return [
        MetricResult("conflict_preservation", 1.0 if preserved and has_conflict else 0.0),
        MetricResult("authority_resolution_accuracy", 1.0 if current_ok else 0.0),
        MetricResult("provenance", 1.0 if preserved else 0.0),
    ]


def _candidate_execution_state(candidate: Mapping[str, Any]) -> str:
    state = _first(candidate, "execution_state", "execution_result")
    if state:
        return normalize_text(state)
    for claim in _dict_list(candidate, "claims"):
        if normalize_text(claim.get("predicate")) in {"execution state", "execution result", "execution_result", "execution_state"}:
            return normalize_text(_first(claim, "value_text", "value", "status"))
    return ""


def evaluate_execution_uncertainty(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    allowed = _list(case.get("expected", {}).get("execution_state_one_of"))
    if not allowed:
        return []
    state = _candidate_execution_state(candidate)
    ok = state in {normalize_text(v) for v in allowed}
    false_exec = 1.0 if state in {"executed", "success", "execution result success", "execution_result success"} else 0.0
    return [
        MetricResult("uncertainty_calibration", 1.0 if ok else 0.0, details=f"state={state or 'missing'}"),
        MetricResult("false_executed_without_evidence", false_exec),
    ]


def evaluate_outcome_granularity(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    if case.get("case_id") != "blind_loss_with_validated_concept":
        return []
    claims = _dict_list(candidate, "claims")
    project_lost = any(
        normalize_text(c.get("subject")) == "project"
        and normalize_text(c.get("predicate")) == "commercial result"
        and normalize_text(_first(c, "value_text", "value")) in {"lost", "not approved", "rejected"}
        for c in claims
    )
    concept_positive = any(
        normalize_text(c.get("subject")) == "city pulse"
        and normalize_text(c.get("predicate")) == "sentiment"
        and normalize_text(_first(c, "value_text", "value")) in {"positive", "very positive"}
        for c in claims
    )
    overgeneralized = any(
        normalize_text(c.get("subject")) == "city pulse"
        and normalize_text(_first(c, "value_text", "value")) in {"negative", "rejected", "not approved"}
        for c in claims
    )
    return [
        MetricResult("outcome_granularity", 1.0 if project_lost and concept_positive and not overgeneralized else 0.0),
        MetricResult("lost_project_solution_overgeneralization", 1.0 if overgeneralized else 0.0),
    ]


def evaluate_forbidden_financial_states(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    if case.get("case_id") != "blind_financial_state_separation":
        return []
    expected = case.get("expected", {}).get("facts", {})
    facts = candidate.get("facts") if isinstance(candidate.get("facts"), dict) else {}
    fin = candidate.get("financial") if isinstance(candidate.get("financial"), dict) else {}
    getv = lambda k: facts.get(k, fin.get(k))
    violations = 0
    # Se os próprios campos estruturados estiverem trocados, conta violação.
    if approx_equal(getv("actual_total"), expected.get("proposed_total"), 0.01):
        violations += 1
    if approx_equal(getv("proposed_total"), expected.get("actual_total"), 0.01):
        violations += 1
    # realizado 775.5k não excede teto 800k.
    claims = _dict_list(candidate, "claims")
    if any(
        normalize_text(c.get("predicate")) in {"actual budget status", "budget status"}
        and normalize_text(_first(c, "value_text", "value")) in {"over budget", "exceeded", "estourou"}
        for c in claims
    ):
        violations += 1
    return [MetricResult("forbidden_inference_count", float(violations))]


def evaluate_findings(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    expected = _list(case.get("expected", {}).get("findings_desirable"))
    actual = _dict_list(candidate, "findings")
    metrics: list[MetricResult] = []
    if expected:
        matched = sum(
            1 for exp in expected if isinstance(exp, dict) and any(_finding_matches(act, exp) for act in actual)
        )
        metrics.append(MetricResult("cross_source_finding_quality", _ratio(matched, len(expected)), details=f"{matched}/{len(expected)}"))
    high_critical = [
        f for f in actual
        if normalize_text(_first(f, "severity", "importance", "priority")) in {"high", "critical"}
    ]
    if high_critical:
        grounded = sum(1 for f in high_critical if _finding_grounded(f))
        metrics.append(MetricResult("high_critical_grounding_rate", _ratio(grounded, len(high_critical)), details=f"{grounded}/{len(high_critical)}"))
    elif expected:
        # Não há finding high/critical para violar grounding; gate fica não avaliado via signal.
        metrics.append(MetricResult("high_critical_grounding_rate", None, status="not_evaluated", details="nenhum finding high/critical"))
    return metrics


def evaluate_retrieval(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    if not case.get("query") or not case.get("candidates"):
        return []
    retrieval = candidate.get("retrieval") if isinstance(candidate.get("retrieval"), dict) else {}
    ranking = _list(retrieval.get("ranking") or candidate.get("ranking"))
    ranking = [str(x) for x in ranking]
    expected = case.get("expected", {})
    top_id = str(expected.get("top_relevant_id") or "")
    recall_at_3 = 1.0 if top_id and top_id in ranking[:3] else 0.0
    try:
        rank = ranking.index(top_id) + 1
        mrr = 1.0 / rank
    except ValueError:
        mrr = 0.0
    semantic = 1.0 if ranking and ranking[0] == top_id else (0.5 if recall_at_3 else 0.0)
    return [
        MetricResult("recall_at_3", recall_at_3),
        MetricResult("mrr", mrr),
        MetricResult("semantic_relevance", semantic),
    ]


def evaluate_jovi_forbidden(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    if case.get("case_id") != "golden_jovi_x300_multisource":
        return []
    violations = 0
    exec_state = _candidate_execution_state(candidate)
    if exec_state in {"executed", "success"}:
        violations += 1
    # proposed_total não pode ser actual_total sem fonte de execução.
    fin = candidate.get("financial") if isinstance(candidate.get("financial"), dict) else {}
    facts = candidate.get("facts") if isinstance(candidate.get("facts"), dict) else {}
    proposed = fin.get("after_tax_total") or fin.get("proposed_total") or facts.get("proposed_total")
    actual = fin.get("actual_total") or facts.get("actual_total")
    if actual is not None and proposed is not None and approx_equal(actual, proposed, 0.01):
        violations += 1
    claims = _dict_list(candidate, "claims")
    # conceito positivo não pode virar rejeitado por propagação da perda.
    for c in claims:
        if normalize_text(c.get("subject")) == "on tour concept" and normalize_text(_first(c, "value_text", "value")) in {"negative", "rejected", "not approved"}:
            violations += 1
            break
    # EVENT JOURNEY em presskit explicitamente é violação se candidato expuser classificações.
    classifications = _list(candidate.get("classifications") or candidate.get("content_classifications"))
    for row in classifications:
        if isinstance(row, dict) and "event journey" in normalize_text(_first(row, "title", "name")):
            section = normalize_text(_first(row, "section", "section_key", "category"))
            if "press" in section or "gift" in section or "brinde" in section:
                violations += 1
                break
    return [MetricResult("forbidden_inference_count", float(violations))]


def evaluate_chambinho_forbidden(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[MetricResult]:
    if case.get("case_id") != "golden_chambinho_festivalzinho_2026_full_cycle":
        return []
    violations = 0
    fin = candidate.get("financial") if isinstance(candidate.get("financial"), dict) else {}
    facts = candidate.get("facts") if isinstance(candidate.get("facts"), dict) else {}
    proposed = fin.get("after_tax_total") or fin.get("proposed_total") or facts.get("proposed_total")
    actual = fin.get("actual_total") or facts.get("actual_total")
    if actual is not None and proposed is not None and approx_equal(actual, proposed, 0.01):
        violations += 1

    # 8 mil é audiência do Festivalzinho; só é violação quando propagada para
    # visitação/impacto específico da ativação Casa Chambinho.
    for key in ("activation_attendees", "house_attendees", "activation_visitors", "casa_chambinho_visitors"):
        value = facts.get(key)
        if value is None:
            value = fin.get(key)
        if value is not None and approx_equal(value, 8000, 0.01):
            violations += 1
            break

    identity = candidate.get("project_identity") if isinstance(candidate.get("project_identity"), dict) else {}
    client_name = normalize_text(_first(identity, "client", "client_brand", "brand"))
    if "lagunitas" in client_name:
        violations += 1
    for key in ("event_date", "presentation_date", "project_date"):
        value = str(identity.get(key) or facts.get(key) or "")
        if value.startswith("2024-05-10") or value.startswith("2024-09-30"):
            violations += 1
            break

    after_movie = normalize_text(facts.get("after_movie_status") or candidate.get("after_movie_status"))
    if after_movie in {"delivered", "completed", "entregue", "finalizado", "ready"}:
        violations += 1

    # Se a saída declara estouro líquido sem qualquer caveat sobre pagamento
    # direto/responsabilidade cliente, consideramos propagação indevida do total bruto.
    budget_status = normalize_text(fin.get("budget_status") or facts.get("budget_status"))
    if budget_status in {"over budget", "over_budget", "estourado", "acima do budget"}:
        findings = _dict_list(candidate, "findings")
        caveat = any(
            any(term in normalize_text(_first(f, "text", "statement", "summary", "title")) for term in (
                "pagamento direto", "pago diretamente", "responsabilidade cliente", "reconciliar", "envelope"
            ))
            for f in findings
        )
        if not caveat:
            violations += 1
    return [MetricResult("forbidden_inference_count", float(violations))]


def evaluate_case(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> tuple[list[MetricResult], dict[str, Any]]:
    metrics: list[MetricResult] = []
    sr = evaluate_source_roles(case, candidate)
    if sr:
        metrics.append(sr)
    for fn in (
        evaluate_claims,
        evaluate_entities,
        evaluate_ambiguous_entity_case,
        evaluate_relations,
        evaluate_feedback_claims,
        evaluate_financial,
        evaluate_conflict,
        evaluate_execution_uncertainty,
        evaluate_outcome_granularity,
        evaluate_forbidden_financial_states,
        evaluate_findings,
        evaluate_retrieval,
        evaluate_jovi_forbidden,
        evaluate_chambinho_forbidden,
    ):
        metrics.extend(fn(case, candidate))

    # Deduplica métricas repetidas pelo nome usando a média, preservando NOT_EVALUATED.
    grouped: dict[str, list[MetricResult]] = {}
    for m in metrics:
        grouped.setdefault(m.name, []).append(m)
    collapsed: list[MetricResult] = []
    for name, rows in grouped.items():
        vals = [r.value for r in rows if r.value is not None and r.status == "scored"]
        if vals:
            details = "; ".join(filter(None, (r.details for r in rows))) or None
            collapsed.append(MetricResult(name, sum(vals) / len(vals), details=details))
        else:
            collapsed.append(MetricResult(name, None, status="not_evaluated", details=rows[0].details))

    by_name = {m.name: m for m in collapsed}
    signals = {
        "high_critical_grounding_rate": by_name.get("high_critical_grounding_rate").value if by_name.get("high_critical_grounding_rate") else None,
        "false_executed_without_evidence": by_name.get("false_executed_without_evidence").value if by_name.get("false_executed_without_evidence") else None,
        "lost_project_solution_overgeneralization": by_name.get("lost_project_solution_overgeneralization").value if by_name.get("lost_project_solution_overgeneralization") else None,
        "critical_relation_precision": by_name.get("critical_relation_precision").value if by_name.get("critical_relation_precision") else None,
        "exact_numeric_accuracy": by_name.get("exact_numeric_accuracy").value if by_name.get("exact_numeric_accuracy") else None,
        "retrieval_recall_at_20": None,  # dataset v1 ainda só mede recall@3.
    }
    return collapsed, signals


# ---------------------------------------------------------------------------
# Score / dimensões / gates
# ---------------------------------------------------------------------------

METRIC_DIMENSIONS: dict[str, str] = {
    "source_role_accuracy": "source_understanding",
    "provenance": "provenance",
    "high_critical_grounding_rate": "provenance",
    "entity_resolution_precision": "entity_resolution",
    "false_merge_count": "entity_resolution",
    "claim_accuracy": "claim_accuracy",
    "claim_precision": "claim_accuracy",
    "claim_recall": "claim_accuracy",
    "critical_relation_precision": "relation_precision",
    "critical_relation_recall": "relation_precision",
    "cross_source_finding_quality": "cross_source_reasoning",
    "financial_state_accuracy": "financial_intelligence",
    "exact_numeric_accuracy": "financial_intelligence",
    "financial_top_category_accuracy": "financial_intelligence",
    "financial_top_line_accuracy": "financial_intelligence",
    "feedback_target_accuracy": "feedback_linking",
    "outcome_granularity": "outcome_granularity",
    "recall_at_3": "retrieval_quality",
    "mrr": "retrieval_quality",
    "semantic_relevance": "retrieval_quality",
    "uncertainty_calibration": "uncertainty_calibration",
    "conflict_preservation": "uncertainty_calibration",
    "authority_resolution_accuracy": "uncertainty_calibration",
    # métricas de erro são invertidas na função abaixo
    "false_executed_without_evidence": "uncertainty_calibration",
    "lost_project_solution_overgeneralization": "outcome_granularity",
    "forbidden_inference_count": "generalization",
}

ERROR_METRICS = {
    "false_merge_count",
    "false_executed_without_evidence",
    "lost_project_solution_overgeneralization",
    "forbidden_inference_count",
}


def metric_quality(metric: MetricResult) -> float | None:
    if metric.value is None or metric.status != "scored":
        return None
    if metric.name in ERROR_METRICS:
        # 0 erros = 1; 1+ erro = degrada rapidamente e nunca fica negativo.
        return max(0.0, 1.0 - float(metric.value))
    return max(0.0, min(1.0, float(metric.value)))


def case_score(metrics: Sequence[MetricResult]) -> float | None:
    vals = [q for q in (metric_quality(m) for m in metrics) if q is not None]
    return sum(vals) / len(vals) if vals else None


def compute_dimension_scores(suite: Mapping[str, Any], case_results: Sequence[CaseResult]) -> dict[str, float | None]:
    buckets: dict[str, list[float]] = {str(d): [] for d in _list(suite.get("dimensions"))}
    for case in case_results:
        for metric in case.metrics:
            dim = METRIC_DIMENSIONS.get(metric.name)
            q = metric_quality(metric)
            if dim and q is not None:
                buckets.setdefault(dim, []).append(q)
    return {dim: (sum(vals) / len(vals) if vals else None) for dim, vals in buckets.items()}


def _aggregate_signal(case_results: Sequence[CaseResult], name: str, case_filter: Callable[[CaseResult], bool] | None = None) -> list[Any]:
    vals = []
    for case in case_results:
        if case_filter and not case_filter(case):
            continue
        value = case.gate_signals.get(name)
        if value is not None:
            vals.append(value)
    return vals


def evaluate_gates(
    suite: Mapping[str, Any],
    case_results: Sequence[CaseResult],
    *,
    baseline: Mapping[str, Any] | None = None,
    regression_tolerance: float = 0.03,
) -> list[GateResult]:
    cfg = suite.get("gates") if isinstance(suite.get("gates"), dict) else {}
    gates: list[GateResult] = []

    vals = _aggregate_signal(case_results, "high_critical_grounding_rate")
    if vals:
        actual = min(float(v) for v in vals)
        expected = float(cfg.get("high_critical_findings_grounded_rate", 1.0))
        gates.append(GateResult("high_critical_findings_grounded_rate", "pass" if actual >= expected else "fail", actual, expected))
    else:
        gates.append(GateResult("high_critical_findings_grounded_rate", "not_evaluated", details="nenhum finding high/critical avaliado"))

    vals = _aggregate_signal(case_results, "exact_numeric_accuracy", lambda c: c.case_type == "golden_real_project")
    if vals:
        actual = min(float(v) for v in vals)
        expected = float(cfg.get("golden_financial_total_accuracy", 1.0))
        gates.append(GateResult("golden_financial_total_accuracy", "pass" if actual >= expected else "fail", actual, expected))
    else:
        gates.append(GateResult("golden_financial_total_accuracy", "not_evaluated"))

    vals = _aggregate_signal(case_results, "false_executed_without_evidence")
    if vals:
        actual = sum(float(v) for v in vals)
        expected = float(cfg.get("false_executed_without_evidence", 0))
        gates.append(GateResult("false_executed_without_evidence", "pass" if actual <= expected else "fail", actual, expected))
    else:
        gates.append(GateResult("false_executed_without_evidence", "not_evaluated"))

    vals = _aggregate_signal(case_results, "lost_project_solution_overgeneralization")
    if vals:
        actual = sum(float(v) for v in vals)
        expected = float(cfg.get("lost_project_solution_overgeneralization", 0))
        gates.append(GateResult("lost_project_solution_overgeneralization", "pass" if actual <= expected else "fail", actual, expected))
    else:
        gates.append(GateResult("lost_project_solution_overgeneralization", "not_evaluated"))

    vals = _aggregate_signal(case_results, "critical_relation_precision")
    if vals:
        actual = min(float(v) for v in vals)
        expected = float(cfg.get("critical_relation_precision_min", 0.9))
        gates.append(GateResult("critical_relation_precision_min", "pass" if actual >= expected else "fail", actual, expected))
    else:
        gates.append(GateResult("critical_relation_precision_min", "not_evaluated"))

    vals = _aggregate_signal(case_results, "retrieval_recall_at_20")
    if vals:
        actual = min(float(v) for v in vals)
        expected = float(cfg.get("retrieval_recall_at_20_min", 0.95))
        gates.append(GateResult("retrieval_recall_at_20_min", "pass" if actual >= expected else "fail", actual, expected))
    else:
        gates.append(GateResult("retrieval_recall_at_20_min", "not_evaluated", details="dataset v1 ainda mede Recall@3"))

    # Blind regression precisa de baseline anterior real.
    if baseline:
        baseline_cases = {str(c.get("case_id")): c for c in _list(baseline.get("case_results")) if isinstance(c, dict)}
        regressions: list[str] = []
        evaluated = 0
        for case in case_results:
            if not case.case_type.startswith("blind") or case.score is None:
                continue
            prev = baseline_cases.get(case.case_id)
            if not prev or prev.get("score") is None:
                continue
            evaluated += 1
            if float(prev["score"]) - float(case.score) > regression_tolerance:
                regressions.append(f"{case.case_id}: {prev['score']:.3f} → {case.score:.3f}")
        if evaluated:
            gates.append(GateResult(
                "blind_project_regression_allowed",
                "pass" if not regressions else "fail",
                actual=len(regressions),
                expected=0,
                details="; ".join(regressions) if regressions else f"{evaluated} blind case(s) comparado(s)",
            ))
        else:
            gates.append(GateResult("blind_project_regression_allowed", "not_evaluated", details="baseline sem blind cases comparáveis"))
    else:
        gates.append(GateResult("blind_project_regression_allowed", "not_evaluated", details="execute com --baseline para comparar regressão"))

    return gates


# ---------------------------------------------------------------------------
# Validação de suíte
# ---------------------------------------------------------------------------

def validate_case(case: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("case_id", "case_type", "purpose"):
        if not case.get(key):
            errors.append(f"campo obrigatório ausente: {key}")
    if not (case.get("sources") or case.get("query")):
        errors.append("caso precisa de sources ou query")
    if not case.get("expected"):
        errors.append("expected ausente")
    if not case.get("metrics"):
        errors.append("metrics ausente")
    return errors


def load_suite(suite_path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    suite_path = Path(suite_path)
    suite = load_yaml(suite_path)
    case_ids = [str(x) for x in _list(suite.get("cases"))]
    if not case_ids:
        raise ValueError("suite.yaml não possui casos")
    cases: list[dict[str, Any]] = []
    for case_id in case_ids:
        path = suite_path.parent / "cases" / f"{case_id}.yaml"
        case = load_yaml(path)
        if str(case.get("case_id")) != case_id:
            raise ValueError(f"case_id não bate com suite: {path}")
        errors = validate_case(case)
        if errors:
            raise ValueError(f"Caso inválido {case_id}: " + "; ".join(errors))
        cases.append(case)
    return suite, cases


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def run_suite(
    suite_path: str | Path,
    adapter: Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any] | None] | None,
    *,
    fixture_dirs: Sequence[str | Path] = (),
    require_all: bool = False,
    require_fixtures: bool = False,
    baseline: Mapping[str, Any] | None = None,
    regression_tolerance: float = 0.03,
    validate_only: bool = False,
    metadata: Mapping[str, Any] | None = None,
) -> SuiteResult:
    started = datetime.now(timezone.utc)
    suite, cases = load_suite(suite_path)
    case_results: list[CaseResult] = []

    if validate_only:
        for case in cases:
            fixtures = resolve_fixtures(case, fixture_dirs)
            failures = []
            if require_fixtures and fixtures.get("required") and not fixtures.get("complete"):
                failures.append("fixtures reais ausentes ou SHA-256 divergente")
            case_results.append(CaseResult(
                case_id=str(case["case_id"]),
                case_type=str(case["case_type"]),
                status="failed" if failures else "passed",
                score=None,
                fixture_status=fixtures,
                failures=failures,
            ))
        finished = datetime.now(timezone.utc)
        return SuiteResult(
            suite_id=str(suite.get("suite_id")),
            suite_version=str(suite.get("version")),
            runner_version=RUNNER_VERSION,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            status="validate_only" if not any(c.failures for c in case_results) else "blocked",
            overall_score=None,
            dimension_scores={str(d): None for d in _list(suite.get("dimensions"))},
            case_results=case_results,
            gates=[],
            metadata=dict(metadata or {}),
        )

    if adapter is None:
        raise ValueError("adapter é obrigatório quando validate_only=False")

    for case in cases:
        fixtures = resolve_fixtures(case, fixture_dirs)
        failures: list[str] = []
        if require_fixtures and fixtures.get("required") and not fixtures.get("complete"):
            failures.append("fixtures reais ausentes ou SHA-256 divergente")
            case_results.append(CaseResult(
                case_id=str(case["case_id"]),
                case_type=str(case["case_type"]),
                status="failed",
                score=0.0,
                fixture_status=fixtures,
                failures=failures,
            ))
            continue
        try:
            candidate = adapter(case, fixtures)
            if candidate is None:
                status = "failed" if require_all else "not_run"
                case_results.append(CaseResult(
                    case_id=str(case["case_id"]),
                    case_type=str(case["case_type"]),
                    status=status,
                    score=0.0 if require_all else None,
                    fixture_status=fixtures,
                    failures=["resposta do pipeline ausente"] if require_all else [],
                ))
                continue
            metrics, signals = evaluate_case(case, candidate)
            score = case_score(metrics)
            case_results.append(CaseResult(
                case_id=str(case["case_id"]),
                case_type=str(case["case_type"]),
                status="passed",
                score=score,
                metrics=metrics,
                gate_signals=signals,
                fixture_status=fixtures,
            ))
        except Exception as exc:
            case_results.append(CaseResult(
                case_id=str(case["case_id"]),
                case_type=str(case["case_type"]),
                status="error",
                score=0.0,
                fixture_status=fixtures,
                failures=[f"{type(exc).__name__}: {exc}"],
            ))

    dimension_scores = compute_dimension_scores(suite, case_results)
    scored_cases = [c.score for c in case_results if c.score is not None and c.status == "passed"]
    overall = sum(scored_cases) / len(scored_cases) if scored_cases else None
    gates = evaluate_gates(
        suite,
        case_results,
        baseline=baseline,
        regression_tolerance=regression_tolerance,
    )
    any_fail = any(g.status == "fail" for g in gates) or any(c.status in {"failed", "error"} for c in case_results)
    any_not_eval = any(g.status == "not_evaluated" for g in gates) or any(c.status == "not_run" for c in case_results)
    status = "blocked" if any_fail else ("provisional" if any_not_eval else "pass")
    finished = datetime.now(timezone.utc)
    return SuiteResult(
        suite_id=str(suite.get("suite_id")),
        suite_version=str(suite.get("version")),
        runner_version=RUNNER_VERSION,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        status=status,
        overall_score=overall,
        dimension_scores=dimension_scores,
        case_results=case_results,
        gates=gates,
        metadata=dict(metadata or {}),
    )


# ---------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------

def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def render_markdown(result: SuiteResult) -> str:
    lines = [
        f"# NAVE IQ Bench — {result.suite_id}",
        "",
        f"- **Suite:** {result.suite_version}",
        f"- **Runner:** {result.runner_version}",
        f"- **Status:** {result.status.upper()}",
        f"- **Overall NAVE IQ:** {_pct(result.overall_score)}",
        "",
        "## Score por dimensão",
        "",
        "| Dimensão | Score |",
        "|---|---:|",
    ]
    for dim, score in result.dimension_scores.items():
        lines.append(f"| {dim} | {_pct(score)} |")
    lines.extend(["", "## Gates", "", "| Gate | Status | Atual | Exigido |", "|---|---|---:|---:|"])
    for g in result.gates:
        lines.append(f"| {g.name} | {g.status.upper()} | {g.actual if g.actual is not None else '—'} | {g.expected if g.expected is not None else '—'} |")
        if g.details:
            lines.append(f"\n> {g.name}: {g.details}\n")
    lines.extend(["", "## Casos", ""])
    for case in result.case_results:
        lines.append(f"### {case.case_id}")
        lines.append(f"**{case.status.upper()} · Score {_pct(case.score)}**")
        if case.fixture_status.get("required"):
            lines.append(f"Fixtures: {case.fixture_status.get('resolved', 0)}/{case.fixture_status.get('required', 0)} resolvidas.")
        if case.failures:
            for failure in case.failures:
                lines.append(f"- ❌ {failure}")
        if case.metrics:
            lines.append("")
            lines.append("| Métrica | Valor |")
            lines.append("|---|---:|")
            for metric in sorted(case.metrics, key=lambda x: x.name):
                if metric.value is None:
                    value = "N/E"
                elif metric.name in ERROR_METRICS:
                    value = f"{metric.value:g}"
                else:
                    value = _pct(metric.value)
                lines.append(f"| {metric.name} | {value} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_reports(result: SuiteResult, output_dir: str | Path, run_id: str | None = None) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out / f"{run_id}.json"
    md_path = out / f"{run_id}.md"
    json_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")
    return json_path, md_path


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("baseline precisa ser objeto JSON")
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NAVE IQ Bench Runner v1")
    parser.add_argument("--suite", default="evals/suite.yaml", help="Caminho para suite.yaml")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--responses", help="Diretório com <case_id>.json")
    source.add_argument("--adapter", help="Callable em formato modulo:function")
    parser.add_argument("--fixtures", action="append", default=[], help="Diretório autorizado de fixtures; pode repetir")
    parser.add_argument("--require-fixtures", action="store_true", help="Falha casos reais se fixture/hash não estiver disponível")
    parser.add_argument("--require-all", action="store_true", help="Falha se faltar resposta para qualquer caso")
    parser.add_argument("--validate-only", action="store_true", help="Valida suíte e fixtures sem executar pipeline")
    parser.add_argument("--baseline", help="JSON de execução anterior para regression gate")
    parser.add_argument("--regression-tolerance", type=float, default=0.03)
    parser.add_argument("--output", default="evals/results", help="Diretório dos relatórios")
    parser.add_argument("--run-id", help="Identificador do run")
    parser.add_argument("--pipeline-version", default="unknown")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.validate_only and not (args.responses or args.adapter):
        print("Erro: use --responses ou --adapter, ou execute com --validate-only.", file=sys.stderr)
        return 2
    adapter = None
    if args.responses:
        adapter = ResponseDirectoryAdapter(args.responses)
    elif args.adapter:
        adapter = load_callable(args.adapter)
    baseline = load_json(args.baseline) if args.baseline else None
    try:
        result = run_suite(
            args.suite,
            adapter,
            fixture_dirs=args.fixtures,
            require_all=args.require_all,
            require_fixtures=args.require_fixtures,
            baseline=baseline,
            regression_tolerance=args.regression_tolerance,
            validate_only=args.validate_only,
            metadata={"pipeline_version": args.pipeline_version},
        )
        json_path, md_path = write_reports(result, args.output, args.run_id)
        if not args.quiet:
            print(render_markdown(result))
            print(f"JSON: {json_path}")
            print(f"Markdown: {md_path}")
        return 1 if result.status == "blocked" else 0
    except Exception as exc:
        print(f"IQ Bench falhou antes da execução: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
