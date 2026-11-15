"""Explainable Agricultural AI — explicações geradas a partir dos resultados do motor.

As frases são montadas por regras a partir dos números calculados (nada é
inventado aqui). Cada afirmação aponta para um indicador com valor, unidade e
fonte. O índice de confiança mede a COMPLETUDE DAS EVIDÊNCIAS — não é a
probabilidade de sucesso da lavoura.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from . import catalogo
from .clima import MESES_PT
from .rotacao import ESTAB_DIAS, ESTAB_MIN_MM, LIMIAR_QUEBRA, OBJETIVOS

PESO_CONFIANCA = {"literatura": 1.0, "literatura_aproximada": 0.75, "analogo": 0.5,
                  "estimativa_equipe": 0.5, "ausente": 0.0}
ATRIBUTOS_CONF = ["ciclo_dias", "kc", "ky", "tmax_critica_c", "tbase_c", "protecao_solo"]

DESCRICOES = {
    "A": ("Rotação atual", "Continuidade do manejo informado pelo agricultor — referência de comparação."),
    "B": ("Conservação do solo", "Prioriza cobertura vegetal, leguminosas fixadoras de N, aporte de biomassa e menor exposição à erosão."),
    "C": ("Resiliência hídrica", "Prioriza menor demanda de água não suprida pela chuva e menor vulnerabilidade climática."),
    "D": ("Equilíbrio pelas suas prioridades", "Solução da fronteira de Pareto que melhor atende aos pesos definidos pelo agricultor."),
}

def _br(v, nd: int = 2) -> str:
    """Número no padrão pt-BR (vírgula decimal)."""
    return f"{v:.{nd}f}".replace(".", ",")



def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{100 * x:.0f}%"


def confianca(slots_culturas: List[str], n_anos: int, solo_informado: bool,
              declividade_disponivel: bool, local_calibrado: bool) -> dict:
    comps = {}
    comps["serie_climatica"] = min(1.0, n_anos / 30.0)
    notas = []
    for cid in set(slots_culturas):
        c = catalogo.obter(cid)
        for a in ATRIBUTOS_CONF:
            notas.append(PESO_CONFIANCA.get(c.confianca.get(a, "ausente"), 0.0))
    comps["parametros_culturas"] = sum(notas) / len(notas) if notas else 0.0
    comps["dados_solo_locais"] = 1.0 if solo_informado else 0.0
    comps["topografia"] = 1.0 if declividade_disponivel else 0.0
    comps["observacao_satelite_numerica"] = 0.0
    comps["calibracao_local"] = 1.0 if local_calibrado else 0.0
    valor = 100 * sum(comps.values()) / len(comps)
    rotulo = "alta" if valor >= 75 else "moderada" if valor >= 50 else "baixa"
    return {"valor": round(valor, 0), "rotulo": rotulo,
            "componentes": {k: round(v, 2) for k, v in comps.items()},
            "nota": "Completude das evidências usadas na análise. NÃO é probabilidade de sucesso agrícola.",
            "o_que_aumentaria": [k for k, v in comps.items() if v < 1.0]}


def _comparar(obj: Dict[str, float], ref: Dict[str, float]) -> List[dict]:
    out = []
    for k, meta in OBJETIVOS.items():
        a, b = obj.get(k), ref.get(k)
        if a is None or b is None:
            continue
        delta = a - b
        melhor = delta < 0 if meta["sentido"] == "min" else delta > 0
        out.append({"objetivo": k, "nome": meta["nome"], "valor": a, "referencia": b,
                    "delta": round(delta, 4), "melhor_que_atual": bool(melhor and abs(delta) > 1e-6),
                    "unidade": meta["unidade"]})
    return out


def explicar(chave: str, av: dict, ref: Optional[dict], ind_clima: dict, conf: dict,
             irrigacao_mm_ano: float) -> dict:
    titulo, objetivo = DESCRICOES[chave]
    o, ind = av["objetivos"], av["indicadores"]
    slots = av.get("slots", [])
    comps = _comparar(o, ref["objetivos"]) if ref is not None and chave != "A" else []
    por_que: List[str] = []
    chuvosos = ind_clima.get("meses_chuvosos_nomes") or []
    ia = ind_clima.get("indice_aridez")
    if ia is not None:
        por_que.append(f"O local tem índice de aridez {_br(ia, 2)} ({ind_clima.get('classe_aridez')}) e estação chuvosa "
                       f"de {len(chuvosos)} mês(es) pelo critério P ≥ 0,5·ET0 ({', '.join(chuvosos) or 'nenhum'}).")
    if chave != "A":
        for cmp_ in comps:
            if cmp_["melhor_que_atual"]:
                if cmp_["objetivo"] == "demanda_irrigacao_mm_ano":
                    por_que.append(f"Reduz a demanda hídrica não suprida pela chuva de {cmp_['referencia']:.0f} para "
                                   f"{cmp_['valor']:.0f} mm/ano em relação à rotação atual.")
                else:
                    por_que.append(f"{cmp_['nome']}: {_br(cmp_['referencia'], 2)} → {_br(cmp_['valor'], 2)} (rotação atual → esta estratégia).")
        if irrigacao_mm_ano <= 0:
            por_que.append(f"Em sequeiro, só foram aceitas semeaduras em meses com chuva mediana ≥ {ESTAB_MIN_MM:.0f} mm "
                           f"nos primeiros {ESTAB_DIAS} dias (critério de estabelecimento do NASA1).")
        leg = [s["nome"] for s in slots if catalogo.obter(s["cultura"]).fixa_nitrogenio]
        bio = [s["nome"] for s in slots if catalogo.obter(s["cultura"]).alta_biomassa]
        tol = [s["nome"] for s in slots if s["tmax_critica_c"] >= 38]
        if leg:
            por_que.append(f"Inclui leguminosas fixadoras de nitrogênio: {', '.join(dict.fromkeys(leg))}.")
        if bio:
            por_que.append(f"Inclui culturas de alto aporte de biomassa/cobertura: {', '.join(dict.fromkeys(bio))}.")
        if tol and chave in ("C", "D"):
            por_que.append(f"Usa culturas com maior tolerância térmica de referência (≥ 38 °C): {', '.join(dict.fromkeys(tol))}.")
    else:
        por_que.append("É o manejo atual informado; serve de referência com o mesmo horizonte (24 meses) e a mesma série climática.")

    evidencias = [
        {"indicador": "Precipitação anual média", "valor": round(ind_clima["precipitacao_anual_media_mm"]), "unidade": "mm/ano",
         "fonte": "NASA POWER PRECTOTCORR", "periodo": f"{ind_clima['periodo']['inicio']}–{ind_clima['periodo']['fim']}"},
        {"indicador": "ET0 anual média (Hargreaves)", "valor": round(ind_clima["et0_anual_media_mm"]), "unidade": "mm/ano",
         "fonte": "NASA POWER T2M/T2M_MAX/T2M_MIN + FAO-56 Eq. 52", "periodo": f"{ind_clima['periodo']['inicio']}–{ind_clima['periodo']['fim']}"},
        {"indicador": "Dias com Tmax ≥ 35 °C", "valor": round(ind_clima["dias_calor_ano_medio"]), "unidade": "dias/ano",
         "fonte": "NASA POWER T2M_MAX", "periodo": f"{ind_clima['periodo']['inicio']}–{ind_clima['periodo']['fim']}"},
    ]
    for s in slots:
        evidencias.append({"indicador": f"{s['nome']} ({s['mes_nome']}, ano {s['ano']}): ETc × chuva efetiva",
                           "valor": f"{s['etc_mm']:.0f} × {s['chuva_efetiva_mm']:.0f}", "unidade": "mm/ciclo (média)",
                           "fonte": "FAO-56 Kc × ET0; chuva efetiva USDA-SCS", "periodo": f"{ind['periodo_avaliado'][0]}–{ind['periodo_avaliado'][1]}"})

    beneficios: List[str] = []
    if ref is not None and chave != "A":
        ro, ri = ref["objetivos"], ref["indicadores"]
        if o["melhoria_solo"] > ro["melhoria_solo"]:
            tem_leg = any(catalogo.obter(s["cultura"]).fixa_nitrogenio for s in slots)
            tem_bio = any(catalogo.obter(s["cultura"]).alta_biomassa for s in slots)
            fontes_ganho = [x for x, ok in (("fixação biológica de N", tem_leg), ("aporte de palhada/matéria orgânica", tem_bio)) if ok]
            beneficios.append("Potencial de melhoria do solo por " + " e ".join(fontes_ganho or ["maior presença de plantas vivas"])
                              + ", a ser confirmado com análise de solo ao longo dos anos.")
        if o["potencial_erosao"] < ro["potencial_erosao"]:
            beneficios.append(f"Menos chuva erosiva caindo sobre solo descoberto (potencial {_br(ro['potencial_erosao'], 2)} → {_br(o['potencial_erosao'], 2)}).")
        if ind["risco_quebra_anos"] < ri["risco_quebra_anos"]:
            beneficios.append(f"Na série histórica, a fração de anos-safra com perda potencial por falta de água > {int(LIMIAR_QUEBRA * 100)}% por déficit hídrico "
                              f"cai de {_pct(ri['risco_quebra_anos'])} para {_pct(ind['risco_quebra_anos'])}.")
        if o["diversificacao"] > ro["diversificacao"]:
            beneficios.append("Maior diversificação de espécies e famílias botânicas, o que tende a quebrar ciclos de pragas e doenças.")
    if not beneficios and chave != "A":
        beneficios.append("Nenhum ganho claro em relação à rotação atual nos objetivos avaliados.")

    riscos: List[str] = []
    if ind["risco_quebra_anos"] > 0:
        riscos.append(f"Em {_pct(ind['risco_quebra_anos'])} das observações de ano-safra (pares de anos sobrepostos da série) ao menos uma cultura comercial teria "
                      f"perda potencial > {int(LIMIAR_QUEBRA * 100)}% por falta de água.")
    if ind.get("falha_estabelecimento_anos"):
        riscos.append(f"Em {_pct(ind['falha_estabelecimento_anos'])} dos anos, a chuva dos primeiros {ESTAB_DIAS} dias de alguma "
                      f"semeadura ficou abaixo de {ESTAB_MIN_MM:.0f} mm (risco de falha de germinação/replantio).")
    for s in slots:
        if s.get("fracao_dias_frio", 0) >= 0.05:
            riscos.append(f"{s['nome']}: {_pct(s['fracao_dias_frio'])} dos dias do ciclo abaixo de {s['tbase_c']:.0f} °C ou com geada.")
        if s["fracao_dias_calor"] >= 0.2:
            riscos.append(f"{s['nome']}: {_pct(s['fracao_dias_calor'])} dos dias do ciclo com Tmax ≥ {s['tmax_critica_c']:.0f} °C "
                          "(limiar de referência da cultura).")
    riscos += av.get("alertas_fitossanitarios", [])
    riscos += av.get("restricoes", {}).get("mensagens", [])
    if av.get("ky_assumido_1"):
        riscos.append("Fator Ky da FAO-33 não tabelado para: " + ", ".join(av["ky_assumido_1"])
                      + " (assumido Ky = 1,0 na estimativa de perda).")
    if any(s["tipo"] == "cobertura" for s in slots):
        riscos.append("Culturas de cobertura não geram renda direta e exigem semente e operação de manejo.")
    riscos.append("Potencial econômico não avaliado: faltam preços e produtividades locais confiáveis.")

    ausentes = []
    if conf["componentes"]["dados_solo_locais"] < 1:
        ausentes.append("Análise de solo do talhão (textura, matéria orgânica, pH).")
    if conf["componentes"]["topografia"] < 1:
        ausentes.append("Declividade do terreno (informe ou obtenha via SRTM com internet).")
    ausentes.append("Observações numéricas de NDVI/SMAP por talhão (apenas camadas visuais nesta versão).")
    if conf["componentes"]["calibracao_local"] < 1:
        ausentes.append("Calibração local dos parâmetros das culturas.")
    estimados = sorted({catalogo.obter(s["cultura"]).nome for s in slots
                        for a in ATRIBUTOS_CONF
                        if catalogo.obter(s["cultura"]).confianca.get(a) in ("estimativa_equipe", "analogo")})
    if estimados:
        ausentes.append("Parâmetros estimados/análogos (validar com agrônomo): " + ", ".join(estimados) + ".")

    return {"titulo": titulo, "objetivo": objetivo, "por_que": por_que, "evidencias": evidencias,
            "beneficios": beneficios, "riscos": list(dict.fromkeys(riscos)), "confianca": conf,
            "informacoes_ausentes": ausentes, "comparacao_com_atual": comps}
