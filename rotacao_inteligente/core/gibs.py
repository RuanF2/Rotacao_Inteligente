"""Camadas de satélite da NASA GIBS (WMTS, EPSG:3857) para o bloco Mapa.

Os identificadores de camada (MODIS_Terra_L3_NDVI_16Day,
IMERG_Precipitation_Rate, SMAP_L4_Analyzed_Root_Zone_Soil_Moisture)
foram LIDOS do GetCapabilities do GIBS em 2026-11-14 — não são nomes
de memória. Esta função lê o GetCapabilities para:
  - validar os IDs das camadas;
  - ler a DIMENSÃO TEMPORAL de cada camada (correção 2026-11-14):
    `<Default>` = data mais recente recomendada; `<Value>` = lista de
    intervalos `start/end/PnD` (ex.: 2026-05-27/2026-11-13/P1D).

Funções públicas:
  - camadas_disponiveis() -> ids + validade + datas de cada camada.
  - data_padrao(camada) -> data mais recente (do <Default>).
  - data_mais_proxima_valida(camada, data_desejada) -> ajusta a data
    escolhida para a data válida mais próxima dentro dos intervalos.
  - verificar_tile(camada, data) -> HEAD no tile; True se responde.
  - tile_url_gibs(camada, data) -> URL WMTS para folium.

As camadas são VISUAL: não entram em nenhum cálculo do app. O rótulo
`config.GIBS_ROTULO_VISUAL` deixa isso claro na UI.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

import requests

import config

_log = logging.getLogger(__name__)

# Timeout curto: se o GIBS não responder, o app segue sem tiles.
_TIMEOUT_S = 8

# Namespace OWS usado no WMTSCapabilities.
_OWS = "{http://www.opengis.net/ows/1.1}"
# Namespace WMTS (Layer, Dimension, Default, Current, Value estão aqui).
_WMTS = "{http://www.opengis.net/wmts/1.0}"

# Cache em memória do GetCapabilities parseado (uma leitura por sessão).
_CAPS_CACHE: Optional["ET.Element"] = None


# ---------------------------------------------------------------------------
# Parse do GetCapabilities (IDs + dimensão temporal por camada)
# ---------------------------------------------------------------------------

def _baixar_caps() -> Optional[ET.Element]:
    """Lê e cacheia o GetCapabilities do GIBS. Devolve None se falhar."""
    global _CAPS_CACHE
    if _CAPS_CACHE is not None:
        return _CAPS_CACHE
    try:
        r = requests.get(config.GIBS_CAPABILITIES_URL, timeout=_TIMEOUT_S)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001 — rede é best-effort
        _log.warning("GetCapabilities GIBS falhou: %s", e)
        return None
    try:
        _CAPS_CACHE = ET.fromstring(r.content)
    except ET.ParseError as e:
        _log.warning("GetCapabilities GIBS não é XML válido: %s", e)
        return None
    return _CAPS_CACHE


def _bloco_camada(root: ET.Element, ident: str) -> Optional[ET.Element]:
    """Acha o bloco <Layer> cujo <ows:Identifier> == ident."""
    for layer in root.iter(f"{_WMTS}Layer"):
        ident_el = layer.find(f"{_OWS}Identifier")
        if ident_el is not None and ident_el.text == ident:
            return layer
    return None


def _parse_intervalos(dimension_el: ET.Element) -> List[Tuple[_dt.date, _dt.date, int]]:
    """Parse dos <Value>start/end/PnD</Value> de uma <Dimension>.

    Devolve lista de (start, end, periodo_dias). PnD -> n dias
    (P1D=1, P16D=16). Intervalos sem período (data única) viram
    (d, d, 1). Robusto a formatos variados do GIBS.
    """
    out: List[Tuple[_dt.date, _dt.date, int]] = []
    for val_el in dimension_el.iter(f"{_WMTS}Value"):
        texto = (val_el.text or "").strip()
        if not texto:
            continue
        # Formato: start/end/PnD  ou  start/end  ou  data_unica
        partes = texto.split("/")
        if len(partes) == 3:
            try:
                start = _dt.date.fromisoformat(partes[0])
                end = _dt.date.fromisoformat(partes[1])
            except ValueError:
                continue
            m = re.match(r"P(\d+)D", partes[2])
            periodo = int(m.group(1)) if m else 1
            out.append((start, end, periodo))
        elif len(partes) == 2:
            try:
                start = _dt.date.fromisoformat(partes[0])
                end = _dt.date.fromisoformat(partes[1])
            except ValueError:
                continue
            out.append((start, end, 1))
        elif len(partes) == 1:
            try:
                d = _dt.date.fromisoformat(partes[0])
                out.append((d, d, 1))
            except ValueError:
                continue
    return out


def _data_do_default(dimension_el: ET.Element) -> Optional[_dt.date]:
    """Lê o <Default> da dimensão temporal (data mais recente)."""
    default_el = dimension_el.find(f"{_WMTS}Default")
    if default_el is None or not (default_el.text or "").strip():
        return None
    try:
        return _dt.date.fromisoformat(default_el.text.strip())
    except ValueError:
        return None


def _info_temporal_camada(root: ET.Element, ident: str
                          ) -> Tuple[Optional[_dt.date], List[Tuple[_dt.date, _dt.date, int]]]:
    """Devolve (data_default, intervalos) da camada, lidos do XML.

    data_default: do <Default> (data mais recente recomendada).
    intervalos: lista de (start, end, periodo_dias) dos <Value>.
    """
    bloco = _bloco_camada(root, ident)
    if bloco is None:
        return None, []
    # Acha a <Dimension> temporal (identifier == "Time").
    for dim in bloco.iter(f"{_WMTS}Dimension"):
        dim_ident = dim.find(f"{_OWS}Identifier")
        if dim_ident is None or dim_ident.text != "Time":
            continue
        default = _data_do_default(dim)
        intervalos = _parse_intervalos(dim)
        return default, intervalos
    return None, []


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def camadas_disponiveis() -> Dict[str, dict]:
    """Devolve o subconjunto de config.GIBS_CAMADAS com info do GIBS.

    Cada camada traz:
      - validado: True se o ID existe no GetCapabilities.
      - data_padrao: data mais recente (do <Default>), ou None.
      - intervalos: [(start, end, periodo_dias), ...] dos <Value>.

    Se NÃO houver rede, devolve TODAS as camadas do config marcadas
    validado=False e sem info temporal (melhor esforço: tentamos mostrar
    mesmo sem validar — o tile pode funcionar mesmo se o GetCaps falhar).
    """
    root = _baixar_caps()
    out: Dict[str, dict] = {}
    for chave, camada in config.GIBS_CAMADAS.items():
        default, intervalos = (None, [])
        validado = False
        if root is not None:
            d, ints = _info_temporal_camada(root, camada["id"])
            validado = _bloco_camada(root, camada["id"]) is not None
            default, intervalos = d, ints
        out[chave] = {
            **camada,
            "validado": validado,
            "data_padrao": default,
            "intervalos": intervalos,
        }
    return out


def data_padrao(camada: str) -> Optional[_dt.date]:
    """Data mais recente da camada (do <Default> do GetCapabilities).

    Devolve None se a camada não existir ou a rede falhar.
    """
    if camada not in config.GIBS_CAMADAS:
        return None
    info = camadas_disponiveis().get(camada)
    return info["data_padrao"] if info else None


def data_mais_proxima_valida(camada: str, data_desejada: _dt.date
                              ) -> Optional[_dt.date]:
    """Ajusta `data_desejada` para a data VÁLIDA mais próxima da camada.

    Cada intervalo (start, end, periodo) define um conjunto de datas
    válidas: start, start+periodo, start+2*periodo, ..., <= end. Para
    cada intervalo, acha a data válida mais próxima de data_desejada;
    entre todos os intervalos, devolve a mais próxima global.

    Ex.: IMERG (P1D) com data_desejada=2026-11-14 e intervalo
    2026-05-27/2026-11-13/P1D -> 2026-11-13 (última disponível).

    Devolve None se a camada não existir, a rede falhar, ou não houver
    intervalos (e nem Default). Se houver Default mas não intervalos,
    devolve o Default.
    """
    if camada not in config.GIBS_CAMADAS:
        return None
    info = camadas_disponiveis().get(camada)
    if not info:
        return None
    intervalos = info.get("intervalos") or []
    if not intervalos:
        return info.get("data_padrao")

    melhor: Optional[_dt.date] = None
    melhor_dist = None
    for start, end, periodo in intervalos:
        # Datas válidas: start, start+periodo, ..., <= end.
        if periodo < 1:
            periodo = 1
        # Se a data_desejada está DENTRO do intervalo [start, end],
        # a data válida mais próxima é o piso/techo no grid do período.
        # Calcula direto (evita iterar milhares de dias para P1D).
        if start <= data_desejada <= end:
            delta = (data_desejada - start).days
            # Índices vizinhos no grid.
            k_lo = delta // periodo
            cand_lo = start + _dt.timedelta(days=k_lo * periodo)
            cand_hi = start + _dt.timedelta(days=(k_lo + 1) * periodo)
            for cand in (cand_lo, cand_hi):
                if start <= cand <= end:
                    dist = abs((data_desejada - cand).days)
                    if melhor is None or dist < melhor_dist:
                        melhor, melhor_dist = cand, dist
                        if dist == 0:
                            return melhor
            continue
        # Fora do intervalo: a borda mais próxima (start ou end).
        for borda in (start, end):
            dist = abs((data_desejada - borda).days)
            if melhor is None or dist < melhor_dist:
                melhor, melhor_dist = borda, dist
    return melhor


def verificar_tile(camada: str, data: str) -> bool:
    """Faz um HEAD no tile 0/0/0 e devolve True se responde (200).

    Usado pelo app para avisar quando os tiles não carregam (sem rede
    ou data inválida). Timeout curto; nunca levanta — só devolve
    False em falha.
    """
    url = tile_url_gibs(camada, data)
    if not url:
        return False
    # Tile 0/0/0 (z/x/y) — existe em todas as camadas globais do GIBS.
    url_tile = url.format(z=0, y=0, x=0)
    try:
        r = requests.head(url_tile, timeout=_TIMEOUT_S, allow_redirects=True)
        return r.status_code == 200
    except Exception as e:  # noqa: BLE001
        _log.warning("verificar_tile %s @ %s falhou: %s", camada, data, e)
        return False


def tile_url_gibs(camada: str, data: str) -> Optional[str]:
    """Monta a URL de tiles WMTS do GIBS para a camada e data.

    Args:
        camada: chave em config.GIBS_CAMADAS ('ndvi'/'imerg'/'smap').
        data: data no formato YYYY-MM-DD (ou 'default' para a última
              recomendada — mas o app ajusta antes com
              data_mais_proxima_valida).

    Returns:
        URL pronta para folium.TileLayer(tiles=...), ou None se a
        camada não existir no config.
    """
    if camada not in config.GIBS_CAMADAS:
        return None
    c = config.GIBS_CAMADAS[camada]
    # Usa replace (não str.format) para não tocar nos placeholders
    # {z}/{y}/{x} que o folium.TileLayer resolve depois.
    return (config.GIBS_WMTS_BASE
            .replace("{layer}", c["id"])
            .replace("{time}", data)
            .replace("{tile_matrix_set}", c["tile_matrix_set"]))
