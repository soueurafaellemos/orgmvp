from __future__ import annotations

import streamlit as st

from coverage_diagnostic import (
    CoverageDiagnostic,
    coerce_coverage_diagnostic,
    diagnostic_dataframe,
    diagnostic_json_bytes,
    suggestions_dataframe,
)


def render_coverage_diagnostic(
    value: CoverageDiagnostic | dict | None,
    *,
    heading: str = "Diagnóstico de cobertura",
    expanded: bool = True,
    download_key: str = "coverage_diagnostic",
    default_mode: str | None = None,
) -> None:
    if not value:
        return

    try:
        diagnostic = (
            coerce_coverage_diagnostic(
                value,
                default_mode=default_mode,
            )
        )
    except Exception as exc:
        st.warning(
            "O diagnóstico salvo utiliza uma estrutura "
            "antiga ou incompleta. O restante do projeto "
            "continua disponível normalmente."
        )

        if isinstance(value, dict):
            summary = str(
                value.get("summary")
                or ""
            ).strip()
            if summary:
                st.write(summary)

        with st.expander(
            "Detalhe técnico do diagnóstico",
            expanded=False,
        ):
            st.code(
                str(exc)
            )
        return

    if diagnostic is None:
        return

    st.subheader(heading)
    st.caption(
        "A NAVE compara o conteúdo da fonte com o que ficou consultável. "
        "O diagnóstico também separa falhas de extração de possíveis "
        "evoluções da estrutura da plataforma."
    )

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Cobertura estimada", f"{diagnostic.coverage_score}%")
    metric2.metric("Unidades com conteúdo", diagnostic.source_units_meaningful)
    metric3.metric("Unidades cobertas", diagnostic.source_units_covered)
    metric4.metric("Registros estruturados", diagnostic.structured_records)

    st.write(diagnostic.summary)

    findings = diagnostic_dataframe(diagnostic)
    suggestions = suggestions_dataframe(diagnostic)

    with st.expander("Ver diagnóstico detalhado", expanded=expanded):
        if findings.empty:
            st.success(
                "Nenhuma lacuna relevante foi identificada nesta análise."
            )
        else:
            st.dataframe(
                findings,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Confiança": st.column_config.ProgressColumn(
                        "Confiança",
                        min_value=0,
                        max_value=100,
                        format="%.1f%%",
                    )
                },
            )

        st.markdown("### Evoluções sugeridas para a NAVE")
        if suggestions.empty:
            st.info(
                "O conteúdo que ficou de fora cabe nas áreas atuais; "
                "a melhoria necessária é de extração ou classificação."
            )
        else:
            st.dataframe(
                suggestions,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Confiança": st.column_config.ProgressColumn(
                        "Confiança",
                        min_value=0,
                        max_value=100,
                        format="%.1f%%",
                    )
                },
            )

        if diagnostic.warnings:
            st.markdown("### Alertas técnicos")
            for warning in diagnostic.warnings:
                st.write("• " + str(warning))

        st.download_button(
            "Baixar diagnóstico",
            diagnostic_json_bytes(diagnostic),
            "diagnostico_cobertura_nave.json",
            mime="application/json",
            use_container_width=True,
            key=f"download_{download_key}",
        )
