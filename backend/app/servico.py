"""Orquestração: transforma uma propriedade em análise completa (usado pela API)."""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Dict, List, Optional

import numpy as np

from . import catalogo, clima, explicabilidade, fontes, rotacao, topografia, vulnerabilidade
from .legacy import legacy_config

_CACHE: "OrderedDict[str, dict]" = OrderedDict()
_CACHE_MAX = 16

def _br(v, nd: int = 2) -> str:
    """Número no padrão pt-BR (vírgula decimal)."""
    return f"{v:.{nd}f}".replace(".", ",")



def _chave(d: dict) -> str:
    return hashlib.sha1(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()


def _solo_informado(solo: Optional[dict]) -> bool:
    if not solo:
        return False
    campos = ["textura", "profundidade_cm", "materia_organica_pct", "ph"]
    return sum(1 for c in campos if solo.get(c) not in (None, "")) >= 2


def resolver_declividade(prop: dict) -> dict:
    if prop.get("declividade_pct") is not None:
        return {"declividade_pct": float(prop["declividade_pct"]), "fonte": "informado pelo usuário", "erro": None}
    if prop.get("usar_srtm", True):
        try:
            t = topografia.obter(prop["lat"], prop["lon"])
            return {"declividade_pct": t["declividade_pct"], "elevacao_m": t["elevacao_m"],
                    "fonte": t["fonte"], "aviso": t["aviso"], "erro": None}
        except topografia.TopografiaError as e:
            return {"declividade_pct": None, "fonte": None, "erro": str(e)}
    return {"declividade_pct": None, "fonte": None, "erro": "não informado"}


def _alertas(ind: dict, vul: dict, aval_a: dict) -> List[dict]:
    out = []
    t = ind["tendencia_tmax_c"]
    if t.get("significativa") and t["inclinacao_por_decada"] > 0:
        out.append({"nivel": "alto", "titulo": "Aquecimento significativo",
                    "texto": f"Tmax média sobe {_br(t['inclinacao_por_decada'], 2)} °C por década "
                             f"(Theil-Sen, p = {_br(t['p_valor'], 3)}) na série NASA POWER."})
    tc = ind["tendencia_dias_calor"]
    if tc.get("significativa") and tc["inclinacao_por_decada"] > 0:
        out.append({"nivel": "alto", "titulo": "Mais dias de calor extremo",
                    "texto": f"+{tc['inclinacao_por_decada']:.0f} dias/ano com Tmax ≥ 35 °C a cada década."})
    tp = ind["tendencia_precipitacao_mm"]
    if tp.get("inclinacao_por_decada") is not None:
        sig = "estatisticamente significativa" if tp["significativa"] else "não significativa (p ≥ 0,05)"
        out.append({"nivel": "medio" if tp["significativa"] else "info", "titulo": "Tendência da chuva anual",
                    "texto": f"{tp['inclinacao_por_decada']:+.0f} mm por década — {sig}."})
    if vul.get("classe") in ("alta", "crítica"):
        out.append({"nivel": "alto", "titulo": f"Vulnerabilidade {vul['classe']}",
                    "texto": f"Índice experimental = {_br(vul['indice'], 2)} (0 = baixa, 1 = crítica)."})
    q = aval_a["indicadores"]["risco_quebra_anos"]
    if q >= 0.3:
        out.append({"nivel": "alto", "titulo": "Rotação atual exposta à seca",
                    "texto": f"Em {q * 100:.0f}% das observações de ano-safra (pares de anos sobrepostos da série) a rotação atual teria perda potencial por falta de água "
                             f"> 50% em ao menos uma cultura comercial."})
    if ind.get("cv_precipitacao_anual") and ind["cv_precipitacao_anual"] > 0.25:
        out.append({"nivel": "medio", "titulo": "Chuva muito irregular",
                    "texto": f"Coeficiente de variação da chuva anual = {ind['cv_precipitacao_anual'] * 100:.0f}%."})
    return out


def _resumo_estrategia(chave: str, av: dict, expl: dict) -> dict:
    return {"chave": chave, "titulo": expl["titulo"], "objetivo": expl["objetivo"],
            "slots": [{"cultura": s["cultura"], "ano": s["ano"], "mes": s["mes"]} for s in av["slots"]],
            "avaliacao": av, "explicacao": expl}


def analisar(prop: dict) -> dict:
    chave = _chave({k: prop.get(k) for k in ["lat", "lon", "rotacao_atual", "irrigacao_mm_ano", "culturas_permitidas",
                                             "prioridades", "declividade_pct", "usar_srtm", "solo"]})
    if chave in _CACHE:
        _CACHE.move_to_end(chave)
        res = dict(_CACHE[chave])
        res["propriedade"] = prop
        return res
    lat, lon = float(prop["lat"]), float(prop["lon"])
    irr = float(prop.get("irrigacao_mm_ano") or 0.0)
    serie = clima.carregar(lat, lon)
    resumo_clima = clima.resumo_para_api(serie)
    ind = resumo_clima["indicadores"]
    tab = rotacao.TabelaAvaliacao(serie)
    slots_a = rotacao.slots_de_dicts(prop.get("rotacao_atual") or [])
    if not slots_a:
        raise rotacao.RotacaoError("Informe ao menos uma cultura na rotação atual.")
    aval_a = rotacao.avaliar(slots_a, tab, irr)
    decl = resolver_declividade(prop)
    vul = vulnerabilidade.avaliar(ind, decl.get("declividade_pct"),
                                  aval_a["indicadores"]["meses_solo_descoberto"] / rotacao.HORIZONTE_MESES,
                                  decl.get("fonte"))
    opt = rotacao.otimizar(tab, irr, prop.get("culturas_permitidas"))
    cands = [aval_a] + [rotacao.avaliar(p, tab, irr) for p in opt["pareto"]]
    sel = rotacao.selecionar(cands, prop.get("prioridades"))
    local_cal = legacy_config.local_validado(lat, lon)
    ests = []
    for k in ["A", "B", "C", "D"]:
        i = 0 if k == "A" else sel[k]
        if i is None:
            continue
        av = cands[i]
        conf = explicabilidade.confianca([s["cultura"] for s in av["slots"]], ind["periodo"]["n_anos_completos"],
                                         _solo_informado(prop.get("solo")), decl.get("declividade_pct") is not None,
                                         local_cal)
        expl = explicabilidade.explicar(k, av, aval_a, ind, conf, irr)
        ests.append(_resumo_estrategia(k, av, expl))
    pareto_pts = []
    escolhidos = {sel["B"]: "B", sel["C"]: "C", sel.get("D"): "D"}
    for i, av in enumerate(cands):
        o = av["objetivos"]
        pareto_pts.append({"id": i, "estrategia": "A" if i == 0 else escolhidos.get(i),
                           "rotulo": " → ".join(f"{s['nome']} ({s['mes_nome']}/a{s['ano']})" for s in av["slots"]),
                           **o, "das": av["das"]["valor"], "risco_quebra_anos": av["indicadores"]["risco_quebra_anos"]})
    res = {
        "propriedade": prop,
        "local_calibrado": local_cal,
        "fontes": fontes.disponibilidade(lat, lon),
        "clima": resumo_clima,
        "topografia": decl,
        "vulnerabilidade": vul,
        "estrategias": ests,
        "pareto": pareto_pts,
        "otimizacao": {k: v for k, v in opt.items() if k != "pareto"} | {"n_pareto": len(opt["pareto"]),
                                                                         "objetivos": rotacao.OBJETIVOS,
                                                                         "pesos_prioridades": sel["pesos_prioridades"]},
        "alertas": _alertas(ind, vul, aval_a),
        "horizonte_meses": rotacao.HORIZONTE_MESES,
        "avisos_gerais": [
            "Dados NASA POWER representam a célula da grade (~50 km), não o talhão.",
            "Resultados são estimativas de um modelo de balanço hídrico simplificado (sem armazenamento de água no solo).",
            "Ferramenta de apoio à decisão: não substitui assistência técnica agronômica local.",
        ],
    }
    _CACHE[chave] = res
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return res


# ---------------------------------------------------------------------------
# Simulador climático
# ---------------------------------------------------------------------------
def _avaliar_estrategias(serie: clima.SerieClimatica, estrategias: Dict[str, List[dict]], irr: float,
                         decl: Optional[float]) -> dict:
    tab = rotacao.TabelaAvaliacao(serie)
    ind = clima.indicadores(serie)
    if serie.perturbacao is not None:
        # GWETROOT é saída de modelo e não pode ser recalculado pelo método delta: sai do índice no cenário.
        ind["gwetroot_medio"] = None
    out = {"indicadores_clima": {k: ind[k] for k in ["precipitacao_anual_media_mm", "et0_anual_media_mm", "indice_aridez",
                                                    "classe_aridez", "dias_calor_ano_medio", "tmax_media_c",
                                                    "cdd_estacao_chuvosa_medio_dias", "duracao_estacao_chuvosa_meses"]},
           "periodo": ind["periodo"], "estrategias": {}}
    solo_desc = None
    for k, slots in estrategias.items():
        av = rotacao.avaliar(rotacao.slots_de_dicts(slots), tab, irr)
        if k == "A":
            solo_desc = av["indicadores"]["meses_solo_descoberto"] / rotacao.HORIZONTE_MESES
        out["estrategias"][k] = {"objetivos": av["objetivos"], "indicadores": av["indicadores"], "das": av["das"]["valor"],
                                 "slots": [{"nome": s["nome"], "mes_nome": s["mes_nome"], "ano": s["ano"],
                                            "satisfacao_hidrica": s["satisfacao_hidrica"],
                                            "perda_rendimento_media": s["perda_rendimento_media"],
                                            "fracao_dias_calor": s["fracao_dias_calor"]} for s in av["slots"]]}
    vul = vulnerabilidade.avaliar(ind, decl, solo_desc)
    out["vulnerabilidade"] = {"indice": vul["indice"], "classe": vul["classe"], "subindices": vul["subindices"]}
    return out


def simular(lat: float, lon: float, estrategias: Dict[str, List[dict]], delta_t: float, delta_p_pct: float,
            irrigacao_mm_ano: float, declividade_pct: Optional[float] = None,
            periodo_recente: tuple = (2011, 2025), base_cenario: str = "historico",
            rotulo_horizonte: Optional[str] = None) -> dict:
    if not (-5 <= delta_t <= 6) or not (-60 <= delta_p_pct <= 60):
        raise ValueError("Perturbação fora da faixa permitida (ΔT −5…+6 °C; ΔP −60…+60 %).")
    base = clima.carregar(lat, lon)
    if base_cenario not in ("historico", "recente"):
        raise ValueError("base_cenario deve ser 'historico' ou 'recente'.")
    serie_base_hip = base if base_cenario == "historico" else clima.recortar(base, *periodo_recente)
    cenarios = {
        "historico": {"rotulo": "Histórico observado", "natureza": "observado (NASA POWER)",
                      **_avaliar_estrategias(base, estrategias, irrigacao_mm_ano, declividade_pct)},
        "recente": {"rotulo": f"Recente observado ({periodo_recente[0]}–{periodo_recente[1]})", "natureza": "observado (NASA POWER)",
                    **_avaliar_estrategias(clima.recortar(base, *periodo_recente), estrategias, irrigacao_mm_ano, declividade_pct)},
        "hipotetico": {"rotulo": f"Hipotético: ΔT {('+' if (delta_t) > 0 else '') + _br(delta_t, 1)} °C, ΔP {delta_p_pct:+.0f}%",
                       "natureza": "perturbação hipotética definida pelo usuário — NÃO é projeção nem previsão",
                       "base": base_cenario, "rotulo_horizonte": rotulo_horizonte,
                       **_avaliar_estrategias(clima.perturbar(serie_base_hip, delta_t, delta_p_pct), estrategias,
                                              irrigacao_mm_ano, declividade_pct)},
    }
    sens_t, sens_p = [], []
    for dt in [0, 1, 2, 3, 4]:
        tab = rotacao.TabelaAvaliacao(clima.perturbar(serie_base_hip, dt, delta_p_pct))
        linha = {"delta_t": dt}
        for k, slots in estrategias.items():
            av = rotacao.avaliar(rotacao.slots_de_dicts(slots), tab, irrigacao_mm_ano, detalhar=False)
            linha[k] = av["objetivos"]["vulnerabilidade_climatica"]
            linha[f"{k}_quebra"] = av["indicadores"]["risco_quebra_anos"]
        sens_t.append(linha)
    for dp in [-30, -20, -10, 0, 10]:
        tab = rotacao.TabelaAvaliacao(clima.perturbar(serie_base_hip, delta_t, dp))
        linha = {"delta_p_pct": dp}
        for k, slots in estrategias.items():
            av = rotacao.avaliar(rotacao.slots_de_dicts(slots), tab, irrigacao_mm_ano, detalhar=False)
            linha[k] = av["objetivos"]["demanda_irrigacao_mm_ano"]
            linha[f"{k}_quebra"] = av["indicadores"]["risco_quebra_anos"]
        sens_p.append(linha)
    return {"cenarios": cenarios, "sensibilidade_temperatura": sens_t, "sensibilidade_precipitacao": sens_p,
            "parametros": {"delta_t_c": delta_t, "delta_p_pct": delta_p_pct, "irrigacao_mm_ano": irrigacao_mm_ano,
                           "base_cenario": base_cenario, "rotulo_horizonte": rotulo_horizonte,
                           "nota_horizonte": "O horizonte é apenas um rótulo do cenário; não altera os cálculos."},
            "metodo": "Método delta: Tmed/Tmax/Tmin + ΔT; chuva diária × (1 + ΔP/100); ET0 recalculada (Hargreaves). "
                      "As estratégias são reavaliadas em todos os pares de anos da série perturbada.",
            "aviso": "Projeções NEX-GDDP-CMIP6 ainda não estão integradas. Os cenários hipotéticos servem para testar "
                     "sensibilidade, não para prever o clima futuro."}


def mapa_pontos() -> List[dict]:
    """Vulnerabilidade calculada nos locais com cache (para a camada do mapa)."""
    out = []
    for loc in fontes.locais_demo():
        if not loc["tem_cache"]:
            continue
        try:
            s = clima.carregar(loc["lat"], loc["lon"])
            ind = clima.indicadores(s)
            v = vulnerabilidade.avaliar(ind)
            out.append({"nome": loc["nome"], "lat": loc["lat"], "lon": loc["lon"], "categoria": loc["categoria"],
                        "precipitacao_anual_mm": round(ind["precipitacao_anual_media_mm"]),
                        "tmax_media_c": round(ind["tmax_media_c"], 1), "dias_calor": round(ind["dias_calor_ano_medio"]),
                        "gwetroot": None if ind["gwetroot_medio"] is None else round(ind["gwetroot_medio"], 2),
                        "indice_aridez": round(ind["indice_aridez"], 2), "classe_aridez": ind["classe_aridez"],
                        "vulnerabilidade": v["indice"], "classe_vulnerabilidade": v["classe"],
                        "indice_fournier": round(ind["indice_fournier_modificado"]),
                        "nota": "sem declividade e sem rotação (somente indicadores climáticos)"})
        except Exception as e:  # noqa: BLE001
            out.append({"nome": loc["nome"], "lat": loc["lat"], "lon": loc["lon"], "erro": str(e)})
    return out
