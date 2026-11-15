"""Motor de dados climáticos — NASA POWER (via núcleo legado) + indicadores.

Responsabilidades:
  * carregar a série diária NASA POWER (cache primeiro, rede depois) usando
    ``core.nasa_power`` do NASA1 — sem reimplementar o download;
  * limpar a série (apenas dias com dado, sem inventar valores);
  * calcular ET0 diária por Hargreaves-Samani (FAO-56, Eq. 52), porque o
    conjunto baixado não inclui vento (necessário para Penman-Monteith);
  * calcular indicadores climáticos documentados em METHODOLOGY.md;
  * aplicar perturbações HIPOTÉTICAS (ΔT, ΔP) para o simulador.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from .legacy import enso, legacy_config, nasa_power

VARS_ESSENCIAIS = ["PRECTOTCORR", "T2M", "T2M_MAX", "T2M_MIN"]
LIMIAR_DIA_SECO_MM = 1.0       # ETCCDI: dia seco = RR < 1 mm
LIMIAR_CALOR_C = 35.0          # dias com Tmax >= 35 °C
UNIDADES = {
    "T2M": "°C", "T2M_MAX": "°C", "T2M_MIN": "°C", "PRECTOTCORR": "mm/dia",
    "RH2M": "%", "ALLSKY_SFC_SW_DWN": "MJ/m²/dia", "GWETROOT": "fração 0–1",
    "GWETTOP": "fração 0–1", "ET0": "mm/dia",
}
MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


class ClimaError(Exception):
    pass


@dataclass
class SerieClimatica:
    lat: float
    lon: float
    df: pd.DataFrame                     # diário, colunas NASA POWER + ET0
    falhas: List[str]
    metadados: Dict[str, dict]
    origem: str                          # "cache" | "rede" | "misto"
    anos_completos: List[int]            # anos civis com >= 360 dias de chuva válida
    dias_preenchidos: int = 0            # lacunas isoladas interpoladas (temperatura)
    perturbacao: Optional[dict] = None   # None = dado observado; dict = cenário hipotético
    avisos: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ET0 — Hargreaves-Samani (FAO-56 Eq. 52) com Ra pela Eq. 21
# ---------------------------------------------------------------------------
def radiacao_extraterrestre(lat_graus: float, dia_juliano: np.ndarray) -> np.ndarray:
    """Ra em MJ m-2 dia-1 (FAO-56, Eqs. 21-25)."""
    phi = math.radians(lat_graus)
    j = np.asarray(dia_juliano, dtype=float)
    dr = 1 + 0.033 * np.cos(2 * np.pi * j / 365)
    delta = 0.409 * np.sin(2 * np.pi * j / 365 - 1.39)
    x = -math.tan(phi) * np.tan(delta)
    ws = np.arccos(np.clip(x, -1.0, 1.0))
    gsc = 0.0820
    ra = (24 * 60 / np.pi) * gsc * dr * (
        ws * math.sin(phi) * np.sin(delta) + math.cos(phi) * np.cos(delta) * np.sin(ws)
    )
    return np.maximum(ra, 0.0)


def et0_hargreaves(tmed: np.ndarray, tmax: np.ndarray, tmin: np.ndarray,
                   ra: np.ndarray) -> np.ndarray:
    """ET0 (mm/dia) = 0,0023 (Tmed + 17,8) (Tmax − Tmin)^0,5 · 0,408 Ra."""
    amp = np.clip(np.asarray(tmax) - np.asarray(tmin), 0.0, None)
    et0 = 0.0023 * (np.asarray(tmed) + 17.8) * np.sqrt(amp) * 0.408 * np.asarray(ra)
    return np.clip(et0, 0.0, None)


def _adicionar_et0(df: pd.DataFrame, lat: float) -> pd.DataFrame:
    df = df.copy()
    ra = radiacao_extraterrestre(lat, df.index.day_of_year.values)
    df["ET0"] = et0_hargreaves(df["T2M"].values, df["T2M_MAX"].values,
                               df["T2M_MIN"].values, ra)
    return df


# ---------------------------------------------------------------------------
# Carregamento
# ---------------------------------------------------------------------------
def _limpar(df: pd.DataFrame) -> Tuple[pd.DataFrame, int, List[str]]:
    """Remove a cauda sem dados e interpola só lacunas ISOLADAS (<= 3 dias) de temperatura.

    Chuva nunca é interpolada: dias sem chuva válida ficam NaN e os
    anos com mais de 5 dias faltando saem dos cálculos anuais.
    """
    avisos: List[str] = []
    faltam = [v for v in VARS_ESSENCIAIS if v not in df.columns]
    if faltam:
        raise ClimaError(f"Variáveis essenciais ausentes na NASA POWER: {faltam}")
    validos = df[VARS_ESSENCIAIS].notna().all(axis=1)
    if not validos.any():
        raise ClimaError("A série NASA POWER não tem nenhum dia válido.")
    ultimo = validos[validos].index.max()
    cortados = int((df.index > ultimo).sum())
    df = df.loc[:ultimo].copy()
    if cortados:
        avisos.append(f"{cortados} dias finais sem dado na NASA POWER foram descartados "
                      f"(último dia válido: {ultimo.date()}).")
    preench = 0
    for v in ["T2M", "T2M_MAX", "T2M_MIN"]:
        n_antes = int(df[v].isna().sum())
        df[v] = df[v].interpolate(limit=3, limit_area="inside")
        preench += n_antes - int(df[v].isna().sum())
    if preench:
        avisos.append(f"{preench} valores isolados de temperatura interpolados (lacunas ≤ 3 dias).")
    return df, preench, avisos


@lru_cache(maxsize=32)
def _carregar_cache(lat: float, lon: float) -> SerieClimatica:
    df, falhas, infos = nasa_power.carregar_series(
        lat, lon, legacy_config.ANO_INICIO_SERIE, legacy_config.ANO_FIM_SERIE
    )
    if df.empty:
        raise ClimaError(
            "Não foi possível obter dados da NASA POWER para este ponto "
            "(sem cache local e sem acesso à API). Detalhes: " + "; ".join(falhas[:3])
        )
    origem = "cache" if legacy_config.local_tem_cache(lat, lon) else "rede"
    df, preench, avisos = _limpar(df)
    df = _adicionar_et0(df, lat)
    meta = {i.nome: {"descricao": i.longname, "unidade_api": i.units,
                     "unidade": UNIDADES.get(i.nome, i.units)} for i in infos}
    meta["ET0"] = {"descricao": "Evapotranspiração de referência (Hargreaves-Samani, FAO-56 Eq. 52)",
                   "unidade_api": "derivado", "unidade": "mm/dia"}
    chuva_ok = df["PRECTOTCORR"].notna().groupby(df.index.year).sum()
    anos = [int(a) for a, n in chuva_ok.items() if n >= 360]
    return SerieClimatica(lat=lat, lon=lon, df=df, falhas=list(falhas), metadados=meta,
                          origem=origem, anos_completos=anos, dias_preenchidos=preench,
                          avisos=avisos)


def carregar(lat: float, lon: float) -> SerieClimatica:
    """Carrega a série diária para (lat, lon) arredondados a 2 casas (convenção do cache)."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ClimaError("Coordenadas fora do intervalo válido.")
    return _carregar_cache(round(float(lat), 2), round(float(lon), 2))


def perturbar(serie: SerieClimatica, delta_t: float = 0.0, delta_p_pct: float = 0.0
              ) -> SerieClimatica:
    """Aplica uma perturbação HIPOTÉTICA (método delta) e recalcula a ET0.

    Não é previsão nem projeção: é um teste de sensibilidade definido pelo usuário.
    """
    if delta_t == 0 and delta_p_pct == 0:
        return serie
    df = serie.df.copy()
    for v in ["T2M", "T2M_MAX", "T2M_MIN"]:
        df[v] = df[v] + delta_t
    df["PRECTOTCORR"] = (df["PRECTOTCORR"] * (1 + delta_p_pct / 100.0)).clip(lower=0)
    df = _adicionar_et0(df.drop(columns=["ET0"]), serie.lat)
    return SerieClimatica(lat=serie.lat, lon=serie.lon, df=df, falhas=serie.falhas,
                          metadados=serie.metadados, origem=serie.origem,
                          anos_completos=serie.anos_completos,
                          dias_preenchidos=serie.dias_preenchidos,
                          perturbacao={"delta_t_c": delta_t, "delta_p_pct": delta_p_pct,
                                       "natureza": "perturbação hipotética definida pelo usuário"},
                          avisos=serie.avisos)


def recortar(serie: SerieClimatica, ano_ini: int, ano_fim: int) -> SerieClimatica:
    df = serie.df.loc[f"{ano_ini}-01-01":f"{ano_fim + 1}-12-31"]
    anos = [a for a in serie.anos_completos if ano_ini <= a <= ano_fim]
    return SerieClimatica(lat=serie.lat, lon=serie.lon, df=df, falhas=serie.falhas,
                          metadados=serie.metadados, origem=serie.origem, anos_completos=anos,
                          dias_preenchidos=serie.dias_preenchidos,
                          perturbacao=serie.perturbacao, avisos=serie.avisos)


# ---------------------------------------------------------------------------
# Indicadores
# ---------------------------------------------------------------------------
def precipitacao_efetiva_mensal(p_mm: np.ndarray) -> np.ndarray:
    """Método USDA-SCS (usado no CROPWAT/FAO) para totais mensais em mm."""
    p = np.asarray(p_mm, dtype=float)
    return np.where(p <= 250, p * (125 - 0.2 * p) / 125, 125 + 0.1 * p)


def classe_aridez(ia: float) -> str:
    if ia < 0.05:
        return "hiperárido"
    if ia < 0.20:
        return "árido"
    if ia < 0.50:
        return "semiárido"
    if ia < 0.65:
        return "subúmido seco"
    return "úmido"


def classe_fournier(mfi: float) -> str:
    if mfi < 60:
        return "muito baixa"
    if mfi < 90:
        return "baixa"
    if mfi < 120:
        return "moderada"
    if mfi < 160:
        return "alta"
    return "muito alta"


def _maior_sequencia(bool_arr: np.ndarray) -> int:
    best = cur = 0
    for b in bool_arr:
        cur = cur + 1 if b else 0
        if cur > best:
            best = cur
    return best


def climatologia_mensal(serie: SerieClimatica) -> pd.DataFrame:
    df = serie.df
    anos = serie.anos_completos
    d = df[df.index.year.isin(anos)]
    mensal = pd.DataFrame({
        "P": d["PRECTOTCORR"].resample("MS").sum(min_count=25),
        "ET0": d["ET0"].resample("MS").sum(min_count=25),
        "T2M": d["T2M"].resample("MS").mean(),
        "T2M_MAX": d["T2M_MAX"].resample("MS").mean(),
        "T2M_MIN": d["T2M_MIN"].resample("MS").mean(),
        "DIAS_CALOR": (d["T2M_MAX"] >= LIMIAR_CALOR_C).resample("MS").sum(),
    })
    for v in ["GWETROOT", "GWETTOP", "RH2M", "ALLSKY_SFC_SW_DWN"]:
        if v in d.columns:
            mensal[v] = d[v].resample("MS").mean()
    clim = mensal.groupby(mensal.index.month).mean()
    clim.index.name = "mes"
    return clim


def meses_chuvosos(clim: pd.DataFrame) -> List[int]:
    """Meses com P ≥ 0,5·ET0 (critério de período de crescimento da FAO/AEZ)."""
    return [int(m) for m in clim.index if clim.loc[m, "P"] >= 0.5 * clim.loc[m, "ET0"]]


def series_anuais(serie: SerieClimatica, chuvosos: List[int]) -> pd.DataFrame:
    df = serie.df
    linhas = []
    for ano in serie.anos_completos:
        d = df[df.index.year == ano]
        p = d["PRECTOTCORR"]
        seco = (p < LIMIAR_DIA_SECO_MM).values
        if chuvosos:
            dc = d[d.index.month.isin(chuvosos)]
            cdd_chuva = _maior_sequencia((dc["PRECTOTCORR"] < LIMIAR_DIA_SECO_MM).values)
        else:
            cdd_chuva = None
        linhas.append({
            "ano": ano,
            "P_mm": float(p.sum()),
            "ET0_mm": float(d["ET0"].sum()),
            "T2M_med": float(d["T2M"].mean()),
            "T2M_MAX_med": float(d["T2M_MAX"].mean()),
            "dias_calor": int((d["T2M_MAX"] >= LIMIAR_CALOR_C).sum()),
            "CDD": _maior_sequencia(seco),
            "CDD_estacao_chuvosa": cdd_chuva,
            "Rx1day": float(p.max()),
            "Rx5day": float(p.rolling(5).sum().max()),
            "R20mm": int((p >= 20).sum()),
            "GWETROOT_med": float(d["GWETROOT"].mean()) if "GWETROOT" in d else None,
        })
    return pd.DataFrame(linhas)


def _tendencia(anos: np.ndarray, valores: np.ndarray) -> dict:
    ok = ~np.isnan(valores)
    if ok.sum() < 10:
        return {"inclinacao_por_decada": None, "p_valor": None, "significativa": None}
    res = stats.theilslopes(valores[ok], anos[ok])
    tau, p = stats.kendalltau(anos[ok], valores[ok])
    return {"inclinacao_por_decada": float(res[0] * 10), "p_valor": float(p),
            "significativa": bool(p < 0.05),
            "metodo": "Theil-Sen + teste de Mann-Kendall (tau de Kendall)"}


def indicadores(serie: SerieClimatica) -> dict:
    """Indicadores climáticos da série (todos com unidade e método)."""
    if len(serie.anos_completos) < 10:
        raise ClimaError("Série com menos de 10 anos completos — indicadores não confiáveis.")
    clim = climatologia_mensal(serie)
    chuvosos = meses_chuvosos(clim)
    anuais = series_anuais(serie, chuvosos)
    p_anual = anuais["P_mm"].values
    et0_anual = anuais["ET0_mm"].values
    ia = float(np.mean(p_anual) / np.mean(et0_anual)) if np.mean(et0_anual) > 0 else None
    p_clim = clim["P"].values
    mfi = float(np.sum(p_clim ** 2) / np.sum(p_clim)) if np.sum(p_clim) > 0 else 0.0
    anos_arr = anuais["ano"].values.astype(float)
    out = {
        "periodo": {"inicio": int(min(serie.anos_completos)), "fim": int(max(serie.anos_completos)),
                    "n_anos_completos": len(serie.anos_completos)},
        "precipitacao_anual_media_mm": float(np.mean(p_anual)),
        "precipitacao_anual_mediana_mm": float(np.median(p_anual)),
        "cv_precipitacao_anual": float(np.std(p_anual, ddof=1) / np.mean(p_anual)) if np.mean(p_anual) > 0 else None,
        "et0_anual_media_mm": float(np.mean(et0_anual)),
        "indice_aridez": ia,
        "classe_aridez": classe_aridez(ia) if ia is not None else None,
        "meses_chuvosos": chuvosos,
        "meses_chuvosos_nomes": [MESES_PT[m - 1] for m in chuvosos],
        "duracao_estacao_chuvosa_meses": len(chuvosos),
        "cdd_estacao_chuvosa_medio_dias": (float(anuais["CDD_estacao_chuvosa"].mean())
                                           if chuvosos else None),
        "cdd_anual_medio_dias": float(anuais["CDD"].mean()),
        "dias_calor_ano_medio": float(anuais["dias_calor"].mean()),
        "tmax_media_c": float(anuais["T2M_MAX_med"].mean()),
        "tmed_media_c": float(anuais["T2M_med"].mean()),
        "rx5day_medio_mm": float(anuais["Rx5day"].mean()),
        "r20mm_medio_dias": float(anuais["R20mm"].mean()),
        "gwetroot_medio": (float(anuais["GWETROOT_med"].mean())
                           if anuais["GWETROOT_med"].notna().any() else None),
        "indice_fournier_modificado": mfi,
        "classe_erosividade": classe_fournier(mfi),
        "tendencia_precipitacao_mm": _tendencia(anos_arr, p_anual.astype(float)),
        "tendencia_tmax_c": _tendencia(anos_arr, anuais["T2M_MAX_med"].values.astype(float)),
        "tendencia_dias_calor": _tendencia(anos_arr, anuais["dias_calor"].values.astype(float)),
    }
    return out


def comparar_periodos(serie: SerieClimatica, a: Tuple[int, int], b: Tuple[int, int]) -> dict:
    """Compara dois períodos observados (ex.: 1991–2005 × 2011–2025)."""
    res = {}
    for nome, (i, f) in {"periodo_a": a, "periodo_b": b}.items():
        s = recortar(serie, i, f)
        if len(s.anos_completos) < 10:
            res[nome] = {"intervalo": [i, f], "erro": "menos de 10 anos completos"}
            continue
        ind = indicadores(s)
        res[nome] = {"intervalo": [i, f], "precipitacao_anual_media_mm": ind["precipitacao_anual_media_mm"],
                     "tmax_media_c": ind["tmax_media_c"], "dias_calor_ano_medio": ind["dias_calor_ano_medio"],
                     "cdd_estacao_chuvosa_medio_dias": ind["cdd_estacao_chuvosa_medio_dias"],
                     "indice_aridez": ind["indice_aridez"], "classe_aridez": ind["classe_aridez"]}
    return res


def chuva_por_enso(serie: SerieClimatica, meses: List[int]) -> Optional[dict]:
    """Chuva da estação chuvosa agrupada pela classe ENSO (ONI DJF, NOAA/CPC — núcleo legado)."""
    try:
        classes, contagem, _ = enso.carregar_classificacao()
    except Exception:  # noqa: BLE001
        return None
    if not meses:
        return None
    df = serie.df
    linhas = []
    for c in classes:
        if c.classe == "dado não preenchido":
            continue
        n = c.ano  # ano agrícola N = nov/N .. out/N+1
        ini, fim = pd.Timestamp(n, 11, 1), pd.Timestamp(n + 1, 10, 31)
        d = df.loc[ini:fim]
        if len(d) < 360 or d["PRECTOTCORR"].isna().sum() > 5:
            continue
        p = float(d[d.index.month.isin(meses)]["PRECTOTCORR"].sum())
        linhas.append({"ano_agricola": n, "classe": c.classe, "oni": c.oni, "chuva_estacao_mm": p})
    if not linhas:
        return None
    t = pd.DataFrame(linhas)
    resumo = (t.groupby("classe")["chuva_estacao_mm"].agg(["mean", "median", "count"])
              .rename(columns={"mean": "media_mm", "median": "mediana_mm", "count": "n_anos"}))
    return {"por_classe": resumo.reset_index().to_dict(orient="records"),
            "anos": linhas,
            "fonte": "ONI v6 (NOAA/CPC), trimestre DJF; ano agrícola N = nov/N–out/N+1 (convenção do NASA1)"}


def resumo_para_api(serie: SerieClimatica) -> dict:
    clim = climatologia_mensal(serie)
    ind = indicadores(serie)
    anuais = series_anuais(serie, ind["meses_chuvosos"])
    clim_out = []
    for m, row in clim.iterrows():
        item = {"mes": int(m), "mes_nome": MESES_PT[int(m) - 1]}
        for k, v in row.items():
            item[k] = None if pd.isna(v) else round(float(v), 3)
        clim_out.append(item)
    anuais_out = [{k: (None if (isinstance(v, float) and np.isnan(v)) else v)
                   for k, v in r.items()} for r in anuais.to_dict(orient="records")]
    df = serie.df
    return {
        "local": {"lat": serie.lat, "lon": serie.lon},
        "fonte": {
            "nome": "NASA POWER — Daily API, comunidade AG",
            "url": "https://power.larc.nasa.gov/",
            "resolucao_espacial": "≈0,5° × 0,625° (MERRA-2) para meteorologia; ≈1° para radiação (CERES/GEWEX)",
            "resolucao_temporal": "diária",
            "periodo_dados": [str(df.index.min().date()), str(df.index.max().date())],
            "origem_nesta_execucao": serie.origem,
            "aviso_escala": "Valores representam a célula da grade (dezenas de km), não o talhão.",
        },
        "variaveis": serie.metadados,
        "falhas": serie.falhas,
        "avisos": serie.avisos,
        "perturbacao": serie.perturbacao,
        "indicadores": ind,
        "climatologia_mensal": clim_out,
        "series_anuais": anuais_out,
        "comparacao_periodos": comparar_periodos(serie, (1991, 2005), (2011, 2025)),
        "enso": chuva_por_enso(serie, ind["meses_chuvosos"]),
    }
