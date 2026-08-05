from __future__ import annotations

from collections import defaultdict
from typing import Any


SEVERITY_ORDER = {
    "Crítica": 0,
    "Importante": 1,
    "Enriquecimento": 2,
}

FIELD_LABELS = {
    "project_name": "nome do projeto",
    "objective": "objetivo",
    "audience_profile": "perfil do público",
    "audience_quantity": "quantidade ou público estimado",
    "budget_total_brl": "budget total",
    "budget_unit_brl": "budget unitário",
    "location_city": "cidade",
    "location_state": "estado",
    "event_date": "data do evento",
    "available_days": "prazo disponível",
    "desired_types": "tipo de entrega procurada",
    "desired_attributes": "atributos desejados",
    "restrictions": "restrições",
}

FIELD_WEIGHTS = {
    "project_name": 4,
    "objective": 14,
    "audience_profile": 9,
    "audience_quantity": 13,
    "budget": 16,
    "location": 10,
    "event_date": 10,
    "available_days": 10,
    "desired_types": 8,
    "desired_attributes": 4,
    "restrictions": 2,
}


def _filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    if isinstance(value, (int, float)):
        return value > 0
    return bool(str(value).strip())


def _issue(
    *,
    severity: str,
    category: str,
    title: str,
    finding: str,
    question: str,
    responsible: str,
    impact: str,
    blocks: bool,
    source_support: str | None = None,
) -> dict:
    return {
        "severity": severity,
        "category": category,
        "title": title,
        "finding": finding,
        "question": question,
        "responsible": responsible,
        "impact": impact,
        "blocks_recommendation": blocks,
        "source_support": source_support,
    }


def calculate_completeness(brief: dict) -> int:
    score = 0

    if _filled(brief.get("project_name")):
        score += FIELD_WEIGHTS["project_name"]
    if _filled(brief.get("objective")):
        score += FIELD_WEIGHTS["objective"]
    if _filled(brief.get("audience_profile")):
        score += FIELD_WEIGHTS["audience_profile"]
    if _filled(brief.get("audience_quantity")):
        score += FIELD_WEIGHTS["audience_quantity"]
    if (
        _filled(brief.get("budget_total_brl"))
        or _filled(brief.get("budget_unit_brl"))
    ):
        score += FIELD_WEIGHTS["budget"]
    if (
        _filled(brief.get("location_city"))
        or _filled(brief.get("location_state"))
    ):
        score += FIELD_WEIGHTS["location"]
    if _filled(brief.get("event_date")):
        score += FIELD_WEIGHTS["event_date"]
    if _filled(brief.get("available_days")):
        score += FIELD_WEIGHTS["available_days"]
    if _filled(brief.get("desired_types")):
        score += FIELD_WEIGHTS["desired_types"]
    if _filled(brief.get("desired_attributes")):
        score += FIELD_WEIGHTS["desired_attributes"]
    if _filled(brief.get("restrictions")):
        score += FIELD_WEIGHTS["restrictions"]

    return min(100, int(score))


def _deterministic_issues(brief: dict) -> list[dict]:
    issues: list[dict] = []
    desired_types = set(brief.get("desired_types") or [])

    if not _filled(brief.get("objective")):
        issues.append(
            _issue(
                severity="Crítica",
                category="Objetivo",
                title="Objetivo não definido",
                finding=(
                    "O briefing não explicita o resultado que a marca "
                    "pretende gerar com a iniciativa."
                ),
                question=(
                    "Qual comportamento, percepção ou resultado o projeto "
                    "precisa provocar no público?"
                ),
                responsible="Atendimento",
                impact="Aderência",
                blocks=True,
            )
        )

    if not _filled(brief.get("budget_total_brl")) and not _filled(
        brief.get("budget_unit_brl")
    ):
        issues.append(
            _issue(
                severity="Crítica",
                category="Budget",
                title="Budget não informado",
                finding=(
                    "Não há verba total nem valor de referência por pessoa."
                ),
                question=(
                    "Qual é o budget disponível e o que precisa estar "
                    "contemplado nesse valor?"
                ),
                responsible="Atendimento",
                impact="Budget",
                blocks=True,
            )
        )

    if not _filled(brief.get("audience_quantity")):
        severity = (
            "Crítica"
            if desired_types & {"product", "venue"}
            else "Importante"
        )
        issues.append(
            _issue(
                severity=severity,
                category="Quantidade",
                title="Escala não confirmada",
                finding=(
                    "O briefing não informa a quantidade de participantes, "
                    "unidades ou pessoas impactadas."
                ),
                question=(
                    "Qual é o público estimado e a entrega será para todos, "
                    "vencedores, convidados VIP ou grupos específicos?"
                ),
                responsible="Atendimento",
                impact="Escala",
                blocks=severity == "Crítica",
            )
        )

    if not _filled(brief.get("audience_profile")):
        issues.append(
            _issue(
                severity="Importante",
                category="Público",
                title="Perfil do público incompleto",
                finding=(
                    "Não há informações suficientes sobre perfil, contexto "
                    "ou motivadores do público."
                ),
                question=(
                    "Quem é o público prioritário e quais hábitos, interesses "
                    "ou barreiras devem orientar a solução?"
                ),
                responsible="Atendimento",
                impact="Aderência",
                blocks=False,
            )
        )

    if not _filled(brief.get("event_date")):
        issues.append(
            _issue(
                severity="Importante",
                category="Data",
                title="Data do evento não confirmada",
                finding=(
                    "A data não foi identificada de forma inequívoca."
                ),
                question=(
                    "Qual é a data confirmada do evento e existem marcos "
                    "anteriores de aprovação, produção ou montagem?"
                ),
                responsible="Produção",
                impact="Prazo",
                blocks=False,
            )
        )

    if not _filled(brief.get("available_days")):
        issues.append(
            _issue(
                severity="Crítica",
                category="Prazo",
                title="Janela de produção não definida",
                finding=(
                    "Não foi possível validar quantos dias estão disponíveis "
                    "para cotação, aprovação, produção e entrega."
                ),
                question=(
                    "Qual é o prazo real disponível e qual é a data-limite "
                    "para aprovação final?"
                ),
                responsible="Produção",
                impact="Prazo",
                blocks=True,
            )
        )

    if not (
        _filled(brief.get("location_city"))
        or _filled(brief.get("location_state"))
    ):
        severity = (
            "Crítica"
            if desired_types & {"activation", "venue"}
            else "Importante"
        )
        issues.append(
            _issue(
                severity=severity,
                category="Localização",
                title="Localização não informada",
                finding=(
                    "Cidade e estado não estão claros no material."
                ),
                question=(
                    "Onde acontecerá o evento ou a entrega e existem "
                    "restrições de acesso, frete ou montagem?"
                ),
                responsible="Produção",
                impact="Logística",
                blocks=severity == "Crítica",
            )
        )

    if not _filled(brief.get("desired_types")):
        issues.append(
            _issue(
                severity="Crítica",
                category="Escopo",
                title="Escopo da busca indefinido",
                finding=(
                    "Não está claro se a consulta deve buscar brindes, "
                    "ativações, locais ou uma combinação."
                ),
                question=(
                    "Quais categorias podem entrar na solução: brindes, "
                    "ativações, locais ou todas?"
                ),
                responsible="Atendimento",
                impact="Aderência",
                blocks=True,
            )
        )

    # Provocações estratégicas, sem transformar ausência em erro.
    if desired_types & {"product"}:
        issues.append(
            _issue(
                severity="Enriquecimento",
                category="Distribuição",
                title="Estratégia de distribuição",
                finding=(
                    "A forma de entrega pode alterar quantidade, percepção "
                    "de valor e desenho da experiência."
                ),
                question=(
                    "O brinde será entregue a todos, condicionado a uma "
                    "interação, destinado a vencedores ou segmentado por VIP?"
                ),
                responsible="Criação",
                impact="Experiência",
                blocks=False,
            )
        )

    if desired_types & {"activation"}:
        issues.append(
            _issue(
                severity="Enriquecimento",
                category="Mensuração",
                title="Critério de sucesso da ativação",
                finding=(
                    "A experiência pode ser mais útil se já nascer com uma "
                    "forma clara de mensuração."
                ),
                question=(
                    "Quais indicadores definirão sucesso: participação, "
                    "tempo de permanência, leads, conteúdo, ranking ou NPS?"
                ),
                responsible="Atendimento",
                impact="Mensuração",
                blocks=False,
            )
        )

    if desired_types & {"venue"}:
        issues.append(
            _issue(
                severity="Enriquecimento",
                category="Experiência",
                title="Atmosfera e flexibilidade do local",
                finding=(
                    "Capacidade e preço não são os únicos critérios relevantes "
                    "para a escolha do espaço."
                ),
                question=(
                    "Quais atributos de atmosfera, exclusividade, mobilidade "
                    "e possibilidade cenográfica são indispensáveis?"
                ),
                responsible="Criação",
                impact="Experiência",
                blocks=False,
            )
        )

    return issues


def _dedupe_issues(issues: list[dict]) -> list[dict]:
    result = []
    seen = set()

    for issue in issues:
        key = (
            str(issue.get("category") or "").strip().lower(),
            str(issue.get("question") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)

    return sorted(
        result,
        key=lambda item: (
            SEVERITY_ORDER.get(item.get("severity"), 99),
            item.get("category") or "",
            item.get("title") or "",
        ),
    )


def build_diagnostic(brief: dict) -> dict:
    ai_issues = [
        dict(item)
        for item in (brief.get("diagnostic_items") or [])
        if isinstance(item, dict)
    ]
    issues = _dedupe_issues(
        _deterministic_issues(brief) + ai_issues
    )

    score = calculate_completeness(brief)
    critical_blockers = [
        item
        for item in issues
        if item.get("severity") == "Crítica"
        and item.get("blocks_recommendation")
    ]

    if score < 45:
        status = "Briefing insuficiente"
    elif critical_blockers:
        status = "Aguardando respostas do atendimento"
    elif score >= 82:
        status = "Pronto para recomendar"
    else:
        status = "Recomendação possível com ressalvas"

    return {
        "completeness_score": score,
        "readiness_status": status,
        "critical_blockers": len(critical_blockers),
        "issues": issues,
        "diagnostic_summary": (
            brief.get("diagnostic_summary")
            or _default_summary(status, score, len(critical_blockers))
        ),
        "recommended_next_step": (
            brief.get("recommended_next_step")
            or _default_next_step(status)
        ),
    }


def _default_summary(
    status: str,
    score: int,
    blockers: int,
) -> str:
    if status == "Pronto para recomendar":
        return (
            "O briefing possui os elementos centrais para uma consulta "
            "comparável e tecnicamente mais segura."
        )
    if status == "Recomendação possível com ressalvas":
        return (
            "A recomendação pode avançar, mas algumas respostas ainda podem "
            "alterar preço, aderência ou logística."
        )
    if status == "Aguardando respostas do atendimento":
        return (
            f"Foram identificadas {blockers} pendência(s) crítica(s). "
            "É recomendável confirmar esses pontos antes da decisão final."
        )
    return (
        "O material ainda não sustenta uma recomendação segura sem preencher "
        "informações essenciais."
    )


def _default_next_step(status: str) -> str:
    if status == "Pronto para recomendar":
        return "Gerar a recomendação e iniciar a validação com fornecedores."
    if status == "Recomendação possível com ressalvas":
        return (
            "Gerar alternativas preliminares e confirmar as pendências em "
            "paralelo."
        )
    return (
        "Enviar a pauta de complementação ao atendimento antes de fechar a "
        "recomendação."
    )


def generate_service_agenda(
    brief: dict,
    diagnostic: dict,
) -> str:
    project = brief.get("project_name") or "Projeto não identificado"
    source_files = brief.get("source_files") or []
    issues = diagnostic.get("issues") or []

    lines = [
        "PAUTA DE COMPLEMENTAÇÃO DO BRIEFING",
        "=" * 42,
        f"Projeto: {project}",
        f"Status: {diagnostic.get('readiness_status')}",
        f"Completude: {diagnostic.get('completeness_score')}%",
        "",
        "RESUMO DO ENTENDIMENTO",
        brief.get("source_summary") or "Não informado.",
        "",
    ]

    if source_files:
        lines.extend(
            [
                "FONTES ANALISADAS",
                *[f"- {name}" for name in source_files],
                "",
            ]
        )

    grouped = defaultdict(list)
    for issue in issues:
        grouped[issue.get("severity") or "Outro"].append(issue)

    labels = [
        ("Crítica", "1. PENDÊNCIAS CRÍTICAS"),
        ("Importante", "2. PENDÊNCIAS IMPORTANTES"),
        ("Enriquecimento", "3. PONTOS DE ENRIQUECIMENTO"),
    ]

    for severity, heading in labels:
        items = grouped.get(severity, [])
        if not items:
            continue

        lines.extend([heading, "-" * len(heading)])

        for index, item in enumerate(items, start=1):
            lines.extend(
                [
                    f"{index}. {item.get('title')}",
                    f"   Tema: {item.get('category')}",
                    f"   Responsável: {item.get('responsible')}",
                    f"   Impacto: {item.get('impact')}",
                    f"   Contexto: {item.get('finding')}",
                    f"   Pergunta: {item.get('question')}",
                ]
            )
            if item.get("source_support"):
                lines.append(
                    f"   Apoio da fonte: {item.get('source_support')}"
                )
            lines.append("")

    lines.extend(
        [
            "PRÓXIMO PASSO RECOMENDADO",
            diagnostic.get("recommended_next_step") or "",
            "",
            (
                "Observação: esta pauta foi gerada a partir das informações "
                "disponíveis e deve ser revisada pelo time antes do envio."
            ),
        ]
    )

    return "\n".join(lines)
