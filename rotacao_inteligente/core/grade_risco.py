"""Grade de risco hídrico do Piauí (camada "Risco hídrico (modelo)").

Gera uma grade de ~1° sobre o Piauí (só pontos dentro do bbox do
estado), baixando ÚNICA variável (PRECTOTCORR, 1991-2026) para cada
ponto e salvando em `data/cache/grade_piaui/`. Para a cultura e o
cenário ENSO escolhidos, calcula em cada ponto o % de anos daquela
classe ENSO com chuva do ciclo ABAIXO da água efetiva da cultura, no
mês de semeadura padrão.

REUTILIZA as funções existentes (não muda regras de cálculo):
  - core.nasa_power._chamar_api / _periodo_para_datas  (download)
  - core.nasa_power.para_dataframe                    (JSON -> DataFrame)
  - core.resiliencia.risco_hidrico_por_classe          (% anos < limiar)
  - core.culturas.Cultura.agua_efetiva_mm_ciclo        (demanda hídrica)

A métrica de risco é EXATAMENTE risco_hidrico_por_classe (Etapa 6),
aplicada por ponto da grade. Nenhuma regra nova.

Rótulo: `config.GRADE_ROTULO` = "resolução da grade do NASA POWER,
não é nível de campo".
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

import config
from core import nasa_power
from core.resiliencia import risco_hidrico_por_classe
from core.culturas import Cultura

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Geração da grade de pontos (lat, lon) dentro do Piauí
# ---------------------------------------------------------------------------

# Cache em memória dos anéis (rings) do polígono do Piauí, lidos uma
# vez do GeoJSON. Evita reler/parsear o arquivo a cada chamada.
_RINGS_PIAUI: Optional[List[List[Tuple[float, float]]]] = None
_FONTE_FILTRO: Optional[str] = None   # "malha oficial" | "retângulo"


def _ponto_em_poligono(lat: float, lon: float,
                       rings: List[List[Tuple[float, float]]]) -> bool:
    """Teste ponto-em-polígono por ray casting (Python puro, sem shapely).

    `rings` é uma lista de anéis (cada anel = lista de (lon, lat)).
    Convenção GeoJSON: o primeiro anel é o exterior (inclusão); anéis
    seguintes são buracos (exclusão). O ponto está dentro se está no
    exterior e em nenhum buraco.

    O ray cast é horizontal (varre em lon); robusto a vértices nas
    bordas usa a reraça-ângulo padrão (PNPOLY de W. Randolph Franklin).
    """
    def em_um_anel(lat, lon, anel):
        dentro = False
        n = len(anel)
        j = n - 1
        for i in range(n):
            yi, xi = anel[i][1], anel[i][0]   # (lat=y, lon=x)
            yj, xj = anel[j][1], anel[j][0]
            # Aresta cruza a reta horizontal y=lat à direita de (lon,lat)?
            if ((yi > lat) != (yj > lat)):
                x_int = (xj - xi) * (lat - yi) / (yj - yi) + xi
                if lon < x_int:
                    dentro = not dentro
            j = i
        return dentro

    if not rings:
        return False
    # Exterior (anel 0) -> tem que estar dentro.
    if not em_um_anel(lat, lon, rings[0]):
        return False
    # Buracos (anéis 1+) -> não pode estar dentro de nenhum.
    for anel in rings[1:]:
        if em_um_anel(lat, lon, anel):
            return False
    return True


def _carregar_rings_piaui() -> Optional[List[List[Tuple[float, float]]]]:
    """Lê o GeoJSON da malha do Piauí e devolve os anéis (lon, lat).

    Suporta Polygon (1 anel exterior + buracos) e MultiPolygon (vários
    Polygon). Cada anel vira uma lista de (lon, lat). Devolve None se
    o arquivo não existir ou falhar ao ler — quem chama cai no fallback.

    Faz cache em memória (_RINGS_PIAUI) para não reler a cada chamada.
    """
    global _RINGS_PIAUI, _FONTE_FILTRO
    if _RINGS_PIAUI is not None:
        return _RINGS_PIAUI
    caminho = config.PIAUI_MALHA_GEOJSON
    if not caminho.exists():
        _FONTE_FILTRO = "retângulo"
        return None
    try:
        import json
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        _log.warning("Malha do Piauí inválida (%s): %s. Uso retângulo.",
                     caminho, e)
        _FONTE_FILTRO = "retângulo"
        return None
    rings: List[List[Tuple[float, float]]] = []
    feats = dados.get("features") if isinstance(dados, dict) else None
    if feats is None and isinstance(dados, dict) and "geometry" in dados:
        feats = [dados]
    for f in feats or []:
        g = f.get("geometry") if isinstance(f, dict) else None
        if g is None:
            continue
        t = g.get("type")
        if t == "Polygon":
            for ring in g["coordinates"]:
                rings.append([(float(lo), float(la)) for lo, la in ring])
        elif t == "MultiPolygon":
            for pol in g["coordinates"]:
                for ring in pol:
                    rings.append([(float(lo), float(la)) for lo, la in ring])
    if not rings:
        _log.warning("Malha do Piauí sem geometria: %s. Uso retângulo.",
                     caminho)
        _FONTE_FILTRO = "retângulo"
        return None
    _RINGS_PIAUI = rings
    _FONTE_FILTRO = "malha oficial"
    return rings


def fonte_do_filtro() -> str:
    """Qual filtro a grade usou: 'malha oficial' ou 'retângulo' (fallback).

    Preenchido por gerar_pontos_grade (via _carregar_rings_piaui).
    'retângulo' quando não há data/piaui_uf.geojson ou ele é inválido.
    """
    if _FONTE_FILTRO is None:
        _carregar_rings_piaui()   # define _FONTE_FILTRO
    return _FONTE_FILTRO or "retângulo"


def gerar_pontos_grade(passo: float = config.GRADE_PASSO_GRAUS
                       ) -> List[Tuple[float, float]]:
    """Gera pontos (lat, lon) de uma grade regular dentro do Piauí.

    Filtro (correção 2026-11-14):
    - Se data/piaui_uf.geojson existe (baixado por
      scripts/baixar_malha_piaui.py), gera a grade candidata no
      retângulo envoltório e faz PONTO-EM-POLÍGONO (filtro exato pela
      fronteira do estado). Use `fonte_do_filtro()` para saber.
    - Senão, usa o retângulo config.PIAUI_BBOX como fallback (menos
      preciso — pode incluir pontos fora da fronteira). Rotulado.

    A grade candidata cobre o retângulo [lat_min, lat_max] ×
    [lon_min, lon_max] com passo `passo` graus, alinhada para coordenadas
    "redondas" (cache estável, leitura fácil no mapa).

    Returns:
        Lista de (lat, lon) ordenada Norte→Sul, Oeste→Leste.
    """
    import math
    b = config.PIAUI_BBOX
    # Alinha para DENTRO do bbox: ceil no min, floor no max.
    lat0 = math.ceil(b["lat_min"] / passo) * passo
    lat1 = math.floor(b["lat_max"] / passo) * passo
    lon0 = math.ceil(b["lon_min"] / passo) * passo
    lon1 = math.floor(b["lon_max"] / passo) * passo
    lats, lat = [], lat0
    while lat <= lat1 + 1e-9:
        lats.append(round(lat, 4))
        lat += passo
    lons, lon = [], lon0
    while lon <= lon1 + 1e-9:
        lons.append(round(lon, 4))
        lon += passo
    candidatos = [(la, lo) for la in sorted(lats, reverse=True)
                  for lo in sorted(lons)]
    # Filtro por fronteira (malha) se disponível; senão, retângulo.
    rings = _carregar_rings_piaui()
    if rings is not None:
        pontos = [p for p in candidatos if _ponto_em_poligono(p[0], p[1], rings)]
    else:
        pontos = candidatos   # já dentro do retângulo
    return pontos


# ---------------------------------------------------------------------------
# 2. Download de PRECTOTCORR para a grade (com cache em grade_piaui/)
# ---------------------------------------------------------------------------

def _nome_cache_grade(lat: float, lon: float, variavel: str) -> Path:
    """Caminho do cache de um ponto da grade (GRADE_PIAUI_DIR).

    Mesma convenção de nome do nasa_power._nome_cache, mas no diretório
    da grade, para não misturar com caches de pontos individuais.
    """
    lat_s = f"{lat:+.2f}".replace(".", "p").replace("+", "m").replace("-", "n")
    lon_s = f"{lon:+.2f}".replace(".", "p").replace("+", "m").replace("-", "n")
    nome = (f"grade_{lat_s}_{lon_s}_{config.ANO_INICIO_SERIE}"
            f"_{config.ANO_FIM_SERIE}_{variavel}.json")
    return config.GRADE_PIAUI_DIR / nome


def _baixar_ponto_grade(lat: float, lon: float) -> Optional[Dict]:
    """Baixa PRECTOTCORR de um ponto da grade (com cache local).

    Ordem: (1) cache da grade, (2) cache de ponto individual (reaproveita
    se já foi baixado pelo app), (3) rede. Em caso de falha de rede,
    devolve None (o chamador decide pular ou parar).

    Returns:
        Payload JSON da NASA POWER, ou None se falhar.
    """
    var = "PRECTOTCORR"
    cache = _nome_cache_grade(lat, lon, var)
    # 1) Cache local da grade.
    if cache.exists():
        try:
            with cache.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass  # cache corrompido -> baixa de novo
    # 2) Reaproveita cache de ponto individual se existir.
    cache_ponto = nasa_power._nome_cache(lat, lon, config.ANO_INICIO_SERIE,
                                         config.ANO_FIM_SERIE, var)
    if cache_ponto.exists():
        try:
            with cache_ponto.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            config.GRADE_PIAUI_DIR.mkdir(parents=True, exist_ok=True)
            with cache.open("w", encoding="utf-8") as f:
                json.dump(payload, f)
            return payload
        except (json.JSONDecodeError, OSError):
            pass
    # 3) Rede.
    start, end = nasa_power._periodo_para_datas(config.ANO_INICIO_SERIE,
                                                 config.ANO_FIM_SERIE)
    try:
        payload = nasa_power._chamar_api(var, lat, lon, start, end)
        nasa_power._avaliar_resposta(payload, var)
    except nasa_power.NasaPowerError as e:
        _log.warning("Falha ao baixar ponto (%.2f, %.2f): %s", lat, lon, e)
        return None
    # Salva no cache da grade.
    config.GRADE_PIAUI_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with cache.open("w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError as e:
        _log.warning("Não salvou cache da grade (%.2f, %.2f): %s",
                     lat, lon, e)
    return payload


def baixar_grade(passo: float = config.GRADE_PASSO_GRAUS,
                 parar_em_erro: bool = False
                 ) -> Tuple[List[Tuple[float, float, pd.DataFrame]],
                            Dict[str, int]]:
    """Baixa PRECTOTCORR para todos os pontos da grade do Piauí.

    Args:
        passo: resolução da grade em graus.
        parar_em_erro: se True, levanta NasaPowerRedeIndisponivel na
            primeira falha de download (para o app sinalizar "pare,
            não entregue parcial"). Se False, pula o ponto falho.

    Returns:
        (pontos_com_dados, estatisticas)
            pontos_com_dados: [(lat, lon, df_prec), ...] só dos pontos
                baixados com sucesso.
            estatisticas: {"total": N, "ok": N, "falhas": N,
                           "tempo_s": float}.
    """
    t0 = time.time()
    pontos = gerar_pontos_grade(passo)
    out: List[Tuple[float, float, pd.DataFrame]] = []
    n_ok = n_falha = 0
    for lat, lon in pontos:
        payload = _baixar_ponto_grade(lat, lon)
        if payload is None:
            n_falha += 1
            if parar_em_erro:
                raise nasa_power.NasaPowerRedeIndisponivel(
                    f"Download da grade falhou em ({lat}, lon={lon}). "
                    "Parei (parar_em_erro=True) — verifique a conexão "
                    "e tente de novo. Não há cache parcial para a grade."
                )
            continue
        try:
            df, _ = nasa_power.para_dataframe(payload)
        except nasa_power.NasaPowerError as e:
            _log.warning("Payload inválido em (%.2f, %.2f): %s", lat, lon, e)
            n_falha += 1
            continue
        out.append((lat, lon, df))
        n_ok += 1
        time.sleep(0.1)   # cortesia à API entre chamadas de rede
    stats = {
        "total": len(pontos),
        "ok": n_ok,
        "falhas": n_falha,
        "tempo_s": round(time.time() - t0, 1),
    }
    return out, stats


# ---------------------------------------------------------------------------
# 3. Risco hídrico por ponto (reutiliza risco_hidrico_por_classe)
# ---------------------------------------------------------------------------

def risco_ponto(df_prec: pd.DataFrame,
                cultura: Cultura,
                classificacoes,
                classe_enso: str,
                mes_semeadura: Optional[int] = None,
                ) -> Optional[float]:
    """% de anos da classe ENSO com chuva do ciclo < água efetiva.

    Reutiliza `risco_hidrico_por_classe` (Etapa 6) — mesma regra de
    cálculo do app, sem nenhuma alteração. O limiar default é
    `cultura.agua_efetiva_mm_ciclo` (do CSV ou fallback 250 mm).

    Args:
        df_prec: DataFrame com coluna PRECTOTCORR do ponto.
        cultura: cultura escolhida (usa agua_efetiva_mm_ciclo).
        classificacoes: lista de ClassificacaoAno (do enso).
        classe_enso: 'El Niño' / 'La Niña' / 'neutro'.
        mes_semeadura: mês 1..12 (None = melhor_mes_semeadura).

    Returns:
        Percentual 0..100, ou None se a classe não tiver anos.
    """
    risco_por_classe = risco_hidrico_por_classe(
        df_prec, cultura, classificacoes,
        config.ANO_AGRICOLA_PRIMEIRO_COMPLETO,
        config.ANO_AGRICOLA_ULTIMO_COMPLETO,
        mes_semeadura=mes_semeadura,
        # agua_mm_ciclo=None -> usa cultura.agua_efetiva_mm_ciclo.
    )
    return risco_por_classe.get(classe_enso)


def calcular_risco_grade(pontos_dfs: List[Tuple[float, float, pd.DataFrame]],
                        cultura: Cultura,
                        classificacoes,
                        classe_enso: str,
                        mes_semeadura: Optional[int] = None,
                        ) -> List[Dict]:
    """Aplica risco_ponto a todos os pontos da grade.

    Returns:
        [{"lat":, "lon":, "risco_pct":, "n_anos":}, ...] de todos os
        pontos; risco_pct=None se a classe não tiver anos.
    """
    out = []
    for lat, lon, df in pontos_dfs:
        risco = risco_ponto(df, cultura, classificacoes, classe_enso,
                            mes_semeadura=mes_semeadura)
        # Conta anos da classe para o tooltip (reaproveita a mesma fn).
        from core.resiliencia import _chuvas_por_classe
        por = _chuvas_por_classe(
            df, cultura, classificacoes,
            config.ANO_AGRICOLA_PRIMEIRO_COMPLETO,
            config.ANO_AGRICOLA_ULTIMO_COMPLETO,
            mes_semeadura, None, None)
        n_anos = len(por.get(classe_enso) or [])
        out.append({
            "lat": lat, "lon": lon,
            "risco_pct": risco,
            "n_anos": n_anos,
        })
    return out
