"""Relatório em Markdown gerado a partir da análise (sem texto inventado)."""
from __future__ import annotations

from datetime import datetime, timezone

from . import catalogo
from .rotacao import OBJETIVOS


def _f(v, nd=2, suf=""):
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        return f"{v:.{nd}f}{suf}".replace(".", ",")
    return str(v)


def gerar_markdown(an: dict) -> str:
    p = an["propriedade"]
    c = an["clima"]
    ind = c["indicadores"]
    v = an["vulnerabilidade"]
    L = []
    L.append(f"# Relatório — {p.get('nome') or 'Propriedade'}")
    L.append(f"_Rotação Inteligente 2.0 · gerado em {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}_\n")
    if p.get("demonstrativa"):
        L.append("> **Propriedade demonstrativa.** Localização real; área, solo e rotação atual são exemplos para demonstração.\n")
    L.append("> **Como ler este relatório:** as perdas percentuais estimadas seguem o modelo FAO-33 de déficit hídrico (Ky × fração de água não atendida). **Não incluem danos por frio, geada, pragas ou doenças.** Um valor de 0% não significa produção garantida. Verifique os alertas de risco térmico e a viabilidade agronômica de cada sequência.\n")
    # Resumo antes das tabelas: mesma avaliação já calculada, sem nova previsão.
    estrategias = an.get("estrategias", [])
    escolha = next((e for e in estrategias if e.get("chave") == "D" and e["avaliacao"]["restricoes"].get("viavel")), None)
    if escolha is None:
        escolha = next((e for e in estrategias if e.get("chave") not in ("A",) and e["avaliacao"]["restricoes"].get("viavel")), None)
    L.append("## Resumo para o agricultor")
    L.append("**Atenção:** este resumo orienta comparações, não substitui análise de solo, visita técnica ou avaliação das culturas na região.")
    if escolha:
        av = escolha["avaliacao"]
        seq = " → ".join(f"{s['nome']} ({s['mes_nome']}, ano {s['ano']})" for s in av.get("slots", []))
        L.append(f"- **Alternativa conforme as prioridades informadas:** {escolha['chave']} — {escolha['titulo']} (não é superior em todos os critérios).")
        L.append(f"- **O que e quando plantar (simulação):** {seq}.")
        L.append(f"- **Demanda hídrica estimada:** {_f(av['indicadores']['etc_total_mm_ano'], 0)} mm/ano; **água não atendida:** {_f(av['objetivos']['demanda_irrigacao_mm_ano'], 0)} mm/ano.")
        L.append(f"- **Benefício potencial:** {escolha['explicacao'].get('objetivo') or 'depende dos critérios e dados disponíveis'}.")
        riscos = escolha["explicacao"].get("riscos", [])
        if riscos:
            L.append(f"- **Cuidados destacados:** {'; '.join(riscos[:2])}.")
        termicos = [f"{sl['nome']}: frio/geada em {_f(sl.get('fracao_dias_frio', 0)*100, 0)}% dos dias" for sl in av.get("slots", []) if sl.get("fracao_dias_frio", 0) >= 0.05]
        if termicos:
            L.append(f"- **Risco de frio/geada:** {'; '.join(termicos)}. Não incluído na perda potencial por falta de água.")
    else:
        L.append("- **Nenhuma alternativa agronomicamente elegível encontrada.** Revise parâmetros e calendário com um profissional.")
    L.append("- **Escopo do índice térmico regional:** considera calor extremo (Tmax ≥ 35 °C); risco de frio/geada é avaliado por cultura, separadamente.\n")
    L.append("## 1. Propriedade")
    local = ", ".join(x for x in (p.get("regiao"), p.get("pais")) if x) or "Localização não identificada"
    fonte_local = f" (fonte: {p['localidade_fonte']})" if p.get("localidade_fonte") and local != "Localização não identificada" else ""
    L.append(f"- Coordenadas: {p['lat']:.4f}, {p['lon']:.4f} — {local}{fonte_local}")
    if p.get("area_ha"):
        L.append(f"- Área: {_f(p['area_ha'], 1)} ha")
    solo = p.get("solo") or {}
    L.append(f"- Solo informado: textura {solo.get('textura') or 'não informada'}, MO {solo.get('materia_organica_pct') or '—'} %, pH {solo.get('ph') or '—'}")
    L.append(f"- Água para irrigação: {_f(p.get('irrigacao_mm_ano') or 0, 0)} mm/ano" + (" (sequeiro)" if not p.get("irrigacao_mm_ano") else ""))
    t = an["topografia"]
    L.append(f"- Declividade: {_f(t.get('declividade_pct'), 1, ' %')} ({t.get('fonte') or t.get('erro') or 'não disponível'})\n")

    L.append("## 2. Fontes de dados utilizadas")
    for f in an["fontes"]:
        if f["status"] == "integrado" and f["cobre_local"]:
            L.append(f"- **{f['nome']}** ({f['instituicao']}) — {f['uso']} Resolução: {f['resolucao_espacial']}; {f['resolucao_temporal']}.")
    L.append(f"- Período NASA POWER: {c['fonte']['periodo_dados'][0]} a {c['fonte']['periodo_dados'][1]} "
             f"({ind['periodo']['n_anos_completos']} anos completos usados: {ind['periodo']['inicio']}–{ind['periodo']['fim']}).")
    nao = [f["nome"] for f in an["fontes"] if f["status"] != "integrado"]
    L.append(f"- Não usados nos cálculos (visuais ou não integrados): {', '.join(nao)}.\n")

    L.append("## 3. Condições ambientais (observadas)")
    L.append("| Indicador | Valor |\n|---|---|")
    linhas = [
        ("Precipitação anual média", _f(ind["precipitacao_anual_media_mm"], 0, " mm")),
        ("ET0 anual média (Hargreaves)", _f(ind["et0_anual_media_mm"], 0, " mm")),
        ("Índice de aridez (P/ET0)", f"{_f(ind['indice_aridez'])} — {ind['classe_aridez']}"),
        ("Estação chuvosa (P ≥ 0,5·ET0)", ", ".join(ind["meses_chuvosos_nomes"]) or "nenhum mês"),
        ("CV da chuva anual", _f(ind["cv_precipitacao_anual"] * 100, 0, " %")),
        ("Maior veranico na estação chuvosa (média)", _f(ind["cdd_estacao_chuvosa_medio_dias"], 0, " dias")),
        ("Dias/ano com Tmax ≥ 35 °C", _f(ind["dias_calor_ano_medio"], 0)),
        ("Umidade da zona radicular (GWETROOT, modelo)", _f(ind["gwetroot_medio"])),
        ("Índice de Fournier modificado", f"{_f(ind['indice_fournier_modificado'], 0)} — erosividade {ind['classe_erosividade']}"),
        ("Tendência Tmax", f"{_f(ind['tendencia_tmax_c']['inclinacao_por_decada'])} °C/década (p = {_f(ind['tendencia_tmax_c']['p_valor'], 3)})"),
        ("Tendência chuva anual", f"{_f(ind['tendencia_precipitacao_mm']['inclinacao_por_decada'], 0)} mm/década (p = {_f(ind['tendencia_precipitacao_mm']['p_valor'], 3)})"),
    ]
    for a, b in linhas:
        L.append(f"| {a} | {b} |")
    L.append("")
    L.append(f"**Vulnerabilidade agrícola (índice experimental):** {_f(v['indice'])} — **{v['classe']}** "
             f"({v['n_indicadores']} indicadores; {v['metodo']}).\n")

    L.append("## 4. Estratégias comparadas (horizonte de 24 meses, mesma série climática)")
    L.append("| Objetivo | " + " | ".join(f"{e['chave']} — {e['titulo']}" for e in an["estrategias"]) + " |")
    L.append("|---|" + "---|" * len(an["estrategias"]))
    for k, meta in OBJETIVOS.items():
        seta = "↓" if meta["sentido"] == "min" else "↑"
        L.append(f"| {meta['nome']} ({meta['unidade']}) {seta} | "
                 + " | ".join(_f(e["avaliacao"]["objetivos"][k], 0 if "mm" in meta["unidade"] else 2) for e in an["estrategias"]) + " |")
    L.append("| Anos-safra com perda potencial por falta de água > 50% | " + " | ".join(_f(e["avaliacao"]["indicadores"]["risco_quebra_anos"] * 100, 0, " %") for e in an["estrategias"]) + " |")
    L.append("| Dívida Ambiental do Solo (DAS, 0–100) ↓ | " + " | ".join(_f(e["avaliacao"]["das"]["valor"], 0) for e in an["estrategias"]) + " |")
    L.append("")
    for e in an["estrategias"]:
        ex = e["explicacao"]
        seq = " → ".join(f"{s['nome']} (semeadura {s['mes_nome']}, ano {s['ano']})" for s in e["avaliacao"]["slots"])
        L.append(f"### Estratégia {e['chave']} — {ex['titulo']}")
        L.append(f"_{ex['objetivo']}_\n")
        L.append(f"**Sequência:** {seq}\n")
        if not e["avaliacao"]["restricoes"]["viavel"]:
            L.append("**ATENÇÃO: sequência fora das restrições agronômicas.** "
                     "A rotação atual, quando assim classificada, é somente referência histórica, não recomendação segura.\n")
        L.append("**Como interpretar:** 0% de perda por falta de água não significa risco agrícola nulo; "
                 "o índice de atendimento disponível considera também a exposição ao frio, mas a porcentagem de perda não.\n")
        for slot in e["avaliacao"]["slots"]:
            L.append(f"- {slot['nome']}: perda potencial **por falta de água** de "
                     f"{_f(slot['perda_rendimento_media'] * 100, 0)}%; "
                     f"dias com frio/geada {_f(slot.get('fracao_dias_frio', 0) * 100, 0)}%. "
                     "Os efeitos térmicos não entram na porcentagem de perda hídrica.")
        L.append("**Por que foi sugerida:**")
        L += [f"- {x}" for x in ex["por_que"]]
        L.append("\n**Benefícios potenciais (não garantidos):**")
        L += [f"- {x}" for x in ex["beneficios"]] or ["- —"]
        L.append("\n**Riscos e restrições:**")
        L += [f"- {x}" for x in ex["riscos"]]
        L.append(f"\n**Completude das evidências:** {_f(ex['confianca']['valor'], 0)}/100 ({ex['confianca']['rotulo']}). "
                 f"{ex['confianca']['nota']}\n")

    L.append("## 5. Limitações")
    L += [f"- {x}" for x in an["avisos_gerais"]]
    L.append("- Índice de vulnerabilidade e DAS são indicadores experimentais de triagem, com faixas documentadas em METHODOLOGY.md; "
             "a DAS não mede fertilidade, carbono ou degradação observada.")
    L.append("- Parâmetros de culturas marcados como estimativa/análogo precisam de validação agronômica local.")
    L.append("- Perda potencial (FAO-33) quantifica somente o componente de déficit hídrico; não estima danos por geadas, frio, doenças ou outros fatores.\n")
    L.append("- Potencial econômico não foi avaliado.\n")
    L.append("## 6. Recomendação")
    rec = next((e for e in an["estrategias"] if e["chave"] == "D"), None) or next(e for e in an["estrategias"] if e["chave"] == "C")
    L.append(f"Considerando as prioridades informadas, a estratégia **{rec['chave']} — {rec['explicacao']['titulo']}** é a que "
             "melhor equilibra os objetivos no modelo. Antes de adotar, valide com assistência técnica local, faça análise "
             "de solo e teste em uma parte da área.\n")
    L.append("---\n_Ferramenta de apoio. Não substitui o julgamento do agricultor nem a orientação de especialistas locais._")
    return "\n".join(L)
