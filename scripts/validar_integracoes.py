"""Validação das integrações externas contra os serviços REAIS (exige internet).

Testa, usando o mesmo código do backend:
  1. NASA POWER  — ponto novo, SEM cache (download das 8 variáveis 1991–2026);
  2. OpenTopoData — elevação SRTM 90 m e declividade (banco de cache temporário, para não mascarar);
  2b. OpenStreetMap Nominatim — geocodificação reversa (município/região/país);
  3. NASA GIBS    — GetCapabilities + 1 tile real de cada camada usada no mapa.

Gera `VALIDACAO_INTEGRACOES.md` e `validacao_integracoes.json` na raiz do projeto com URL, status HTTP,
duração, data/hora UTC, tamanho da resposta e erro (se houver). Nada é simulado: se o serviço não
responder, o teste é registrado como FALHOU.

Uso (na raiz do projeto, com o ambiente do backend ativado):
    python scripts/validar_integracoes.py
    python scripts/validar_integracoes.py --lat -9.39 --lon -40.50     # escolher outro ponto novo
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))
os.environ["ROTACAO_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "validacao.db")  # cache SRTM vazio
os.environ["ROTACAO_OFFLINE"] = "0"

import requests  # noqa: E402

from app import clima, geocodificacao, topografia  # noqa: E402
from app.legacy import legacy_config, nasa_power  # noqa: E402

REG: list[dict] = []


def agora() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def registrar(servico, etapa, ok, **kw):
    item = {"servico": servico, "etapa": etapa, "resultado": "OK" if ok else "FALHOU", "quando_utc": agora(), **kw}
    REG.append(item)
    print(f"[{item['resultado']:6}] {servico} — {etapa}: " + ", ".join(f"{k}={v}" for k, v in kw.items() if k != "amostra"))
    return item


# ---------------------------------------------------------------------------
# Registro das requisições HTTP feitas pelo núcleo (sem alterar o código dele)
# ---------------------------------------------------------------------------
_get_original = requests.get


def _get_registrado(url, *a, **kw):
    t0 = time.time()
    try:
        r = _get_original(url, *a, **kw)
        REG.append({"servico": "http", "etapa": "requisição", "resultado": "OK" if r.ok else "FALHOU",
                    "quando_utc": agora(), "url": r.url, "status": r.status_code,
                    "duracao_s": round(time.time() - t0, 2), "bytes": len(r.content)})
        return r
    except Exception as e:  # noqa: BLE001
        REG.append({"servico": "http", "etapa": "requisição", "resultado": "FALHOU", "quando_utc": agora(),
                    "url": url, "params": str(kw.get("params"))[:300], "erro": f"{type(e).__name__}: {e}"[:300],
                    "duracao_s": round(time.time() - t0, 2)})
        raise


requests.get = _get_registrado


def testar_power(lat: float, lon: float):
    vars_ = legacy_config.NASA_POWER_VARS
    existentes = [v for v in vars_ if nasa_power._nome_cache(lat, lon, legacy_config.ANO_INICIO_SERIE,
                                                              legacy_config.ANO_FIM_SERIE, v).exists()]
    if existentes:
        registrar("NASA POWER", "pré-condição: ponto sem cache", False,
                  detalhe=f"já há cache para {existentes}; escolha outro --lat/--lon")
        return
    registrar("NASA POWER", "pré-condição: ponto sem cache", True, lat=lat, lon=lon)
    t0 = time.time()
    try:
        s = clima.carregar(lat, lon)
    except Exception as e:  # noqa: BLE001
        registrar("NASA POWER", "download e leitura da série", False, erro=f"{type(e).__name__}: {e}"[:400])
        return
    df = s.df
    criados = [v for v in vars_ if nasa_power._nome_cache(lat, lon, legacy_config.ANO_INICIO_SERIE,
                                                           legacy_config.ANO_FIM_SERIE, v).exists()]
    ok = not s.falhas and len(criados) == len(vars_)
    registrar("NASA POWER", "download e leitura da série", ok, origem="NASA POWER ao vivo",
              duracao_s=round(time.time() - t0, 1), periodo=f"{df.index.min().date()}..{df.index.max().date()}",
              dias=len(df), anos_completos=len(s.anos_completos), falhas=s.falhas or "nenhuma",
              arquivos_cache_criados=len(criados))
    if ok:
        payload = json.loads(nasa_power._nome_cache(lat, lon, legacy_config.ANO_INICIO_SERIE,
                                                    legacy_config.ANO_FIM_SERIE, "PRECTOTCORR").read_text())
        h = payload.get("header", {})
        registrar("NASA POWER", "metadados da resposta", True, api=h.get("api", {}).get("version"),
                  fontes=h.get("sources"), coords=payload.get("geometry", {}).get("coordinates"))
        ind = clima.indicadores(s)
        registrar("NASA POWER", "indicadores calculados com o dado baixado", True,
                  chuva_anual_mm=round(ind["precipitacao_anual_media_mm"]), aridez=round(ind["indice_aridez"], 2),
                  dias_calor=round(ind["dias_calor_ano_medio"]))


def testar_srtm(lat: float, lon: float):
    t0 = time.time()
    try:
        r = topografia.obter(lat, lon)
        ok = r["origem"] == "rede" and r["elevacao_m"] is not None
        registrar("OpenTopoData (SRTM 90 m)", "elevação e declividade", ok, origem=r["origem"],
                  elevacao_m=r["elevacao_m"], declividade_pct=r["declividade_pct"], duracao_s=round(time.time() - t0, 1),
                  url=topografia.settings.OPENTOPODATA_URL)
    except Exception as e:  # noqa: BLE001
        registrar("OpenTopoData (SRTM 90 m)", "elevação e declividade", False, erro=str(e)[:400])


def testar_geocodificacao(lat: float, lon: float):
    t0 = time.time()
    try:
        r = geocodificacao.reverso(lat, lon)
        registrar("OpenStreetMap Nominatim", "geocodificação reversa", r["origem"] == "rede",
                  origem=r["origem"], identificado=r["identificado"], municipio=r["municipio"], regiao=r["regiao"],
                  pais=r["pais"], duracao_s=round(time.time() - t0, 1), url=geocodificacao.URL)
    except Exception as e:  # noqa: BLE001
        registrar("OpenStreetMap Nominatim", "geocodificação reversa", False, erro=str(e)[:300])


def _tile_xy(lat, lon, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def testar_gibs(lat: float, lon: float):
    t0 = time.time()
    try:
        r = _get_original(legacy_config.GIBS_CAPABILITIES_URL, timeout=60)
        registrar("NASA GIBS", "GetCapabilities", r.ok, status=r.status_code, bytes=len(r.content),
                  duracao_s=round(time.time() - t0, 1))
        if not r.ok:
            return
    except Exception as e:  # noqa: BLE001
        registrar("NASA GIBS", "GetCapabilities", False, erro=f"{type(e).__name__}: {e}"[:300])
        return
    from core import gibs  # núcleo do NASA1
    for chave, c in legacy_config.GIBS_CAMADAS.items():
        try:
            alvo = dt.date.today() - dt.timedelta(days=20)
            data = gibs.data_mais_proxima_valida(chave, alvo)
            data_s = data.isoformat() if data else alvo.isoformat()
            z = 3
            x, y = _tile_xy(lat, lon, z)
            url = (legacy_config.GIBS_WMTS_BASE.replace("{layer}", c["id"]).replace("{time}", data_s)
                   .replace("{tile_matrix_set}", c["tile_matrix_set"])
                   .replace("{z}", str(z)).replace("{y}", str(y)).replace("{x}", str(x)))
            t1 = time.time()
            t = _get_original(url, timeout=60)
            ok = t.ok and t.headers.get("Content-Type", "").startswith("image/")
            registrar("NASA GIBS", f"tile {c['id']}", ok, data=data_s, status=t.status_code,
                      content_type=t.headers.get("Content-Type"), bytes=len(t.content),
                      duracao_s=round(time.time() - t1, 1), url=url)
        except Exception as e:  # noqa: BLE001
            registrar("NASA GIBS", f"tile {c['id']}", False, erro=f"{type(e).__name__}: {e}"[:300])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=-9.39)    # Petrolina-PE (semiárido), sem cache no pacote
    ap.add_argument("--lon", type=float, default=-40.50)
    a = ap.parse_args()
    print(f"Validação de integrações — início {agora()} — ponto ({a.lat}, {a.lon})\n")
    testar_power(a.lat, a.lon)
    testar_srtm(a.lat, a.lon)
    testar_geocodificacao(a.lat, a.lon)
    testar_gibs(a.lat, a.lon)
    resumo = {}
    for r in REG:
        if r["servico"] != "http":
            resumo.setdefault(r["servico"], []).append(r["resultado"])
    (RAIZ / "validacao_integracoes.json").write_text(json.dumps(REG, ensure_ascii=False, indent=1), encoding="utf-8")
    L = [f"# Validação das integrações externas\n", f"Executado em {agora()} (UTC), ponto ({a.lat}, {a.lon}).\n",
         "| Serviço | Etapas OK | Etapas com falha |", "|---|---|---|"]
    for s, rs in resumo.items():
        L.append(f"| {s} | {rs.count('OK')} | {rs.count('FALHOU')} |")
    L.append("\n## Registro detalhado\n")
    for r in REG:
        L.append("- " + " · ".join(f"**{k}**: {v}" for k, v in r.items()))
    L.append("\n## Verificação visual no navegador (GIBS)\n")
    L.append("Abra a interface → Análise ambiental → mapa → seletor de camadas, ligue NDVI, IMERG e SMAP e confirme que "
             "as imagens aparecem. Anote o resultado aqui; este script testa os tiles por HTTP, não a renderização.")
    (RAIZ / "VALIDACAO_INTEGRACOES.md").write_text("\n".join(L), encoding="utf-8")
    falhou = any(r["resultado"] == "FALHOU" for r in REG if r["servico"] != "http")
    print(f"\nRelatório: {RAIZ / 'VALIDACAO_INTEGRACOES.md'}  —  {'HÁ FALHAS' if falhou else 'TODAS AS ETAPAS OK'}")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
