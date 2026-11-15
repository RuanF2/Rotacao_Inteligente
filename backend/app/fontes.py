"""Registro de fontes de dados e verificação de cobertura por localização.

Status possíveis (sem exagero — o que está aqui é o que o sistema realmente faz):
  * "integrado"   — dados numéricos entram nos cálculos;
  * "visual"      — camada de satélite exibida no mapa (tiles NASA GIBS), sem entrar nos cálculos;
  * "nao_integrado" — previsto na arquitetura, ainda não implementado nesta versão.
"""
from __future__ import annotations

from typing import List

from .legacy import legacy_config

FONTES = [
    {"id": "nasa_power", "nome": "NASA POWER (Daily, comunidade AG)", "instituicao": "NASA Langley Research Center",
     "url": "https://power.larc.nasa.gov/", "status": "integrado",
     "uso": "Chuva, temperatura (média/máx/mín), umidade relativa, radiação e umidade do solo (GWETTOP/GWETROOT, modelo). Base de todos os cálculos.",
     "resolucao_espacial": "≈0,5° × 0,625° (meteorologia MERRA-2); ≈1° (radiação)", "resolucao_temporal": "diária, 1981–presente (usamos 1991–2026)",
     "cobertura": "global", "requer": "internet na 1ª consulta de um ponto novo (depois usa cache local)"},
    {"id": "noaa_oni", "nome": "Oceanic Niño Index (ONI v6)", "instituicao": "NOAA Climate Prediction Center",
     "url": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/", "status": "integrado",
     "uso": "Classificação El Niño / La Niña / neutro por ano agrícola (herdado do NASA1).",
     "resolucao_espacial": "índice do Pacífico equatorial (Niño 3.4)", "resolucao_temporal": "trimestral (DJF)",
     "cobertura": "índice global", "requer": "arquivo local data/oni.csv"},
    {"id": "srtm", "nome": "SRTM 90 m (via OpenTopoData)", "instituicao": "NASA/NGA — Shuttle Radar Topography Mission",
     "url": "https://www.earthdata.nasa.gov/data/instruments/srtm", "status": "integrado",
     "uso": "Elevação e declividade estimada (janela 3×3, método de Horn) para o indicador de erosão.",
     "resolucao_espacial": "≈90 m", "resolucao_temporal": "estático (2000)",
     "cobertura": "60°N a 56°S", "requer": "internet (API pública OpenTopoData); o usuário pode informar a declividade manualmente"},
    {"id": "gibs_ndvi", "nome": "MODIS Terra NDVI 16 dias (NASA GIBS)", "instituicao": "NASA EOSDIS / GIBS",
     "url": "https://nasa-gibs.github.io/gibs-api-docs/", "status": "visual",
     "uso": "Camada visual de vegetação no mapa (não entra nos cálculos).",
     "resolucao_espacial": "250 m (produto); tiles até nível 9", "resolucao_temporal": "16 dias",
     "cobertura": "global (terras)", "requer": "internet no navegador"},
    {"id": "gibs_imerg", "nome": "GPM IMERG — taxa de precipitação (NASA GIBS)", "instituicao": "NASA GPM / GIBS",
     "url": "https://gpm.nasa.gov/data/imerg", "status": "visual",
     "uso": "Camada visual de chuva por satélite no mapa (não entra nos cálculos; a chuva numérica vem do NASA POWER).",
     "resolucao_espacial": "0,1°", "resolucao_temporal": "diária (camada GIBS)",
     "cobertura": "global (melhor qualidade entre 60°N e 60°S)", "requer": "internet no navegador"},
    {"id": "gibs_smap", "nome": "SMAP L4 — umidade do solo na zona radicular (NASA GIBS)", "instituicao": "NASA JPL / GIBS",
     "url": "https://smap.jpl.nasa.gov/", "status": "visual",
     "uso": "Camada visual de umidade do solo. A análise numérica usa o GWETROOT do NASA POWER (modelo), não o SMAP.",
     "resolucao_espacial": "9 km", "resolucao_temporal": "diária (camada GIBS)",
     "cobertura": "global (terras), desde 2015", "requer": "internet no navegador"},
    {"id": "landsat", "nome": "Landsat / HLS — NDVI de alta resolução", "instituicao": "NASA / USGS",
     "url": "https://landsat.gsfc.nasa.gov/", "status": "nao_integrado",
     "uso": "Planejado: NDVI em 30 m por talhão. Requer acesso Earthdata/STAC; não implementado nesta versão.",
     "resolucao_espacial": "30 m", "resolucao_temporal": "≈8–16 dias", "cobertura": "global (terras)", "requer": "conta NASA Earthdata"},
    {"id": "ecostress", "nome": "ECOSTRESS — temperatura de superfície e evapotranspiração", "instituicao": "NASA JPL",
     "url": "https://ecostress.jpl.nasa.gov/", "status": "nao_integrado",
     "uso": "Planejado. Cobertura irregular (órbita da ISS).",
     "resolucao_espacial": "≈70 m", "resolucao_temporal": "irregular", "cobertura": "aprox. 52°N a 52°S", "requer": "conta NASA Earthdata"},
    {"id": "cmip6", "nome": "NEX-GDDP-CMIP6", "instituicao": "NASA NCCS",
     "url": "https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6", "status": "nao_integrado",
     "uso": "Planejado para o simulador. Nesta versão o simulador usa perturbações HIPOTÉTICAS (ΔT, ΔP) definidas pelo usuário, claramente rotuladas.",
     "resolucao_espacial": "0,25°", "resolucao_temporal": "diária, 1950–2100", "cobertura": "global (terras)", "requer": "download de grandes arquivos NetCDF"},
]


def _cobre(fonte_id: str, lat: float) -> bool:
    if fonte_id == "srtm":
        return -56.0 <= lat <= 60.0
    if fonte_id == "ecostress":
        return -52.0 <= lat <= 52.0
    return True


def disponibilidade(lat: float, lon: float) -> List[dict]:
    out = []
    tem_cache = legacy_config.local_tem_cache(round(lat, 2), round(lon, 2))
    for f in FONTES:
        cobre = _cobre(f["id"], lat)
        nota = None
        if f["id"] == "nasa_power":
            nota = "cache local disponível (funciona offline)" if tem_cache else "sem cache: será baixado da API (exige internet)"
        if not cobre:
            nota = "fora da área de cobertura do produto para esta latitude"
        out.append({**f, "cobre_local": cobre, "nota_local": nota,
                    "usado_nos_calculos": f["status"] == "integrado" and cobre})
    return out


def locais_demo() -> List[dict]:
    out = []
    for loc in legacy_config.LOCAIS_VALIDADOS:
        out.append({**loc, "categoria": "validado", "tem_cache": legacy_config.local_tem_cache(loc["lat"], loc["lon"])})
    for loc in legacy_config.LOCAIS_DEMOS:
        out.append({**loc, "categoria": "demo_global", "tem_cache": legacy_config.local_tem_cache(loc["lat"], loc["lon"])})
    return out


def camadas_gibs() -> dict:
    return {"camadas": legacy_config.GIBS_CAMADAS, "url_modelo": legacy_config.GIBS_WMTS_BASE,
            "rotulo": legacy_config.GIBS_ROTULO_VISUAL}
