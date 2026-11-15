"""Elevação e declividade a partir do SRTM 90 m (serviço público OpenTopoData).

Amostra uma janela 3×3 de pontos espaçados ≈90 m em torno da coordenada e
calcula a declividade pelo método de Horn (1981). O resultado é uma
ESTIMATIVA para a vizinhança do ponto, não um levantamento topográfico do talhão.
"""
from __future__ import annotations

import math
from typing import Optional

import requests

from . import db, settings

ESPACAMENTO_M = 90.0


class TopografiaError(Exception):
    pass


def _grade(lat: float, lon: float):
    dlat = ESPACAMENTO_M / 111_320.0
    dlon = ESPACAMENTO_M / (111_320.0 * max(0.01, math.cos(math.radians(lat))))
    pts = []
    for i in (1, 0, -1):          # norte -> sul
        for j in (-1, 0, 1):      # oeste -> leste
            pts.append((lat + i * dlat, lon + j * dlon))
    return pts


def declividade_horn(z: list, dx: float, dy: float) -> float:
    """z = [a b c / d e f / g h i] (linha norte primeiro). Retorna declividade em %."""
    a, b, c, d, e, f, g, h, i = z
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * dx)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * dy)
    return 100.0 * math.hypot(dzdx, dzdy)


def obter(lat: float, lon: float, sessao: Optional[requests.Session] = None) -> dict:
    if not (-56.0 <= lat <= 60.0):
        raise TopografiaError("SRTM não cobre esta latitude (cobertura 60°N–56°S).")
    chave = f"{lat:.4f},{lon:.4f}"
    cache = db.cache_topo_get(chave)
    if cache:
        return {**cache, "origem": "cache"}
    if settings.OFFLINE:
        raise TopografiaError("Modo offline: sem acesso ao serviço de elevação.")
    pts = _grade(lat, lon)
    locs = "|".join(f"{a:.6f},{b:.6f}" for a, b in pts)
    http = sessao or requests
    try:
        resp = http.get(settings.OPENTOPODATA_URL, params={"locations": locs}, timeout=20)
        resp.raise_for_status()
        dados = resp.json()
    except Exception as e:  # noqa: BLE001
        raise TopografiaError("serviço de elevação SRTM (OpenTopoData) indisponível — sem internet ou serviço fora do ar "
                              f"({type(e).__name__})") from e
    res = dados.get("results") or []
    z = [r.get("elevation") for r in res]
    if len(z) != 9 or any(v is None for v in z):
        raise TopografiaError("Resposta de elevação incompleta (ponto sobre água ou fora da cobertura).")
    dy = ESPACAMENTO_M
    dx = ESPACAMENTO_M
    out = {"elevacao_m": float(z[4]), "declividade_pct": round(declividade_horn(z, dx, dy), 2),
           "fonte": "SRTM 90 m via OpenTopoData (janela 3×3, método de Horn)",
           "aviso": "Estimativa na vizinhança de ~180 m do ponto; não substitui levantamento do talhão."}
    db.cache_topo_set(chave, out)
    return {**out, "origem": "rede"}
