"""tests/test_grade_risco.py - Testes da grade de risco hídrico do Piauí.

Estratégia (igual ao test_nasa_power.py):
- Testes de unidade: monkeypatch em requests.get para simular a rede,
  fixtures de payload e classificação ENSO. Não dependem de internet.
- Um teste marcado "online" (skip por padrão) baixa a grade real e
  reporta tempo + nº de pontos.

Cobre (revisão 2026-11-14):
- gerar_pontos_grade: nº de pontos e ordenação dentro do bbox do Piauí.
- _baixar_ponto_grade: cache hit não chama rede; cache miss chama e
  salva no cache da grade.
- risco_ponto: reutiliza risco_hidrico_por_classe (mesma regra do app).
- baixar_grade(parar_em_erro=True): para na 1ª falha (não entrega parcial).

Rodar:
    pytest -v                          # só testes offline
    pytest -v --run-online             # inclui o teste online da grade
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import config
from core import nasa_power, grade_risco
from core.culturas import Cultura
from core.enso import ClassificacaoAno


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _cultura(ciclo_dias=30, agua_mm_ciclo=200.0):
    """Cria uma Cultura mínima para os testes (sem ler o CSV).

    Mesma assinatura do helper cultura() em test_etapa6.py, com todos
    os campos opcionais preenchidos (None ou default).
    """
    return Cultura(
        nome="cultura-teste", tipo="comercial",
        ciclo_dias=ciclo_dias, agua_mm_ciclo=agua_mm_ciclo,
        tmax_limite_c=None, fixa_nitrogenio="nao",
        protecao_erosao=None, valor_mercado=None,
        taxa_semeadura_kg_ha=None, rendimento_potencial_kg_ha=None,
        rendimento_regional_kg_ha=None, fonte="", lacunas=[],
    )


class FakeResponse:
    """Simula requests.Response (igual ao test_nasa_power.py)."""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.exceptions.HTTPError(
                f"{self.status_code} error", response=self)


def _payload_prec_fake(lat, lon, chuva_fev=10.0, anos=range(2000, 2011)):
    """Payload PRECTOTCORR fake: chuva só em fevereiro (chuva_fev mm/dia).

    Ciclo de 30 dias a partir de 1/fev -> 30 × chuva_fev mm.
    """
    por_dia = {}
    for y in anos:
        for m in range(1, 13):
            for d in range(1, 29):   # 28 dias/mês para simplificar
                data = f"{y}{m:02d}{d:02d}"
                por_dia[data] = chuva_fev if m == 2 else 0.0
    return {
        "geometry": {"type": "Point", "coordinates": [lon, lat, 0]},
        "parameters": {"PRECTOTCORR": {"longname": "Precipitation Correction",
                                       "units": "mm"}},
        "properties": {"parameter": {"PRECTOTCORR": por_dia}},
    }


@pytest.fixture
def grade_tmp(tmp_path, monkeypatch):
    """Troca GRADE_PIAUI_DIR e CACHE_DIR por dirs temporários."""
    monkeypatch.setattr(config, "GRADE_PIAUI_DIR", tmp_path / "grade")
    (tmp_path / "grade").mkdir(parents=True)
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    (tmp_path / "cache").mkdir(parents=True)
    return config.GRADE_PIAUI_DIR


@pytest.fixture
def classes_enso_mock():
    """Classificação mock: El Niño em todos os anos 2000-2010."""
    return [
        ClassificacaoAno(ano=y, oni=1.0, classe="El Niño",
                          no_limite=False)
        for y in range(2000, 2011)
    ]


# ---------------------------------------------------------------------------
# 1. gerar_pontos_grade — nº de pontos e ordenação
# ---------------------------------------------------------------------------

def test_gerar_pontos_grade_dentro_do_bbox():
    """Todos os pontos da grade devem cair dentro do retângulo do Piauí
    (mesmo no modo malha, os candidatos são gerados no retângulo e
    depois filtrados — então todo ponto está dentro do retângulo)."""
    pts = grade_risco.gerar_pontos_grade()
    assert len(pts) > 0, "grade não pode ser vazia"
    b = config.PIAUI_BBOX
    for lat, lon in pts:
        assert b["lat_min"] - 1e-9 <= lat <= b["lat_max"] + 1e-9
        assert b["lon_min"] - 1e-9 <= lon <= b["lon_max"] + 1e-9


def test_gerar_pontos_grade_ordenacao_norte_sul():
    """Pontos ordenados Norte→Sul, Oeste→Leste (lat desc, lon cres)."""
    pts = grade_risco.gerar_pontos_grade()
    lats = [p[0] for p in pts]
    assert lats == sorted(lats, reverse=True), "lat deve ser decrescente"


def test_gerar_pontos_grade_resolucao_1grau():
    """Com passo 1°, a grade do Piauí (retângulo -10.93..-2.74,
    -45.99..-40.37) tem ~40 pontos no fallback retangular."""
    pts = grade_risco.gerar_pontos_grade(1.0)
    # lat: -10 a -3 (8) × lon: -45 a -41 (5) = 40 candidatos no retângulo.
    # Sem malha -> 40 pontos. Com malha -> ≤40 (filtro por fronteira).
    assert 20 <= len(pts) <= 50, f"nº de pontos inesperado: {len(pts)}"


# ---------------------------------------------------------------------------
# 1.b. Ponto-em-polígono (correção 2) e fonte_do_filtro
# ---------------------------------------------------------------------------

def test_ponto_em_poligono_quadrado():
    """Ray casting num quadrado unitário (0,0)-(1,1)."""
    ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    assert grade_risco._ponto_em_poligono(0.5, 0.5, [ring])    # dentro
    assert not grade_risco._ponto_em_poligono(1.5, 0.5, [ring])  # fora
    assert not grade_risco._ponto_em_poligono(-0.1, 0.5, [ring])  # fora


def test_ponto_em_poligono_com_buraco():
    """Ponto no buraco (anel interno) NÃO está dentro do polígono."""
    ext = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]  # exterior
    buraco = [(1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0)]  # buraco
    # (2,2) está no buraco -> fora do polígono efetivo.
    assert not grade_risco._ponto_em_poligono(2.0, 2.0, [ext, buraco])
    # (0.5,0.5) está no exterior e fora do buraco -> dentro.
    assert grade_risco._ponto_em_poligono(0.5, 0.5, [ext, buraco])


def test_fonte_do_filtro_retangulo_sem_malha(grade_tmp, monkeypatch):
    """Sem data/piaui_uf.geojson, a fonte do filtro é 'retângulo'."""
    # Garante que a malha não existe e reseta o cache em memória.
    if config.PIAUI_MALHA_GEOJSON.exists():
        monkeypatch.setattr(config, "PIAUI_MALHA_GEOJSON",
                             grade_tmp.parent / "inexistente.geojson")
    grade_risco._RINGS_PIAUI = None
    grade_risco._FONTE_FILTRO = None
    assert grade_risco.fonte_do_filtro() == "retângulo"


def test_fonte_do_filtro_malha_quando_existe(grade_tmp, tmp_path,
                                              monkeypatch):
    """Com data/piaui_uf.geojson válido, a fonte é 'malha oficial' e a
    grade é filtrada por ponto-em-polígono."""
    # Cria um GeoJSON fake: um polígono retangular pequeno perto de
    # Teresina (-6..-4 lat, -44..-42 lon). Só os pontos da grade que
    # caírem dentro dele passam.
    geo = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-44.0, -6.0], [-42.0, -6.0],
                                  [-42.0, -4.0], [-44.0, -4.0],
                                  [-44.0, -6.0]]]
            },
            "properties": {},
        }],
    }
    import json
    caminho = tmp_path / "piaui_uf.geojson"
    caminho.write_text(json.dumps(geo), encoding="utf-8")
    monkeypatch.setattr(config, "PIAUI_MALHA_GEOJSON", caminho)
    # Reduz o bbox pra conter só esse pedaço (teste rápido).
    monkeypatch.setattr(config, "PIAUI_BBOX",
                        {"lat_min": -7.0, "lat_max": -3.0,
                         "lon_min": -45.0, "lon_max": -41.0})
    grade_risco._RINGS_PIAUI = None
    grade_risco._FONTE_FILTRO = None
    assert grade_risco.fonte_do_filtro() == "malha oficial"
    pts = grade_risco.gerar_pontos_grade()
    # No retângulo -7..-3 × -45..-41 com passo 1: (-6,-44),(-6,-43),
    # (-6,-42),(-5,-44),(-5,-43),(-5,-42),(-4,-44),(-4,-43),(-4,-42).
    # O polígono -6..-4 × -44..-42 inclui (-5,-43). Cantos (-6,-44)
    # etc. podem cair exatamente na borda (ray cast: borda é ambíguo,
    # aceitamos 1 a 9).
    assert 1 <= len(pts) <= 9
    # Limpa cache em memória p/ não vazar p/ outros testes.
    grade_risco._RINGS_PIAUI = None
    grade_risco._FONTE_FILTRO = None


# ---------------------------------------------------------------------------
# 2. _baixar_ponto_grade — cache hit não chama rede
# ---------------------------------------------------------------------------

def test_baixar_ponto_grade_cache_hit_nao_chama_rede(grade_tmp,
                                                     monkeypatch):
    """Se o cache da grade existe, requests.get NÃO é chamado."""
    lat, lon = -5.0, -43.0
    payload = _payload_prec_fake(lat, lon)
    cache_file = grade_risco._nome_cache_grade(lat, lon, "PRECTOTCORR")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    chamadas = {"n": 0}

    def fake_get(url, **kwargs):
        chamadas["n"] += 1
        return FakeResponse(200, payload)

    monkeypatch.setattr(nasa_power.requests, "get", fake_get)

    out = grade_risco._baixar_ponto_grade(lat, lon)
    assert out == payload
    assert chamadas["n"] == 0, "não deveria chamar rede com cache"


def test_baixar_ponto_grade_cache_miss_chama_e_salva(grade_tmp,
                                                      monkeypatch):
    """Sem cache, chama a rede e SALVA no cache da grade."""
    lat, lon = -6.0, -44.0
    payload = _payload_prec_fake(lat, lon)

    chamadas = {"n": 0}

    def fake_get(url, **kwargs):
        chamadas["n"] += 1
        return FakeResponse(200, payload)

    monkeypatch.setattr(nasa_power.requests, "get", fake_get)

    out = grade_risco._baixar_ponto_grade(lat, lon)
    assert out == payload
    assert chamadas["n"] == 1, "deveria chamar a rede 1x sem cache"
    cache_file = grade_risco._nome_cache_grade(lat, lon, "PRECTOTCORR")
    assert cache_file.exists(), "deveria salvar no cache da grade"


# ---------------------------------------------------------------------------
# 3. risco_ponto — reutiliza risco_hidrico_por_classe
# ---------------------------------------------------------------------------

def test_risco_ponto_chuva_suficiente_risco_zero(grade_tmp,
                                                  classes_enso_mock):
    """Cultura com água 200mm, ciclo 30d, chuva fev 10mm/dia = 300mm > 200.
    Risco El Niño deve ser 0% (todos os anos acima do limiar)."""
    df, _ = nasa_power.para_dataframe(_payload_prec_fake(-5.0, -43.0,
                                                          chuva_fev=10.0))
    c = _cultura(ciclo_dias=30, agua_mm_ciclo=200.0)
    risco = grade_risco.risco_ponto(df, c, classes_enso_mock, "El Niño",
                                     mes_semeadura=2)
    assert risco == 0.0


def test_risco_ponto_chuva_insuficiente_risco_100(grade_tmp,
                                                    classes_enso_mock):
    """Cultura com água 200mm, ciclo 30d, chuva fev 1mm/dia = 30mm < 200.
    Risco El Niño deve ser 100% (todos os anos abaixo do limiar)."""
    df, _ = nasa_power.para_dataframe(_payload_prec_fake(-5.0, -43.0,
                                                          chuva_fev=1.0))
    c = _cultura(ciclo_dias=30, agua_mm_ciclo=200.0)
    risco = grade_risco.risco_ponto(df, c, classes_enso_mock, "El Niño",
                                     mes_semeadura=2)
    assert risco == 100.0


def test_risco_ponto_classe_sem_anos_retorna_none(grade_tmp,
                                                    classes_enso_mock):
    """La Niña não tem anos no mock (todos El Niño) -> risco None."""
    df, _ = nasa_power.para_dataframe(_payload_prec_fake(-5.0, -43.0))
    c = _cultura(ciclo_dias=30, agua_mm_ciclo=200.0)
    risco = grade_risco.risco_ponto(df, c, classes_enso_mock, "La Niña",
                                     mes_semeadura=2)
    assert risco is None


def test_risco_ponto_mes_none_usa_melhor_mes(grade_tmp, classes_enso_mock):
    """mes_semeadura=None -> usa melhor_mes_semeadura (não quebra)."""
    df, _ = nasa_power.para_dataframe(_payload_prec_fake(-5.0, -43.0,
                                                          chuva_fev=10.0))
    c = _cultura(ciclo_dias=30, agua_mm_ciclo=200.0)
    risco = grade_risco.risco_ponto(df, c, classes_enso_mock, "El Niño",
                                     mes_semeadura=None)
    # melhor mês será fevereiro (único com chuva); risco 0%.
    assert risco == 0.0


# ---------------------------------------------------------------------------
# 4. baixar_grade(parar_em_erro=True) — para na 1ª falha, não parcial
# ---------------------------------------------------------------------------

def test_baixar_grade_parar_em_erro_levanta_na_falha(grade_tmp,
                                                      monkeypatch):
    """Sem cache e sem rede, parar_em_erro=True levanta na 1ª chamada."""
    import requests

    def fake_get(url, **kwargs):
        raise requests.exceptions.RequestException("sem rede simulada")

    monkeypatch.setattr(nasa_power.requests, "get", fake_get)
    # Reduz o bbox para 1 ponto (teste rápido).
    monkeypatch.setattr(config, "PIAUI_BBOX",
                        {"lat_min": -5.5, "lat_max": -4.5,
                         "lon_min": -43.5, "lon_max": -42.5})

    with pytest.raises(nasa_power.NasaPowerRedeIndisponivel):
        grade_risco.baixar_grade(parar_em_erro=True)


def test_baixar_grade_sem_parar_pula_falhas(grade_tmp, monkeypatch):
    """Sem parar_em_erro, pontos que falham são pulados (estatística)."""
    import requests

    def fake_get(url, **kwargs):
        raise requests.exceptions.RequestException("sem rede")

    monkeypatch.setattr(nasa_power.requests, "get", fake_get)
    monkeypatch.setattr(config, "PIAUI_BBOX",
                        {"lat_min": -5.5, "lat_max": -4.5,
                         "lon_min": -43.5, "lon_max": -42.5})
    # Pula o sleep para acelerar.
    monkeypatch.setattr(grade_risco.time, "sleep", lambda *a, **k: None)

    pontos, stats = grade_risco.baixar_grade(parar_em_erro=False)
    assert pontos == []
    assert stats["ok"] == 0
    assert stats["falhas"] == stats["total"]
    assert stats["total"] >= 1


# ---------------------------------------------------------------------------
# 5. calcular_risco_grade — integração (sem rede)
# ---------------------------------------------------------------------------

def test_calcular_risco_grade_integracao(grade_tmp, classes_enso_mock,
                                           monkeypatch):
    """Baixa 1 ponto fake e calcula o risco da grade (sem rede real)."""
    lat, lon = -5.0, -43.0
    payload = _payload_prec_fake(lat, lon, chuva_fev=10.0)

    def fake_get(url, **kwargs):
        return FakeResponse(200, payload)

    monkeypatch.setattr(nasa_power.requests, "get", fake_get)
    monkeypatch.setattr(config, "PIAUI_BBOX",
                        {"lat_min": -5.5, "lat_max": -4.5,
                         "lon_min": -43.5, "lon_max": -42.5})
    monkeypatch.setattr(grade_risco.time, "sleep", lambda *a, **k: None)

    pontos_dfs, _ = grade_risco.baixar_grade(parar_em_erro=True)
    assert len(pontos_dfs) == 1

    c = _cultura(ciclo_dias=30, agua_mm_ciclo=200.0)
    out = grade_risco.calcular_risco_grade(
        pontos_dfs, c, classes_enso_mock, "El Niño", mes_semeadura=2)
    assert len(out) == 1
    assert out[0]["risco_pct"] == 0.0
    assert out[0]["n_anos"] > 0


# ---------------------------------------------------------------------------
# 6. Teste online (skip por padrão) — baixa a grade real do Piauí
# ---------------------------------------------------------------------------

@pytest.mark.online
def test_baixar_grade_online_real():
    """Baixa a grade real do Piauí e reporta tempo + nº de pontos.

    Skip por padrão (precisa de --run-online e internet). Reporta no
    output do pytest o tempo e o nº de pontos baixados.
    """
    pontos_dfs, stats = grade_risco.baixar_grade(parar_em_erro=True)
    print(f"\n[grade online] pontos={stats['ok']}/{stats['total']} "
          f"falhas={stats['falhas']} tempo={stats['tempo_s']}s")
    assert stats["total"] >= 100, "grade do Piauí deve ter ≥100 pontos"
    assert stats["ok"] > 0, "pelo menos 1 ponto deve baixar com rede"
