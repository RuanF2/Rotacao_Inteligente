"""Agricultural Vulnerability Engine — índice experimental e documentado.

Cada indicador é convertido para uma nota 0–1 por FAIXAS DOCUMENTADAS
(ver METHODOLOGY.md, seção 3). O índice composto é a MÉDIA SIMPLES das notas
disponíveis (pesos iguais — opção padrão recomendada pelo Handbook on
Constructing Composite Indicators da OCDE/JRC quando não há base empírica
para pesos diferentes). Se houver menos de ``MIN_INDICADORES`` indicadores,
o sistema NÃO classifica: devolve "dados insuficientes".
"""
from __future__ import annotations

from typing import Dict, List, Optional

MIN_INDICADORES = 5

# (limite_superior_da_faixa, nota). A última faixa usa float('inf').
# "crescente" = valor maior => mais vulnerável; "decrescente" = o contrário.
INDICADORES = {
    "aridez": {
        "nome": "Índice de aridez (P/ET0)", "unidade": "adimensional", "sentido": "decrescente",
        "faixas": [(0.20, 1.0), (0.50, 0.67), (0.65, 0.33), (float("inf"), 0.0)],
        "base": "Classes de aridez UNEP/UNCCD (árido < 0,20; semiárido < 0,50; subúmido seco < 0,65).",
        "grupo": "hidrico", "fonte_dado": "NASA POWER (P) + ET0 Hargreaves (T2M, T2M_MAX, T2M_MIN)",
    },
    "variabilidade_chuva": {
        "nome": "Coeficiente de variação da chuva anual", "unidade": "fração", "sentido": "crescente",
        "faixas": [(0.15, 0.0), (0.25, 0.33), (0.35, 0.67), (float("inf"), 1.0)],
        "base": "Faixas definidas pela equipe; CV > 0,30 é tratado na literatura de terras secas como alta variabilidade.",
        "grupo": "hidrico", "fonte_dado": "NASA POWER PRECTOTCORR",
    },
    "veranicos": {
        "nome": "Maior sequência seca na estação chuvosa (média anual)", "unidade": "dias", "sentido": "crescente",
        "faixas": [(10, 0.0), (15, 0.33), (25, 0.67), (float("inf"), 1.0)],
        "base": "Dia seco = chuva < 1 mm (ETCCDI). Faixas da equipe: veranicos > 10–15 dias já afetam culturas de sequeiro.",
        "grupo": "hidrico", "fonte_dado": "NASA POWER PRECTOTCORR",
    },
    "umidade_solo": {
        "nome": "Umidade relativa da zona radicular (GWETROOT, modelo)", "unidade": "fração 0–1", "sentido": "decrescente",
        "faixas": [(0.25, 1.0), (0.35, 0.67), (0.50, 0.33), (float("inf"), 0.0)],
        "base": "Faixas da equipe. GWETROOT é estimativa de modelo (MERRA-2 via NASA POWER), não medição SMAP nem de campo.",
        "grupo": "hidrico", "fonte_dado": "NASA POWER GWETROOT",
    },
    "estresse_termico": {
        "nome": "Dias por ano com Tmax ≥ 35 °C", "unidade": "dias/ano", "sentido": "crescente",
        "faixas": [(10, 0.0), (30, 0.33), (90, 0.67), (float("inf"), 1.0)],
        "base": "35 °C é limiar de dano reprodutivo para várias culturas (ex.: milho, Hatfield & Prueger 2015). Faixas da equipe.",
        "grupo": "termico", "fonte_dado": "NASA POWER T2M_MAX",
    },
    "erosividade": {
        "nome": "Índice de Fournier modificado (erosividade da chuva)", "unidade": "mm", "sentido": "crescente",
        "faixas": [(60, 0.0), (90, 0.25), (120, 0.5), (160, 0.75), (float("inf"), 1.0)],
        "base": "Classes de Arnoldus (1980) para o IFM.",
        "grupo": "erosao", "fonte_dado": "NASA POWER PRECTOTCORR (climatologia mensal)",
    },
    "declividade": {
        "nome": "Declividade do terreno", "unidade": "%", "sentido": "crescente",
        "faixas": [(3, 0.0), (8, 0.33), (20, 0.67), (float("inf"), 1.0)],
        "base": "Classes de relevo da Embrapa/SiBCS (plano < 3 %, suave ondulado < 8 %, ondulado < 20 %).",
        "grupo": "erosao", "fonte_dado": "informado pelo usuário ou SRTM 90 m (OpenTopoData)",
    },
    "solo_descoberto": {
        "nome": "Fração do ano com solo descoberto (rotação atual)", "unidade": "fração", "sentido": "crescente",
        "faixas": None,  # já é 0–1
        "base": "Calculado do calendário informado pelo agricultor; é prática de manejo, não observação de satélite.",
        "grupo": "erosao", "fonte_dado": "rotação atual informada",
    },
}

CLASSES = [(0.25, "baixa"), (0.50, "moderada"), (0.75, "alta"), (float("inf"), "crítica")]


def nota(chave: str, valor: Optional[float]) -> Optional[float]:
    if valor is None:
        return None
    meta = INDICADORES[chave]
    if meta["faixas"] is None:
        return float(min(1.0, max(0.0, valor)))
    for limite, n in meta["faixas"]:
        if valor < limite:
            return n
    return meta["faixas"][-1][1]


def classificar(indice: Optional[float]) -> Optional[str]:
    if indice is None:
        return None
    for limite, nome in CLASSES:
        if indice < limite:
            return nome
    return "crítica"


def avaliar(ind_clima: dict, declividade_pct: Optional[float] = None,
            fracao_solo_descoberto: Optional[float] = None,
            fonte_declividade: Optional[str] = None) -> dict:
    valores = {
        "aridez": ind_clima.get("indice_aridez"),
        "variabilidade_chuva": ind_clima.get("cv_precipitacao_anual"),
        "veranicos": ind_clima.get("cdd_estacao_chuvosa_medio_dias"),
        "umidade_solo": ind_clima.get("gwetroot_medio"),
        "estresse_termico": ind_clima.get("dias_calor_ano_medio"),
        "erosividade": ind_clima.get("indice_fournier_modificado"),
        "declividade": declividade_pct,
        "solo_descoberto": fracao_solo_descoberto,
    }
    itens: List[dict] = []
    ausentes: List[str] = []
    for k, v in valores.items():
        meta = INDICADORES[k]
        n = nota(k, v)
        if n is None:
            ausentes.append(meta["nome"])
        fonte = meta["fonte_dado"]
        if k == "declividade" and fonte_declividade:
            fonte = fonte_declividade
        itens.append({"chave": k, "nome": meta["nome"], "valor": v, "unidade": meta["unidade"],
                      "nota": n, "classe": classificar(n) if n is not None else None,
                      "grupo": meta["grupo"], "base_faixas": meta["base"], "fonte": fonte})
    notas = [i["nota"] for i in itens if i["nota"] is not None]
    grupos: Dict[str, Optional[float]] = {}
    for g in ("hidrico", "termico", "erosao"):
        ns = [i["nota"] for i in itens if i["grupo"] == g and i["nota"] is not None]
        grupos[g] = round(sum(ns) / len(ns), 3) if ns else None
    if len(notas) < MIN_INDICADORES:
        return {"indice": None, "classe": "dados insuficientes", "indicadores": itens,
                "subindices": grupos, "ausentes": ausentes, "n_indicadores": len(notas),
                "metodo": "média simples (pesos iguais) das notas 0–1 disponíveis",
                "aviso": f"Apenas {len(notas)} indicadores disponíveis (mínimo {MIN_INDICADORES})."}
    indice = round(sum(notas) / len(notas), 3)
    return {"indice": indice, "classe": classificar(indice), "indicadores": itens,
            "subindices": grupos, "ausentes": ausentes, "n_indicadores": len(notas),
            "metodo": "média simples (pesos iguais) das notas 0–1 disponíveis",
            "aviso": "Índice experimental de triagem. Não substitui diagnóstico agronômico de campo."}
