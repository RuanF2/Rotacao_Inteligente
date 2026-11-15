"""Geocodificação reversa (coordenada → município/região/país) via OpenStreetMap Nominatim.

Regras de uso do Nominatim respeitadas (https://operations.osmfoundation.org/policies/nominatim/):
  * no máximo 1 requisição por segundo (trava global + espera mínima entre chamadas);
  * User-Agent identificando a aplicação (configurável por ROTACAO_GEOCODER_UA);
  * resultados guardados em cache (SQLite), por coordenada arredondada a 3 casas (~100 m).

Nunca deduz localidade sem a fonte: se o serviço falhar ou não houver endereço (ex.: oceano), o
resultado é "não identificada" e o chamador mantém só as coordenadas.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Optional

import requests

from . import db, settings

URL = os.environ.get("ROTACAO_GEOCODER_URL", "https://nominatim.openstreetmap.org/reverse")
USER_AGENT = os.environ.get("ROTACAO_GEOCODER_UA", "RotacaoInteligente/2.0 (NASA Space Apps 2026; uso educacional)")
INTERVALO_MIN_S = 1.1
FONTE = "OpenStreetMap Nominatim"
LICENCA = "© colaboradores do OpenStreetMap (ODbL)"

_trava = threading.Lock()
_ultima = {"t": 0.0}


class GeocodificacaoError(Exception):
    """Serviço indisponível, limite excedido ou resposta inválida."""


def _chave(lat: float, lon: float) -> str:
    return f"{lat:.3f},{lon:.3f}"


def _cache_get(chave: str) -> Optional[dict]:
    with db.conectar() as con:
        con.execute("CREATE TABLE IF NOT EXISTS cache_geocodificacao (chave TEXT PRIMARY KEY, dados TEXT NOT NULL)")
        row = con.execute("SELECT dados FROM cache_geocodificacao WHERE chave=?", (chave,)).fetchone()
    return json.loads(row["dados"]) if row else None


def _cache_set(chave: str, dados: dict) -> None:
    with db.conectar() as con:
        con.execute("CREATE TABLE IF NOT EXISTS cache_geocodificacao (chave TEXT PRIMARY KEY, dados TEXT NOT NULL)")
        con.execute("INSERT OR REPLACE INTO cache_geocodificacao (chave, dados) VALUES (?,?)", (chave, json.dumps(dados)))


def interpretar(payload: dict, lat: float, lon: float) -> dict:
    """Converte a resposta do Nominatim; sem endereço => não identificada (nada é inventado)."""
    base = {"lat": lat, "lon": lon, "fonte": FONTE, "licenca": LICENCA}
    if not isinstance(payload, dict) or payload.get("error") or not payload.get("address"):
        return {**base, "identificado": False, "municipio": None, "regiao": None, "pais": None,
                "codigo_pais": None, "descricao": None,
                "motivo": (payload or {}).get("error", "sem endereço para este ponto") if isinstance(payload, dict) else "resposta inválida"}
    a = payload["address"]
    municipio = (a.get("city") or a.get("town") or a.get("village") or a.get("municipality")
                 or a.get("hamlet") or a.get("county"))
    regiao = a.get("state") or a.get("region") or a.get("province")
    pais = a.get("country")
    return {**base, "identificado": bool(pais), "municipio": municipio, "regiao": regiao, "pais": pais,
            "codigo_pais": (a.get("country_code") or "").upper() or None,
            "descricao": payload.get("display_name"), "motivo": None if pais else "resposta sem país"}


def reverso(lat: float, lon: float, sessao: Optional[requests.Session] = None) -> dict:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordenadas fora do intervalo válido.")
    chave = _chave(lat, lon)
    cache = _cache_get(chave)
    if cache:
        return {**cache, "origem": "cache"}
    if settings.OFFLINE:
        raise GeocodificacaoError("Modo offline: geocodificação reversa indisponível.")
    http = sessao or requests
    with _trava:  # serializa as chamadas e respeita 1 req/s
        espera = INTERVALO_MIN_S - (time.monotonic() - _ultima["t"])
        if espera > 0:
            time.sleep(espera)
        try:
            resp = http.get(URL, params={"lat": f"{lat:.5f}", "lon": f"{lon:.5f}", "format": "jsonv2", "zoom": 10,
                                         "addressdetails": 1, "accept-language": "pt-BR,pt,en"},
                            headers={"User-Agent": USER_AGENT}, timeout=10)
        except requests.RequestException as e:
            raise GeocodificacaoError(f"Serviço de geocodificação indisponível ({type(e).__name__}).") from e
        finally:
            _ultima["t"] = time.monotonic()
    if resp.status_code == 429:
        raise GeocodificacaoError("Limite de requisições do serviço de geocodificação atingido; tente em alguns segundos.")
    if resp.status_code >= 400:
        raise GeocodificacaoError(f"Serviço de geocodificação respondeu HTTP {resp.status_code}.")
    try:
        dados = interpretar(resp.json(), lat, lon)
    except ValueError as e:
        raise GeocodificacaoError("Resposta de geocodificação inválida.") from e
    _cache_set(chave, dados)
    return {**dados, "origem": "rede"}
